"""
Notion Service Integration Module for AI College Request Automation.

This module provides the backend integration layer between the automation engine
(Python orchestrator) and Notion (Database, Approval Queue, and Audit Log).

Exact functions implemented:
1. create_request_page(...) -> str
2. update_request_page(...) -> None
3. create_approval_page(...) -> str
4. get_pending_approvals() -> list[dict]
5. get_human_decision(...) -> dict | None
6. create_run_log(...) -> str
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Set up logger
logger = logging.getLogger("notion_service")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [notion_service] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class NotionServiceError(Exception):
    """Custom exception raised for all Notion API and integration failures."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def _load_env_file(env_path: Optional[Union[str, Path]] = None) -> None:
    """Lightweight .env loader that searches current and parent directories."""
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    else:
        cwd = Path.cwd()
        candidates.extend([
            cwd / ".env",
            cwd / ".." / ".env",
            Path(__file__).resolve().parent / ".env",
            Path(__file__).resolve().parent.parent / ".env",
        ])

    for p in candidates:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k and k not in os.environ:
                                os.environ[k] = v
            except Exception as e:
                logger.warning("Could not read .env file at %s: %s", p, e)
            break


# Automatically load .env on module import
_load_env_file()

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


def _get_config() -> dict[str, str]:
    """Retrieve Notion configuration from environment variables."""
    api_key = os.environ.get("NOTION_API_KEY", "").strip()
    requests_db_id = os.environ.get("NOTION_REQUESTS_DB_ID", "").strip()
    runlog_db_id = os.environ.get("NOTION_RUNLOG_DB_ID", "").strip()
    approvals_db_id = os.environ.get("NOTION_APPROVALS_DB_ID", "").strip()

    return {
        "api_key": api_key,
        "requests_db_id": requests_db_id,
        "runlog_db_id": runlog_db_id,
        "approvals_db_id": approvals_db_id,
    }


def _clean_human_readable_text(text: str, max_length: int = 1500) -> str:
    """
    Ensure AI Summary and AI Recommendation are clean, short, human-readable sentences.
    Detects and unwraps raw JSON dumps if accidentally passed by caller.
    """
    if not text:
        return ""

    text = text.strip()

    # Guard: Check if string is raw JSON
    if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
        try:
            parsed = json.loads(text)
            logger.warning("Raw JSON detected in human-facing text field. Extracting readable message.")
            if isinstance(parsed, dict):
                # Try common keys
                for key in ["summary", "recommendation", "message", "text", "description", "reason", "content"]:
                    if key in parsed and isinstance(parsed[key], str):
                        text = parsed[key]
                        break
                else:
                    # Format key-values into a readable sentence
                    text = "; ".join(f"{k}: {v}" for k, v in parsed.items() if not isinstance(v, (dict, list)))
            elif isinstance(parsed, list):
                text = ", ".join(str(item) for item in parsed)
        except Exception:
            pass

    # Normalize excessive whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Truncate if overly long while keeping whole words
    if len(text) > max_length:
        text = text[:max_length - 3].rsplit(" ", 1)[0] + "..."

    return text


def _split_rich_text(content: str, max_chunk_size: int = 1900) -> list[dict[str, Any]]:
    """
    Notion enforces a 2000 character limit per rich_text block.
    Splits long strings into a list of Notion text objects.
    """
    if not content:
        return [{"type": "text", "text": {"content": ""}}]

    chunks = []
    for i in range(0, len(content), max_chunk_size):
        chunk = content[i : i + max_chunk_size]
        chunks.append({
            "type": "text",
            "text": {"content": chunk}
        })
    return chunks


def _extract_rich_text_value(prop: Optional[dict[str, Any]]) -> str:
    """Helper to extract plain text string from a Notion rich_text property."""
    if not prop or not isinstance(prop, dict):
        return ""
    rich_text_list = prop.get("rich_text", [])
    return "".join(item.get("plain_text", "") for item in rich_text_list)


def _extract_title_value(prop: Optional[dict[str, Any]]) -> str:
    """Helper to extract plain text string from a Notion title property."""
    if not prop or not isinstance(prop, dict):
        return ""
    title_list = prop.get("title", [])
    return "".join(item.get("plain_text", "") for item in title_list)


