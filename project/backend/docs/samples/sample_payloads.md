# Sample Webhook Payload

## Request

`POST http://localhost:8000/webhook/request`

```json
{
  "text": "I need a recommendation letter for my MIT application by next Friday. Could Professor Johnson please write one highlighting my research work in ML?",
  "requester_name": "Alice Chen",
  "requester_role": "Senior Undergraduate Student"
}
```

## Response (202 Accepted)

```json
{
  "request_id": "req_a1b2c3d4",
  "status": "PENDING_APPROVAL",
  "message": "Request received and queued (status: PENDING_APPROVAL)"
}
```

---

# Sample GET /requests/{id} Response

`GET http://localhost:8000/requests/req_a1b2c3d4`

```json
{
  "request_id": "req_a1b2c3d4",
  "status": "PENDING_APPROVAL",
  "requester_name": "Alice Chen",
  "requester_role": "Senior Undergraduate Student",
  "text": "I need a recommendation letter for my MIT application by next Friday. Could Professor Johnson please write one highlighting my research work in ML?",
  "created_at": "2026-08-20T17:40:01.123456Z",
  "updated_at": "2026-08-20T17:40:03.456789Z",
  "category": "recommendation_letter",
  "recommended_action": "send_email",
  "summary": "Senior student Alice Chen requests a recommendation letter from Professor Johnson for MIT application. Deadline: next Friday. Focus: ML research.",
  "priority": "high",
  "confidence": 0.92,
  "requires_approval": true,
  "extracted_fields": {
    "deadline": "next Friday",
    "institution": "MIT",
    "professor": "Professor Johnson",
    "topic": "ML research"
  },
  "action_type": "send_email",
  "external_action_id": null,
  "error_message": null,
  "notion_request_page_id": "12345678abcdef12345678abcdef1234",
  "notion_approval_page_id": "abcdef1234567890abcdef1234567890"
}
```

---

# Sample Override Request

`POST http://localhost:8000/override/req_a1b2c3d4`

```json
{
  "decision": "approved"
}
```

Response:
```json
{
  "request_id": "req_a1b2c3d4",
  "status": "COMPLETED",
  "message": "Override approved"
}
```

---

# Sample Run Logs Response

`GET http://localhost:8000/requests/req_a1b2c3d4/logs`

```json
[
  {
    "id": 1,
    "request_id": "req_a1b2c3d4",
    "event": "Request received",
    "detail": "Requester: Alice Chen (Senior Undergraduate Student)",
    "status": "RECEIVED",
    "timestamp": "2026-08-20T17:40:01.100000Z"
  },
  {
    "id": 2,
    "request_id": "req_a1b2c3d4",
    "event": "Processing started",
    "detail": "",
    "status": "PROCESSING",
    "timestamp": "2026-08-20T17:40:01.200000Z"
  },
  {
    "id": 3,
    "request_id": "req_a1b2c3d4",
    "event": "Notion request page created",
    "detail": "Notion page ID: 12345678abcdef12345678abcdef1234",
    "status": "PROCESSING",
    "timestamp": "2026-08-20T17:40:01.800000Z"
  },
  {
    "id": 4,
    "request_id": "req_a1b2c3d4",
    "event": "AI analysis complete",
    "detail": "category=recommendation_letter, action=send_email, priority=high, confidence=0.92, requires_approval=True",
    "status": "PROCESSING",
    "timestamp": "2026-08-20T17:40:02.500000Z"
  },
  {
    "id": 5,
    "request_id": "req_a1b2c3d4",
    "event": "Notion page updated with AI output",
    "detail": "category=recommendation_letter, action=send_email, priority=high, confidence=0.92, requires_approval=True",
    "status": "PROCESSING",
    "timestamp": "2026-08-20T17:40:02.900000Z"
  },
  {
    "id": 6,
    "request_id": "req_a1b2c3d4",
    "event": "Pending human approval",
    "detail": "All requests require approval per hackathon safety policy",
    "status": "PENDING_APPROVAL",
    "timestamp": "2026-08-20T17:40:03.100000Z"
  },
  {
    "id": 7,
    "request_id": "req_a1b2c3d4",
    "event": "Approval page created in Notion",
    "detail": "Approval page ID: abcdef1234567890abcdef1234567890",
    "status": "PENDING_APPROVAL",
    "timestamp": "2026-08-20T17:40:03.400000Z"
  },
  {
    "id": 8,
    "request_id": "req_a1b2c3d4",
    "event": "Request approved",
    "detail": "",
    "status": "APPROVED",
    "timestamp": "2026-08-20T17:40:55.000000Z"
  },
  {
    "id": 9,
    "request_id": "req_a1b2c3d4",
    "event": "Executing action",
    "detail": "send_email",
    "status": "EXECUTING",
    "timestamp": "2026-08-20T17:40:55.100000Z"
  },
  {
    "id": 10,
    "request_id": "req_a1b2c3d4",
    "event": "Action completed successfully",
    "detail": "external_action_id=email_msg_abc123",
    "status": "COMPLETED",
    "timestamp": "2026-08-20T17:40:56.200000Z"
  }
]
```

---

# Sample Health Check Response

`GET http://localhost:8000/health`

```json
{
  "status": "ok",
  "ai_service": "reachable",
  "db": "ok",
  "timestamp": "2026-08-20T17:45:00.000000Z"
}
```
