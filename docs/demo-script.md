# AI College Request Automation — Demo Script
### Live Demo Walk-Through | Hackathon Presentation

> **Before you go on stage:** Run `python scripts/health_check.py` and verify every row shows ✓.  
> Keep this doc open on a second screen during the demo. Read from it verbatim if needed.

---

## Pre-Demo Checklist (run 10 minutes before)

```bash
# 1. Reset state to a clean slate
python scripts/reset_demo.py

# 2. Verify all systems are green
python scripts/health_check.py

# 3. Dry-run the first submission to confirm payload looks right
python scripts/submit_demo.py --id 1 --dry-run

# 4. Have Notion open in a browser tab (pinned to the Home / "Needs Attention" view)
# 5. Have the Mailtrap inbox open in another tab (or know it will show in logs)
# 6. Have a terminal split: one pane running the backend, one for your commands
```

---

## Step 1 — Submit a Real Request (30 seconds)

> **Say:** *"Let's walk through a real request, start to finish, end to end."*

```bash
python scripts/submit_demo.py --id 1
```

**What they'll see in terminal:**
```
══ Demo Request #1: Leave Request — English ══
Category: leave_request
Text:     Sir, I need leave tomorrow because of a family emergency...
From:     Priya Mehta (student)

→ Submitting to http://localhost:8000/webhook/request ...
✓ Submitted! request_id = req_a1b2c3d4
  Track it: GET http://localhost:8000/requests/req_a1b2c3d4
```

**Point at:** the `request_id` — *"this ID follows the request through every system."*

---

## Step 2 — Show the Automatic Trigger Firing (20 seconds)

> **Say:** *"The moment that webhook fires, our backend picks it up and begins processing."*

**Point at the backend terminal pane.** You'll see structured JSON logs:
```
2026-08-21 00:20:00  INFO  [orchestrator]  request_id=req_a1b2c3d4 status=RECEIVED
2026-08-21 00:20:01  INFO  [ai_client]     request_id=req_a1b2c3d4 Calling AI service...
2026-08-21 00:20:02  INFO  [orchestrator]  request_id=req_a1b2c3d4 status=PROCESSING
```

**Say:** *"Every single step is logged with the same request ID — fully traceable."*

---

## Step 3 — Show the AI Classification Result (45 seconds)

**Run in terminal:**
```bash
curl http://localhost:8000/requests/req_a1b2c3d4 | python -m json.tool
```

**Point at the response JSON:**
```json
{
  "request_id": "req_a1b2c3d4",
  "status": "PENDING_APPROVAL",
  "category": "leave_request",
  "confidence": 0.96,
  "summary": "Student requests leave for 21st August due to a family emergency.",
  "recommended_action": "request_teacher_approval",
  "requires_approval": true
}
```

> **Say:** *"The AI classified it correctly — leave request, 96% confidence, human approval required.  
> Now here's the important part: the AI recommends. It does NOT decide."*

---

## Step 4 — Open Notion (30 seconds)

Switch to the Notion browser tab, already on the **"Needs Attention"** view.

> **Say:** *"The teacher — or any authorized approver — sees this request appear instantly in Notion.  
> No email chain, no WhatsApp message, no manual entry. It just appears."*

**Show the judge:**
- The request is in the "🔴 Needs Attention" section
- Priority, category, requester, AI summary all visible
- Status is `PENDING_APPROVAL`

---

## Step 5 — Approve Live in Notion (20 seconds)

In Notion, find the matching entry in the **Approvals** database.

**Click:** `Decision` field → select **`approved`**  
**Add:** a Reviewer name (e.g. "Prof. Sharma")

> **Say:** *"The teacher approves. This is their only interaction — one click, in Notion, no code."*

---

## Step 6 — Show the Real Action Firing (30 seconds)