def _extract_select_value(prop: Optional[dict[str, Any]]) -> Optional[str]:
    """Helper to extract selected name from a Notion select property."""
    if not prop or not isinstance(prop, dict):
        return None
    select_obj = prop.get("select")
    if select_obj and isinstance(select_obj, dict):
        return select_obj.get("name")
    return None


def _notion_request(
    endpoint: str,
    method: str = "POST",
    data: Optional[dict[str, Any]] = None,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """
    Execute an HTTP request to the Notion API with automatic retry on 429 and 5xx errors.
    """
    config = _get_config()
    token = api_key or config["api_key"]
    if not token:
        raise NotionServiceError("NOTION_API_KEY is not set. Please provide a valid Notion integration token.")

    url = f"{NOTION_BASE_URL}/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }

    body_bytes = json.dumps(data).encode("utf-8") if data is not None else None

    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = resp.read().decode("utf-8")
                if resp_data:
                    return json.loads(resp_data)
                return {}
        except urllib.error.HTTPError as e:
            status_code = e.code
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                error_body = ""

            # Check for Rate Limit (429)
            if status_code == 429:
                retry_after_header = e.headers.get("Retry-After")
                if retry_after_header:
                    try:
                        sleep_time = float(retry_after_header)
                    except ValueError:
                        sleep_time = INITIAL_BACKOFF * (2 ** (attempt - 1))
                else:
                    sleep_time = INITIAL_BACKOFF * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)

                logger.warning(
                    "Notion API Rate Limited (429) on %s %s. Retrying in %.2fs (attempt %d/%d)...",
                    method, endpoint, sleep_time, attempt, MAX_RETRIES
                )
                time.sleep(sleep_time)
                continue

            # Check for transient server errors (500, 502, 503, 504)
            if status_code in (500, 502, 503, 504) and attempt < MAX_RETRIES:
                sleep_time = INITIAL_BACKOFF * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                logger.warning(
                    "Notion API Server Error (%d) on %s %s. Retrying in %.2fs (attempt %d/%d)...",
                    status_code, method, endpoint, sleep_time, attempt, MAX_RETRIES
                )
                time.sleep(sleep_time)
                continue

            # Non-retryable error or exhausted retries
            msg = f"Notion API error [{status_code}] on {method} {endpoint}: {error_body}"
            logger.error(msg)
            raise NotionServiceError(msg, status_code=status_code, response_body=error_body) from e

        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                sleep_time = INITIAL_BACKOFF * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                logger.warning(
                    "Network error connecting to Notion API on %s %s: %s. Retrying in %.2fs (attempt %d/%d)...",
                    method, endpoint, e, sleep_time, attempt, MAX_RETRIES
                )
                time.sleep(sleep_time)
                continue
            msg = f"Failed to connect to Notion API after {MAX_RETRIES} attempts: {e}"
            logger.error(msg)
            raise NotionServiceError(msg) from e

    raise NotionServiceError(f"Exceeded max retries ({MAX_RETRIES}) on Notion API call {method} {endpoint}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. CREATE REQUEST PAGE
# ─────────────────────────────────────────────────────────────────────────────
def create_request_page(
    request_id: str,
    title: str,
    category: str,
    requester: str,
    original_text: str,
    ai_summary: str,
    ai_recommendation: str,
    priority: str,
    confidence: float,
    status: str,
    requires_approval: bool,
) -> str:
    """
    Create a new row in the REQUESTS Notion database.

    Args:
        request_id: Unique string identifier for the request.
        title: Short title summarizing the student/faculty request.
        category: Category select value (e.g. "Course Registration", "Fee Waiver", etc.).
        requester: Name or email of requester.
        original_text: Original raw input submitted by requester.
        ai_summary: Clean, human-readable summary generated by AI.
        ai_recommendation: Proposed action recommended by AI.
        priority: Priority select value ("low", "medium", "high", "urgent").
        confidence: AI confidence score (float between 0.0 and 1.0).
        status: Initial status (e.g. "RECEIVED", "PROCESSING", "PENDING_APPROVAL").
        requires_approval: True if request requires human approval before execution.

    Returns:
        str: The created Notion Page ID.
    """
    config = _get_config()
    db_id = config["requests_db_id"]
    if not db_id:
        raise NotionServiceError("NOTION_REQUESTS_DB_ID is not configured in environment.")

    # Guard: Clean AI texts to prevent JSON dumps from showing in Notion
    cleaned_summary = _clean_human_readable_text(ai_summary)
    cleaned_rec = _clean_human_readable_text(ai_recommendation)

    now_iso = datetime.now(timezone.utc).isoformat()
    norm_priority = priority.strip().lower() if priority else "medium"
    norm_status = status.strip().upper() if status else "RECEIVED"

    payload: dict[str, Any] = {
        "parent": {"database_id": db_id},
        "properties": {
            "Title": {
                "title": [{"type": "text", "text": {"content": title or f"Request {request_id}"}}]
            },
            "Request ID": {
                "rich_text": _split_rich_text(request_id)
            },
            "Category": {
                "select": {"name": category or "General Query"}
            },
            "Requester": {
                "rich_text": _split_rich_text(requester)
            },
            "Original Request": {
                "rich_text": _split_rich_text(original_text)
            },
            "AI Summary": {
                "rich_text": _split_rich_text(cleaned_summary)
            },
            "AI Recommendation": {
                "rich_text": _split_rich_text(cleaned_rec)
            },
            "Priority": {
                "select": {"name": norm_priority}
            },
            "Confidence": {
                "number": max(0.0, min(1.0, float(confidence)))
            },
            "Status": {
                "select": {"name": norm_status}
            },
            "Requires Approval": {
                "checkbox": bool(requires_approval)
            },
            "Human Decision": {
                "select": {"name": "pending"}
            },
            "Created At": {
                "date": {"start": now_iso}
            },
            "Updated At": {
                "date": {"start": now_iso}
            },
            "Action Result": {
                "rich_text": [{"type": "text", "text": {"content": ""}}]
            },
        },
    }

    try:
        res = _notion_request("pages", method="POST", data=payload)
        page_id = res.get("id", "")
        logger.info("Created Notion Request page ID=%s for request_id=%s", page_id, request_id)
        return page_id
    except Exception as e:
        logger.error("Failed to create Notion request page for %s: %s", request_id, e)
        if isinstance(e, NotionServiceError):
            raise
        raise NotionServiceError(f"create_request_page failed for {request_id}: {e}") from e


# ─────────────────────────────────────────────────────────────────────────────
# 2. UPDATE REQUEST PAGE
# ─────────────────────────────────────────────────────────────────────────────
def update_request_page(
    notion_page_id: str,
    status: str,
    human_decision: str | None = None,
    action_result: str | None = None,
) -> None:
    """
    Update status, human decision, and action result for a Notion request page.

    Args:
        notion_page_id: Notion Page ID of the request to update.
        status: New status (e.g. "APPROVED", "EXECUTING", "COMPLETED", "FAILED", "ESCALATED").
        human_decision: Optional human decision ("approved", "rejected", "overridden", "pending").
        action_result: Optional result message or execution details.
    """
    if not notion_page_id:
        raise NotionServiceError("notion_page_id is required for update_request_page.")

    now_iso = datetime.now(timezone.utc).isoformat()
    norm_status = status.strip().upper() if status else "PROCESSING"

    properties: dict[str, Any] = {
        "Status": {"select": {"name": norm_status}},
        "Updated At": {"date": {"start": now_iso}},
    }

    if human_decision is not None:
        norm_decision = human_decision.strip().lower()
        properties["Human Decision"] = {"select": {"name": norm_decision}}

    if action_result is not None:
        cleaned_result = _clean_human_readable_text(action_result, max_length=1900)
        properties["Action Result"] = {"rich_text": _split_rich_text(cleaned_result)}

    payload = {"properties": properties}

    try:
        _notion_request(f"pages/{notion_page_id}", method="PATCH", data=payload)
        logger.info("Updated Notion Request page ID=%s with status=%s", notion_page_id, norm_status)
    except Exception as e:
        logger.error("Failed to update Notion request page ID=%s: %s", notion_page_id, e)
        if isinstance(e, NotionServiceError):
            raise
        raise NotionServiceError(f"update_request_page failed for {notion_page_id}: {e}") from e


# ─────────────────────────────────────────────────────────────────────────────
# 3. CREATE APPROVAL PAGE
# ─────────────────────────────────────────────────────────────────────────────
def create_approval_page(request_id: str, request_summary: str) -> str:
    """
    Create a new row in the APPROVALS Notion database for human review.

    Args:
        request_id: Unique string identifier for the request.
        request_summary: Short human-readable summary for quick skimming by reviewer.

    Returns:
        str: The created Notion Page ID.
    """
    config = _get_config()
    db_id = config["approvals_db_id"]
    if not db_id:
        raise NotionServiceError("NOTION_APPROVALS_DB_ID is not configured in environment.")

    cleaned_summary = _clean_human_readable_text(request_summary)

    payload: dict[str, Any] = {
        "parent": {"database_id": db_id},
        "properties": {
            "Request ID": {
                "title": [{"type": "text", "text": {"content": request_id}}]
            },
            "Request": {
                "rich_text": _split_rich_text(cleaned_summary)
            },
            "Decision": {
                "select": {"name": "pending"}
            },
            "Reviewer": {
                "rich_text": [{"type": "text", "text": {"content": ""}}]
            },
            "Decision Reason": {
                "rich_text": [{"type": "text", "text": {"content": ""}}]
            },
            "Override Instructions": {
                "rich_text": [{"type": "text", "text": {"content": ""}}]
            },
        },
    }

    try:
        res = _notion_request("pages", method="POST", data=payload)
        page_id = res.get("id", "")
        logger.info("Created Notion Approval page ID=%s for request_id=%s", page_id, request_id)
        return page_id
    except Exception as e:
        logger.error("Failed to create Notion approval page for %s: %s", request_id, e)
        if isinstance(e, NotionServiceError):
            raise
        raise NotionServiceError(f"create_approval_page failed for {request_id}: {e}") from e


# ─────────────────────────────────────────────────────────────────────────────
# 4. GET PENDING APPROVALS
# ─────────────────────────────────────────────────────────────────────────────
def get_pending_approvals() -> list[dict[str, Any]]:
    """
    Query the Approvals database for all items where Decision is 'pending'.

    Returns:
        list[dict]: List of pending approval records with keys:
                    [{"request_id": ..., "decision": ..., "reviewer": ...,
                      "reason": ..., "override_instructions": ...}, ...]
    """
    config = _get_config()
    db_id = config["approvals_db_id"]
    if not db_id:
        raise NotionServiceError("NOTION_APPROVALS_DB_ID is not configured in environment.")

    payload = {
        "filter": {
            "property": "Decision",
            "select": {"equals": "pending"}
        }
    }

    try:
        res = _notion_request(f"databases/{db_id}/query", method="POST", data=payload)
        results = res.get("results", [])

        pending_list: list[dict[str, Any]] = []
        for page in results:
            props = page.get("properties", {})
            req_id = _extract_title_value(props.get("Request ID")) or _extract_rich_text_value(props.get("Request ID"))
            decision = _extract_select_value(props.get("Decision")) or "pending"
            reviewer = _extract_rich_text_value(props.get("Reviewer"))
            reason = _extract_rich_text_value(props.get("Decision Reason"))
            override_instructions = _extract_rich_text_value(props.get("Override Instructions"))

            pending_list.append({
                "request_id": req_id,
                "decision": decision,
                "reviewer": reviewer,
                "reason": reason,
                "override_instructions": override_instructions,
                "notion_page_id": page.get("id", ""),
            })

        logger.info("Retrieved %d pending approvals from Notion", len(pending_list))
        return pending_list
    except Exception as e:
        logger.error("Failed to retrieve pending approvals: %s", e)
        if isinstance(e, NotionServiceError):
            raise
        raise NotionServiceError(f"get_pending_approvals failed: {e}") from e


# ─────────────────────────────────────────────────────────────────────────────
# 5. GET HUMAN DECISION
# ─────────────────────────────────────────────────────────────────────────────
def get_human_decision(request_id: str) -> dict[str, Any] | None:
    """
    Check if a human has made a decision on a specific request in the Approvals DB.

    Args:
        request_id: Unique string identifier for the request.

    Returns:
        dict | None:
            Returns None if decision is still 'pending' or not found.
            Returns {"decision": "approved"|"rejected"|"override_approved",
                     "reviewer": str, "reason": str} once decided.
    """
    config = _get_config()
    db_id = config["approvals_db_id"]
    if not db_id:
        raise NotionServiceError("NOTION_APPROVALS_DB_ID is not configured in environment.")

    # Filter query for specific request_id
    payload = {
        "filter": {
            "or": [
                {
                    "property": "Request ID",
                    "title": {"equals": request_id}
                },
                {
                    "property": "Request ID",
                    "rich_text": {"equals": request_id}
                }
            ]
        }
    }

    try:
        res = _notion_request(f"databases/{db_id}/query", method="POST", data=payload)
        results = res.get("results", [])
        if not results:
            logger.info("No approval record found for request_id=%s", request_id)
            return None

        page = results[0]
        props = page.get("properties", {})
        raw_decision = _extract_select_value(props.get("Decision"))

        if not raw_decision or raw_decision.strip().lower() == "pending":
            return None

        decision = raw_decision.strip().lower()
        reviewer = _extract_rich_text_value(props.get("Reviewer"))
        reason = _extract_rich_text_value(props.get("Decision Reason"))
        override_instructions = _extract_rich_text_value(props.get("Override Instructions"))

        # Map common variations to standard contract
        if "override" in decision:
            decision = "override_approved"
        elif "approve" in decision:
            decision = "approved"
        elif "reject" in decision:
            decision = "rejected"

        result = {
            "decision": decision,
            "reviewer": reviewer,
            "reason": reason,
        }
        if override_instructions:
            result["override_instructions"] = override_instructions

        logger.info("Human decision detected for request_id=%s: %s (by %s)", request_id, decision, reviewer)
        return result
    except Exception as e:
        logger.error("Failed to get human decision for %s: %s", request_id, e)
        if isinstance(e, NotionServiceError):
            raise
        raise NotionServiceError(f"get_human_decision failed for {request_id}: {e}") from e


# ─────────────────────────────────────────────────────────────────────────────
# 6. CREATE RUN LOG
# ─────────────────────────────────────────────────────────────────────────────
def create_run_log(
    request_id: str,
    event: str,
    actor: str,
    action: str,
    status: str,
    reason: str = "",
    error: str = "",
    external_action_id: str = "",
) -> str:
    """
    Append an audit log row to the RUN LOG Notion database.
    Every row is created programmatically by backend actions.

    Args:
        request_id: Associated request identifier.
        event: Short event name (e.g. "INTENT_CLASSIFIED", "APPROVAL_REQUESTED", "EXECUTION_COMPLETE").
        actor: Entity performing event ("system", "AI", "human").
        action: Concrete action taken.
        status: Status indicator ("SUCCESS", "INFO", "WARNING", "ERROR", "PENDING", "IN_PROGRESS").
        reason: Optional contextual rationale or explanation.
        error: Optional error trace or message.
        external_action_id: Optional external integration ID (e.g. email ID, LMS transaction ID).

    Returns:
        str: The created Notion Page ID.
    """
    config = _get_config()
    db_id = config["runlog_db_id"]
    if not db_id:
        raise NotionServiceError("NOTION_RUNLOG_DB_ID is not configured in environment.")

    now_iso = datetime.now(timezone.utc).isoformat()
    run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"
    norm_actor = actor.strip() if actor in ("system", "AI", "human") else "system"
    norm_status = status.strip().upper() if status else "INFO"

    payload: dict[str, Any] = {
        "parent": {"database_id": db_id},
        "properties": {
            "Run ID": {
                "title": [{"type": "text", "text": {"content": run_id}}]
            },
            "Request ID": {
                "rich_text": _split_rich_text(request_id)
            },
            "Timestamp": {
                "date": {"start": now_iso}
            },
            "Event": {
                "rich_text": _split_rich_text(event)
            },
            "Actor": {
                "select": {"name": norm_actor}
            },
            "Action": {
                "rich_text": _split_rich_text(action)
            },
            "Status": {
                "select": {"name": norm_status}
            },
            "Reason": {
                "rich_text": _split_rich_text(reason)
            },
            "Error": {
                "rich_text": _split_rich_text(error)
            },
            "External Action ID": {
                "rich_text": _split_rich_text(external_action_id)
            },
        },
    }

    try:
        res = _notion_request("pages", method="POST", data=payload)
        page_id = res.get("id", "")
        logger.info("Created Run Log entry ID=%s for request_id=%s event=%s", page_id, request_id, event)
        return page_id
    except Exception as e:
        logger.error("Failed to create run log entry for %s: %s", request_id, e)
        if isinstance(e, NotionServiceError):
            raise
        raise NotionServiceError(f"create_run_log failed for {request_id}: {e}") from e
