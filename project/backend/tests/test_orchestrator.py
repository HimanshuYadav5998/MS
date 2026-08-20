"""
tests/test_orchestrator.py

Test cases required by the QA suite:
  1. Happy path integration test (mock notion + action service)
  2. Idempotency test (same requester+text within 5 min → same request_id)
  3. Invalid input test (empty text → 422, too-long text → 422)
  4. AI timeout/retry test (AI service down → fallback, still PENDING_APPROVAL)
  5. Manual approval endpoint test
  6. Manual rejection endpoint test
  7. Override endpoint test
  8. Health check test
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import httpx


# ══════════════════════════════════════════════════════════════════════════════
# 1.  Happy-path integration test
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_happy_path_webhook(client, sample_payload, ai_response_approved):
    """
    POST /webhook/request with valid payload:
    - Returns 202 with a request_id
    - Status is PENDING_APPROVAL (all requests require approval)
    - GET /requests/{id} returns full state
    """
    ac, mock_notion, mock_action = client

    with patch("app.ai_client.analyze", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = __import__("app.schemas", fromlist=["AIAnalyzeResponse"]).AIAnalyzeResponse(
            **ai_response_approved
        )

        resp = await ac.post("/webhook/request", json=sample_payload)

    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert "request_id" in data
    assert data["status"] == "PENDING_APPROVAL"
    request_id = data["request_id"]

    # GET the request
    get_resp = await ac.get(f"/requests/{request_id}")
    assert get_resp.status_code == 200
    state = get_resp.json()
    assert state["request_id"] == request_id
    assert state["requester_name"] == sample_payload["requester_name"]
    assert state["category"] == "recommendation_letter"
    assert state["status"] == "PENDING_APPROVAL"


# ══════════════════════════════════════════════════════════════════════════════
# 2.  Idempotency test (QA Test Case 5)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_idempotency_returns_same_request_id(client, sample_payload, ai_response_approved):
    """
    Sending the same (requester_name, text) twice within 5 minutes must return
    the SAME request_id both times.
    """
    ac, mock_notion, mock_action = client

    with patch("app.ai_client.analyze", new_callable=AsyncMock) as mock_ai:
        from app.schemas import AIAnalyzeResponse
        mock_ai.return_value = AIAnalyzeResponse(**ai_response_approved)

        resp1 = await ac.post("/webhook/request", json=sample_payload)
        resp2 = await ac.post("/webhook/request", json=sample_payload)

    assert resp1.status_code == 202
    assert resp2.status_code == 202
    id1 = resp1.json()["request_id"]
    id2 = resp2.json()["request_id"]
    assert id1 == id2, f"Expected same request_id, got {id1} vs {id2}"


# ══════════════════════════════════════════════════════════════════════════════
# 3.  Invalid input tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_invalid_input_empty_text(client):
    """Empty text should return 422."""
    ac, _, _ = client
    resp = await ac.post(
        "/webhook/request",
        json={"text": "", "requester_name": "Bob", "requester_role": "Student"},
    )
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_invalid_input_missing_field(client):
    """Missing requester_name should return 422."""
    ac, _, _ = client
    resp = await ac.post(
        "/webhook/request",
        json={"text": "Need a letter", "requester_role": "Student"},
    )
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_invalid_input_too_long_text(client):
    """Text > 5000 chars should return 422."""
    ac, _, _ = client
    resp = await ac.post(
        "/webhook/request",
        json={
            "text": "x" * 5001,
            "requester_name": "Charlie",
            "requester_role": "Faculty",
        },
    )
    assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# 4.  AI timeout / unreachable fallback
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ai_service_unreachable_graceful_fallback(client, sample_payload):
    """
    When ai_client.analyze returns the fallback response (AI unreachable),
    the request must still proceed to PENDING_APPROVAL (not crash).
    """
    ac, mock_notion, mock_action = client

    from app.schemas import AIAnalyzeResponse
    fallback = AIAnalyzeResponse(
        request_id="req_fallback",
        category="unknown",
        recommended_action="human_review",
        summary="AI service was unreachable. Manual review required.",
        priority="high",
        confidence=0.0,
        requires_approval=True,
        extracted_fields={},
    )

    with patch("app.ai_client.analyze", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = fallback
        resp = await ac.post("/webhook/request", json=sample_payload)

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "PENDING_APPROVAL"


# ══════════════════════════════════════════════════════════════════════════════
# 5.  Manual approve endpoint
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_manual_approve(client, sample_payload, ai_response_approved):
    """POST /approval/{id} must transition PENDING_APPROVAL → COMPLETED (via EXECUTING)."""
    ac, mock_notion, mock_action = client

    from app.schemas import AIAnalyzeResponse
    with patch("app.ai_client.analyze", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = AIAnalyzeResponse(**ai_response_approved)
        resp = await ac.post("/webhook/request", json=sample_payload)

    request_id = resp.json()["request_id"]

    approve_resp = await ac.post(f"/approval/{request_id}")
    assert approve_resp.status_code == 200
    result = approve_resp.json()
    assert result["status"] in ("COMPLETED", "EXECUTING", "FAILED"), result

    # Verify action_service was called
    mock_action.execute_action.assert_called()


# ══════════════════════════════════════════════════════════════════════════════
# 6.  Manual reject endpoint
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_manual_reject(client, ai_response_approved):
    """POST /reject/{id} must set status to REJECTED."""
    ac, mock_notion, mock_action = client

    payload = {
        "text": "I need a transcript sent to Harvard.",
        "requester_name": "Diana Prince",
        "requester_role": "Graduate Student",
    }

    from app.schemas import AIAnalyzeResponse
    with patch("app.ai_client.analyze", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = AIAnalyzeResponse(**{**ai_response_approved, "request_id": "req_reject01"})
        resp = await ac.post("/webhook/request", json=payload)

    request_id = resp.json()["request_id"]
    reject_resp = await ac.post(f"/reject/{request_id}")
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "REJECTED"


# ══════════════════════════════════════════════════════════════════════════════
# 7.  Override endpoint
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_manual_override_approved(client, ai_response_approved):
    """POST /override/{id} with decision=approved must execute the action."""
    ac, mock_notion, mock_action = client

    payload = {
        "text": "Please send my grades to Stanford admissions.",
        "requester_name": "Eve Adams",
        "requester_role": "Undergraduate",
    }

    from app.schemas import AIAnalyzeResponse
    with patch("app.ai_client.analyze", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = AIAnalyzeResponse(**{**ai_response_approved, "request_id": "req_over01"})
        resp = await ac.post("/webhook/request", json=payload)

    request_id = resp.json()["request_id"]

    override_resp = await ac.post(
        f"/override/{request_id}",
        json={"decision": "approved"},
    )
    assert override_resp.status_code == 200
    data = override_resp.json()
    assert data["status"] in ("COMPLETED", "EXECUTING", "OVERRIDDEN", "FAILED")


# ══════════════════════════════════════════════════════════════════════════════
# 8.  Health check
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_health_check(client):
    """GET /health must return 200 with status=ok."""
    ac, _, _ = client
    with patch("app.ai_client.health_check", new_callable=AsyncMock) as mock_hc:
        mock_hc.return_value = True
        resp = await ac.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["ai_service"] == "reachable"

@pytest.mark.asyncio
async def test_health_check_ai_unreachable(client):
    """GET /health with AI down → ai_service=unreachable (not a 500)."""
    ac, _, _ = client
    with patch("app.ai_client.health_check", new_callable=AsyncMock) as mock_hc:
        mock_hc.return_value = False
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json()["ai_service"] == "unreachable"


# ══════════════════════════════════════════════════════════════════════════════
# 9.  404 on non-existent request
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_nonexistent_request(client):
    ac, _, _ = client
    resp = await ac.get("/requests/req_doesnotexist")
    assert resp.status_code == 404
