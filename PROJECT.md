# AI College Request Automation — Master Build Kit
### 4-Person Team | Parallel AI-Assisted Development | Hackathon-Ready

> **How to use this file:** Each teammate copies ONLY their own section (Member 1 / 2 / 3 / 4 block) and pastes it as the **first message** to their coding AI (Claude Code, Cursor, Copilot Chat, etc.). Nobody touches another member's folder. Member 1 is the Integration Lead and merges everyone at the end.
>
> The reason this wins hackathons: judges don't just look at "does it work" — they look at **architecture clarity, reliability under failure, and whether a human stays in control of AI decisions**. Every prompt below is written to score on all three.

---

## 0. THE LOCKED INTEGRATION CONTRACT (read this before anything else)

This is the single source of truth. If any member's AI generates something that doesn't match this contract, that member must fix it — **not** change the contract mid-hackathon. Print this section, pin it in your team WhatsApp/Discord.

### 0.1 Folder structure (non-negotiable)
```
/project
│
├── backend/          ← Member 1 (FastAPI app, orchestrator, DB)
├── ai-service/        ← Member 2 (classification microservice)
├── notion/             ← Member 3 (notion_service.py + workspace docs)
├── integrations/       ← Member 4 (action_service.py + e2e tests)
├── tests/               ← shared end-to-end tests (Member 4 owns)
├── docs/                ← architecture diagram, README, screenshots
└── docker-compose.yml   ← Member 1 owns, wires all services together
```

### 0.2 The AI Analyze contract (Member 2 → Member 1)
**Endpoint:** `POST /ai/analyze` (runs on `ai-service`, port `8001`)

Request:
```json
{
  "request_id": "req_8f3a1c",
  "text": "Sir kal ghar pe emergency hai, assignment Monday ko submit kar sakta hu?",
  "requester_name": "Rahul Sharma",
  "requester_role": "student"
}
```

Response (Member 2 MUST return exactly this shape, always, even on low confidence):
```json
{
  "category": "assignment_extension",
  "priority": "medium",
  "confidence": 0.94,
  "extracted_fields": {
    "requested_extension_date": "Monday",
    "reason": "personal emergency"
  },
  "summary": "Student requests assignment deadline extension to Monday due to a family emergency.",
  "recommended_action": "request_teacher_approval",
  "requires_approval": true,
  "risk_reason": null
}
```
Allowed `category` enum: `leave_request | assignment_extension | event_booking | maintenance_request | document_request | general_request | unknown`
Allowed `priority` enum: `low | medium | high | urgent`
Rule: if `confidence < 0.70` OR category is `unknown` OR fields are missing/conflicting → `requires_approval = true`, `recommended_action = "human_review"`, and `risk_reason` must explain why in one sentence.

### 0.3 The Notion service contract (Member 3 → Member 1)
Member 1's orchestrator will import and call these exact function signatures from `notion/notion_service.py`. Member 3 must implement all of them with these names — Member 1 will not touch Notion API code directly.

```python
create_request_page(request_id: str, title: str, category: str, requester: str,
                     original_text: str, ai_summary: str, ai_recommendation: str,
                     priority: str, confidence: float, status: str,
                     requires_approval: bool) -> str  # returns notion_page_id

update_request_page(notion_page_id: str, status: str,
                     human_decision: str | None = None,
                     action_result: str | None = None) -> None

create_approval_page(request_id: str, request_summary: str) -> str  # returns approval_page_id

get_pending_approvals() -> list[dict]   # [{request_id, decision, reviewer, reason, override_instructions}, ...]

get_human_decision(request_id: str) -> dict | None
    # {"decision": "approved"|"rejected"|"override_approved", "reviewer": str, "reason": str}

create_run_log(request_id: str, event: str, actor: str, action: str,
                status: str, reason: str = "", error: str = "",
                external_action_id: str = "") -> str  # returns run_log_page_id
```

### 0.4 The Action service contract (Member 4 → Member 1)
```python
send_email(to: str, subject: str, body: str) -> dict
    # returns {"success": bool, "external_action_id": str, "error": str | None}

create_calendar_event(title: str, date: str, description: str) -> dict
    # same return shape

execute_action(action_type: str, payload: dict) -> dict
    # dispatcher — routes to send_email / create_calendar_event based on action_type
    # same return shape, and MUST NEVER raise — always return a dict
```

