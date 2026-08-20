# Architecture — AI College Request Automation

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        AI College Request Automation                         │
│                                                                              │
│  ┌────────────┐    POST /webhook/request    ┌──────────────────────────────┐ │
│  │  External  │ ──────────────────────────► │       FastAPI Backend        │ │
│  │  Webhook   │                             │       (port 8000)            │ │
│  │  Caller    │ ◄────────────────────────── │    app/main.py               │ │
│  └────────────┘    202 Accepted + req_id    └──────────────┬───────────────┘ │
│                                                            │                 │
│                                             ┌──────────────▼───────────────┐ │
│                                             │      orchestrator.py         │ │
│                                             │   THE ENGINE (state machine) │ │
│                                             │                              │ │
│                                             │  Step 4: DB insert RECEIVED  │ │
│                                             │  Step 5: Notion create page  │ │
│                                             │  Step 6: AI analyze          │ │
│                                             │  Step 7: Notion update page  │ │
│                                             │  Step 8: PENDING_APPROVAL    │ │
│                                             │  Step 9: Background poller   │ │
│                                             │  Step 10: Execute action     │ │
│                                             │  Step 11: Reject             │ │
│                                             │  Step 12: Run Log (every tx) │ │
│                                             └──┬──────────┬────────────────┘ │
│                                                │          │                  │
│              ┌─────────────────────────────────▼──┐   ┌───▼────────────────┐ │
│              │         ai_client.py               │   │  notion_service.py │ │
│              │  POST http://localhost:8001/analyze │   │  (Member 2)        │ │
│              │  • 5s timeout                      │   │                    │ │
│              │  • 2 retries + exponential backoff  │   │  create_request_   │ │
│              │  • fallback on full failure         │   │  page()            │ │
│              └────────────────────────────────────┘   │  create_approval_  │ │
│                                                        │  page()            │ │
│              ┌─────────────────────────────────────┐   │  get_human_        │ │
│              │  AI Classification Microservice     │   │  decision()        │ │
│              │  (Member 3, port 8001)              │   │  create_run_log()  │ │
│              │  POST /ai/analyze → AIAnalyzeRsp    │   └────────────────────┘ │
│              └─────────────────────────────────────┘                          │
│                                                        ┌───────────────────┐  │
│              ┌─────────────────────────────────────┐   │  Notion (SaaS)    │  │
│              │  action_service.py (Member 4)       │   │  • Requests DB    │  │
│              │  execute_action(type, payload)      │   │  • Approvals DB   │  │
│              │  → send_email / calendar / etc.     │   │  • Run Log DB     │  │
│              └─────────────────────────────────────┘   └───────────────────┘  │
│                                                                                │
│  ┌────────────────────────────────────────────────────────────────────────┐   │
│  │  SQLite DB (college_requests.db)                                       │   │
│  │  • college_requests  (full state per request)                          │   │
│  │  • run_logs          (append-only event log)                           │   │
│  │  • idempotency_records (5-min dedup window)                            │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Request Lifecycle

```
Webhook POST
    │
    ▼
[RECEIVED] ──── DB insert, Run Log
    │
    ▼
[PROCESSING] ── Notion create_request_page, AI analyze, Notion update
    │
    ▼
[PENDING_APPROVAL] ── Notion create_approval_page, background poller starts
    │
    ├── Human approves (Notion or POST /approval/{id})
    │       │
    │       ▼
    │   [APPROVED] → [EXECUTING] → [COMPLETED] or [FAILED]
    │
    ├── Human rejects (Notion or POST /reject/{id})
    │       │
    │       ▼
    │   [REJECTED]
    │
    ├── Manual override (POST /override/{id})
    │       │
    │       ▼
    │   [OVERRIDDEN] → [EXECUTING] → [COMPLETED] or [FAILED]
    │
    └── Timeout (no decision in 1 hour)
            │
            ▼
        [ESCALATED]
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| All requests require approval | Hackathon safety-first policy |
| DB + Notion dual logging | Resilience — DB log survives Notion outages |
| No retries on action failure | Avoids duplicate emails/actions on partial failures |
| Idempotency via SHA-256 fingerprint | Prevents duplicate processing on webhook retries |
| asyncio.wait_for on all external calls | Hard 10s cap — no request hangs forever |
| Fallback AIAnalyzeResponse on AI failure | AI outage never crashes a request |

## Component Ownership

| Component | Owner | Language |
|-----------|-------|----------|
| `backend/` (orchestrator, API) | Member 1 | Python/FastAPI |
| `notion/notion_service.py` | Member 2 | Python |
| AI Microservice (port 8001) | Member 3 | TBD |
| `integrations/action_service.py` | Member 4 | Python |