Within ~10 seconds of the approval, switch back to the terminal.  
You'll see:
```
INFO  [orchestrator]  request_id=req_a1b2c3d4 status=EXECUTING
INFO  [action_service] 📧 [MOCK EMAIL] to=teacher@college.edu | subject=Leave Approved...
INFO  [orchestrator]  request_id=req_a1b2c3d4 status=COMPLETED
```

**If using Mailtrap:** Open the Mailtrap inbox tab and show the email landed.

> **Say:** *"The email fires automatically. The teacher did one thing — click Approve — and the system handled the rest."*

---

## Step 7 — Show the Run Log (45 seconds)

In Notion, click the **📜 Run Log** view.

> **Say:** *"Here's every single thing that happened to this request, in order.  
> Let me read it to you like a story."*

**Narrate aloud, pointing at each row:**
1. `RECEIVED` — Request arrived
2. `PROCESSING` — AI classification started
3. `PENDING_APPROVAL` — Routed for teacher review (AI confidence 96%)
4. `APPROVED` — Prof. Sharma approved at [time]
5. `EXECUTING` — Email being sent
6. `COMPLETED` — Email delivered, action_id: `mock_email_abc123`

> **Say:** *"A non-technical principal can open this log tomorrow and understand everything that happened today, without asking anyone."*

---

## Step 8 — Demonstrate a Rejection (60 seconds)

> **Say:** *"Now let me show you what happens when a request is rejected."*

```bash
python scripts/submit_demo.py --id 1
# Note the new request_id
```

In Notion → Approvals → set Decision to **`rejected`**, add a reason.

Within seconds:
```
INFO  [orchestrator]  request_id=req_xyz status=REJECTED
```

```bash
curl http://localhost:8000/requests/req_xyz | python -m json.tool
# Show: "status": "REJECTED", "action_result": null
```

> **Say:** *"No email was sent. No calendar event created. The system does nothing — correctly.  
> The rejection is logged, but no real-world action fires. Human in control."*

---

## Step 9 — Bad Input Escalation (60 seconds)

> **Say:** *"Here's what I love most about our system. Watch what happens when someone sends garbage."*

```bash
python scripts/submit_demo.py --id 5
```

*This submits:* `"hello sir please do the needful and help me with my thing thanks"`

```bash
curl http://localhost:8000/requests/<new_id> | python -m json.tool
```

**Show:**
```json
{
  "category": "unknown",
  "confidence": 0.31,
  "requires_approval": true,
  "recommended_action": "human_review",
  "status": "PENDING_APPROVAL"
}
```

> **Say:** *"It didn't crash. It didn't guess. It didn't auto-approve something it didn't understand.  
> It flagged it for a human. That's not just good engineering — that's responsible AI."*

**In Notion:** Show it sitting in "🔴 Needs Attention" waiting for a human decision.

---

## Step 10 — System Status View (30 seconds)

In Notion, click to the **📊 System Status** section on the home page.

> **Say:** *"Today's numbers — right there, in real-time, no refresh needed.  
> Every request, every decision, every action — auditable, transparent, and human-controlled."*

**Close:** *"The system runs in a single webhook call, handles English and Hinglish,  
never crashes on bad input, and always keeps a human in the loop. Thank you."*

---

## Emergency Recovery Procedures

| Symptom | Fix |
|---------|-----|
| Backend not responding | `cd backend && uvicorn app.main:app --reload` |
| Notion pages not appearing | Check `NOTION_API_KEY` in `.env`, run `health_check.py` |
| Email not firing | Check backend logs, verify `EMAIL_PROVIDER` value |
| Demo stuck at PENDING_APPROVAL | Use manual endpoint: `POST /approval/{request_id}` |
| Wrong request shown | Run `reset_demo.py`, start fresh |

```bash
# Manual approval (safety net if Notion polling lags)
curl -X POST http://localhost:8000/approval/req_YOURREQID
```

See [`docs/troubleshooting.md`](./troubleshooting.md) for full recovery playbook.
