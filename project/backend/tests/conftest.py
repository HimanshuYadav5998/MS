"""
tests/conftest.py — shared fixtures for the test suite.

Uses an in-memory SQLite database so tests never touch the real DB.
All Notion and action_service calls are mocked via monkeypatch.
"""
from __future__ import annotations

import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Path setup ─────────────────────────────────────────────────────────────────
# project/backend/tests/conftest.py
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))        # .../backend/tests
_BACKEND_DIR = os.path.dirname(_TESTS_DIR)                      # .../backend
_PROJECT_DIR = os.path.dirname(_BACKEND_DIR)                    # .../project
_WORKSPACE_DIR = os.path.dirname(_PROJECT_DIR)                  # workspace root

for _p in [_BACKEND_DIR, _PROJECT_DIR, _WORKSPACE_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Override DB URL before importing app ──────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("NOTION_API_KEY", "test-key")
os.environ.setdefault("NOTION_REQUESTS_DB_ID", "test-db")
os.environ.setdefault("NOTION_RUNLOG_DB_ID", "test-runlog")
os.environ.setdefault("NOTION_APPROVALS_DB_ID", "test-approvals")
os.environ.setdefault("AI_SERVICE_URL", "http://localhost:8001")
os.environ["APPROVAL_POLL_INTERVAL_SECONDS"] = "1"
os.environ["APPROVAL_POLL_MAX_WAIT_SECONDS"] = "5"

# Now safe to import app modules
from app.config import get_settings
settings = get_settings()

from app.models import Base
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """In-memory SQLite engine, fresh per test."""
    eng = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    """Async session backed by the test engine."""
    factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(test_engine):
    """
    AsyncClient wired to the FastAPI app with mocked external services.
    Patches:
      - app.models.engine → test_engine
      - app.models.AsyncSessionLocal → test session factory
      - app.orchestrator.AsyncSessionLocal → test session factory
      - orchestrator._get_notion_service → returns mock
      - orchestrator._get_action_service → returns mock
      - ai_client (mocked per test)
    """
    from app import models as _models
    import app.orchestrator as _orch

    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    # Build mock notion_service
    mock_notion = MagicMock()
    mock_notion.create_request_page.return_value = "notion_page_test"
    mock_notion.update_request_page.return_value = None
    mock_notion.create_approval_page.return_value = "notion_approval_test"
    mock_notion.get_human_decision.return_value = None
    mock_notion.create_run_log.return_value = None

    # Build mock action_service
    mock_action = MagicMock()
    mock_action.execute_action.return_value = {"success": True, "action_id": "test_action_001"}

    with (
        patch.object(_models, "engine", test_engine),
        patch.object(_models, "AsyncSessionLocal", test_session_factory),
        patch.object(_orch, "AsyncSessionLocal", test_session_factory),
        patch.object(_orch, "_get_notion_service", return_value=mock_notion),
        patch.object(_orch, "_get_action_service", return_value=mock_action),
    ):
        # Re-init DB tables on the test engine
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac, mock_notion, mock_action


@pytest.fixture
def sample_payload() -> dict:
    return {
        "text": "I need a recommendation letter for my MIT application by next Friday.",
        "requester_name": "Alice Chen",
        "requester_role": "Senior Student",
    }


@pytest.fixture
def ai_response_approved() -> dict:
    return {
        "request_id": "req_test0001",
        "category": "recommendation_letter",
        "recommended_action": "send_email",
        "summary": "Student requests recommendation letter for MIT by next Friday.",
        "priority": "high",
        "confidence": 0.92,
        "requires_approval": True,
        "extracted_fields": {"deadline": "next Friday", "institution": "MIT"},
    }
