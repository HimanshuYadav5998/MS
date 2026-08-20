"""
ai_client.py — Async httpx wrapper for the AI classification microservice.

Contract:
  POST http://localhost:8001/ai/analyze
  Body: {"request_id": str, "text": str}
  Response: AIAnalyzeResponse (validated via Pydantic)

Reliability features:
  - 5 second timeout per attempt
  - Up to 2 retries with exponential backoff on timeout / 5xx
  - On full failure: returns a safe fallback AIAnalyzeResponse with
    requires_approval=True so the orchestrator can still proceed gracefully.

Never raises — callers can always rely on getting an AIAnalyzeResponse back.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import get_settings
from app.schemas import AIAnalyzeRequest, AIAnalyzeResponse

logger = logging.getLogger(__name__)
settings = get_settings()

_FALLBACK_RESPONSE_TEMPLATE = {
    "category": "unknown",
    "recommended_action": "human_review",
    "summary": "AI service was unreachable. Manual review required.",
    "priority": "high",
    "confidence": 0.0,
    "requires_approval": True,
    "extracted_fields": {},
}


def _fallback_response(request_id: str, reason: str) -> AIAnalyzeResponse:
    """Return a safe fallback when the AI service is unavailable."""
    logger.warning(
        "AI service fallback triggered",
        extra={"request_id": request_id, "reason": reason},
    )
    return AIAnalyzeResponse(
        request_id=request_id,
        **_FALLBACK_RESPONSE_TEMPLATE,  # type: ignore[arg-type]
    )


async def analyze(request_id: str, text: str) -> AIAnalyzeResponse:
    """
    Call the AI microservice with retry + exponential backoff.

    Returns:
        AIAnalyzeResponse — always, even on total failure (fallback).
    """
    payload = AIAnalyzeRequest(request_id=request_id, text=text)
    url = f"{settings.AI_SERVICE_URL}/ai/analyze"
    max_retries = settings.AI_SERVICE_MAX_RETRIES
    timeout = settings.AI_SERVICE_TIMEOUT_SECONDS

    last_error: str = ""

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
        for attempt in range(max_retries + 1):
            backoff = 2**attempt  # 1s, 2s, 4s …
            try:
                logger.info(
                    "Calling AI service",
                    extra={"request_id": request_id, "attempt": attempt + 1, "url": url},
                )
                response = await client.post(url, json=payload.model_dump())

                if response.status_code >= 500:
                    last_error = f"AI service returned HTTP {response.status_code}"
                    logger.warning(
                        last_error,
                        extra={"request_id": request_id, "attempt": attempt + 1},
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(backoff)
                        continue
                    return _fallback_response(request_id, last_error)

                if response.status_code != 200:
                    # 4xx — not a transient error, don't retry
                    last_error = f"AI service returned HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(last_error, extra={"request_id": request_id})
                    return _fallback_response(request_id, last_error)

                raw = response.json()
                # Ensure request_id is always present in the response
                raw.setdefault("request_id", request_id)
                result = AIAnalyzeResponse.model_validate(raw)
                logger.info(
                    "AI analysis complete",
                    extra={
                        "request_id": request_id,
                        "category": result.category,
                        "requires_approval": result.requires_approval,
                        "confidence": result.confidence,
                    },
                )
                return result

            except httpx.TimeoutException as exc:
                last_error = f"AI service timeout on attempt {attempt + 1}: {exc}"
                logger.warning(last_error, extra={"request_id": request_id})
                if attempt < max_retries:
                    await asyncio.sleep(backoff)
                    continue

            except httpx.RequestError as exc:
                last_error = f"AI service connection error on attempt {attempt + 1}: {exc}"
                logger.warning(last_error, extra={"request_id": request_id})
                if attempt < max_retries:
                    await asyncio.sleep(backoff)
                    continue

    return _fallback_response(request_id, last_error)


async def health_check() -> bool:
    """Return True if AI service responds to a basic GET /health call."""
    url = f"{settings.AI_SERVICE_URL}/health"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
            response = await client.get(url)
            return response.status_code == 200
    except (httpx.RequestError, httpx.TimeoutException):
        return False
