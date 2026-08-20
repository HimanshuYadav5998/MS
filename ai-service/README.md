# AI College Request Analyzer — AI Microservice

> **Role**: AI Intelligence Layer — classifies and structures natural-language college requests into validated JSON.
> Does NOT call Notion, does NOT send emails, does NOT touch any database.
> Backend calls this over HTTP and acts on the structured output.

---

## Architecture

```
Backend / Notion Integration
        │
        │  POST /ai/analyze
        ▼
┌───────────────────────────────────────────┐
│         AI College Request Analyzer        │
│              (FastAPI, port 8001)          │
│                                           │
│  AnalyzeRequest  ──►  LLM Classifier      │
│                        │   (OpenAI API)   │
│                        │                  │
│                        ▼                  │
│                  Pydantic Validation       │
│                        │                  │
│                        ▼                  │
│               Safety Overrides (Python)   │
│                        │                  │
│  Fallback ◄────────────┘                  │
│  (Rule-Based)    if API unavailable       │
│                                           │
│  ──►  AnalyzeResponse (strict JSON)       │
└───────────────────────────────────────────┘
```

---

## Quick Start

```bash
cd ai-service

# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and add your LLM_API_KEY
# (Leave blank to run fully offline with the rule-based fallback)

# 3. Start the service
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

The service will be available at **http://localhost:8001**.
Interactive API docs: **http://localhost:8001/docs**

---

## API Reference

### `GET /health`

Returns 200 OK when the service is running.

```json
{ "status": "ok", "service": "ai-college-request-analyzer", "version": "1.0.0" }
```

---

### `POST /ai/analyze`

**Request body:**
```json
{
  "request_id":     "req_8f3a1c",
  "text":           "Sir kal ghar pe emergency hai, assignment Monday ko submit kar sakta hu?",
  "requester_name": "Arjun Sharma",
  "requester_role": "student"
}
```

`requester_role` must be one of: `student` | `faculty` | `staff` | `other`

**Response body (always valid, never malformed):**
```json
{
  "category":           "assignment_extension",
  "priority":           "urgent",
  "confidence":         0.93,
  "extracted_fields":   { "requested_extension_date": "Monday", "reason": "home emergency" },
  "summary":            "Student urgently requests permission to submit assignment on Monday due to a home emergency.",
  "recommended_action": "request_teacher_approval",
  "requires_approval":  true,
  "risk_reason":        null
}
```

---

## Supported Categories

| Category | Description |
|---|---|
| `leave_request` | Student/staff wants to be absent |
| `assignment_extension` | Wants more time for an assignment |
| `event_booking` | Wants to book a room/hall for an event |
| `maintenance_request` | Reports a broken facility or requests repair |
| `document_request` | Wants an official document (certificate, transcript, etc.) |
| `general_request` | Any other administrative query |
| `unknown` | Cannot determine intent — always routed to human review |

---

## Language Support

| Type | Examples |
|---|---|
| Plain English | `"I will not be attending college tomorrow due to illness"` |
| Hinglish (Roman) | `"Maam mujhe kal college nahi aana, ghar pe function hai"` |
| SMS-style / typos | `"sir plzzz extnsion for assignmnt i was sik lst 3 days"` |
| Mixed language | `"Sir Monday ko deadline extend kar sakte hain? Emergency hai"` |

---

## Safety & Escalation Rules

The following are **hard-coded in Python** (not just prompted to the LLM):

| Condition | Effect |
|---|---|
| `confidence < 0.70` | Force `human_review` + `requires_approval=true` |
| `category == unknown` | Force `human_review` + `requires_approval=true` |
| Missing required fields | Force `human_review` + `requires_approval=true` |
| Conflicting information (e.g., two dates) | Force `human_review`, set `risk_reason` |
| Prompt injection detected | Quarantine immediately, never reaches LLM |
| LLM output fails Pydantic validation | Safe fallback response returned |

---

## Evaluation Results Summary

| Metric | Result |
|---|---|
| Overall Category Accuracy | See `docs/eval-results.md` |
| Approval Routing Accuracy | See `docs/eval-results.md` |
| Human-Review Routing | See `docs/eval-results.md` |
| Avg Latency (LLM mode) | ~800–1200 ms |
| Avg Latency (offline mode) | < 5 ms |

Run the eval yourself:
```bash
# With service running on port 8001:
python tests/evaluate.py
# Results saved to docs/eval-results.md
```

---

## Project Structure

```
ai-service/
├── main.py                    # FastAPI app (POST /ai/analyze, GET /health)
├── schemas.py                 # Pydantic models (strict validation)
├── llm_classifier.py          # LLM-backed classifier
├── fallback_classifier.py     # Offline rule-based classifier
├── prompts/
│   └── classify_prompt.txt    # System prompt (tune without redeploying)
├── tests/
│   ├── test_cases.json        # 30 labeled test cases
│   └── evaluate.py            # Evaluation harness
├── docs/
│   └── eval-results.md        # Evaluation report
├── requirements.txt
├── .env.example
└── README.md
```

---

## Tuning the Prompt

Edit `prompts/classify_prompt.txt` directly — no code changes, no redeployment needed.
The file is loaded fresh on first request (or on service restart).

To force a reload during a running session, restart the service.

---

## Adding a New Category

1. Add one entry to `CATEGORY_RULES` in `fallback_classifier.py`
2. Add one entry to `ACTION_MAP` in `fallback_classifier.py`
3. Add one entry to `REQUIRED_FIELDS` in `fallback_classifier.py`
4. Add the new value to the `Category` enum in `schemas.py`
5. Update `prompts/classify_prompt.txt` with the new category definition and a few-shot example

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_API_KEY` | _(empty)_ | OpenAI-compatible API key. If empty, offline mode. |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | API base URL (override for local models) |
| `LLM_MODEL` | `gpt-4o-mini` | Model name |
| `LLM_TIMEOUT_SEC` | `15` | Request timeout in seconds |
| `LLM_MAX_TOKENS` | `512` | Max tokens in LLM response |
| `LLM_TEMPERATURE` | `0.1` | Lower = more deterministic |
