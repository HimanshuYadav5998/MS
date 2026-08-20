# AI College Request Automation — Backend

> **Role:** Orchestrator / Integration Lead (Backend)
> **Owner:** Member 1
> **Stack:** Python 3.11, FastAPI, SQLite (SQLAlchemy async), httpx, Pydantic v2

---

## 5-Minute Setup

### Prerequisites
- Python 3.11+
- (Optional) Docker + Docker Compose

### Local Dev Setup

```bash
# 1. Clone and enter the project
cd project/backend

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — fill in NOTION_API_KEY, NOTION_*_DB_ID

# 5. Run the server
uvicorn app.main:app --reload --port 8000
```

The API is now live at **http://localhost:8000**.
Interactive docs: **http://localhost:8000/docs**

---

### Docker Compose (Recommended for Demo)

```bash
cd project
cp backend/.env.example backend/.env
# Edit backend/.env with real Notion credentials

docker-compose up --build
```

This starts:
- **Backend** on port 8000
- **AI Service stub** on port 8001 (replace with real service image)

---

## Running Tests

```bash
cd project/backend
pytest tests/ -v
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/health` | Server health + AI service reachability |
| `POST` | `/webhook/request` | Submit a new college request |
| `GET`  | `/requests/{id}` | Full state + AI output for a request |
| `GET`  | `/requests/{id}/logs` | All run log entries for a request |
| `POST` | `/approval/{id}` | Manually approve a pending request |
| `POST` | `/reject/{id}` | Manually reject a pending request |
| `POST` | `/override/{id}` | Override with `{"decision": "approved"\|"rejected"}` |
| `POST` | `/actions/{id}/execute` | Re-trigger execution (demo recovery) |

Full interactive docs: `http://localhost:8000/docs`

---

## Architecture

```
                          ┌─────────────────────────────────────┐
  Webhook POST ──────────►│           orchestrator.py            │
                          │  (THE ENGINE — sole action executor) │
                          └──────────┬──────────┬───────────────┘
                                     │          │
              ┌──────────────────────▼──┐   ┌───▼────────────────────┐
              │  ai_client.py (httpx)   │   │  notion_service.py      │
              │  POST /ai/analyze       │   │  (human-facing panel)   │
              │  5s timeout, 2 retries  │   │  create/update pages    │
              └─────────────────────────┘   │  get_human_decision     │
                                            └─────────────────────────┘
                                                       │
                                            ┌──────────▼──────────────┐
                                            │   action_service.py     │
                                            │   execute_action()      │
                                            │   (email / calendar)    │
                                            └─────────────────────────┘
```

---

## State Machine

```
RECEIVED → PROCESSING → PENDING_APPROVAL
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
          APPROVED        REJECTED        ESCALATED
              │
              ▼
          EXECUTING
              │
      ┌───────┴───────┐
      ▼               ▼
  COMPLETED        FAILED
```

Additional: `OVERRIDDEN` (manual override before APPROVED/REJECTED)

---

## Run Log

Every state transition generates a run log entry visible in:
1. Local DB (`run_logs` table)
2. Notion Run Log database

The full story of any request can be reconstructed from the run log alone.

---

## Team Contracts

### notion_service.py (Member 2)
Functions the backend calls — see `/project/notion/notion_service.py` for signatures:
- `create_request_page(...)` → `str | None` (page_id)
- `update_request_page(...)`
- `create_approval_page(...)` → `str | None` (page_id)
- `get_human_decision(...)` → `"approved" | "rejected" | None`
- `create_run_log(...)`

### action_service.py (Member 4)
- `execute_action(action_type: str, payload: dict)` → `{"success": bool, "action_id": str, ...}`

### AI Service (Member 3)
- `POST http://localhost:8001/ai/analyze`
- Body: `{"request_id": str, "text": str}`
- Response: see `AIAnalyzeResponse` in `app/schemas.py`

---

## Swapping to PostgreSQL

Change one line in `.env`:
```
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/college_requests
```
No code changes required.

---

## Database Schema

See `docs/schema.md` for the full table definitions.
