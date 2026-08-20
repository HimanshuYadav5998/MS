"""
action_service.py — Stub / interface contract for the action service.

Written by Team Member 4.  The backend (orchestrator.py) is the ONLY component
allowed to call execute_action().

This stub documents the expected interface so the backend compiles and
tests pass without the real implementation.

Replace this file with the real implementation before demo day.
"""
from __future__ import annotations

from typing import Any


def execute_action(action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a real external action (send_email, create_calendar_event, etc.).

    Args:
        action_type: One of "send_email", "create_calendar_event", etc.
        payload: Dict built from extracted_fields + request metadata.

    Returns:
        {
            "success": bool,
            "action_id": str,          # external identifier (e.g. email message ID)
            "error": str | None,       # present only when success=False
        }
    """
    print(f"[action_service STUB] execute_action: type={action_type}, payload={payload}")
    return {
        "success": True,
        "action_id": f"stub_action_{payload.get('request_id', 'unknown')}",
        "error": None,
    }