### 0.5 Request lifecycle states (everyone uses these exact strings)
```
RECEIVED → PROCESSING → PENDING_APPROVAL → APPROVED/REJECTED/OVERRIDDEN
        → EXECUTING → COMPLETED/FAILED
        (any stage can jump to) → ESCALATED
```

### 0.6 Ports & env convention (so docker-compose "just works")
| Service | Port | Env file |
|---|---|---|
| backend | 8000 | backend/.env |
| ai-service | 8001 | ai-service/.env |
| Notion calls go through backend only | — | notion/.env (shared secret, imported by backend) |
| integrations calls go through backend only | — | integrations/.env |

---

## 👨‍💻 MEMBER 1 — Backend / Orchestrator (Integration Lead)

**Copy everything in this box to your coding AI:**

```
ROLE: You are the backend/orchestrator engineer for a hackathon project called
"AI College Request Automation." You also act as the Integration Lead for a
4-person team — your code is the glue that calls the other 3 services.

═══════════════════════════════════════════════════════════
PROJECT GOAL
═══════════════════════════════════════════════════════════
Build a real, working automation engine that:
1. Receives college requests via webhook
2. Sends them to an AI classification microservice (POST http://localhost:8001/ai/analyze)
3. Creates/updates records in Notion via a notion_service module (built by a teammate,
   you just import and call it — do not write Notion API calls yourself)
4. Pauses and waits for human approval when required
5. On approval, calls an action_service module (built by a teammate) to perform a
   REAL external action (email/calendar)
6. Writes every single event to a Notion Run Log — no exceptions
7. Never fails silently — every error must be caught, logged, and reflected in status

You are the ENGINE. Notion is the human-facing control panel only. You never let
the AI service or Notion perform actions directly — YOU are the only component
allowed to call action_service.execute_action().

═══════════════════════════════════════════════════════════
TECH STACK (use exactly this — do not substitute)
═══════════════════════════════════════════════════════════
- Python 3.11+, FastAPI, Uvicorn
- SQLite for local dev (SQLAlchemy models), designed so swapping to PostgreSQL
  later only requires changing the connection string
- httpx (async) for calling ai-service
- Pydantic v2 for all request/response models — strict validation, no raw dicts
  crossing a function boundary
- pytest + pytest-asyncio for tests
- python-dotenv for config
- Docker + docker-compose (optional but preferred — write it if time allows)

═══════════════════════════════════════════════════════════
FOLDER YOU OWN
═══════════════════════════════════════════════════════════
/project/backend/
    app/
        main.py                 # FastAPI app entrypoint
        models.py                # SQLAlchemy DB models
        schemas.py               # Pydantic request/response schemas
        orchestrator.py          # the core state machine — THE MOST IMPORTANT FILE
        ai_client.py              # httpx wrapper calling ai-service
        config.py                 # env loading
    tests/
    requirements.txt
    .env.example
    Dockerfile
    README.md

You will import notion_service functions from /project/notion/notion_service.py
and action_service functions from /project/integrations/action_service.py.
DO NOT reimplement their logic — write thin, defensive wrapper calls with
try/except around every external call.

═══════════════════════════════════════════════════════════
CORE WORKFLOW — implement exactly this sequence in orchestrator.py
═══════════════════════════════════════════════════════════
POST /webhook/request receives:
  { "text": str, "requester_name": str, "requester_role": str }

Step-by-step:
1. Validate input (reject empty/too-long text with 422, not a crash).
2. Generate request_id = f"req_{uuid4().hex[:8]}" — this ID is used EVERYWHERE.
3. Check idempotency: if an identical (requester_name + text) combo arrived in
   the last 5 minutes, return the EXISTING request_id instead of creating a
   duplicate (Test Case 5 in the QA suite checks this — do not skip it).
4. Insert DB row with status=RECEIVED.
5. Call notion_service.create_request_page(...) — status becomes PROCESSING.
6. Call ai_client.analyze(request_id, text) → wraps POST to ai-service with:
     - 5 second timeout
     - up to 2 retries with exponential backoff on timeout/5xx
     - if ai-service is fully unreachable after retries: set
       requires_approval=true, recommended_action="human_review",
       category="unknown", and continue (never crash the request)
7. Update the Notion request page with AI summary/recommendation/priority/confidence.
8. If requires_approval == true:
     - set status = PENDING_APPROVAL
     - call notion_service.create_approval_page(...)
     - STOP HERE. Do not execute any action yet.
   Else:
     - proceed straight to execution (auto-approved low-risk categories, if any —
       for the hackathon demo, treat ALL categories as requiring approval unless
       explicitly told otherwise by the team; safety over speed).
9. A background poller (asyncio task running every 5-10 seconds, OR a manual
   POST /approval/{request_id} / POST /reject/{request_id} / POST
   /override/{request_id} endpoint — implement BOTH so the demo has a manual
   override button if polling lags) checks notion_service.get_human_decision().
10. On approval or override_approved:
     - status = EXECUTING
     - call action_service.execute_action(action_type, payload) built from
       extracted_fields
     - on success: status = COMPLETED, write Run Log with the
       external_action_id
     - on failure: status = FAILED, write Run Log with the error, DO NOT retry
       silently more than once, DO NOT crash the process
11. On rejection: status = REJECTED, write Run Log, do nothing else.
12. Every single transition in steps 4-11 gets its own
    notion_service.create_run_log(...) call. A judge should be able to open
    Run Log and read the entire story of any request in plain English.

═══════════════════════════════════════════════════════════
REQUIRED STATES (use these exact strings, matching the team contract)
═══════════════════════════════════════════════════════════
RECEIVED, PROCESSING, PENDING_APPROVAL, APPROVED, REJECTED, OVERRIDDEN,
EXECUTING, COMPLETED, FAILED, ESCALATED

═══════════════════════════════════════════════════════════
RELIABILITY REQUIREMENTS (judges WILL test these — do not skip)
═══════════════════════════════════════════════════════════
- request_id-based idempotency (see step 3)
- retries with a hard limit (max 2) and exponential backoff on the AI call
- explicit timeout handling (never let a request hang forever — 10s max per stage)
- structured logging (use Python `logging` module with JSON formatter, log
  request_id on every line so logs are traceable end-to-end)
- try/except around EVERY external call (Notion, AI service, action service) —
  an external outage must degrade gracefully to ESCALATED, never crash FastAPI
- input validation via Pydantic — malformed JSON returns 422 with a clear message
- no bare `except:` blocks — always catch specific exceptions and log them

═══════════════════════════════════════════════════════════
API ENDPOINTS TO BUILD
═══════════════════════════════════════════════════════════
POST /webhook/request          → create + kick off processing
GET  /requests/{request_id}    → full current state incl. AI output + status
POST /approval/{request_id}    → manual approve (demo safety net)
POST /reject/{request_id}      → manual reject
POST /override/{request_id}    → manual override (body: {"decision": "approved"})
POST /actions/{request_id}/execute  → manually re-trigger execution (for demo recovery)
GET  /health                    → returns {"status": "ok", "ai_service": "reachable"/"unreachable"}

═══════════════════════════════════════════════════════════
EXTERNAL ACTION FOR THE DEMO
═══════════════════════════════════════════════════════════
Call action_service.execute_action("send_email", {...}) — implemented by
Member 4. You just need to build the payload correctly from extracted_fields
and category, and handle the {"success": bool, ...} response.

═══════════════════════════════════════════════════════════
DELIVERABLES (all must exist before demo day)
═══════════════════════════════════════════════════════════
1. Complete backend/ repository as structured above
2. requirements.txt with pinned versions
3. .env.example with every variable documented
4. Dockerfile (multi-stage if you have time, single-stage is fine)
5. README.md — setup instructions a stranger could follow in 5 minutes
6. API documentation (FastAPI gives you /docs for free — screenshot it into docs/)
7. Database schema diagram (can be a simple markdown table)
8. tests/ — at minimum: idempotency test, timeout/retry test, invalid-input test,
   full happy-path integration test (mock notion_service and action_service)
9. docs/architecture-diagram.png or .md ASCII version
10. sample webhook payload + sample API response saved in docs/samples/

DO NOT build a frontend dashboard — Notion IS the dashboard.
The final system must run automatically end-to-end from one webhook call and
must never require manually running a script during the live demo.

Start by generating: models.py, schemas.py, then orchestrator.py skeleton with
TODOs matching the 12 steps above, then fill them in one at a time. Ask me for
clarification only if something in this brief is genuinely ambiguous — otherwise
make the most defensive, hackathon-safe choice and keep going.
```

