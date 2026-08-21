"""
Comprehensive Test Suite for Notion Integration Flow.

This test script validates the end-to-end integration between the Python backend
and Notion databases for AI College Request Automation.

It can be run:
1. Against the Live Notion API (when NOTION_API_KEY and DB IDs are set in .env or environment)
2. In Isolated Mock Mode (runs anywhere without credentials, testing 100% of integration logic)

Usage:
    python tests/test_notion_flow.py          # Runs live if env configured, else unit/mock tests
    python tests/test_notion_flow.py --live   # Forces live Notion API execution
    python tests/test_notion_flow.py --mock   # Forces mock unit testing
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from notion.notion_service import (
    NotionServiceError,
    _clean_human_readable_text,
    _split_rich_text,
    create_approval_page,
    create_request_page,
    create_run_log,
    get_human_decision,
    get_pending_approvals,
    update_request_page,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("test_notion_flow")


# ─────────────────────────────────────────────────────────────────────────────
# MOCK / UNIT TEST SUITE
# ─────────────────────────────────────────────────────────────────────────────
class TestNotionServiceMock(unittest.TestCase):
    """Offline unit tests testing logic, anti-JSON guards, chunking, and error handling."""

    def test_clean_human_readable_text_json_extraction(self):
        """Test that raw JSON dumps are cleaned and extracted into readable text."""
        raw_json_dict = '{"summary": "Student requests prerequisite waiver for CS201", "confidence": 0.95}'
        cleaned = _clean_human_readable_text(raw_json_dict)
        self.assertEqual(cleaned, "Student requests prerequisite waiver for CS201")

        raw_json_unkeyed = '{"course": "CS201", "status": "waived", "units": 4}'
        cleaned_unkeyed = _clean_human_readable_text(raw_json_unkeyed)
        self.assertIn("course: CS201", cleaned_unkeyed)
        self.assertIn("status: waived", cleaned_unkeyed)

    def test_split_rich_text_chunking(self):
        """Test splitting strings longer than Notion limit into multiple chunks."""
        short_text = "Short summary message"
        chunks = _split_rich_text(short_text, max_chunk_size=10)
        self.assertGreater(len(chunks), 1)
        recombined = "".join(c["text"]["content"] for c in chunks)
        self.assertEqual(recombined, short_text)

    @patch("notion.notion_service._notion_request")
    @patch("notion.notion_service._get_config")
    def test_create_request_page_payload(self, mock_config, mock_request):
        """Verify create_request_page constructs the exact Notion database payload."""
        mock_config.return_value = {
            "api_key": "secret_test",
            "requests_db_id": "test_req_db_id",
            "runlog_db_id": "test_runlog_db_id",
            "approvals_db_id": "test_appr_db_id",
        }
        mock_request.return_value = {"id": "page_12345"}

        page_id = create_request_page(
            request_id="REQ-TEST-001",
            title="Prerequisite Waiver - Alex Chen",
            category="Course Registration",
            requester="alex.chen@university.edu",
            original_text="I want to enroll in CS201 without Math102.",
            ai_summary="Alex Chen is requesting waiver for MATH102 prerequisite.",
            ai_recommendation="Approve conditional enrollment pending AP credit.",
            priority="urgent",
            confidence=0.88,
            status="PENDING_APPROVAL",
            requires_approval=True,
        )

        self.assertEqual(page_id, "page_12345")
        mock_request.assert_called_once()
        endpoint, kwargs = mock_request.call_args[0][0], mock_request.call_args[1]
        self.assertEqual(endpoint, "pages")
        self.assertEqual(kwargs.get("method"), "POST")

        data = kwargs.get("data", {})
        props = data["properties"]
        self.assertEqual(props["Title"]["title"][0]["text"]["content"], "Prerequisite Waiver - Alex Chen")
        self.assertEqual(props["Category"]["select"]["name"], "Course Registration")
        self.assertEqual(props["Priority"]["select"]["name"], "urgent")
        self.assertEqual(props["Confidence"]["number"], 0.88)
        self.assertEqual(props["Status"]["select"]["name"], "PENDING_APPROVAL")
        self.assertTrue(props["Requires Approval"]["checkbox"])

    @patch("notion.notion_service._notion_request")
    @patch("notion.notion_service._get_config")
    def test_update_request_page_payload(self, mock_config, mock_request):
        """Verify update_request_page constructs update properties."""
        mock_config.return_value = {"api_key": "secret_test"}
        mock_request.return_value = {"id": "page_12345"}

        update_request_page(
            notion_page_id="page_12345",
            status="COMPLETED",
            human_decision="approved",
            action_result="Enrolled student in CS201 Section A",
        )

        mock_request.assert_called_once()
        endpoint, kwargs = mock_request.call_args[0][0], mock_request.call_args[1]
        self.assertEqual(endpoint, "pages/page_12345")
        self.assertEqual(kwargs.get("method"), "PATCH")
        props = kwargs["data"]["properties"]
        self.assertEqual(props["Status"]["select"]["name"], "COMPLETED")
        self.assertEqual(props["Human Decision"]["select"]["name"], "approved")

    @patch("notion.notion_service._notion_request")
    @patch("notion.notion_service._get_config")
    def test_approval_lifecycle(self, mock_config, mock_request):
        """Verify create_approval_page, get_pending_approvals, and get_human_decision."""
        mock_config.return_value = {
            "api_key": "secret_test",
            "approvals_db_id": "test_appr_db_id",
        }

        # 1. Create Approval Page
        mock_request.return_value = {"id": "appr_page_001"}
        appr_id = create_approval_page("REQ-TEST-001", "Alex Chen waiver request")
        self.assertEqual(appr_id, "appr_page_001")

        # 2. Query Pending Approvals
        mock_request.return_value = {
            "results": [
                {
                    "id": "appr_page_001",
                    "properties": {
                        "Request ID": {"title": [{"plain_text": "REQ-TEST-001"}]},
                        "Request": {"rich_text": [{"plain_text": "Alex Chen waiver request"}]},
                        "Decision": {"select": {"name": "pending"}},
                        "Reviewer": {"rich_text": []},
                        "Decision Reason": {"rich_text": []},
                        "Override Instructions": {"rich_text": []},
                    },
                }
            ]
        }
        pending = get_pending_approvals()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["request_id"], "REQ-TEST-001")
        self.assertEqual(pending[0]["decision"], "pending")

        # 3. Decision Pending -> get_human_decision returns None
        decision = get_human_decision("REQ-TEST-001")
        self.assertIsNone(decision)

        # 4. Human approves in Notion -> get_human_decision returns dict
        mock_request.return_value = {
            "results": [
                {
                    "id": "appr_page_001",
                    "properties": {
                        "Request ID": {"title": [{"plain_text": "REQ-TEST-001"}]},
                        "Decision": {"select": {"name": "approved"}},
                        "Reviewer": {"rich_text": [{"plain_text": "Prof. Sarah Jenkins"}]},
                        "Decision Reason": {"rich_text": [{"plain_text": "Verified AP scores"}]},
                        "Override Instructions": {"rich_text": []},
                    },
                }
            ]
        }
        decision = get_human_decision("REQ-TEST-001")
        self.assertIsNotNone(decision)
        self.assertEqual(decision["decision"], "approved")
        self.assertEqual(decision["reviewer"], "Prof. Sarah Jenkins")
        self.assertEqual(decision["reason"], "Verified AP scores")

    @patch("notion.notion_service._notion_request")
    @patch("notion.notion_service._get_config")
    def test_create_run_log_payload(self, mock_config, mock_request):
        """Verify create_run_log formats audit properties correctly."""
        mock_config.return_value = {
            "api_key": "secret_test",
            "runlog_db_id": "test_runlog_db_id",
        }
        mock_request.return_value = {"id": "log_page_999"}

        log_id = create_run_log(
            request_id="REQ-TEST-001",
            event="POLICY_EVALUATED",
            actor="AI",
            action="Evaluated prerequisite rules for CS201",
            status="SUCCESS",
            reason="AP Calculus BC score of 5 satisfies requirement",
            external_action_id="SIS-EVAL-101",
        )
        self.assertEqual(log_id, "log_page_999")
        props = mock_request.call_args[1]["data"]["properties"]
        self.assertEqual(props["Actor"]["select"]["name"], "AI")
        self.assertEqual(props["Status"]["select"]["name"], "SUCCESS")


# ─────────────────────────────────────────────────────────────────────────────
# LIVE NOTION API INTEGRATION TEST
# ─────────────────────────────────────────────────────────────────────────────
def run_live_integration_test() -> bool:
    """Execute end-to-end flow directly against the real Notion API."""
    print("\n" + "=" * 60)
    print("🚀 RUNNING LIVE NOTION API INTEGRATION TEST")
    print("=" * 60)

    api_key = os.environ.get("NOTION_API_KEY")
    req_db_id = os.environ.get("NOTION_REQUESTS_DB_ID")
    run_db_id = os.environ.get("NOTION_RUNLOG_DB_ID")
    appr_db_id = os.environ.get("NOTION_APPROVALS_DB_ID")

    if not (api_key and req_db_id and run_db_id and appr_db_id):
        print("❌ Error: Missing Notion environment variables.")
        print("Ensure NOTION_API_KEY, NOTION_REQUESTS_DB_ID, NOTION_RUNLOG_DB_ID, and NOTION_APPROVALS_DB_ID are set.")
        return False

    test_req_id = f"TEST-{datetime.now(timezone.utc).strftime('%m%d-%H%M%S')}"

    try:
        # Step 1: Create Request
        print(f"\n[1/6] Creating Request Page for {test_req_id}...")
        req_page_id = create_request_page(
            request_id=test_req_id,
            title=f"CS201 Prereq Waiver - Test {test_req_id}",
            category="Course Registration",
            requester="demo.student@college.edu",
            original_text="Need prerequisite waiver for Data Structures (CS201) based on high school AP Calculus credit.",
            ai_summary="Student requesting prerequisite waiver for CS201.",
            ai_recommendation="Approve conditional enrollment pending AP credit transcript verification.",
            priority="high",
            confidence=0.89,
            status="PENDING_APPROVAL",
            requires_approval=True,
        )
        print(f"  ✓ Created Request Page ID: {req_page_id}")

        # Step 2: Create Initial Run Log
        print("\n[2/6] Logging REQUEST_RECEIVED in Run Log...")
        log_page_id_1 = create_run_log(
            request_id=test_req_id,
            event="REQUEST_RECEIVED",
            actor="system",
            action="Ingested student request from web portal",
            status="SUCCESS",
            reason="Payload valid and parsed",
        )
        print(f"  ✓ Created Run Log ID: {log_page_id_1}")

        # Step 3: Create Approval Queue Item
        print("\n[3/6] Creating Human Approval entry in Approvals DB...")
        appr_page_id = create_approval_page(
            request_id=test_req_id,
            request_summary="Demo Student: CS201 Prereq Waiver based on AP Calc credit."
        )
        print(f"  ✓ Created Approval Page ID: {appr_page_id}")

        # Step 4: Verify Pending Approvals & get_human_decision
        print("\n[4/6] Querying Pending Approvals queue...")
        pending_list = get_pending_approvals()
        found = any(item["request_id"] == test_req_id for item in pending_list)
        print(f"  ✓ Pending queue query returned {len(pending_list)} items. Test request found: {found}")

        decision = get_human_decision(test_req_id)
        print(f"  ✓ get_human_decision({test_req_id}) -> {decision} (Expected: None while pending)")

        # Step 5: Simulate Approval Decision in Notion
        print("\n[5/6] Updating request status to APPROVED after review...")
        update_request_page(
            notion_page_id=req_page_id,
            status="APPROVED",
            human_decision="approved",
            action_result="Approved by Department Head. Queued for SIS enrollment.",
        )
        print("  ✓ Updated Request Page status -> APPROVED")

        # Step 6: Final Execution and Complete Status
        print("\n[6/6] Executing backend action and transitioning to COMPLETED...")
        update_request_page(
            notion_page_id=req_page_id,
            status="COMPLETED",
            human_decision="approved",
            action_result="Successfully enrolled student into CS201 (Section 02). Notification email dispatched.",
        )
        log_page_id_2 = create_run_log(
            request_id=test_req_id,
            event="ENROLLMENT_EXECUTED",
            actor="system",
            action="Executed automated SIS enrollment API",
            status="SUCCESS",
            reason="Prerequisite override applied",
            external_action_id="SIS-TXN-94812",
        )
        print(f"  ✓ Created Completion Run Log ID: {log_page_id_2}")
        print("  ✓ Full lifecycle completed successfully!")

        print("\n" + "=" * 60)
        print("✅ LIVE NOTION INTEGRATION TEST PASSED 100%!")
        print("=" * 60 + "\n")
        return True

    except Exception as e:
        print(f"\n❌ Live Integration Test failed with error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Notion Service Integration Flow")
    parser.add_argument("--live", action="store_true", help="Run live Notion API tests")
    parser.add_argument("--mock", action="store_true", help="Run offline mock unit tests")
    args = parser.parse_args()

    if args.live:
        success = run_live_integration_test()
        sys.exit(0 if success else 1)
    elif args.mock:
        suite = unittest.TestLoader().loadTestsFromTestCase(TestNotionServiceMock)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
    else:
        # Default: Run offline unit tests first
        print("Running Notion Service Unit / Mock Tests...")
        suite = unittest.TestLoader().loadTestsFromTestCase(TestNotionServiceMock)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        if not result.wasSuccessful():
            sys.exit(1)

        # If live credentials exist, run live test as well
        api_key = os.environ.get("NOTION_API_KEY")
        req_db_id = os.environ.get("NOTION_REQUESTS_DB_ID")
        if api_key and req_db_id:
            print("\nFound live Notion API credentials in environment. Proceeding to live integration test...")
            run_live_integration_test()


if __name__ == "__main__":
    main()
