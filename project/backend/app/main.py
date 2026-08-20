"""
main.py — FastAPI application entrypoint.

Registers all routes, configures JSON structured logging, initialises the DB,
and exposes the full API surface documented in the project brief.
"""
from __future__ import annotations

import logging
import logging.config
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai_client, orchestrator
from app.config import get_settings
from app.models import CollegeRequest, RunLog, get_session, init_db
from app.schemas import (
    HealthResponse,
    ManualExecuteOut,
    OverrideRequestIn,
    RequestStateOut,
    RequestStatus,
    WebhookRequestIn,
    WebhookRequestOut,
)

settings = get_settings()

# ── JSON Structured Logging ────────────────────────────────────────────────────

class JsonFormatter(logging.Formatter):
    """Emit log records as JSON lines so they're grep-able by request_id."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        # Merge any extra fields attached via extra={...}
        for key, value in record.__dict__.items():
            if key not in {
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "message", "module", "msecs", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName", "request_id",
            }:
                log_obj[key] = value

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


def _configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
    root.handlers = [handler]


# ── App lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    _configure_logging()
    logging.getLogger(__name__).info("Starting AI College Request Automation backend")
    await init_db()
    yield
    logging.getLogger(__name__).info("Shutting down")


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI College Request Automation",
    description=(
        "Orchestrator backend: receives college requests, classifies with AI, "
        "pauses for human approval via Notion, then executes approved actions."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

logger = logging.getLogger(__name__)


# ── Global exception handler (never crash FastAPI) ─────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


# ═══════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════

# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Ops"])
async def health_check() -> HealthResponse:
    """Returns server health + AI service reachability."""
    ai_reachable = await ai_client.health_check()
    return HealthResponse(
        status="ok",
        ai_service="reachable" if ai_reachable else "unreachable",
    )


# ── Webhook ───────────────────────────────────────────────────────────────────

@app.post(
    "/webhook/request",
    response_model=WebhookRequestOut,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Requests"],
    summary="Receive a new college request",
)
async def webhook_request(payload: WebhookRequestIn) -> WebhookRequestOut:
    """
    Entry point for all college requests.
    Kicks off the full orchestration workflow asynchronously.
    Returns 202 Accepted immediately with the request_id.
    """
    try:
        request_id, req_status = await orchestrator.process_request(payload)
        return WebhookRequestOut(
            request_id=request_id,
            status=req_status,
            message=f"Request received and queued (status: {req_status.value})",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"webhook_request failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}") from exc


# ── Get request state ─────────────────────────────────────────────────────────

@app.get(
    "/requests/{request_id}",
    response_model=RequestStateOut,
    tags=["Requests"],
    summary="Get full current state of a request",
)
async def get_request(
    request_id: str,
    session: AsyncSession = Depends(get_session),
) -> RequestStateOut:
    result = await session.execute(
        select(CollegeRequest).where(CollegeRequest.request_id == request_id)
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")

    return RequestStateOut(
        request_id=req.request_id,
        status=RequestStatus(req.status),
        requester_name=req.requester_name,
        requester_role=req.requester_role,
        text=req.text,
        created_at=req.created_at,
        updated_at=req.updated_at,
        category=req.category,
        recommended_action=req.recommended_action,
        summary=req.summary,
        priority=req.priority,
        confidence=req.confidence,
        requires_approval=bool(req.requires_approval) if req.requires_approval is not None else None,
        extracted_fields=req.extracted_fields,
        action_type=req.action_type,
        external_action_id=req.external_action_id,
        error_message=req.error_message,
        notion_request_page_id=req.notion_request_page_id,
        notion_approval_page_id=req.notion_approval_page_id,
    )


# ── Manual approve ────────────────────────────────────────────────────────────

@app.post(
    "/approval/{request_id}",
    response_model=WebhookRequestOut,
    tags=["Decisions"],
    summary="Manually approve a pending request (demo safety net)",
)
async def approve_request(request_id: str) -> WebhookRequestOut:
    req_status, message = await orchestrator.manual_approve(request_id)
    if req_status == RequestStatus.FAILED and message == "Request not found":
        raise HTTPException(status_code=404, detail=message)
    return WebhookRequestOut(request_id=request_id, status=req_status, message=message)


# ── Manual reject ─────────────────────────────────────────────────────────────

@app.post(
    "/reject/{request_id}",
    response_model=WebhookRequestOut,
    tags=["Decisions"],
    summary="Manually reject a pending request",
)
async def reject_request(request_id: str) -> WebhookRequestOut:
    req_status, message = await orchestrator.manual_reject(request_id)
    if req_status == RequestStatus.FAILED and message == "Request not found":
        raise HTTPException(status_code=404, detail=message)
    return WebhookRequestOut(request_id=request_id, status=req_status, message=message)


# ── Manual override ───────────────────────────────────────────────────────────

@app.post(
    "/override/{request_id}",
    response_model=WebhookRequestOut,
    tags=["Decisions"],
    summary="Override a request decision (approved or rejected)",
)
async def override_request(request_id: str, body: OverrideRequestIn) -> WebhookRequestOut:
    req_status, message = await orchestrator.manual_override(request_id, body.decision.value)
    if req_status == RequestStatus.FAILED and message == "Request not found":
        raise HTTPException(status_code=404, detail=message)
    return WebhookRequestOut(request_id=request_id, status=req_status, message=message)


# ── Manual re-execute ─────────────────────────────────────────────────────────

@app.post(
    "/actions/{request_id}/execute",
    response_model=ManualExecuteOut,
    tags=["Decisions"],
    summary="Manually re-trigger action execution (demo recovery)",
)
async def manual_execute(request_id: str) -> ManualExecuteOut:
    req_status, message, ext_id = await orchestrator.manual_execute(request_id)
    if req_status == RequestStatus.FAILED and message == "Request not found":
        raise HTTPException(status_code=404, detail=message)
    return ManualExecuteOut(
        request_id=request_id,
        status=req_status,
        message=message,
        external_action_id=ext_id,
    )


# ── Run log (bonus endpoint for debugging) ────────────────────────────────────

@app.get(
    "/requests/{request_id}/logs",
    tags=["Requests"],
    summary="Get all run log entries for a request",
)
async def get_run_logs(
    request_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    result = await session.execute(
        select(RunLog)
        .where(RunLog.request_id == request_id)
        .order_by(RunLog.timestamp.asc())
    )
    logs = result.scalars().all()
    if not logs:
        raise HTTPException(status_code=404, detail=f"No logs found for {request_id}")
    return [
        {
            "id": log.id,
            "request_id": log.request_id,
            "event": log.event,
            "detail": log.detail,
            "status": log.status,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in logs
    ]
