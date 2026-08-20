"""
tests/conftest.py
==================
Shared pytest fixtures for the AI College Request Automation test suite.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# ── Make integrations importable from tests/ ──────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Auto-clear module cache on each test that changes EMAIL_PROVIDER ──────────
@pytest.fixture(autouse=True)
def _isolate_action_service():
    """
    Yield, then remove action_service from sys.modules so the next test
    that sets EMAIL_PROVIDER gets a fresh import with the new value.
    """
    yield
    for key in list(sys.modules.keys()):
        if "action_service" in key:
            del sys.modules[key]


@pytest.fixture
def mock_env(monkeypatch):
    """Set all env vars to safe mock defaults."""
    monkeypatch.setenv("EMAIL_PROVIDER", "mock")
    monkeypatch.setenv("CALENDAR_PROVIDER", "mock")
    monkeypatch.setenv("BACKEND_URL", os.getenv("BACKEND_URL", "http://localhost:8000"))
    monkeypatch.setenv("AI_SERVICE_URL", os.getenv("AI_SERVICE_URL", "http://localhost:8001"))
    return monkeypatch