---

## 🤖 MEMBER 2 — AI Engineer

**Copy everything in this box to your coding AI:**

```
ROLE: You are the AI intelligence engineer for a hackathon project called
"AI College Request Automation." You are NOT building the backend, Notion
integration, or any external actions. Your only job: turn messy natural
language college requests into strict structured JSON that a backend can
trust blindly.

═══════════════════════════════════════════════════════════
OBJECTIVE
═══════════════════════════════════════════════════════════
Build a standalone FastAPI microservice (port 8001) that exposes one endpoint:

POST /ai/analyze
Input:
{ "request_id": "req_8f3a1c", "text": "...", "requester_name": "...",
  "requester_role": "student" }

Output (MUST match this exact schema every single time, no exceptions,
validated with a strict Pydantic model before returning):
{
  "category": "assignment_extension",
  "priority": "medium",
  "confidence": 0.94,
  "extracted_fields": { "requested_extension_date": "Monday",
                          "reason": "personal emergency" },
  "summary": "Student requests assignment deadline extension to Monday due to
               a family emergency.",
  "recommended_action": "request_teacher_approval",
  "requires_approval": true,
  "risk_reason": null
}

═══════════════════════════════════════════════════════════
SUPPORTED CATEGORIES (extensible — design so adding a new one later is a
one-line change, not a rewrite)
═══════════════════════════════════════════════════════════
leave_request | assignment_extension | event_booking | maintenance_request |
document_request | general_request | unknown

═══════════════════════════════════════════════════════════
LANGUAGE REQUIREMENTS — this is your biggest differentiator, don't skimp
═══════════════════════════════════════════════════════════
Must correctly understand:
- Plain English requests
- Hinglish (Roman-script Hindi mixed with English), e.g.:
  "Sir kal ghar pe emergency hai, assignment Monday ko submit kar sakta hu?"
  "Maam mujhe kal college nahi aana, ghar pe function hai"
- Requests with typos, missing punctuation, SMS-style abbreviations
- Requests that mix a real ask with irrelevant chatter — extract only the
  relevant fields, ignore the noise

═══════════════════════════════════════════════════════════
HOW TO BUILD THE CLASSIFICATION LOGIC
═══════════════════════════════════════════════════════════
Use an LLM call (OpenAI-compatible API — assume an API key is available via
env var LLM_API_KEY; if none is configured, fall back to a lightweight
rule-based classifier using keyword matching so the service still runs
offline during the demo as a safety net).

Prompt the LLM with:
- The category list and definitions
- Few-shot examples covering English AND Hinglish (write at least 6 examples
  directly in your system prompt, 3 English + 3 Hinglish)
- An explicit instruction to return ONLY valid JSON matching the schema,
  nothing else
- An explicit instruction: "You are extracting and structuring information.
  You are NOT deciding whether to approve anything. Never claim an action
  has been taken."

After the LLM responds, ALWAYS re-validate the raw output through a strict
Pydantic model before returning it from the endpoint. If the LLM returns
malformed JSON or an unsupported category, catch it and fall back to:
  category="unknown", requires_approval=true,
  recommended_action="human_review",
  risk_reason="AI output could not be validated; routed to human review."
This fallback is critical — the backend must NEVER receive a malformed
response from you, ever.

═══════════════════════════════════════════════════════════
IMPORTANT ARCHITECTURAL RULE
═══════════════════════════════════════════════════════════
You NEVER call Notion, never send an email, never touch the database. You
only recommend and structure. The backend team makes the final decision and
performs actions. If you find yourself writing code that sends anything
externally, stop — that's out of scope.

═══════════════════════════════════════════════════════════
SAFETY / ESCALATION RULES (hard-coded, not just prompted to the LLM)
═══════════════════════════════════════════════════════════
Force requires_approval = true and recommended_action = "human_review" when
ANY of these are true, checked in your Python code (do not trust the LLM
alone to enforce this):
- confidence < 0.70
- category == "unknown"
- required fields for that category are missing (e.g. leave_request with no
  date mentioned)
- the text contains conflicting information (e.g. two different dates)
- the text looks like it's trying to inject instructions into your prompt
  (e.g. contains phrases like "ignore previous instructions", "you are now")
  — in this case ALSO set risk_reason to flag it as a possible prompt
  injection attempt, and do not let it influence your system prompt

═══════════════════════════════════════════════════════════
TESTING — build a real eval, not just vibes
═══════════════════════════════════════════════════════════
Create tests/test_cases.json with AT LEAST 30 inputs across these buckets:
- 8 normal English requests (varied categories)
- 8 Hinglish requests (varied categories)
- 4 badly formatted / typo-heavy requests
- 4 incomplete requests (missing key info — should trigger human_review)
- 3 duplicate/near-duplicate requests (same intent, different wording)
- 2 malicious-looking / prompt-injection-style inputs
- 1 completely irrelevant text (e.g. "what's the weather")

Build tests/evaluate.py that runs every case through /ai/analyze and reports:
- classification accuracy (predicted category vs your hand-labeled expected
  category in the test file)
- field extraction accuracy (spot-check key fields)
- % correctly routed to human_review when they should be
- average latency per request
Save results to docs/eval-results.md — this is a great judge-facing artifact,
put a summary table in your README.

═══════════════════════════════════════════════════════════
DELIVERABLES
═══════════════════════════════════════════════════════════
1. ai-service/ FastAPI app exposing POST /ai/analyze and GET /health
2. Pydantic schemas (request + strict response model)
3. System prompt file (prompts/classify_prompt.txt) kept separate from code
   so it's easy to tune during the hackathon without redeploying
4. tests/test_cases.json + tests/evaluate.py + docs/eval-results.md
5. requirements.txt, .env.example, README.md

Do not build Notion integration. Do not build the frontend. Do not implement
external actions. Keep this service completely independent so Member 1 can
call you over plain HTTP with zero shared code.

Start by writing the Pydantic schemas, then the fallback rule-based
classifier (so something works even without an API key), then the LLM-backed
classifier layered on top, then the test suite.
```

