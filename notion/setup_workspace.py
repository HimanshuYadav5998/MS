"""
Notion Workspace Setup Script for AI College Request Automation.

This script programmatically initializes the complete Notion workspace:
1. Creates the Workspace Home Page: "AI College Operations Hub"
2. Creates the 3 core databases:
   - REQUESTS database (14 properties, 10 status options)
   - RUN LOG database (10 properties, audit trail)
   - APPROVALS database (7 properties, human review queue)
3. Populates the Home Page with structured sections, linked view descriptions,
   KPI status callouts, and direct database links.
4. Updates or generates the `.env` file with the newly created Database IDs.

Usage:
    python notion/setup_workspace.py [--parent-page-id <PAGE_ID>] [--token <NOTION_TOKEN>]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [setup_workspace] %(message)s",
)
logger = logging.getLogger("setup_workspace")

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"


def notion_api_call(
    endpoint: str,
    method: str = "POST",
    data: Optional[dict[str, Any]] = None,
    token: str = "",
) -> dict[str, Any]:
    """Execute raw HTTP request to Notion API."""
    if not token:
        raise ValueError("Notion API Token is required.")

    url = f"{NOTION_BASE_URL}/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }
    body_bytes = json.dumps(data).encode("utf-8") if data is not None else None

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_data = resp.read().decode("utf-8")
            return json.loads(resp_data) if resp_data else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        logger.error("Notion API error (%d) on %s %s: %s", e.code, method, endpoint, error_body)
        raise RuntimeError(f"Notion API error [{e.code}]: {error_body}") from e
    except Exception as e:
        logger.error("Network error on %s %s: %s", method, endpoint, e)
        raise


def create_requests_database(parent_page_id: str, token: str) -> dict[str, Any]:
    """Create the REQUESTS database."""
    logger.info("Creating REQUESTS database under parent page %s...", parent_page_id)
    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "icon": {"type": "emoji", "emoji": "📋"},
        "title": [{"type": "text", "text": {"content": "Requests - AI College Operations"}}],
        "properties": {
            "Title": {"title": {}},
            "Request ID": {"rich_text": {}},
            "Category": {
                "select": {
                    "options": [
                        {"name": "Course Registration", "color": "blue"},
                        {"name": "Leave Application", "color": "purple"},
                        {"name": "Fee Waiver", "color": "green"},
                        {"name": "Hostel Request", "color": "orange"},
                        {"name": "Scholarship", "color": "yellow"},
                        {"name": "Grade Appeal", "color": "pink"},
                        {"name": "General Query", "color": "gray"},
                        {"name": "IT Support", "color": "brown"},
                        {"name": "Transcript Request", "color": "default"},
                    ]
                }
            },
            "Requester": {"rich_text": {}},
            "Original Request": {"rich_text": {}},
            "AI Summary": {"rich_text": {}},
            "AI Recommendation": {"rich_text": {}},
            "Priority": {
                "select": {
                    "options": [
                        {"name": "low", "color": "gray"},
                        {"name": "medium", "color": "blue"},
                        {"name": "high", "color": "orange"},
                        {"name": "urgent", "color": "red"},
                    ]
                }
            },
            "Confidence": {"number": {"format": "number"}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "RECEIVED", "color": "gray"},
                        {"name": "PROCESSING", "color": "yellow"},
                        {"name": "PENDING_APPROVAL", "color": "red"},
                        {"name": "APPROVED", "color": "blue"},
                        {"name": "REJECTED", "color": "pink"},
                        {"name": "OVERRIDDEN", "color": "purple"},
                        {"name": "EXECUTING", "color": "orange"},
                        {"name": "COMPLETED", "color": "green"},
                        {"name": "FAILED", "color": "red"},
                        {"name": "ESCALATED", "color": "brown"},
                    ]
                }
            },
            "Requires Approval": {"checkbox": {}},
            "Human Decision": {
                "select": {
                    "options": [
                        {"name": "approved", "color": "green"},
                        {"name": "rejected", "color": "red"},
                        {"name": "overridden", "color": "purple"},
                        {"name": "pending", "color": "yellow"},
                    ]
                }
            },
            "Created At": {"date": {}},
            "Updated At": {"date": {}},
            "Action Result": {"rich_text": {}},
        },
    }
    return notion_api_call("databases", method="POST", data=payload, token=token)


def create_runlog_database(parent_page_id: str, token: str) -> dict[str, Any]:
    """Create the RUN LOG database."""
    logger.info("Creating RUN LOG database under parent page %s...", parent_page_id)
    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "icon": {"type": "emoji", "emoji": "📜"},
        "title": [{"type": "text", "text": {"content": "Run Log - Audit Trail"}}],
        "properties": {
            "Run ID": {"title": {}},
            "Request ID": {"rich_text": {}},
            "Timestamp": {"date": {}},
            "Event": {"rich_text": {}},
            "Actor": {
                "select": {
                    "options": [
                        {"name": "system", "color": "gray"},
                        {"name": "AI", "color": "purple"},
                        {"name": "human", "color": "blue"},
                    ]
                }
            },
            "Action": {"rich_text": {}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "SUCCESS", "color": "green"},
                        {"name": "INFO", "color": "blue"},
                        {"name": "WARNING", "color": "yellow"},
                        {"name": "ERROR", "color": "red"},
                        {"name": "PENDING", "color": "gray"},
                        {"name": "IN_PROGRESS", "color": "orange"},
                    ]
                }
            },
            "Reason": {"rich_text": {}},
            "Error": {"rich_text": {}},
            "External Action ID": {"rich_text": {}},
        },
    }
    return notion_api_call("databases", method="POST", data=payload, token=token)


def create_approvals_database(parent_page_id: str, token: str) -> dict[str, Any]:
    """Create the APPROVALS database."""
    logger.info("Creating APPROVALS database under parent page %s...", parent_page_id)
    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "icon": {"type": "emoji", "emoji": "⚖️"},
        "title": [{"type": "text", "text": {"content": "Approvals - Human Review Queue"}}],
        "properties": {
            "Request ID": {"title": {}},
            "Request": {"rich_text": {}},
            "Decision": {
                "select": {
                    "options": [
                        {"name": "pending", "color": "yellow"},
                        {"name": "approved", "color": "green"},
                        {"name": "rejected", "color": "red"},
                        {"name": "override_approved", "color": "purple"},
                    ]
                }
            },
            "Reviewer": {"rich_text": {}},
            "Decision Reason": {"rich_text": {}},
            "Decision Time": {"date": {}},
            "Override Instructions": {"rich_text": {}},
        },
    }
    return notion_api_call("databases", method="POST", data=payload, token=token)


def create_operations_hub_page(parent_page_id: str, token: str) -> dict[str, Any]:
    """Create the AI College Operations Hub home page."""
    logger.info("Creating AI College Operations Hub page under parent %s...", parent_page_id)
    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "icon": {"type": "emoji", "emoji": "🎓"},
        "cover": {
            "type": "external",
            "external": {
                "url": "https://images.unsplash.com/photo-1541339907198-e08756dedf3f?auto=format&fit=crop&w=1600&q=80"
            },
        },
        "properties": {
            "title": [
                {
                    "type": "text",
                    "text": {"content": "AI College Operations Hub"},
                }
            ]
        },
        "children": [
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Welcome to the AI College Operations Hub. This Notion workspace serves as the live human control panel, database, approval queue, and immutable audit trail. All operations are driven 100% programmatically by backend AI workflows."
                            },
                        }
                    ],
                    "icon": {"type": "emoji", "emoji": "🏛️"},
                    "color": "blue_background",
                },
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "📊 System Status & Live Metrics"}}]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Real-time summary of student requests and operations:"
                            },
                        }
                    ]
                },
            },
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "🟢 System Operational | Backend Polling: Active (10s interval) | Auto-Approval Policy: Active | Audit Trail: Enabled"
                            },
                            "annotations": {"bold": True},
                        }
                    ],
                    "icon": {"type": "emoji", "emoji": "⚡"},
                    "color": "gray_background",
                },
            },
            {"object": "block", "type": "divider", "divider": {}},
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "🔴 Needs Attention (Faculty & Admin Approvals)"}}]
                },
            },
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Teacher / Admin Instructions: Requests below require human discretion. Review the AI Summary & Recommendation in the Approvals database, then change the Decision column to "
                            },
                        },
                        {
                            "type": "text",
                            "text": {"content": "approved"},
                            "annotations": {"bold": True, "code": True},
                        },
                        {"type": "text", "text": {", "}},
                        {
                            "type": "text",
                            "text": {"content": "rejected"},
                            "annotations": {"bold": True, "code": True},
                        },
                        {"type": "text", "text": {", or "}},
                        {
                            "type": "text",
                            "text": {"content": "override_approved"},
                            "annotations": {"bold": True, "code": True},
                        },
                        {"type": "text", "text": {". The backend will automatically detect your decision and resume execution."}},
                    ],
                    "icon": {"type": "emoji", "emoji": "⚠️"},
                    "color": "red_background",
                },
            },
            {"object": "block", "type": "divider", "divider": {}},
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "🟡 Processing & Execution"}}]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Requests currently being analyzed by AI, validated against college policies, or executing downstream actions."
                            },
                        }
                    ]
                },
            },
            {"object": "block", "type": "divider", "divider": {}},
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "🟢 Completed Today"}}]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Successfully fulfilled requests with recorded action results and student notifications sent."
                            },
                        }
                    ]
                },
            },
            {"object": "block", "type": "divider", "divider": {}},
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "⚠️ Failed / Escalated"}}]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Requests flagged for technical failure, security policy violation, or complex edge cases requiring human escalation."
                            },
                        }
                    ]
                },
            },
            {"object": "block", "type": "divider", "divider": {}},
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "📜 Real-Time Run Log & Forensic Audit Trail"}}]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Immutable event stream recording all AI decisions, rule checks, human approvals, and system state transitions."
                            },
                        }
                    ]
                },
            },
        ],
    }
    return notion_api_call("pages", method="POST", data=payload, token=token)


def update_env_file(
    token: str,
    requests_db_id: str,
    runlog_db_id: str,
    approvals_db_id: str,
    hub_page_id: str = "",
    target_dir: Optional[Path] = None,
) -> None:
    """Save or update the .env file with created database IDs."""
    target_dir = target_dir or Path.cwd()
    env_file = target_dir / ".env"

    env_lines = [
        "# Notion API Configuration for AI College Request Automation",
        f"NOTION_API_KEY={token}",
        f"NOTION_REQUESTS_DB_ID={requests_db_id}",
        f"NOTION_RUNLOG_DB_ID={runlog_db_id}",
        f"NOTION_APPROVALS_DB_ID={approvals_db_id}",
    ]
    if hub_page_id:
        env_lines.append(f"NOTION_HUB_PAGE_ID={hub_page_id}")

    content = "\n".join(env_lines) + "\n"
    with open(env_file, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("Successfully updated %s with Notion Database IDs.", env_file)


def run_setup(parent_page_id: str, token: str) -> dict[str, str]:
    """Execute complete workspace setup programmatically."""
    logger.info("Starting AI College Request Automation Notion Setup...")

    # Step 1: Create Hub Home Page
    hub_page = create_operations_hub_page(parent_page_id, token)
    hub_page_id = hub_page["id"]
    logger.info("Created Hub Home Page: %s", hub_page.get("url", hub_page_id))

    # Step 2: Create Databases under the Hub Page
    requests_db = create_requests_database(hub_page_id, token)
    requests_db_id = requests_db["id"]
    logger.info("Created Requests DB ID: %s", requests_db_id)

    runlog_db = create_runlog_database(hub_page_id, token)
    runlog_db_id = runlog_db["id"]
    logger.info("Created Run Log DB ID: %s", runlog_db_id)

    approvals_db = create_approvals_database(hub_page_id, token)
    approvals_db_id = approvals_db["id"]
    logger.info("Created Approvals DB ID: %s", approvals_db_id)

    # Step 3: Write .env file
    update_env_file(
        token=token,
        requests_db_id=requests_db_id,
        runlog_db_id=runlog_db_id,
        approvals_db_id=approvals_db_id,
        hub_page_id=hub_page_id,
    )

    print("\n" + "=" * 60)
    print("🎓 NOTION WORKSPACE SETUP COMPLETE!")
    print("=" * 60)
    print(f"Hub Page URL:      {hub_page.get('url', 'https://notion.so/' + hub_page_id.replace('-', ''))}")
    print(f"Requests DB ID:    {requests_db_id}")
    print(f"Run Log DB ID:     {runlog_db_id}")
    print(f"Approvals DB ID:   {approvals_db_id}")
    print("=" * 60 + "\n")

    return {
        "hub_page_id": hub_page_id,
        "requests_db_id": requests_db_id,
        "runlog_db_id": runlog_db_id,
        "approvals_db_id": approvals_db_id,
    }


def main():
    parser = argparse.ArgumentParser(description="Setup AI College Request Automation Notion Workspace")
    parser.add_argument("--parent-page-id", type=str, default=os.environ.get("NOTION_PARENT_PAGE_ID", ""),
                        help="Notion Parent Page ID where the workspace will be created")
    parser.add_argument("--token", type=str, default=os.environ.get("NOTION_API_KEY", ""),
                        help="Notion Internal Integration Token")
    args = parser.parse_args()

    token = args.token.strip()
    parent_page_id = args.parent_page_id.strip()

    if not token:
        token = input("Enter your NOTION_API_KEY (secret_...): ").strip()
    if not parent_page_id:
        parent_page_id = input("Enter your NOTION_PARENT_PAGE_ID: ").strip()

    if not token or not parent_page_id:
        print("Error: Both NOTION_API_KEY and NOTION_PARENT_PAGE_ID are required.")
        sys.exit(1)

    try:
        run_setup(parent_page_id=parent_page_id, token=token)
    except Exception as e:
        logger.error("Workspace setup failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
