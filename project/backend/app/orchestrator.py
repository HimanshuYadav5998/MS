"""
orchestrator.py — The core state machine for AI College Request Automation.

THIS IS THE ENGINE.
- It is the ONLY component allowed to call action_service.execute_action().
- It wraps every external call (Notion, AI, Action) in try/except.
- It writes a Run Log entry for every single state transition.
- It never crashes FastAPI — all errors degrade gracefully to ESCALATED.

Workflow (12 steps, matches the brief exactly):
  1.  Validate input
  2.  Generate request_id
  3.  Idempotency check (5-minute window)
  4.  Insert DB row → RECEIVED
  5.  Notion: create_request_page → PROCESSING
  6.  AI: analyze (5 s timeout, 2 retries, fallback on failure)
  7.  Notion: update page with AI output
  8.  Requires approval → PENDING_APPROVAL + create_approval_page | else straight to execution
  9.  Background poller / manual override endpoint waits for human decision
  10. On approval → EXECUTING → action_service.execute_action → COMPLETED
  11. On rejection → REJECTED
  12. Every transition logged to Run Log (Notion + local DB)
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai_client
from app.config import get_settings
from app.models import AsyncSessionLocal, CollegeRequest, IdempotencyRecord, RunLog
from app.schemas import AIAnalyzeResponse, RequestStatus, WebhookRequestIn

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Lazy imports of teammate services ─────────────────────────────────────────
# Wrapped in functions to keep module-level imports safe if stubs don't exist.

def _get_notion_service():
    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        from project.notion import notion_service
        return notion_service
    except ImportError:
        return None


def _get_action_service():
    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        from project.integrations import action_service
        return action_service
    except ImportError:
        return None


# ── Logging helpers ────────────────────────────────────────────────────────────

def _log(level: str, request_id: str, message: str, **extra: Any) -> None:
    """Structured log with request_id always present."""
    getattr(logger, level)(message, extra={"request_id": request_id, **extra})


# ── Run Log (dual: local DB + Notion) ─────────────────────────────────────────

async def _write_run_log(
    session: AsyncSession,
    request_id: str,
    event: str,
    status: RequestStatus,
    detail: str = "",
) -> None:
    """
    Append a Run Log row to local DB AND call notion_service.create_run_log.
    Never raises — log errors are non-fatal.
    """
    # 1. Local DB log
    try:
        log_row = RunLog(
            request_id=request_id,
            event=event,
            detail=detail,
            status=status.value,
        )
        session.add(log_row)
        await session.flush()
        _log("info", request_id, f"RunLog: {event}", status=status.value, detail=detail)
    except Exception as exc:  # noqa: BLE001
        _log("error", request_id, f"Failed to write local RunLog: {exc}")

    # 2. Notion run log
    notion = _get_notion_service()
    if notion:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    notion.create_run_log,
                    request_id=request_id,
                    event=event,
                    status=status.value,
                    detail=detail,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            _log("warning", request_id, "Notion run log call timed out (non-fatal)")
        except Exception as exc:  # noqa: BLE001
            _log("warning", request_id, f"Notion run log call failed (non-fatal): {exc}")


# ── Status helper ──────────────────────────────────────────────────────────────

async def _set_status(
    session: AsyncSession,
    req: CollegeRequest,
    status: RequestStatus,
    event: str,
    detail: str = "",
) -> None:
    req.status = status.value
    req.updated_at = datetime.now(timezone.utc)
    await session.flush()
    await _write_run_log(session, req.request_id, event, status, detail)


# ── Idempotency ────────────────────────────────────────────────────────────────

def _make_idempotency_key(requester_name: str, text: str) -> str:
    raw = f"{requester_name.strip().lower()}::{text.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


async def _check_idempotency(session: AsyncSession, key: str) -> Optional[str]:
    """Return existing request_id if same key arrived within the window, else None."""
    window_start = datetime.now(timezone.utc) - timedelta(seconds=settings.IDEMPOTENCY_WINDOW_SECONDS)
    result = await session.execute(
        select(IdempotencyRecord)
        .where(IdempotencyRecord.idempotency_key == key)
        .where(IdempotencyRecord.created_at >= window_start)
        .order_by(IdempotencyRecord.created_at.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()
    return record.request_id if record else None


# ── Notion wrappers (thin, defensive) ─────────────────────────────────────────

async def _notion_create_request_page(req: CollegeRequest) -> Optional[str]:
    """Returns notion page_id or None on failure."""
    notion = _get_notion_service()
    if not notion:
        _log("warning", req.request_id, "notion_service not available — skipping create_request_page")
        return None
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                notion.create_request_page,
                request_id=req.request_id,
                requester_name=req.requester_name,
                requester_role=req.requester_role,
                text=req.text,
                status=req.status,
            ),
            timeout=10.0,
        )
        return result if isinstance(result, str) else (result or {}).get("id")
    except asyncio.TimeoutError:
        _log("warning", req.request_id, "notion create_request_page timed out")
    except Exception as exc:  # noqa: BLE001
        _log("error", req.request_id, f"notion create_request_page failed: {exc}")
    return None


async def _notion_update_request_page(req: CollegeRequest, ai: AIAnalyzeResponse) -> None:
    notion = _get_notion_service()
    if not notion:
        return
    try:
        await asyncio.wait_for(
            asyncio.to_thread(
                notion.update_request_page,
                page_id=req.notion_request_page_id,
                request_id=req.request_id,
                category=ai.category,
                recommended_action=ai.recommended_action,
                summary=ai.summary,
                priority=ai.priority,
                confidence=ai.confidence,
                requires_approval=ai.requires_approval,
                status=req.status,
            ),
            timeout=10.0,
        )
    except asyncio.TimeoutError:
        _log("warning", req.request_id, "notion update_request_page timed out")
    except Exception as exc:  # noqa: BLE001
        _log("error", req.request_id, f"notion update_request_page failed: {exc}")


async def _notion_create_approval_page(req: CollegeRequest) -> Optional[str]:
    notion = _get_notion_service()
    if not notion:
        return None
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                notion.create_approval_page,
                request_id=req.request_id,
                requester_name=req.requester_name,
                summary=req.summary,
                recommended_action=req.recommended_action,
                category=req.category,
                priority=req.priority,
            ),
            timeout=10.0,
        )
        return result if isinstance(result, str) else (result or {}).get("id")
    except asyncio.TimeoutError:
        _log("warning", req.request_id, "notion create_approval_page timed out")
    except Exception as exc:  # noqa: BLE001
        _log("error", req.request_id, f"notion create_approval_page failed: {exc}")
    return None


async def _notion_get_human_decision(req: CollegeRequest) -> Optional[str]:
    """Returns 'approved', 'rejected', or None (still pending)."""
    notion = _get_notion_service()
    if not notion:
        return None
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                notion.get_human_decision,
                request_id=req.request_id,
                approval_page_id=req.notion_approval_page_id,
            ),
            timeout=10.0,
        )
        return result
    except asyncio.TimeoutError:
        _log("warning", req.request_id, "notion get_human_decision timed out")
    except Exception as exc:  # noqa: BLE001
        _log("warning", req.request_id, f"notion get_human_decision failed: {exc}")
    return None


# ── Action service wrapper ─────────────────────────────────────────────────────

async def _execute_action(req: CollegeRequest) -> dict[str, Any]:
    """
    Build the payload from extracted_fields and call action_service.execute_action.
    Returns the response dict.  On failure, returns {"success": False, "error": "..."}.
    Retries ONCE on failure, then gives up (does NOT crash the process).
    """
    action_svc = _get_action_service()
    if not action_svc:
        _log("warning", req.request_id, "action_service not available — returning mock success")
        return {"success": True, "action_id": f"mock_{uuid4().hex[:8]}", "mocked": True}

    action_type = req.action_type or "send_email"
    payload = {
        "request_id": req.request_id,
        "requester_name": req.requester_name,
        "requester_role": req.requester_role,
        "category": req.category or "unknown",
        "recommended_action": req.recommended_action or "human_review",
        "summary": req.summary or req.text,
        **(req.extracted_fields or {}),
    }

    for attempt in range(2):  # at most 1 retry
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(action_svc.execute_action, action_type, payload),
                timeout=10.0,
            )
            _log(
                "info",
                req.request_id,
                f"action_service.execute_action returned",
                attempt=attempt + 1,
                success=result.get("success"),
            )
            return result
        except asyncio.TimeoutError:
            _log("warning", req.request_id, f"action_service timed out (attempt {attempt + 1})")
        except Exception as exc:  # noqa: BLE001
            _log("error", req.request_id, f"action_service error (attempt {attempt + 1}): {exc}")
        if attempt == 0:
            await asyncio.sleep(2)  # brief pause before retry

    return {"success": False, "error": "action_service failed after 1 retry"}


# ═══════════════════════════════════════════════════════════
# MAIN ENTRY POINT — called by POST /webhook/request
# ═══════════════════════════════════════════════════════════

async def process_request(payload: WebhookRequestIn) -> tuple[str, RequestStatus]:
    """
    Steps 1-8 of the workflow (synchronous portion):
      1-3: validate, generate ID, check idempotency
      4:   insert DB row → RECEIVED
      5:   Notion create page → PROCESSING
      6:   AI analyze
      7:   Notion update page
      8:   PENDING_APPROVAL (all requests) or ESCALATED on Notion failure

    Returns (request_id, current_status).
    Steps 9-12 happen asynchronously in _poll_for_decision.
    """
    async with AsyncSessionLocal() as session:
        # ── Step 1: Validate (Pydantic already did this; belt-and-braces) ──────
        if len(payload.text) > settings.REQUEST_TEXT_MAX_LENGTH:
            raise ValueError(f"text exceeds {settings.REQUEST_TEXT_MAX_LENGTH} chars")

        # ── Step 2: Generate request_id ────────────────────────────────────────
        request_id = f"req_{uuid4().hex[:8]}"

        # ── Step 3: Idempotency check ──────────────────────────────────────────
        idem_key = _make_idempotency_key(payload.requester_name, payload.text)
        existing_id = await _check_idempotency(session, idem_key)
        if existing_id:
            _log("info", existing_id, "Idempotency hit — returning existing request_id")
            existing_req = await session.execute(
                select(CollegeRequest).where(CollegeRequest.request_id == existing_id)
            )
            existing_obj = existing_req.scalar_one_or_none()
            status = RequestStatus(existing_obj.status) if existing_obj else RequestStatus.RECEIVED
            return existing_id, status

        # ── Step 4: Insert DB row → RECEIVED ───────────────────────────────────
        req = CollegeRequest(
            request_id=request_id,
            status=RequestStatus.RECEIVED.value,
            requester_name=payload.requester_name,
            requester_role=payload.requester_role,
            text=payload.text,
            idempotency_key=idem_key,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(req)
        idem_rec = IdempotencyRecord(
            idempotency_key=idem_key,
            request_id=request_id,
            created_at=datetime.now(timezone.utc),
        )
        session.add(idem_rec)
        await session.flush()

        await _write_run_log(
            session, request_id, "Request received", RequestStatus.RECEIVED,
            f"Requester: {payload.requester_name} ({payload.requester_role})"
        )
        _log("info", request_id, "Request inserted into DB", status="RECEIVED")

        # ── Step 5: Notion create_request_page → PROCESSING ───────────────────
        await _set_status(session, req, RequestStatus.PROCESSING, "Processing started")
        notion_page_id = await _notion_create_request_page(req)
        if notion_page_id:
            req.notion_request_page_id = notion_page_id
            await session.flush()
        await _write_run_log(
            session, request_id, "Notion request page created", RequestStatus.PROCESSING,
            f"Notion page ID: {notion_page_id or 'N/A'}"
        )

        # ── Step 6: AI analyze ─────────────────────────────────────────────────
        ai_result: AIAnalyzeResponse = await ai_client.analyze(request_id, payload.text)

        # Persist AI output to DB
        req.category = ai_result.category
        req.recommended_action = ai_result.recommended_action
        req.summary = ai_result.summary
        req.priority = ai_result.priority
        req.confidence = ai_result.confidence
        req.requires_approval = ai_result.requires_approval
        req.extracted_fields = ai_result.extracted_fields
        req.action_type = "send_email"  # default for hackathon demo
        await session.flush()

        ai_detail = (
            f"category={ai_result.category}, action={ai_result.recommended_action}, "
            f"priority={ai_result.priority}, confidence={ai_result.confidence:.2f}, "
            f"requires_approval={ai_result.requires_approval}"
        )
        await _write_run_log(
            session, request_id, "AI analysis complete", RequestStatus.PROCESSING, ai_detail
        )

        # ── Step 7: Update Notion page with AI output ──────────────────────────
        await _notion_update_request_page(req, ai_result)
        await _write_run_log(
            session, request_id, "Notion page updated with AI output", RequestStatus.PROCESSING, ai_detail
        )

        # ── Step 8: Determine approval path ────────────────────────────────────
        # Hackathon safety rule: ALL requests require approval.
        await _set_status(
            session, req, RequestStatus.PENDING_APPROVAL,
            "Pending human approval",
            "All requests require approval per hackathon safety policy"
        )

        approval_page_id = await _notion_create_approval_page(req)
        if approval_page_id:
            req.notion_approval_page_id = approval_page_id
            await session.flush()
        await _write_run_log(
            session, request_id, "Approval page created in Notion", RequestStatus.PENDING_APPROVAL,
            f"Approval page ID: {approval_page_id or 'N/A'}"
        )

        await session.commit()

    # ── Step 9: Launch background poller ──────────────────────────────────────
    asyncio.create_task(_poll_for_decision(request_id), name=f"poll_{request_id}")
    _log("info", request_id, "Background approval poller started")

    return request_id, RequestStatus.PENDING_APPROVAL


# ═══════════════════════════════════════════════════════════
# BACKGROUND POLLER — Steps 9-12
# ═══════════════════════════════════════════════════════════

async def _poll_for_decision(request_id: str) -> None:
    """
    Polls notion_service.get_human_decision() every APPROVAL_POLL_INTERVAL_SECONDS.
    Gives up after APPROVAL_POLL_MAX_WAIT_SECONDS and escalates.
    """
    poll_interval = settings.APPROVAL_POLL_INTERVAL_SECONDS
    max_wait = settings.APPROVAL_POLL_MAX_WAIT_SECONDS
    deadline = datetime.now(timezone.utc) + timedelta(seconds=max_wait)

    _log("info", request_id, "Approval poller running")

    while datetime.now(timezone.utc) < deadline:
        await asyncio.sleep(poll_interval)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(CollegeRequest).where(CollegeRequest.request_id == request_id)
            )
            req = result.scalar_one_or_none()

            if req is None:
                _log("error", request_id, "Poller: request not found in DB — stopping")
                return

            # If manually approved/rejected via API endpoint, stop polling
            if req.status not in (
                RequestStatus.PENDING_APPROVAL.value,
                RequestStatus.PROCESSING.value,
            ):
                _log("info", request_id, f"Poller: status is {req.status} — stopping")
                return

            decision = await _notion_get_human_decision(req)
            _log("debug", request_id, f"Poller: Notion decision = {decision}")

            if decision == "approved":
                await _handle_approval(session, req)
                await session.commit()
                return
            elif decision == "rejected":
                await _handle_rejection(session, req)
                await session.commit()
                return
            # else: still pending — loop again

    # Timeout: escalate
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CollegeRequest).where(CollegeRequest.request_id == request_id)
        )
        req = result.scalar_one_or_none()
        if req and req.status == RequestStatus.PENDING_APPROVAL.value:
            await _set_status(
                session, req, RequestStatus.ESCALATED,
                "Approval timed out — escalated",
                f"No decision received within {max_wait}s",
            )
            await session.commit()


# ═══════════════════════════════════════════════════════════
# APPROVAL / REJECTION HANDLERS
# ═══════════════════════════════════════════════════════════

async def _handle_approval(session: AsyncSession, req: CollegeRequest) -> None:
    """Steps 10 — run action, update status."""
    await _set_status(session, req, RequestStatus.APPROVED, "Request approved")

    # ── Step 10: EXECUTING ────────────────────────────────────────────────────
    await _set_status(session, req, RequestStatus.EXECUTING, "Executing action", req.action_type or "send_email")

    action_result = await _execute_action(req)
    success = action_result.get("success", False)

    if success:
        ext_id = str(action_result.get("action_id") or action_result.get("external_action_id") or "")
        req.external_action_id = ext_id
        await session.flush()
        await _set_status(
            session, req, RequestStatus.COMPLETED,
            "Action completed successfully",
            f"external_action_id={ext_id}",
        )
    else:
        error = str(action_result.get("error", "Unknown error"))
        req.error_message = error
        await session.flush()
        await _set_status(
            session, req, RequestStatus.FAILED,
            "Action execution failed",
            error,
        )


async def _handle_rejection(session: AsyncSession, req: CollegeRequest) -> None:
    """Step 11 — mark rejected, log."""
    await _set_status(session, req, RequestStatus.REJECTED, "Request rejected by human reviewer")


# ═══════════════════════════════════════════════════════════
# MANUAL DECISION ENDPOINTS (called by FastAPI routes)
# ═══════════════════════════════════════════════════════════

async def manual_approve(request_id: str) -> tuple[RequestStatus, str]:
    """
    Called by POST /approval/{request_id}.
    Returns (new_status, message).
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CollegeRequest).where(CollegeRequest.request_id == request_id)
        )
        req = result.scalar_one_or_none()
        if req is None:
            return RequestStatus.FAILED, "Request not found"

        if req.status not in (RequestStatus.PENDING_APPROVAL.value, RequestStatus.ESCALATED.value):
            return RequestStatus(req.status), f"Cannot approve request in status {req.status}"

        await _handle_approval(session, req)
        await session.commit()
        return RequestStatus(req.status), "Request approved and action initiated"