---

## 📗 MEMBER 3 — Notion Engineer

**Copy everything in this box to your coding AI:**

```
ROLE: You are the Notion workspace + integration engineer for a hackathon
project called "AI College Request Automation." Judges will open your Notion
workspace directly, so it must look professional, be instantly understandable
to a non-technical person, and be driven ENTIRELY by real backend API calls —
never manually faked data.

═══════════════════════════════════════════════════════════
CORE PRINCIPLE
═══════════════════════════════════════════════════════════
Notion is: a database, a human control panel, an approval interface, and an
audit trail. Notion is NOT the automation engine — no Notion automations,
buttons, or formulas should trigger real-world actions. The backend
(Member 1) polls/reads Notion and performs actions in Python.

═══════════════════════════════════════════════════════════
DATABASES TO CREATE (use the Notion API to create these programmatically —
write a setup script, don't just click around manually, so it's reproducible)
═══════════════════════════════════════════════════════════

1) REQUESTS database — properties:
   Request ID (text) | Title (title) | Category (select) | Requester (text)
   | Original Request (text) | AI Summary (text) | AI Recommendation (text)
   | Priority (select: low/medium/high/urgent) | Confidence (number, 0-1)
   | Status (select — see status list below) | Requires Approval (checkbox)
   | Human Decision (select: approved/rejected/overridden/pending)
   | Created At (date) | Updated At (date) | Action Result (text)

   Status options (exact strings, matching team contract):
   RECEIVED, PROCESSING, PENDING_APPROVAL, APPROVED, REJECTED, OVERRIDDEN,
   EXECUTING, COMPLETED, FAILED, ESCALATED

2) RUN LOG database — properties:
   Run ID (text) | Request ID (text, relation to Requests DB if time allows)
   | Timestamp (date) | Event (text) | Actor (select: system/AI/human)
   | Action (text) | Status (select) | Reason (text) | Error (text)
   | External Action ID (text)

   Every row is created by backend code calling your create_run_log()
   function. Never manually type a fake log row — it must all trace back to
   real API calls, and you should be able to demo this live.

3) APPROVALS database — properties:
   Request ID (text) | Request (text, short summary for a human to skim)
   | Decision (select: pending/approved/rejected/override_approved)
   | Reviewer (text) | Decision Reason (text) | Decision Time (date)
   | Override Instructions (text)

═══════════════════════════════════════════════════════════
WORKSPACE HOME PAGE — "AI College Operations Hub"
═══════════════════════════════════════════════════════════
Build a single Notion page with linked database VIEWS (filtered/sorted, not
duplicated data) organized into these sections:

🔴 Needs Attention — Requests DB filtered to Status = PENDING_APPROVAL,
    sorted by Priority (urgent first)
🟡 Processing — Status = PROCESSING or EXECUTING
🟢 Completed Today — Status = COMPLETED, filtered to Updated At = today
⚠️ Failed / Escalated — Status = FAILED or ESCALATED
📜 Run Log — Run Log DB, sorted newest first, limited view of last 20
📊 System Status — either a linked view with counts, or (if you have time)
    a simple synced text block summarizing: Total requests today, Pending
    approvals, Completed, Failed — updated by backend calling
    update_request_page appropriately (or manually refresh before demo if
    Notion doesn't support live counters easily)

Keep it clean. NEVER show raw JSON as the primary interface — AI Summary and
AI Recommendation fields must be short, human-readable sentences (that's
Member 2's job to produce, your job is to display them well — if raw JSON
ever lands in these fields, flag it back to Member 2, don't silently dump it).

═══════════════════════════════════════════════════════════
APPROVAL WORKFLOW
═══════════════════════════════════════════════════════════
A human (playing "teacher/admin" in the demo) must be able to, directly in
Notion, without touching code:
- Change the Decision field in Approvals DB to Approved / Rejected /
  Override Approved
- Optionally add Override Instructions (free text) if overriding an AI
  recommendation

The backend detects this change (Member 1 will poll get_human_decision() or
get_pending_approvals()) and continues the workflow. You do NOT trigger the
real action from Notion — no Notion button should call an external webhook
that performs the action directly. All real actions flow through the backend.

═══════════════════════════════════════════════════════════
notion/notion_service.py — implement these EXACT function signatures
(Member 1 imports this file directly, so names/params must match precisely)
═══════════════════════════════════════════════════════════
create_request_page(request_id: str, title: str, category: str, requester: str,
                     original_text: str, ai_summary: str, ai_recommendation: str,
                     priority: str, confidence: float, status: str,
                     requires_approval: bool) -> str   # returns notion_page_id

update_request_page(notion_page_id: str, status: str,
                     human_decision: str | None = None,
                     action_result: str | None = None) -> None

create_approval_page(request_id: str, request_summary: str) -> str

get_pending_approvals() -> list[dict]
    # returns [{"request_id": ..., "decision": ..., "reviewer": ...,
    #           "reason": ..., "override_instructions": ...}, ...]

get_human_decision(request_id: str) -> dict | None
    # returns None if still pending, else
    # {"decision": "approved"|"rejected"|"override_approved",
    #  "reviewer": str, "reason": str}

create_run_log(request_id: str, event: str, actor: str, action: str,
                status: str, reason: str = "", error: str = "",
                external_action_id: str = "") -> str

Wrap every Notion API call in try/except with retries (Notion's API can rate
limit — respect a 429 with backoff). Never let a Notion outage crash the
caller — raise a clear custom exception (e.g. NotionServiceError) that
Member 1's orchestrator can catch and route to ESCALATED.

═══════════════════════════════════════════════════════════
TESTING
═══════════════════════════════════════════════════════════
Write a script (tests/test_notion_flow.py) that creates a real test request
through your functions and verifies, by reading back from the Notion API:
- The request page appears with correct properties
- AI summary/recommendation are readable (not raw JSON)
- An approval page is created and visible
- Changing the Decision field is correctly detected by get_human_decision()
- A Run Log entry is created for each step
- Status transitions correctly end-to-end

═══════════════════════════════════════════════════════════
DELIVERABLES
═══════════════════════════════════════════════════════════
1. notion/notion_service.py implementing all 6 functions above
2. notion/setup_workspace.py — a script that programmatically creates the 3
   databases and the home page (so the whole workspace is reproducible from
   scratch by running one command — huge plus for judges)
3. .env.example (NOTION_API_KEY, NOTION_REQUESTS_DB_ID, NOTION_RUNLOG_DB_ID,
   NOTION_APPROVALS_DB_ID)
4. docs/notion-schema.md documenting every property and status option
5. Screenshots of the finished workspace (home page + each database) saved
   to docs/screenshots/ for the README and pitch deck
6. README.md with setup instructions

The workspace must remain useful and readable even if the backend is
temporarily offline — a non-technical judge should be able to open Notion
alone and understand exactly what happened today and what still needs a
human decision.

Start with setup_workspace.py to create the schema, then notion_service.py
functions one at a time, testing each against the real Notion API as you go.
```

