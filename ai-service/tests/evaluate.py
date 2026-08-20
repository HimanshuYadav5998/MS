#!/usr/bin/env python3
"""
tests/evaluate.py — Evaluation harness for the AI College Request Analyzer.

Usage:
    # Start the service first:
    #   cd ai-service && uvicorn main:app --port 8001
    #
    # Then run:
    python tests/evaluate.py [--url http://localhost:8001] [--output docs/eval-results.md]

Metrics reported:
  - Classification accuracy per bucket and overall
  - Approval routing accuracy (% correctly routed to human_review)
  - Key field extraction spot-check
  - Average / P95 latency per request
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:
    print("ERROR: httpx is not installed. Run: pip install httpx")
    sys.exit(1)

# ──────────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────────

ROOT         = Path(__file__).parent.parent
TEST_CASES   = ROOT / "tests" / "test_cases.json"
DOCS_DIR     = ROOT / "docs"
RESULTS_FILE = DOCS_DIR / "eval-results.md"


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────

def run_single(client: httpx.Client, base_url: str, case: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "request_id":     case["request_id"],
        "text":           case["text"],
        "requester_name": case["requester_name"],
        "requester_role": case["requester_role"],
    }
    start = time.perf_counter()
    try:
        resp = client.post(f"{base_url}/ai/analyze", json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        error  = None
    except Exception as exc:  # noqa: BLE001
        result = {}
        error  = str(exc)
    latency_ms = (time.perf_counter() - start) * 1000

    return {
        "id":          case["id"],
        "bucket":      case["bucket"],
        "expected_category":          case.get("expected_category", ""),
        "expected_requires_approval": case.get("expected_requires_approval", None),
        "expected_action":            case.get("expected_action", None),
        "predicted_category":         result.get("category", "ERROR"),
        "predicted_requires_approval": result.get("requires_approval", None),
        "predicted_action":           result.get("recommended_action", "ERROR"),
        "confidence":                 result.get("confidence", 0.0),
        "extracted_fields":           result.get("extracted_fields", {}),
        "summary":                    result.get("summary", ""),
        "risk_reason":                result.get("risk_reason"),
        "latency_ms":                 latency_ms,
        "error":                      error,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────────────────────────────────────

def compute_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    if total == 0:
        return {}

    # Category accuracy
    cat_correct = sum(
        1 for r in results
        if r["predicted_category"] == r["expected_category"]
    )

    # Approval routing accuracy (only for cases with an expected value)
    approval_cases = [r for r in results if r["expected_requires_approval"] is not None]
    approval_correct = sum(
        1 for r in approval_cases
        if r["predicted_requires_approval"] == r["expected_requires_approval"]
    )

    # Human-review routing (for cases that explicitly expect human_review)
    human_review_cases = [r for r in results if r.get("expected_action") == "human_review"]
    human_review_correct = sum(
        1 for r in human_review_cases
        if r["predicted_action"] == "human_review"
    )

    # Latencies
    latencies = [r["latency_ms"] for r in results if r["error"] is None]
    avg_latency  = statistics.mean(latencies) if latencies else 0
    p95_latency  = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

    # Per-bucket accuracy
    buckets: Dict[str, Dict[str, int]] = {}
    for r in results:
        b = r["bucket"]
        if b not in buckets:
            buckets[b] = {"total": 0, "correct": 0}
        buckets[b]["total"]  += 1
        if r["predicted_category"] == r["expected_category"]:
            buckets[b]["correct"] += 1

    # Error count
    errors = sum(1 for r in results if r["error"])

    return {
        "total":               total,
        "category_correct":    cat_correct,
        "category_accuracy":   cat_correct / total,
        "approval_cases":      len(approval_cases),
        "approval_correct":    approval_correct,
        "approval_accuracy":   approval_correct / len(approval_cases) if approval_cases else 0,
        "human_review_cases":  len(human_review_cases),
        "human_review_correct": human_review_correct,
        "human_review_accuracy": human_review_correct / len(human_review_cases) if human_review_cases else 0,
        "avg_latency_ms":      avg_latency,
        "p95_latency_ms":      p95_latency,
        "errors":              errors,
        "bucket_stats":        buckets,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Spot-check field extraction
# ──────────────────────────────────────────────────────────────────────────────

def field_spot_check(results: List[Dict[str, Any]]) -> List[str]:
    """
    Returns a list of observation strings about field extraction.
    These are qualitative — no binary pass/fail since fields are free-form.
    """
    observations = []
    for r in results:
        ef = r.get("extracted_fields", {})
        cat = r.get("predicted_category", "")
        if cat == "leave_request" and "leave_date" not in ef:
            observations.append(f"[{r['id']}] leave_request missing leave_date")
        if cat == "assignment_extension" and "requested_extension_date" not in ef:
            observations.append(f"[{r['id']}] assignment_extension missing requested_extension_date")
        if cat == "event_booking" and "event_date" not in ef:
            observations.append(f"[{r['id']}] event_booking missing event_date")
        if cat == "maintenance_request" and "location" not in ef:
            observations.append(f"[{r['id']}] maintenance_request missing location")
        if cat == "document_request" and "document_type" not in ef:
            observations.append(f"[{r['id']}] document_request missing document_type")
    return observations


# ──────────────────────────────────────────────────────────────────────────────
# Report generation
# ──────────────────────────────────────────────────────────────────────────────

def generate_markdown_report(
    results: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    field_issues: List[str],
    base_url: str,
) -> str:
    bucket_table_rows = ""
    for bucket, stats in metrics.get("bucket_stats", {}).items():
        acc = stats["correct"] / stats["total"] if stats["total"] else 0
        bucket_table_rows += f"| {bucket} | {stats['total']} | {stats['correct']} | {acc:.0%} |\n"

    per_case_rows = ""
    for r in results:
        status_icon = "✅" if r["predicted_category"] == r["expected_category"] else "❌"
        approval_icon = (
            "✅" if r["predicted_requires_approval"] == r["expected_requires_approval"]
            else "❌"
        )
        err_note = f" ⚠️ `{r['error']}`" if r["error"] else ""
        per_case_rows += (
            f"| {r['id']} | {r['bucket']} | {r['expected_category']} "
            f"| {r['predicted_category']} {status_icon} "
            f"| {r['predicted_requires_approval']} {approval_icon} "
            f"| {r['confidence']:.2f} | {r['latency_ms']:.0f} ms{err_note} |\n"
        )

    field_issues_md = "\n".join(f"- {obs}" for obs in field_issues) if field_issues else "_No field extraction issues detected._"

    return f"""# AI College Request Analyzer — Evaluation Results

