"""
main.py — FastAPI application for AI College Request Automation.

Exposes:
  POST /ai/analyze   — Classify and structure a college request
  GET  /health       — Health check

Port: 8001
"""

from __future__ import annotations

# Load .env before any module that reads env vars
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars can be set directly

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from llm_classifier import llm_classify
from schemas import AnalyzeRequest, AnalyzeResponse, FALLBACK_RESPONSE

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("ai_service")


# ──────────────────────────────────────────────────────────────────────────────
# Lifespan  (startup / shutdown hooks)
# ──────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("AI Service starting up on port 8001")
    yield
    logger.info("AI Service shutting down")


# ──────────────────────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI College Request Analyzer",
    description=(
        "Classifies and structures natural-language college administrative "
        "requests into strict JSON. Supports English, Hinglish, and typo-heavy input."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────────
# Middleware: request latency logging
# ──────────────────────────────────────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed  = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s → %s  [%.1f ms]",
        request.method, request.url.path, response.status_code, elapsed
    )
    return response


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
async def health_check():
    """Returns 200 OK when the service is running."""
    return {"status": "ok", "service": "ai-college-request-analyzer", "version": "1.0.0"}


@app.post(
    "/ai/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    tags=["analysis"],
    summary="Analyze and classify a college request",
    response_description="Structured classification of the request",
)
async def analyze_request(body: AnalyzeRequest) -> AnalyzeResponse:
    """
    Accepts a raw natural-language college request and returns a validated,
    structured JSON response that the backend can trust blindly.

    - Supports English and Hinglish (Roman-script Hindi + English)
    - Handles typos, SMS abbreviations, and mixed-language input
    - Always returns a valid AnalyzeResponse — never raises 500 due to AI error
    """
    logger.info(
        "Analyzing request_id=%s from %s (%s): %.80s…",
        body.request_id,
        body.requester_name,
        body.requester_role.value,
        body.text,
    )

    try:
        result: AnalyzeResponse = await llm_classify(
            text           = body.text,
            requester_name = body.requester_name,
            requester_role = body.requester_role.value,
            request_id     = body.request_id,
        )
    except Exception as exc:  # noqa: BLE001
        # Absolute last resort — this path should never be reached because
        # llm_classify already catches everything internally, but just in case.
        logger.exception(
            "Unhandled exception for request_id=%s: %s — returning fallback",
            body.request_id, exc
        )
        result = FALLBACK_RESPONSE.model_copy()

    logger.info(
        "request_id=%s → category=%s confidence=%.2f requires_approval=%s",
        body.request_id,
        result.category.value,
        result.confidence,
        result.requires_approval,
    )
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Exception handlers
# ──────────────────────────────────────────────────────────────────────────────

@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Request validation failed",
            "details": str(exc),
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info",
    )
