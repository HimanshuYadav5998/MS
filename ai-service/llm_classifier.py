"""
llm_classifier.py — LLM-backed classifier (OpenAI-compatible API).

Layers on top of the rule-based fallback:
  1. Load system prompt from prompts/classify_prompt.txt
  2. Call LLM with user request
  3. Parse + validate JSON response via Pydantic
  4. Apply hard safety overrides in Python (not trusting LLM alone)
  5. On any failure → return fallback response

Safety overrides are enforced HERE regardless of what the LLM returned.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from fallback_classifier import (
    has_conflicting_dates,
    is_prompt_injection,
    _missing_required,
    rule_based_classify,
)
from schemas import (
    AnalyzeResponse,
    Category,
    FALLBACK_RESPONSE,
    Priority,
    RecommendedAction,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

_PROMPT_PATH = Path(__file__).parent / "prompts" / "classify_prompt.txt"
_SYSTEM_PROMPT: Optional[str] = None  # lazy-loaded once

LLM_API_KEY     = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL    = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL       = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT_SEC = float(os.getenv("LLM_TIMEOUT_SEC", "15"))
LLM_MAX_TOKENS  = int(os.getenv("LLM_MAX_TOKENS", "512"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))  # low = deterministic


def _load_system_prompt() -> str:
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        _SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")
    return _SYSTEM_PROMPT


# ──────────────────────────────────────────────────────────────────────────────
# Hard safety overrides  (Python-enforced, not LLM-enforced)
# ──────────────────────────────────────────────────────────────────────────────

def _apply_safety_overrides(
    response: AnalyzeResponse,
    original_text: str,
) -> AnalyzeResponse:
    """
    Mutate the response in-place (return new object) to enforce hard rules.
    The LLM may be wrong; these rules are authoritative.
    """
    force_human = False
    risk_reason = response.risk_reason

    # Rule 1: prompt injection
    if is_prompt_injection(original_text):
        return AnalyzeResponse(
            category           = Category.UNKNOWN,
            priority           = Priority.HIGH,
            confidence         = 0.0,
            extracted_fields   = {},
            summary            = "Request flagged as possible prompt injection attempt.",
            recommended_action = RecommendedAction.HUMAN_REVIEW,
            requires_approval  = True,
            risk_reason        = "Possible prompt injection attempt detected; request quarantined.",
        )

    # Rule 2: low confidence
    if response.confidence < 0.70:
        force_human = True

    # Rule 3: unknown category
    if response.category == Category.UNKNOWN:
        force_human = True

    # Rule 4: conflicting dates
    if has_conflicting_dates(original_text):
        force_human = True
        risk_reason = risk_reason or "Conflicting dates detected in request text."

    # Rule 5: missing required fields
    if _missing_required(response.category, response.extracted_fields):
        force_human = True

    if force_human:
        return AnalyzeResponse(
            category           = response.category,
            priority           = response.priority,
            confidence         = response.confidence,
            extracted_fields   = response.extracted_fields,
            summary            = response.summary,
            recommended_action = RecommendedAction.HUMAN_REVIEW,
            requires_approval  = True,
            risk_reason        = risk_reason,
        )

    return response


# ──────────────────────────────────────────────────────────────────────────────
# JSON extraction  (handles LLM that wraps output in markdown fences)
# ──────────────────────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> str:
    """Strip markdown fences if present, return the raw JSON string."""
    # Try to find JSON object directly
    raw = raw.strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return match.group(0)
    return raw


# ──────────────────────────────────────────────────────────────────────────────
# LLM call
# ──────────────────────────────────────────────────────────────────────────────

async def llm_classify(
    text: str,
    requester_name: str,
    requester_role: str,
    request_id: str,
) -> AnalyzeResponse:
    """
    Main classifier.  Falls back to rule_based_classify on any error.
    """
    # ── Early guard: prompt injection (before touching the LLM at all) ──────
    if is_prompt_injection(text):
        return AnalyzeResponse(
            category           = Category.UNKNOWN,
            priority           = Priority.HIGH,
            confidence         = 0.0,
            extracted_fields   = {},
            summary            = "Request flagged as possible prompt injection attempt.",
            recommended_action = RecommendedAction.HUMAN_REVIEW,
            requires_approval  = True,
            risk_reason        = "Possible prompt injection attempt detected; request quarantined.",
        )

    # ── No API key → offline fallback immediately ────────────────────────────
    if not LLM_API_KEY:
        logger.warning("LLM_API_KEY not configured — using rule-based classifier.")
        result = rule_based_classify(text, requester_role)
        return _apply_safety_overrides(result, text)

    system_prompt = _load_system_prompt()

    user_message = (
        f"request_id: {request_id}\n"
        f"requester_name: {requester_name}\n"
        f"requester_role: {requester_role}\n\n"
        f"REQUEST TEXT:\n{text}"
    )

    payload: Dict[str, Any] = {
        "model":       LLM_MODEL,
        "temperature": LLM_TEMPERATURE,
        "max_tokens":  LLM_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SEC) as client:
            resp = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type":  "application/json",
                },
            )
            resp.raise_for_status()

        data        = resp.json()
        raw_content = data["choices"][0]["message"]["content"]
        json_str    = _extract_json(raw_content)
        parsed_dict = json.loads(json_str)

        # Validate with Pydantic (strict — raises on bad data)
        validated = AnalyzeResponse(**parsed_dict)

    except httpx.TimeoutException:
        logger.error("LLM request timed out for request_id=%s; using fallback.", request_id)
        validated = rule_based_classify(text, requester_role)

    except httpx.HTTPStatusError as exc:
        logger.error(
            "LLM HTTP error %s for request_id=%s; using fallback.",
            exc.response.status_code, request_id
        )
        validated = rule_based_classify(text, requester_role)

    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.error(
            "LLM output validation failed for request_id=%s (%s); using fallback response.",
            request_id, exc
        )
        # Return the safe fallback — backend must never get malformed data
        fallback = FALLBACK_RESPONSE.model_copy()
        return fallback

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error classifying request_id=%s: %s", request_id, exc)
        return FALLBACK_RESPONSE.model_copy()

    # ── Apply hard safety overrides regardless of LLM output ─────────────────
    return _apply_safety_overrides(validated, text)