---

## 🔌 MEMBER 4 — Integrations / Frontend / QA / Demo Engineer

**Copy everything in this box to your coding AI:**

```
ROLE: You are the integrations, QA, and demo engineer for a hackathon project
called "AI College Request Automation." Your job is to make the whole
4-person system actually demonstrable, reliable, and resistant to a judge
poking at it live.

═══════════════════════════════════════════════════════════
WHAT YOU OWN
═══════════════════════════════════════════════════════════
- integrations/action_service.py — the ONLY module allowed to perform real
  external actions (email, calendar)
- The full end-to-end test suite in tests/
- Demo data, demo script, and reset script
- A minimal HTML/React status page is OPTIONAL and only if time allows —
  Notion is the primary dashboard, do not spend hackathon time building a
  competing frontend unless everything else is already done

═══════════════════════════════════════════════════════════
integrations/action_service.py — implement exactly this contract
═══════════════════════════════════════════════════════════
send_email(to: str, subject: str, body: str) -> dict
    # Use a safe sandbox/test provider for the demo — recommended options:
    #   - Mailtrap (sandbox inbox, no real emails sent, great for live demo)
    #   - or a Gmail SMTP test account created just for this hackathon
    #   - or, as an absolute fallback with zero external dependency risk,
    #     a "mock" adapter that just logs to console/file and returns
    #     success=true — keep this behind an env flag EMAIL_PROVIDER=mock
    #     so the demo NEVER fails due to WiFi/SMTP issues on stage
    # Returns: {"success": bool, "external_action_id": str, "error": str|None}

create_calendar_event(title: str, date: str, description: str) -> dict
    # Same return shape. Mock provider acceptable if time is short —
    # prioritize send_email working end-to-end over this being real.

execute_action(action_type: str, payload: dict) -> dict
    # Dispatcher: routes "send_email" / "create_calendar_event" to the right
    # function above based on action_type. MUST NEVER raise an exception —
    # catch everything internally and always return the standard dict, even
    # on total failure: {"success": false, "external_action_id": "",
    # "error": "<readable message>"}

Design it so swapping the mock adapter for a real provider later is a
one-line config change, not a rewrite (e.g. a simple adapter interface with
a MockEmailAdapter and a MailtrapEmailAdapter both implementing the same
send() method).

═══════════════════════════════════════════════════════════
INTEGRATION YOU'RE VERIFYING (you don't build these pieces, you test that
they connect correctly)
═══════════════════════════════════════════════════════════
Webhook → Backend (Member 1) → AI API (Member 2) → Notion (Member 3) →
Human Approval → Backend → Real Action (you) → Run Log (Member 3)

Do NOT duplicate business logic already implemented by Member 1 — if you
find yourself reimplementing orchestration, stop and flag it, that's scope
creep and will cause merge conflicts.

═══════════════════════════════════════════════════════════
END-TO-END TEST SUITE — build all 6, these ARE your grade on reliability
═══════════════════════════════════════════════════════════
Test 1 — Normal request (happy path)
  Input: "Sir, I need leave tomorrow because of a family emergency."
  Expect: AI understands → Notion request created → approval required →
  teacher approves (simulate via Notion API call in the test) → email sent
  (check the mock/sandbox inbox) → Run Log created with all steps.

Test 2 — Rejection
  Teacher rejects. Expect: no external action fires, status = REJECTED,
  Run Log entry created recording the rejection.

Test 3 — Override
  AI recommends "human_review"/reject-leaning, teacher overrides to approve.
  Expect: override is respected, action happens, Run Log explicitly records
  it was an override (not a normal approval).

Test 4 — Bad input
  Input is garbage/nonsense text. Expect: no crash anywhere in the chain,
  request is routed to human review (category=unknown or requires_approval).

Test 5 — Duplicate request
  Same request text + requester submitted twice within a short window.
  Expect: only ONE action is ultimately performed — verify via the
  idempotency check in Member 1's backend.

Test 6 — External failure
  Force action_service to fail (e.g. set EMAIL_PROVIDER to an intentionally
  broken config for this one test). Expect: request becomes FAILED, error is
  logged in Run Log with a readable message, no silent failure, no crash.

Write these as real pytest integration tests in tests/test_e2e.py that spin
up (or hit already-running) backend + ai-service + real Notion sandbox, plus
a scripts/reset_demo.py that wipes/resets Notion databases and the local DB
between test runs and before the live demo.

═══════════════════════════════════════════════════════════
DEMO DATA — prepare 5 realistic requests covering every category
═══════════════════════════════════════════════════════════
1. Leave request (English)
2. Assignment extension (Hinglish — this is your "wow" moment for judges)
3. Event booking
4. Maintenance request
5. Ambiguous/invalid request (deliberately vague, to show graceful escalation)

Save these in demo_data/sample_requests.json with expected outcomes noted,
so anyone on the team can run the demo, not just you.

═══════════════════════════════════════════════════════════
DEMO SCRIPT — write this as a literal step-by-step script in docs/demo-script.md
═══════════════════════════════════════════════════════════
1. Submit a request (curl or a tiny script — instant, no manual typing on stage)
2. Show the automatic trigger firing in your terminal/logs
3. Show the AI classification result (point at the JSON, then the human-
   readable summary)
4. Open Notion — show the request sitting in "Needs Attention"
5. Approve it live in Notion
6. Show the real email/action firing (open the sandbox inbox)
7. Show the completed Run Log — narrate it like a story
8. Demonstrate a rejection (Test 2 scenario, quick)
9. Demonstrate the bad-input escalation (Test 4 scenario, quick) — this is
   what proves reliability to judges, don't cut it for time
10. Close with the System Status view showing today's numbers

═══════════════════════════════════════════════════════════
RELIABILITY ARTIFACTS
═══════════════════════════════════════════════════════════
1. scripts/health_check.py — pings all 3 services (backend/8000, ai-
   service/8001, Notion API) and prints a clean OK/FAIL table — run this
   FIRST, always, 2 minutes before you go on stage
2. scripts/reset_demo.py — resets all state between rehearsals
3. .env.example covering every variable used across integrations/
4. README.md
5. docs/troubleshooting.md — write down every failure you hit while
   building, and the fix, so if it happens again on stage you're not
   debugging live, you're just running a known fix

═══════════════════════════════════════════════════════════
FINAL DELIVERABLES
═══════════════════════════════════════════════════════════
integrations/action_service.py, tests/test_e2e.py, demo_data/,
docs/demo-script.md, docs/troubleshooting.md, scripts/health_check.py,
scripts/reset_demo.py, README.md

Prioritize RELIABILITY over extra features. A judge remembers a demo that
survives a deliberately bad input far more than one extra feature that's
never shown. Start with the mock email adapter working end-to-end first,
then layer in a real sandbox provider, then build the test suite around it.
```

