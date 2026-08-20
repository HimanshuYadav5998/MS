"""
integrations/action_service.py
================================
The ONLY module in the system allowed to perform real external actions
(email, calendar). Called exclusively by the backend orchestrator.

Adapter pattern: swapping mock → real is a one-line env change.
    EMAIL_PROVIDER=mock      → MockEmailAdapter (default, zero network deps)
    EMAIL_PROVIDER=mailtrap  → MailtrapEmailAdapter (sandbox SMTP)

CALENDAR_PROVIDER=mock       → MockCalendarAdapter (default)

Public API (matches the team contract exactly):
    send_email(to, subject, body) -> dict
    create_calendar_event(title, date, description) -> dict
    execute_action(action_type, payload) -> dict
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# ── Environment ───────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=False)

# ── Logging ───────────────────────────────────────────────────────────────────
_LOG_DIR = Path(__file__).parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  [action_service]  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_LOG_DIR / "action_service.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("action_service")

# ── Action log (human-readable JSONL, shown in demo terminal) ─────────────────
_ACTION_LOG = _LOG_DIR / "actions.jsonl"


def _record_action(adapter: str, action: str, payload: dict, result: dict) -> None:
    """Append one line to the action log for demo visibility."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "adapter": adapter,
        "action": action,
        "payload": payload,
        "result": result,
    }
    with _ACTION_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ═══════════════════════════════════════════════════════════════════════════════
# EMAIL ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

class BaseEmailAdapter(ABC):
    """Interface every email adapter must satisfy."""

    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> dict:
        """
        Send an email.
        Returns: {"success": bool, "external_action_id": str, "error": str|None}
        MUST NOT raise — handle exceptions internally.
        """


class MockEmailAdapter(BaseEmailAdapter):
    """
    Safe fallback — zero network dependency.
    Logs the email to console + actions.jsonl and returns success=True.
    Perfect for on-stage demos where WiFi cannot be trusted.
    """

    def send(self, to: str, subject: str, body: str) -> dict:
        action_id = f"mock_email_{uuid.uuid4().hex[:8]}"
        logger.info(
            "📧 [MOCK EMAIL] to=%s | subject=%s | action_id=%s",
            to, subject, action_id,
        )
        logger.info("--- email body ---\n%s\n--- end body ---", body)
        return {"success": True, "external_action_id": action_id, "error": None}


class MailtrapEmailAdapter(BaseEmailAdapter):
    """
    Mailtrap sandbox SMTP adapter.
    Sign up at https://mailtrap.io — free tier is enough for a demo.
    Emails land in your Mailtrap inbox, never reach real recipients.
    """

    def __init__(self) -> None:
        self.host = os.getenv("MAILTRAP_HOST", "sandbox.smtp.mailtrap.io")
        self.port = int(os.getenv("MAILTRAP_PORT", "2525"))
        self.username = os.getenv("MAILTRAP_USERNAME", "")
        self.password = os.getenv("MAILTRAP_PASSWORD", "")
        self.from_addr = os.getenv("MAILTRAP_FROM", "noreply@college-automation.local")

        if not self.username or not self.password:
            logger.warning(
                "Mailtrap credentials not set — MAILTRAP_USERNAME / MAILTRAP_PASSWORD "
                "are empty. Email sends will fail."
            )

    def send(self, to: str, subject: str, body: str) -> dict:
        action_id = f"mailtrap_{uuid.uuid4().hex[:8]}"
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = self.from_addr
            msg["To"] = to
            msg["X-Action-ID"] = action_id

            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.from_addr, [to], msg.as_string())

            logger.info(
                "📧 [MAILTRAP] Sent email to=%s | subject=%s | action_id=%s",
                to, subject, action_id,
            )
            return {"success": True, "external_action_id": action_id, "error": None}

        except smtplib.SMTPAuthenticationError as exc:
            err = f"Mailtrap SMTP auth failed: {exc}"
            logger.error(err)
            return {"success": False, "external_action_id": action_id, "error": err}

        except smtplib.SMTPException as exc:
            err = f"Mailtrap SMTP error: {exc}"
            logger.error(err)
            return {"success": False, "external_action_id": action_id, "error": err}

        except OSError as exc:
            err = f"Network error reaching Mailtrap: {exc}"
            logger.error(err)
            return {"success": False, "external_action_id": action_id, "error": err}

        except Exception as exc:  # noqa: BLE001 — intentional catch-all at boundary
            err = f"Unexpected email error: {exc}"
            logger.error(err, exc_info=True)
            return {"success": False, "external_action_id": action_id, "error": err}


