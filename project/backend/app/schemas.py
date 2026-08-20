"""
schemas.py — Pydantic v2 request/response models.

RULES:
- Strict validation: no bare dicts cross a function boundary.
- Every external-facing payload is represented here.
- model_config = ConfigDict(strict=False) to allow coercion where needed but
  explicit field types for documentation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── State machine states ───────────────────────────────────────────────────────

class RequestStatus(str, Enum):
    RECEIVED         = "RECEIVED"
    PROCESSING       = "PROCESSING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED         = "APPROVED"
    REJECTED         = "REJECTED"
    OVERRIDDEN       = "OVERRIDDEN"
    EXECUTING        = "EXECUTING"
    COMPLETED        = "COMPLETED"
    FAILED           = "FAILED"
    ESCALATED        = "ESCALATED"


# ── Inbound webhook payload ────────────────────────────────────────────────────

class WebhookRequestIn(BaseModel):
    model_config = ConfigDict(strict=False, str_strip_whitespace=True)

    text: str = Field(..., min_length=1, description="Full text of the college request")
    requester_name: str = Field(..., min_length=1, max_length=200)
    requester_role: str = Field(..., min_length=1, max_length=200)

    @field_validator("text")
    @classmethod
    def text_not_too_long(cls, v: str) -> str:
        # Max enforced here; config also has it for runtime checks.
        if len(v) > 5000:
            raise ValueError("Request text exceeds maximum length of 5000 characters")
        return v


class WebhookRequestOut(BaseModel):
    request_id: str
    status: RequestStatus
    message: str


# ── AI service payload / response ──────────────────────────────────────────────

class AIAnalyzeRequest(BaseModel):
    request_id: str
    text: str


class AIAnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")  # allow extra fields from ai-service

    request_id: str
    category: str = "unknown"
    recommended_action: str = "human_review"
    summary: str = ""
    priority: str = "medium"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_approval: bool = True
    extracted_fields: dict[str, Any] = Field(default_factory=dict)


# ── Approval / rejection / override ───────────────────────────────────────────

class ApprovalDecision(str, Enum):
    approved = "approved"
    rejected = "rejected"


class OverrideRequestIn(BaseModel):
    decision: ApprovalDecision


# ── Full request state (GET /requests/{id}) ───────────────────────────────────

class RequestStateOut(BaseModel):
    request_id: str
    status: RequestStatus
    requester_name: str
    requester_role: str
    text: str
    created_at: datetime
    updated_at: datetime

    # AI output — all optional because they're populated async
    category: Optional[str] = None
    recommended_action: Optional[str] = None
    summary: Optional[str] = None
    priority: Optional[str] = None
    confidence: Optional[float] = None
    requires_approval: Optional[bool] = None
    extracted_fields: Optional[dict[str, Any]] = None

    # Action output
    action_type: Optional[str] = None
    external_action_id: Optional[str] = None
    error_message: Optional[str] = None

    # Notion page ids (for deep-linking)
    notion_request_page_id: Optional[str] = None
    notion_approval_page_id: Optional[str] = None


# ── Run log event ──────────────────────────────────────────────────────────────

class RunLogEvent(BaseModel):
    request_id: str
    event: str
    detail: str = ""
    status: RequestStatus
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Health check ───────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    ai_service: str = "unreachable"
    db: str = "ok"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Manual action trigger ──────────────────────────────────────────────────────

class ManualExecuteOut(BaseModel):
    request_id: str
    status: RequestStatus
    message: str
    external_action_id: Optional[str] = None
