# Troubleshooting Playbook
### AI College Request Automation — Every failure we hit, and how to fix it

> **How to use this doc:** If something breaks on stage, CTRL+F the symptom. Every entry has a
> verified fix. Do NOT debug live — just run the known fix.

---

## Service Startup Issues

### ❌ Backend fails to start: `ModuleNotFoundError`

**Symptom:**
```
ModuleNotFoundError: No module named 'fastapi'
```
**Fix:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
**Root cause:** virtualenv not activated, or dependencies not installed.

---

### ❌ Backend starts but crashes immediately: `NOTION_API_KEY not set`

**Symptom:**
```
ValueError: NOTION_API_KEY is required but not set in environment.
```
**Fix:**
```bash
cp integrations/.env.example backend/.env
# Edit backend/.env and fill in NOTION_API_KEY, DB IDs
```

---

### ❌ AI Service unreachable: `Connection refused on port 8001`

**Symptom in health_check.py:**
```
AI Service (localhost:8001)   FAIL  Cannot connect to http://localhost:8001
```
**Fix:**
```bash
cd ai-service
pip install -r requirements.txt
uvicorn app.main:app --port 8001 --reload
```
If it still fails, check that port 8001 isn't in use:
```bash
netstat -ano | findstr :8001   # Windows
lsof -i :8001                  # Mac/Linux
```

---

### ❌ Port already in use

**Symptom:**
```
ERROR:    [Errno 98] Address already in use
```
**Fix:**
```bash
# Windows: find and kill the PID
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Mac/Linux
fuser -k 8000/tcp
```

---

## Notion Issues

### ❌ Notion API returns 401 Unauthorized