class BrokenEmailAdapter(BaseEmailAdapter):
    """
    Intentionally always fails — used ONLY in Test 6 to verify error handling.
    Activate with EMAIL_PROVIDER=broken.
    """

    def send(self, to: str, subject: str, body: str) -> dict:
        action_id = f"broken_{uuid.uuid4().hex[:8]}"
        err = "BrokenEmailAdapter: intentional failure for Test 6"
        logger.warning("🔴 [BROKEN ADAPTER] %s", err)
        return {"success": False, "external_action_id": action_id, "error": err}


# ═══════════════════════════════════════════════════════════════════════════════
# CALENDAR ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

class BaseCalendarAdapter(ABC):
    """Interface every calendar adapter must satisfy."""

    @abstractmethod
    def create_event(self, title: str, date: str, description: str) -> dict:
        """
        Create a calendar event.
        Returns: {"success": bool, "external_action_id": str, "error": str|None}
        MUST NOT raise.
        """


class MockCalendarAdapter(BaseCalendarAdapter):
    """Logs the event, returns success — zero external dependency."""

    def create_event(self, title: str, date: str, description: str) -> dict:
        action_id = f"mock_cal_{uuid.uuid4().hex[:8]}"
        logger.info(
            "📅 [MOCK CALENDAR] title=%s | date=%s | action_id=%s",
            title, date, action_id,
        )
        logger.info("--- event description ---\n%s\n--- end description ---", description)
        return {"success": True, "external_action_id": action_id, "error": None}


class BrokenCalendarAdapter(BaseCalendarAdapter):
    """Intentionally fails — for Test 6 calendar variant."""

    def create_event(self, title: str, date: str, description: str) -> dict:
        action_id = f"broken_cal_{uuid.uuid4().hex[:8]}"
        err = "BrokenCalendarAdapter: intentional failure for Test 6"
        logger.warning("🔴 [BROKEN CALENDAR ADAPTER] %s", err)
        return {"success": False, "external_action_id": action_id, "error": err}


# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTER FACTORY
# ═══════════════════════════════════════════════════════════════════════════════

def _get_email_adapter() -> BaseEmailAdapter:
    """Return the correct email adapter based on EMAIL_PROVIDER env var."""
    provider = os.getenv("EMAIL_PROVIDER", "mock").lower().strip()
    adapters: dict[str, type[BaseEmailAdapter]] = {
        "mock": MockEmailAdapter,
        "mailtrap": MailtrapEmailAdapter,
        "broken": BrokenEmailAdapter,
    }
    if provider not in adapters:
        logger.warning(
            "Unknown EMAIL_PROVIDER=%r — falling back to mock. "
            "Valid options: %s",
            provider, list(adapters.keys()),
        )
        provider = "mock"
    logger.debug("Email adapter selected: %s", provider)
    return adapters[provider]()


def _get_calendar_adapter() -> BaseCalendarAdapter:
    """Return the correct calendar adapter based on CALENDAR_PROVIDER env var."""
    provider = os.getenv("CALENDAR_PROVIDER", "mock").lower().strip()
    adapters: dict[str, type[BaseCalendarAdapter]] = {
        "mock": MockCalendarAdapter,
        "broken": BrokenCalendarAdapter,
    }
    if provider not in adapters:
        logger.warning(
            "Unknown CALENDAR_PROVIDER=%r — falling back to mock.", provider
        )
        provider = "mock"
    logger.debug("Calendar adapter selected: %s", provider)
    return adapters[provider]()


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API — these are the functions Member 1 calls
# ═══════════════════════════════════════════════════════════════════════════════

