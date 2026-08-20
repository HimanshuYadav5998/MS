"""
schemas.py — Pydantic models for /ai/analyze request and response.

Design rule: all output validation is strict — any field with an unsupported
value must be caught HERE, not silently passed to the backend.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ──────────────────────────────────────────────────────────────────────────────
# Enumerations  (add a new category here — one line, no other changes needed)
# ──────────────────────────────────────────────────────────────────────────────

class Category(str, Enum):
    LEAVE_REQUEST       = "leave_request"
    ASSIGNMENT_EXTENSION = "assignment_extension"
    EVENT_BOOKING       = "event_booking"
    MAINTENANCE_REQUEST = "maintenance_request"
    DOCUMENT_REQUEST    = "document_request"
    GENERAL_REQUEST     = "general_request"
    UNKNOWN             = "unknown"


class Priority(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"
    URGENT = "urgent"


class RequesterRole(str, Enum):
    STUDENT = "student"
    FACULTY = "faculty"
    STAFF   = "staff"
    OTHER   = "other"


class RecommendedAction(str, Enum):
    REQUEST_TEACHER_APPROVAL = "request_teacher_approval"
    REQUEST_HOD_APPROVAL     = "request_hod_approval"
    AUTO_PROCESS             = "auto_process"
    HUMAN_REVIEW             = "human_review"
    SCHEDULE_EVENT           = "schedule_event"
    RAISE_MAINTENANCE_TICKET = "raise_maintenance_ticket"
    GENERATE_DOCUMENT        = "generate_document"
    ESCALATE                 = "escalate"


# ──────────────────────────────────────────────────────────────────────────────
# Request model
# ──────────────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    request_id:     str  = Field(..., min_length=1, description="Unique request identifier")
    text:           str  = Field(..., min_length=1, description="Raw natural-language text from the requester")
    requester_name: str  = Field(..., min_length=1, description="Full name of the person making the request")
    requester_role: RequesterRole = Field(
        default=RequesterRole.STUDENT,
        description="Role of the requester in the institution"
    )

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank or whitespace-only")
        return v


# ──────────────────────────────────────────────────────────────────────────────
# Response model (strict — no extra fields allowed through)
# ──────────────────────────────────────────────────────────────────────────────

class AnalyzeResponse(BaseModel):
    model_config = {"extra": "forbid"}   # reject any LLM-injected extra keys

    category:            Category            = Field(..., description="Classified request category")
    priority:            Priority            = Field(..., description="Urgency level")
    confidence:          float               = Field(..., ge=0.0, le=1.0, description="Classification confidence [0,1]")
    extracted_fields:    Dict[str, Any]      = Field(default_factory=dict, description="Key domain fields extracted from the text")
    summary:             str                 = Field(..., min_length=1, description="One-sentence human-readable summary")
    recommended_action:  RecommendedAction   = Field(..., description="Action recommended to the backend")
    requires_approval:   bool                = Field(..., description="Whether human/admin approval is required")
    risk_reason:         Optional[str]       = Field(None, description="Non-null only when a risk/flag was detected")

    @field_validator("confidence")
    @classmethod
    def confidence_two_decimals(cls, v: float) -> float:
        return round(v, 4)

    @model_validator(mode="after")
    def enforce_escalation_consistency(self) -> "AnalyzeResponse":
        """
        Hard rule: unknown category MUST always require approval.
        (Belt-and-suspenders — the classifier also enforces this,
        but the schema is the last line of defence.)
        """
        if self.category == Category.UNKNOWN:
            self.requires_approval = True
            if self.recommended_action != RecommendedAction.HUMAN_REVIEW:
                self.recommended_action = RecommendedAction.HUMAN_REVIEW
        return self


# ──────────────────────────────────────────────────────────────────────────────
# Safe fallback response  (used when LLM output cannot be validated)
# ──────────────────────────────────────────────────────────────────────────────

FALLBACK_RESPONSE = AnalyzeResponse(
    category           = Category.UNKNOWN,
    priority           = Priority.MEDIUM,
    confidence         = 0.0,
    extracted_fields   = {},
    summary            = "Could not parse request; routed to human review.",
    recommended_action = RecommendedAction.HUMAN_REVIEW,
    requires_approval  = True,
    risk_reason        = "AI output could not be validated; routed to human review.",
)