**Symptom:**
```
Notion API    FAIL  Invalid API key (401)
```
**Fix:**
1. Go to [notion.so/my-integrations](https://notion.so/my-integrations)
2. Open your integration → copy the "Internal Integration Secret"
3. Paste it as `NOTION_API_KEY=secret_...` in `integrations/.env`
4. **Critical:** Make sure the integration is connected to your workspace pages.  
   In Notion: open the database → `...` menu → Connections → Add your integration.

---

### ❌ Notion pages not appearing after request submission

**Symptom:** Request submitted, backend shows `PROCESSING`, but nothing appears in Notion.

**Fix checklist:**
1. Verify `NOTION_REQUESTS_DB_ID` is the correct database ID (not page ID).  
   Get it: open the database in Notion → copy URL → the 32-char hex after the last `/` is the DB ID.
2. Check the backend logs for Notion-specific errors:
   ```bash
   grep -i "notion" backend/logs/app.log | tail -20
   ```
3. Confirm the integration has write access to the database (see 401 fix above).

---

### ❌ `create_request_page` raises `NotionServiceError`

**Symptom in logs:**
```
ERROR  [orchestrator]  request_id=... NotionServiceError: 400 Bad Request
```
**Fix:** A property name in `notion_service.py` doesn't match your Notion schema.  
Check the field names in your Requests database match exactly (case-sensitive).  
Run `notion/setup_workspace.py` to recreate the schema from scratch if needed.

---

### ❌ `get_human_decision` returns None even after approving in Notion

**Symptom:** Backend stays in `PENDING_APPROVAL` forever after approving in Notion.

**Fix checklist:**
1. Verify you changed the field in the **Approvals** database, not the Requests database.
2. Check the `Decision` field exact values: must be `approved`, `rejected`, or `override_approved` (lowercase).
3. If using manual endpoints as a fallback:
   ```bash
   curl -X POST http://localhost:8000/approval/req_YOURREQID
   ```
4. Restart the backend if the poller task has hung (rare, but it happens).

---

## Email / Action Service Issues

### ❌ Email not firing after approval

**Symptom:** Request reaches `EXECUTING` but no email in Mailtrap / logs.

**Diagnosis:**
```bash
cat integrations/logs/action_service.log | tail -30
cat integrations/logs/actions.jsonl | tail -5
```

**Fix (mock adapter):** If `EMAIL_PROVIDER=mock`, emails appear only in logs, not an inbox — that's correct behavior.

**Fix (Mailtrap):** Verify credentials:
```bash
# Test SMTP connectivity manually
python -c "
import smtplib
with smtplib.SMTP('sandbox.smtp.mailtrap.io', 2525, timeout=10) as s:
    s.starttls()
    s.login('YOUR_USERNAME', 'YOUR_PASSWORD')
    print('Connected OK')
"
```
If this fails, check WiFi, or fall back to `EMAIL_PROVIDER=mock` for the demo.

---

### ❌ execute_action returning `success: false` with no error message

**Symptom:**
```json
{"success": false, "external_action_id": "", "error": null}
```
**Fix:** This should not happen with the current code (error is always set on failure).  
If it does, check `integrations/logs/action_service.log` for the full traceback.

---

### ❌ `EMAIL_PROVIDER=broken` persisting after Test 6

**Symptom:** All emails failing after running the test suite.

**Fix:**
```bash
# Explicitly set back to mock
export EMAIL_PROVIDER=mock   # Linux/Mac
$env:EMAIL_PROVIDER="mock"   # Windows PowerShell
```
Or set `EMAIL_PROVIDER=mock` in `integrations/.env` and restart services.

---

## Test Suite Issues

### ❌ Tests fail with `Connection refused` on backend/AI service

**Symptom:**
```
requests.exceptions.ConnectionError: ... localhost:8000
```
**Fix:** Start both services before running live integration tests:
```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload

# Terminal 2
cd ai-service && uvicorn app.main:app --port 8001 --reload

# Terminal 3
pytest tests/test_e2e.py -v
```
For offline runs (no services):
```bash
SKIP_LIVE_SERVICES=1 pytest tests/test_e2e.py -v -k "not TestEndToEnd"
```

---

### ❌ Test 5 (duplicate) fails: two different request_ids returned

**Symptom:**
```
AssertionError: Duplicate not deduplicated! id1=req_abc, id2=req_xyz
```
**Fix:** Member 1's idempotency check (step 3 in orchestrator.py) may not be implemented yet.  
Flag this to Member 1. The check is: if `(requester_name + text)` exists in DB within the last 5 minutes, return the existing `request_id`.

---

### ❌ Test 6 (external failure) passes but status is COMPLETED, not FAILED

**Symptom:**
```
AssertionError: Expected FAILED on external failure, got COMPLETED
```
**Fix:** The broken adapter is not being picked up by the already-running backend process.  
The backend runs in a separate process and its `EMAIL_PROVIDER` env var was set at startup.  
**Solution for demo:** Temporarily set `EMAIL_PROVIDER=broken` in `backend/.env`, restart backend, run test, revert.

---

## WiFi / Network Issues on Stage

### ❌ Everything broken — no internet

**Recovery plan (in order):**
1. Switch to `EMAIL_PROVIDER=mock` (no network needed for email)
2. Verify Notion was pre-populated (if Notion is offline, show screenshots instead)
3. Use `SKIP_LIVE_SERVICES=1` and run only offline unit tests for the live demo of "reliability"
4. Show `integrations/logs/actions.jsonl` and `integrations/logs/action_service.log` as proof the system ran

**The system is designed for exactly this scenario.** The mock adapter is the safety net.

---

## General Debugging Commands

```bash
# Check all service health
python scripts/health_check.py

# Tail backend logs in real time
Get-Content backend/logs/app.log -Wait   # Windows PowerShell
tail -f backend/logs/app.log             # Linux/Mac

# Tail action service logs
Get-Content integrations/logs/action_service.log -Wait

# Query a specific request by ID
curl http://localhost:8000/requests/req_YOURID

# List all requests
curl http://localhost:8000/requests

# Manually approve a stuck request
curl -X POST http://localhost:8000/approval/req_YOURID

# Manually reject
curl -X POST http://localhost:8000/reject/req_YOURID

# Full reset
python scripts/reset_demo.py

# Full reset dry run (to see what would be deleted)
python scripts/reset_demo.py --dry-run
```

---

## Things That Have NEVER Failed (after initial setup)
- `execute_action()` raising an exception — it's wrapped in catch-all
- `send_email()` in mock mode — purely local, no network
- Health check script itself — no external dependencies
- `scripts/reset_demo.py` with `--local-only` flag — only touches local files
