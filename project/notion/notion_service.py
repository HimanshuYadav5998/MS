"""
notion_service.py — Stub / interface contract for the Notion service.

Written by Team Member 2.  The backend imports and calls these functions.
This stub documents the expected signatures so the backend compiles and
tests pass without the real Notion implementation.

Replace this file with the real implementation before demo day.
"""
from __future__ import annotations

from typing import Any, Optional


def create_request_page(
    *,
    request_id: str,
    requester_name: str,
    requester_role: str,
    text: str,
    status: str,
) -> Optional[str]:
    """
    Create a Notion page for the incoming request.
    Returns the Notion page ID (str) or None on failure.
    """
    print(f"[notion_service STUB] create_request_page: {request_id}")
    return f"notion_page_{request_id}"


def update_request_page(
    *,
    page_id: Optional[str],
    request_id: str,
    category: str,
    recommended_action: str,
    summary: str,
    priority: str,
    confidence: float,
    requires_approval: bool,
    status: str,
) -> None:
    """Update the Notion request page with AI analysis output."""
    print(f"[notion_service STUB] update_request_page: {request_id}, page={page_id}")


def create_approval_page(
    *,
    request_id: str,
    requester_name: str,
    summary: Optional[str],
    recommended_action: Optional[str],
    category: Optional[str],
    priority: Optional[str],
) -> Optional[str]:
    """
    Create an approval page in Notion for human review.
    Returns the Notion page ID (str) or None on failure.
    """
    print(f"[notion_service STUB] create_approval_page: {request_id}")
    return f"notion_approval_{request_id}"


def get_human_decision(
    *,
    request_id: str,
    approval_page_id: Optional[str],
) -> Optional[str]:
    """
    Poll the Notion approval page for a human decision.
    Returns: "approved", "rejected", or None (still pending).
    """
    print(f"[notion_service STUB] get_human_decision: {request_id}")
    return None  # Stub always returns pending


def create_run_log(
    *,
    request_id: str,
    event: str,
    status: str,
    detail: str = "",
    timestamp: str = "",
) -> None:
    """Append a Run Log entry to the Notion Run Log database."""
    print(f"[notion_service STUB] create_run_log: {request_id} | {event} | {status}")
