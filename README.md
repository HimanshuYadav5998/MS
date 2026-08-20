# AI College Request Automation

> **Hackathon project** — Automates college administrative requests using AI classification, human-in-the-loop approval via Notion, and reliable external action execution.

---

## Architecture

```
Student/Staff
     │  webhook POST /webhook/request
     ▼
┌─────────────────────────────────────────────────────────┐
│  Backend (FastAPI · port 8000)  ← Member 1              │
│  orchestrator.py: the state machine                     │
│  ┌──────────────┐  ┌──────────────────┐                 │
│  │ ai_client    │  │ notion_service   │                 │
│  │ (Member 2)   │  │ (Member 3)       │                 │
│  └──────────────┘  └──────────────────┘                 │
│  ┌──────────────────────────────────────┐               │
│  │ action_service (Member 4)            │               │
│  │  MockEmailAdapter / MailtrapAdapter  │               │
│  └──────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
     │                              │
     ▼                              ▼
┌─────────────┐              ┌──────────────────┐
│ AI Service  │              │  Notion Workspace │
│ port 8001   │              │  (human control  │
│ Member 2    │              │   panel)         │
└─────────────┘              └──────────────────┘
```

**Request lifecycle:**
```
RECEIVED → PROCESSING → PENDING_APPROVAL → APPROVED/REJECTED/OVERRIDDEN
         → EXECUTING → COMPLETED/FAILED
         (any stage can escalate to) → ESCALATED
```

---

## Folder Structure

```
/project
├── backend/          ← Member 1 (FastAPI app, orchestrator, DB)
├── ai-service/       ← Member 2 (classification microservice)
├── notion/           ← Member 3 (notion_service.py + workspace setup)
├── integrations/     ← Member 4 (action_service.py)
│   ├── action_service.py    # email/calendar adapter engine
│   ├── .env.example         # all env vars documented
│   └── logs/                # action log + JSONL audit trail
├── tests/
│   └── test_e2e.py          # 6 E2E + offline unit tests
├── demo_data/
│   └── sample_requests.json # 5 annotated demo requests
├── scripts/
│   ├── health_check.py      # pre-demo service ping
│   ├── reset_demo.py        # clean-slate reset
│   └── submit_demo.py       # stage-safe request submitter
├── docs/
│   ├── demo-script.md       # step-by-step demo narration
│   └── troubleshooting.md   # every failure + fix
└── PROJECT.md               # master build kit (read first)
```

---

## Setup (5 minutes)

### Prerequisites
- Python 3.11+
- All 4 members' code merged
- A [Notion integration](https://notion.so/my-integrations) created
- (Optional) [Mailtrap](https://mailtrap.io) account for real sandbox email

### 1. Install dependencies

```bash
# Backend (Member 1)
cd backend && pip install -r requirements.txt && cd ..

# AI Service (Member 2)
cd ai-service && pip install -r requirements.txt && cd ..

# Notion (Member 3)
cd notion && pip install -r requirements.txt && cd ..

# Integrations / test deps (Member 4)
pip install python-dotenv requests pytest
```

### 2. Configure environment

```bash
# Copy the template
cp integrations/.env.example integrations/.env

# Edit integrations/.env — fill in:
#   NOTION_API_KEY=secret_...
#   NOTION_REQUESTS_DB_ID=...
#   NOTION_RUNLOG_DB_ID=...
#   NOTION_APPROVALS_DB_ID=...
#   EMAIL_PROVIDER=mock          ← keep mock for demos; set mailtrap for real email
```

Also copy into backend, ai-service, and notion directories as each needs their own `.env`.

### 3. Create the Notion workspace

```bash
python notion/setup_workspace.py
```

This creates the 3 databases and home page from scratch, programmatically. Copy the IDs it prints into your `.env` files.

### 4. Start services

```bash
# Terminal 1 — Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 — AI Service
cd ai-service
uvicorn app.main:app --reload --port 8001
```

### 5. Verify everything is running

```bash
python scripts/health_check.py
```

All rows should show `✓ OK`.

---

## Running Tests

```bash
# Fast offline tests (no services needed — run these first, always)
SKIP_LIVE_SERVICES=1 EMAIL_PROVIDER=mock pytest tests/test_e2e.py -v -k "not TestEndToEnd"

# Full E2E tests (requires all services running + Notion configured)
pytest tests/test_e2e.py -v
```

Expected offline test output:
```
tests/test_e2e.py::TestActionServiceUnit::test_mock_email_adapter_returns_success   PASSED
tests/test_e2e.py::TestActionServiceUnit::test_mock_calendar_adapter_returns_success PASSED
tests/test_e2e.py::TestActionServiceUnit::test_execute_action_dispatches_email       PASSED
...
tests/test_e2e.py::TestActionServiceIntegration::test_broken_provider_returns_failure_not_exception PASSED
```

---

## Running the Demo

```bash
# 1. Reset to clean state
python scripts/reset_demo.py

# 2. Pre-flight check
python scripts/health_check.py

# 3. Submit demo requests (on stage)
python scripts/submit_demo.py --id 1    # Leave request (English)
python scripts/submit_demo.py --id 2    # Assignment extension (Hinglish ★)
python scripts/submit_demo.py --id 5    # Bad input (graceful escalation ★)
```

Full narrated demo guide: [`docs/demo-script.md`](docs/demo-script.md)

---

## Email Provider Configuration

| `EMAIL_PROVIDER` | Behavior | Network needed |
|------------------|----------|----------------|
| `mock` (default) | Logs to console + `integrations/logs/actions.jsonl` | ❌ None |
| `mailtrap`       | Sends to Mailtrap sandbox SMTP inbox | ✅ WiFi |
| `broken`         | Always fails (Test 6 only!) | ❌ None |

**Recommendation:** Use `mock` for the demo — the action log is your proof it fired.  
Layer in `mailtrap` during rehearsals when WiFi is reliable.

---

## Adding a New Action Type

1. Create a new adapter class in `integrations/action_service.py` implementing `BaseEmailAdapter` or `BaseCalendarAdapter`
2. Add the handler to `_ACTION_HANDLERS` dict in `execute_action`
3. Done — no other files need to change

---

## Team Contacts

| Role | Owner | Folder |
|------|-------|--------|
| Backend / Integration Lead | Member 1 | `backend/` |
| AI Engineer | Member 2 | `ai-service/` |
| Notion Engineer | Member 3 | `notion/` |
| Integrations / QA / Demo | Member 4 | `integrations/`, `tests/`, `scripts/` |
