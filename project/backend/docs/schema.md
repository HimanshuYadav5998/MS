# Database Schema

## `college_requests`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `request_id` | VARCHAR(32) UNIQUE | `req_<8hex>` — business key |
| `status` | VARCHAR(32) | State machine status |
| `requester_name` | VARCHAR(200) | |
| `requester_role` | VARCHAR(200) | |
| `text` | TEXT | Full request text |
| `idempotency_key` | VARCHAR(64) | SHA-256 of name+text |
| `created_at` | DATETIME | UTC |
| `updated_at` | DATETIME | UTC, updated on change |
| `category` | VARCHAR(100) | From AI service |
| `recommended_action` | VARCHAR(200) | From AI service |
| `summary` | TEXT | From AI service |
| `priority` | VARCHAR(50) | low / medium / high |
| `confidence` | FLOAT | 0.0–1.0 |
| `requires_approval` | INTEGER | Boolean (0/1) |
| `extracted_fields_json` | TEXT | JSON dict from AI |
| `action_type` | VARCHAR(100) | e.g. `send_email` |
| `external_action_id` | VARCHAR(200) | From action service |
| `error_message` | TEXT | Last error if FAILED |
| `notion_request_page_id` | VARCHAR(200) | Notion page link |
| `notion_approval_page_id` | VARCHAR(200) | Notion approval page |

**Indexes:** `request_id` (unique), `idempotency_key`

---

## `run_logs`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `request_id` | VARCHAR(32) | FK → college_requests.request_id |
| `event` | VARCHAR(200) | Human-readable event name |
| `detail` | TEXT | Additional context |
| `status` | VARCHAR(32) | Status at time of event |
| `timestamp` | DATETIME | UTC |

**Indexes:** `(request_id, timestamp)`

---

## `idempotency_records`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `idempotency_key` | VARCHAR(64) | SHA-256 fingerprint |
| `request_id` | VARCHAR(32) | Associated request |
| `created_at` | DATETIME | UTC — used for 5-min window query |

**Indexes:** `idempotency_key`

---

## Notes

- All tables are created automatically at startup via `init_db()`.
- **Swapping to PostgreSQL**: change `DATABASE_URL` in `.env` to a `postgresql+asyncpg://` connection string. No schema changes needed.
- `extracted_fields` is stored as a JSON string in `extracted_fields_json` for SQLite compatibility. The `CollegeRequest` model exposes it as a dict via a Python property.