---

## 🔗 Team Integration Checklist (Member 1 runs this before merging)

- [ ] All 4 folders exist with their own `requirements.txt` and `.env.example`
- [ ] `ai-service` runs standalone on :8001 and passes its own 30-case eval
- [ ] `notion_service.py` functions match Section 0.3 signatures exactly
- [ ] `action_service.py` functions match Section 0.4 signatures exactly and never raise
- [ ] Backend successfully calls all three modules with real (not mocked) data at least once
- [ ] All 6 QA test cases pass end-to-end
- [ ] `docker-compose.yml` brings up backend + ai-service together with one command
- [ ] `scripts/health_check.py` shows all green right before the demo slot
- [ ] Demo script has been rehearsed at least twice, including the failure scenarios

## 🏆 Judging-Alignment Notes (why this structure scores well)

- **Human-in-the-loop AI** — the AI never acts unilaterally; every action is gated by an explicit approval step, which directly addresses "responsible AI" criteria most hackathon rubrics score on.
- **Reliability under failure** — idempotency, retries, and graceful escalation are visible in the Run Log, not just claimed in a slide.
- **Real, not simulated, integration** — Notion is populated via live API calls during the demo, not seeded with fake screenshots.
- **Clear ownership + clean architecture** — the 4-folder split with a locked contract (Section 0) is itself something you can show on a slide to prove the team worked like a real engineering org, not four people improvising.
- **Language coverage (Hinglish)** — directly relevant for an Indian citizen-facing use case and a strong differentiator against teams that only handle English.