> **Service URL**: `{base_url}`
> **Test cases**: {metrics['total']} | **Run timestamp**: see filename

---

## Summary Table

| Metric | Value |
|---|---|
| **Overall Category Accuracy** | {metrics['category_accuracy']:.1%} ({metrics['category_correct']}/{metrics['total']}) |
| **Approval Routing Accuracy** | {metrics['approval_accuracy']:.1%} ({metrics['approval_correct']}/{metrics['approval_cases']}) |
| **Human-Review Routing Accuracy** | {metrics['human_review_accuracy']:.1%} ({metrics['human_review_correct']}/{metrics['human_review_cases']}) |
| **Average Latency** | {metrics['avg_latency_ms']:.0f} ms |
| **P95 Latency** | {metrics['p95_latency_ms']:.0f} ms |
| **Errors (HTTP/timeout)** | {metrics['errors']} |

---

## Per-Bucket Category Accuracy

| Bucket | Total | Correct | Accuracy |
|---|---|---|---|
{bucket_table_rows}

---

## Field Extraction Spot-Check

{field_issues_md}

---

## Per-Case Results

| ID | Bucket | Expected Cat | Predicted Cat | Approval Correct? | Confidence | Latency |
|---|---|---|---|---|---|---|
{per_case_rows}

---

## Notes

- Confidence < 0.70 always routes to `human_review` (hard override in Python).
- `unknown` category always sets `requires_approval=true` (hard override in Pydantic schema).
- Prompt injection inputs are quarantined before reaching the LLM.
- Hinglish inputs are understood natively by both the LLM and the keyword fallback.
"""


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Evaluate the AI College Request Analyzer")
    parser.add_argument("--url",    default="http://localhost:8001", help="Service base URL")
    parser.add_argument("--output", default=str(RESULTS_FILE),       help="Output markdown file path")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")

    # Load test cases
    if not TEST_CASES.exists():
        print(f"ERROR: test_cases.json not found at {TEST_CASES}")
        sys.exit(1)

    with TEST_CASES.open(encoding="utf-8") as f:
        cases = json.load(f)

    print(f"Running {len(cases)} test cases against {base_url}/ai/analyze ...\n")

    # Health check
    try:
        with httpx.Client(timeout=5) as client:
            hc = client.get(f"{base_url}/health")
            hc.raise_for_status()
        print("[OK] Health check passed.\n")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] Health check failed: {exc}")
        print("   Is the service running? Start it with:")
        print("   cd ai-service && uvicorn main:app --port 8001\n")
        sys.exit(1)

    results = []
    with httpx.Client(timeout=30) as client:
        for i, case in enumerate(cases, 1):
            result = run_single(client, base_url, case)
            results.append(result)

            icon = "PASS" if result["predicted_category"] == result["expected_category"] else "FAIL"
            err  = f" ERR: {result['error']}" if result["error"] else ""
            print(
                f"[{i:02d}/{len(cases)}] [{icon}] {result['id']:<15} "
                f"expected={result['expected_category']:<25} "
                f"got={result['predicted_category']:<25} "
                f"{result['latency_ms']:.0f}ms{err}"
            )

    metrics      = compute_metrics(results)
    field_issues = field_spot_check(results)

    print(f"\n{'='*60}")
    print(f"  Category Accuracy   : {metrics['category_accuracy']:.1%}")
    print(f"  Approval Accuracy   : {metrics['approval_accuracy']:.1%}")
    print(f"  Human-Review Routing: {metrics['human_review_accuracy']:.1%}")
    print(f"  Average Latency     : {metrics['avg_latency_ms']:.0f} ms")
    print(f"  P95 Latency         : {metrics['p95_latency_ms']:.0f} ms")
    print(f"  Errors              : {metrics['errors']}")
    print(f"{'='*60}\n")

    if field_issues:
        print("Field extraction observations:")
        for obs in field_issues:
            print(f"  [!] {obs}")
        print()

    # Write markdown report
    report_path = Path(args.output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = generate_markdown_report(results, metrics, field_issues, base_url)
    report_path.write_text(report, encoding="utf-8")
    print(f"[OK] Evaluation report written to: {report_path}")

    # Exit 1 if accuracy below 70% (useful in CI)
    if metrics["category_accuracy"] < 0.70:
        print("[WARN] WARNING: category accuracy is below 70%.")
        sys.exit(1)


if __name__ == "__main__":
    main()
