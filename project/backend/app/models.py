"""
models.py — SQLAlchemy async ORM models.

Uses SQLite for local dev.  Swapping to PostgreSQL requires ONLY changing
DATABASE_URL in .env (e.g. postgresql+asyncpg://user:pass@host/dbname).
No model changes are required.

The engine + session factory live here so orchestrator.py imports them directly.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import get_settings

settings = get_settings()

# ── Engine & session factory ───────────────────────────────────────────────────

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.APP_ENV == "development"),
    future=True,
    # SQLite-specific: needed for async + check_same_thread
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Base ───────────────────────────────────────────────────────────────────────

class Base(AsyncAttrs, DeclarativeBase):
    pass


# ── CollegeRequest ─────────────────────────────────────────────────────────────

class CollegeRequest(Base):
    """
    Represents one incoming college request end-to-end.
    Every field nullable (except PK / request_id) so partial state is safe.
    """
    __tablename__ = "college_requests"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Business key — used everywhere as the external identifier
    request_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)

    # State machine
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RECEIVED")

    # Requester info
    requester_name: Mapped[str] = mapped_column(String(200), nullable=False)
    requester_role: Mapped[str] = mapped_column(String(200), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Idempotency fingerprint (sha256 of requester_name + text, truncated)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # AI analysis output
    category: Mapped[Optional[str]] = mapped_column(String(100))
    recommended_action: Mapped[Optional[str]] = mapped_column(String(200))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[Optional[str]] = mapped_column(String(50))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    requires_approval: Mapped[Optional[bool]] = mapped_column(Integer)  # SQLite bool
    extracted_fields_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON-serialised dict

    # Action output
    action_type: Mapped[Optional[str]] = mapped_column(String(100))
    external_action_id: Mapped[Optional[str]] = mapped_column(String(200))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Notion page IDs (so we can deep-link or update them)
    notion_request_page_id: Mapped[Optional[str]] = mapped_column(String(200))
    notion_approval_page_id: Mapped[Optional[str]] = mapped_column(String(200))

    # ── Helpers ────────────────────────────────────────────────────────────────

    @property
    def extracted_fields(self) -> dict[str, Any]:
        if self.extracted_fields_json:
            try:
                return json.loads(self.extracted_fields_json)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    @extracted_fields.setter
    def extracted_fields(self, value: dict[str, Any]) -> None:
        self.extracted_fields_json = json.dumps(value) if value else None

    def __repr__(self) -> str:
        return f"<CollegeRequest {self.request_id} status={self.status}>"


# ── RunLog ─────────────────────────────────────────────────────────────────────

class RunLog(Base):
    """
    Append-only log of every state transition / event for a request.
    Judges read this to understand the full story of any request.
    """
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_runlog_request_id_ts", "request_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<RunLog {self.request_id} [{self.event}]>"


# ── IdempotencyRecord ──────────────────────────────────────────────────────────

class IdempotencyRecord(Base):
    """
    Short-lived dedup table. Stores idempotency_key → request_id for 5 min.
    A separate background task could prune old rows; for the hackathon we
    filter by timestamp in the query.
    """
    __tablename__ = "idempotency_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ── DB helpers ─────────────────────────────────────────────────────────────────

async def init_db() -> None:
    """Create all tables (idempotent)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:  # type: ignore[return]
    """FastAPI dependency: yields an AsyncSession and commits/rolls back."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
