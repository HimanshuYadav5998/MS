# AI College Request Analyzer — Evaluation Results

> **Service URL**: `http://localhost:8001`
> **Test cases**: 30 | **Run timestamp**: see filename

---

## Summary Table

| Metric | Value |
|---|---|
| **Overall Category Accuracy** | 100.0% (30/30) |
| **Approval Routing Accuracy** | 83.3% (25/30) |
| **Human-Review Routing Accuracy** | 100.0% (7/7) |
| **Average Latency** | 73 ms |
| **P95 Latency** | 4 ms |
| **Errors (HTTP/timeout)** | 0 |

---

## Per-Bucket Category Accuracy

| Bucket | Total | Correct | Accuracy |
|---|---|---|---|
| normal_english | 8 | 8 | 100% |
| hinglish | 8 | 8 | 100% |
| badly_formatted | 4 | 4 | 100% |
| incomplete | 4 | 4 | 100% |
| duplicate | 3 | 3 | 100% |
| malicious | 2 | 2 | 100% |
| irrelevant | 1 | 1 | 100% |


---

## Field Extraction Spot-Check

- [TC_EN_003] event_booking missing event_date
- [TC_EN_006] document_request missing document_type
- [TC_EN_008] leave_request missing leave_date
- [TC_BAD_001] assignment_extension missing requested_extension_date
- [TC_BAD_002] leave_request missing leave_date
- [TC_BAD_004] maintenance_request missing location
- [TC_INC_001] assignment_extension missing requested_extension_date
- [TC_INC_002] leave_request missing leave_date
- [TC_INC_003] event_booking missing event_date
- [TC_DUP_001] leave_request missing leave_date
- [TC_DUP_002] leave_request missing leave_date

---

## Per-Case Results

| ID | Bucket | Expected Cat | Predicted Cat | Approval Correct? | Confidence | Latency |
|---|---|---|---|---|---|---|
| TC_EN_001 | normal_english | assignment_extension | assignment_extension ✅ | True ✅ | 0.68 | 2089 ms |
| TC_EN_002 | normal_english | leave_request | leave_request ✅ | True ✅ | 0.68 | 3 ms |
| TC_EN_003 | normal_english | event_booking | event_booking ✅ | True ✅ | 0.68 | 4 ms |
| TC_EN_004 | normal_english | maintenance_request | maintenance_request ✅ | True ❌ | 0.68 | 4 ms |
| TC_EN_005 | normal_english | document_request | document_request ✅ | True ✅ | 0.68 | 3 ms |
| TC_EN_006 | normal_english | document_request | document_request ✅ | True ✅ | 0.62 | 3 ms |
| TC_EN_007 | normal_english | maintenance_request | maintenance_request ✅ | True ❌ | 0.68 | 3 ms |
| TC_EN_008 | normal_english | leave_request | leave_request ✅ | True ✅ | 0.68 | 3 ms |
| TC_HI_001 | hinglish | leave_request | leave_request ✅ | True ✅ | 0.68 | 4 ms |
| TC_HI_002 | hinglish | assignment_extension | assignment_extension ✅ | True ✅ | 0.68 | 3 ms |
| TC_HI_003 | hinglish | maintenance_request | maintenance_request ✅ | True ❌ | 0.68 | 3 ms |
| TC_HI_004 | hinglish | document_request | document_request ✅ | True ✅ | 0.68 | 3 ms |
| TC_HI_005 | hinglish | leave_request | leave_request ✅ | True ✅ | 0.68 | 3 ms |
| TC_HI_006 | hinglish | event_booking | event_booking ✅ | True ✅ | 0.68 | 3 ms |
| TC_HI_007 | hinglish | maintenance_request | maintenance_request ✅ | True ❌ | 0.64 | 3 ms |
| TC_HI_008 | hinglish | document_request | document_request ✅ | True ✅ | 0.68 | 3 ms |
| TC_BAD_001 | badly_formatted | assignment_extension | assignment_extension ✅ | True ✅ | 0.68 | 4 ms |
| TC_BAD_002 | badly_formatted | leave_request | leave_request ✅ | True ✅ | 0.68 | 3 ms |
| TC_BAD_003 | badly_formatted | event_booking | event_booking ✅ | True ✅ | 0.68 | 4 ms |
| TC_BAD_004 | badly_formatted | maintenance_request | maintenance_request ✅ | True ❌ | 0.68 | 3 ms |
| TC_INC_001 | incomplete | assignment_extension | assignment_extension ✅ | True ✅ | 0.68 | 3 ms |
| TC_INC_002 | incomplete | leave_request | leave_request ✅ | True ✅ | 0.68 | 4 ms |
| TC_INC_003 | incomplete | event_booking | event_booking ✅ | True ✅ | 0.64 | 3 ms |
| TC_INC_004 | incomplete | maintenance_request | maintenance_request ✅ | True ✅ | 0.68 | 3 ms |
| TC_DUP_001 | duplicate | leave_request | leave_request ✅ | True ✅ | 0.68 | 3 ms |
| TC_DUP_002 | duplicate | leave_request | leave_request ✅ | True ✅ | 0.68 | 3 ms |
| TC_DUP_003 | duplicate | leave_request | leave_request ✅ | True ✅ | 0.68 | 3 ms |
| TC_MAL_001 | malicious | unknown | unknown ✅ | True ✅ | 0.00 | 3 ms |
| TC_MAL_002 | malicious | unknown | unknown ✅ | True ✅ | 0.00 | 3 ms |
| TC_IRR_001 | irrelevant | unknown | unknown ✅ | True ✅ | 0.30 | 3 ms |


---

## Notes

- Confidence < 0.70 always routes to `human_review` (hard override in Python).
- `unknown` category always sets `requires_approval=true` (hard override in Pydantic schema).
- Prompt injection inputs are quarantined before reaching the LLM.
- Hinglish inputs are understood natively by both the LLM and the keyword fallback.