def send_email(to: str, subject: str, body: str) -> dict:
    """
    Send an email using the configured provider.

    Args:
        to:      Recipient email address.
        subject: Email subject line.
        body:    Plain-text email body.

    Returns:
        {"success": bool, "external_action_id": str, "error": str|None}
    """
    adapter = _get_email_adapter()
    try:
        result = adapter.send(to=to, subject=subject, body=body)
    except Exception as exc:  # noqa: BLE001 — safety net, adapter should not raise
        action_id = f"err_{uuid.uuid4().hex[:8]}"
        result = {
            "success": False,
            "external_action_id": action_id,
            "error": f"Adapter raised unexpectedly: {exc}",
        }
        logger.error("Adapter raised outside its boundary: %s", exc, exc_info=True)

    _record_action(
        adapter=type(adapter).__name__,
        action="send_email",
        payload={"to": to, "subject": subject},
        result=result,
    )
    return result


def create_calendar_event(title: str, date: str, description: str) -> dict:
    """
    Create a calendar event using the configured provider.

    Args:
        title:       Event title.
        date:        ISO-8601 date string or human-readable date.
        description: Event details / notes.

    Returns:
        {"success": bool, "external_action_id": str, "error": str|None}
    """
    adapter = _get_calendar_adapter()
    try:
        result = adapter.create_event(title=title, date=date, description=description)
    except Exception as exc:  # noqa: BLE001 — safety net
        action_id = f"err_{uuid.uuid4().hex[:8]}"
        result = {
            "success": False,
            "external_action_id": action_id,
            "error": f"Calendar adapter raised unexpectedly: {exc}",
        }
        logger.error(
            "Calendar adapter raised outside its boundary: %s", exc, exc_info=True
        )

    _record_action(
        adapter=type(adapter).__name__,
        action="create_calendar_event",
        payload={"title": title, "date": date},
        result=result,
    )
    return result


# Action type → handler mapping — add new action types here, nowhere else
_ACTION_HANDLERS: dict[str, callable] = {
    "send_email": lambda payload: send_email(
        to=payload.get("to", ""),
        subject=payload.get("subject", "(no subject)"),
        body=payload.get("body", ""),
    ),
    "create_calendar_event": lambda payload: create_calendar_event(
        title=payload.get("title", ""),
        date=payload.get("date", ""),
        description=payload.get("description", ""),
    ),
}


def execute_action(action_type: str, payload: dict) -> dict:
    """
    Dispatcher: routes action_type to the correct handler.

    This function MUST NEVER raise. Even on catastrophic failure it returns
    the standard dict with success=False and a readable error message.

    Args:
        action_type: One of "send_email" | "create_calendar_event".
        payload:     Dict of keyword args for the chosen action.

    Returns:
        {"success": bool, "external_action_id": str, "error": str|None}
    """
    _FALLBACK_ID = ""

    try:
        if not isinstance(action_type, str) or not action_type.strip():
            return {
                "success": False,
                "external_action_id": _FALLBACK_ID,
                "error": "action_type must be a non-empty string.",
            }

        if not isinstance(payload, dict):
            return {
                "success": False,
                "external_action_id": _FALLBACK_ID,
                "error": f"payload must be a dict, got {type(payload).__name__}.",
            }

        handler = _ACTION_HANDLERS.get(action_type.strip().lower())
        if handler is None:
            supported = list(_ACTION_HANDLERS.keys())
            err = (
                f"Unknown action_type={action_type!r}. "
                f"Supported types: {supported}"
            )
            logger.error(err)
            return {
                "success": False,
                "external_action_id": _FALLBACK_ID,
                "error": err,
            }

        logger.info(
            "▶ execute_action: action_type=%s | payload_keys=%s",
            action_type, list(payload.keys()),
        )
        result = handler(payload)

        # Normalise the result shape defensively
        if not isinstance(result, dict):
            return {
                "success": False,
                "external_action_id": _FALLBACK_ID,
                "error": f"Handler returned unexpected type {type(result).__name__}",
            }

        # Guarantee all required keys are present
        result.setdefault("success", False)
        result.setdefault("external_action_id", _FALLBACK_ID)
        result.setdefault("error", None)

        return result

    except Exception as exc:  # noqa: BLE001 — absolute last resort
        err = f"execute_action: unhandled exception for action_type={action_type!r}: {exc}"
        logger.critical(err, exc_info=True)
        return {
            "success": False,
            "external_action_id": _FALLBACK_ID,
            "error": err,
        }