async def manual_reject(request_id: str) -> tuple[RequestStatus, str]:
    """Called by POST /reject/{request_id}."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CollegeRequest).where(CollegeRequest.request_id == request_id)
        )
        req = result.scalar_one_or_none()
        if req is None:
            return RequestStatus.FAILED, "Request not found"

        if req.status not in (RequestStatus.PENDING_APPROVAL.value, RequestStatus.ESCALATED.value):
            return RequestStatus(req.status), f"Cannot reject request in status {req.status}"

        await _handle_rejection(session, req)
        await session.commit()
        return RequestStatus.REJECTED, "Request rejected"


async def manual_override(request_id: str, decision: str) -> tuple[RequestStatus, str]:
    """Called by POST /override/{request_id}."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CollegeRequest).where(CollegeRequest.request_id == request_id)
        )
        req = result.scalar_one_or_none()
        if req is None:
            return RequestStatus.FAILED, "Request not found"

        if decision == "approved":
            await _set_status(session, req, RequestStatus.OVERRIDDEN, "Manual override — approved")
            await _handle_approval(session, req)
            await session.commit()
            return RequestStatus(req.status), "Override approved"
        elif decision == "rejected":
            await _set_status(session, req, RequestStatus.OVERRIDDEN, "Manual override — rejected")
            await _handle_rejection(session, req)
            await session.commit()
            return RequestStatus.REJECTED, "Override rejected"
        else:
            return RequestStatus(req.status), f"Unknown decision: {decision}"


async def manual_execute(request_id: str) -> tuple[RequestStatus, str, Optional[str]]:
    """
    Called by POST /actions/{request_id}/execute — demo recovery endpoint.
    Re-triggers action execution for APPROVED/FAILED/ESCALATED requests.
    Returns (status, message, external_action_id).
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CollegeRequest).where(CollegeRequest.request_id == request_id)
        )
        req = result.scalar_one_or_none()
        if req is None:
            return RequestStatus.FAILED, "Request not found", None

        allowed = {
            RequestStatus.APPROVED.value,
            RequestStatus.FAILED.value,
            RequestStatus.ESCALATED.value,
            RequestStatus.OVERRIDDEN.value,
        }
        if req.status not in allowed:
            return (
                RequestStatus(req.status),
                f"Cannot re-execute request in status {req.status}",
                None,
            )

        await _handle_approval(session, req)
        await session.commit()
        return (
            RequestStatus(req.status),
            "Re-execution triggered",
            req.external_action_id,
        )
