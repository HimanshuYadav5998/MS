#!/usr/bin/env python3
"""
scripts/reset_demo.py
======================
Resets ALL demo state between rehearsals and before the live demo.

What it resets:
  1. Deletes all pages from Notion Requests, Approvals, and Run Log databases
  2. Deletes / re-creates the local SQLite database (backend/requests.db)
  3. Clears the integrations/logs/ action log files
  4. Prints a "CLEAN SLATE" confirmation

Usage:
    python scripts/reset_demo.py                  # full reset
    python scripts/reset_demo.py --notion-only    # only Notion
    python scripts/reset_demo.py --local-only     # only SQLite + logs
    python scripts/reset_demo.py --dry-run        # show what WOULD be deleted

⚠ WARNING: This permanently deletes data from Notion. Only run in your
  sandbox workspace, never in a production Notion account.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "integrations" / ".env")

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_REQUESTS_DB_ID = os.getenv("NOTION_REQUESTS_DB_ID", "")
NOTION_RUNLOG_DB_ID = os.getenv("NOTION_RUNLOG_DB_ID", "")
NOTION_APPROVALS_DB_ID = os.getenv("NOTION_APPROVALS_DB_ID", "")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

PROJECT_ROOT = Path(__file__).parent.parent
SQLITE_PATHS = [
    PROJECT_ROOT / "backend" / "requests.db",
    PROJECT_ROOT / "backend" / "app" / "requests.db",
    PROJECT_ROOT / "backend" / "database.db",
]
LOG_DIR = PROJECT_ROOT / "integrations" / "logs"

BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"
DIM = "\033[2m"


# ── Notion helpers ────────────────────────────────────────────────────────────

def _notion_query_all_pages(db_id: str) -> list[dict]:
    """Retrieve all page IDs from a Notion database."""
    pages = []
    cursor = None
    while True:
        body: dict = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        resp = requests.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers=NOTION_HEADERS,
            json=body,
            timeout=15,
        )
        if resp.status_code == 404:
            print(f"  {YELLOW}⚠ DB {db_id[:8]}… not found (may not be set up yet){RESET}")
            return []
        resp.raise_for_status()
        data = resp.json()
        pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return pages


def _notion_archive_page(page_id: str) -> bool:
    """Archive (soft-delete) a Notion page."""
    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=NOTION_HEADERS,
        json={"archived": True},
        timeout=10,
    )
    return resp.status_code == 200


def reset_notion_database(db_id: str, db_name: str, dry_run: bool = False) -> int:
    """Archive all pages in a Notion database. Returns page count deleted."""
    if not db_id or db_id.startswith("your_"):
        print(f"  {YELLOW}⚠ {db_name}: DB ID not configured, skipping.{RESET}")
        return 0

    print(f"\n  Querying {db_name}...", end="", flush=True)
    pages = _notion_query_all_pages(db_id)
    print(f" {len(pages)} pages found.")

    if not pages:
        print(f"  {GREEN}✓ {db_name}: already empty.{RESET}")
        return 0

    if dry_run:
        print(f"  {YELLOW}[DRY RUN] Would archive {len(pages)} pages from {db_name}{RESET}")
        return len(pages)

    archived = 0
    for page in pages:
        page_id = page["id"]
        if _notion_archive_page(page_id):
            archived += 1
        else:
            print(f"  {YELLOW}⚠ Failed to archive page {page_id}{RESET}")
        time.sleep(0.05)  # Gentle rate limit respect

    print(f"  {GREEN}✓ {db_name}: archived {archived}/{len(pages)} pages.{RESET}")
    return archived


# ── Local state ───────────────────────────────────────────────────────────────

def reset_sqlite(dry_run: bool = False) -> None:
    """Delete the SQLite database file(s) so the backend starts fresh."""
    found = False
    for db_path in SQLITE_PATHS:
        if db_path.exists():
            found = True
            if dry_run:
                print(f"  {YELLOW}[DRY RUN] Would delete {db_path}{RESET}")
            else:
                db_path.unlink()
                print(f"  {GREEN}✓ Deleted {db_path}{RESET}")

    if not found:
        print(f"  {DIM}No SQLite DB found at expected paths (backend may not have run yet){RESET}")


def reset_action_logs(dry_run: bool = False) -> None:
    """Clear the action log files in integrations/logs/."""
    if not LOG_DIR.exists():
        print(f"  {DIM}Log directory {LOG_DIR} does not exist, nothing to clear.{RESET}")
        return

    log_files = list(LOG_DIR.glob("*.log")) + list(LOG_DIR.glob("*.jsonl"))
    if not log_files:
        print(f"  {DIM}No log files found in {LOG_DIR}.{RESET}")
        return

    for f in log_files:
        if dry_run:
            print(f"  {YELLOW}[DRY RUN] Would clear {f.name}{RESET}")
        else:
            f.write_text("")  # Clear content but keep file
            print(f"  {GREEN}✓ Cleared {f.name}{RESET}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Reset all demo state")
    parser.add_argument("--notion-only", action="store_true", help="Only reset Notion")
    parser.add_argument("--local-only", action="store_true", help="Only reset SQLite + logs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be reset, don't do it")
    args = parser.parse_args()

    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════════╗")
    print(f"║   AI College Request Automation — Demo Reset              ║")
    if args.dry_run:
        print(f"║   {YELLOW}DRY RUN — no changes will be made{RESET}{CYAN}                      ║")
    print(f"╚══════════════════════════════════════════════════════════╝{RESET}\n")

    if args.dry_run:
        print(f"{YELLOW}⚠ DRY RUN MODE — showing what would be deleted.{RESET}\n")

    total_deleted = 0

    # ── Notion reset
    if not args.local_only:
        if not NOTION_API_KEY or NOTION_API_KEY.startswith("secret_your"):
            print(f"{YELLOW}⚠ NOTION_API_KEY not configured — skipping Notion reset.{RESET}")
            print(f"  Set NOTION_API_KEY in integrations/.env\n")
        else:
            print(f"{BOLD}Resetting Notion databases...{RESET}")
            total_deleted += reset_notion_database(
                NOTION_REQUESTS_DB_ID, "Requests DB", args.dry_run
            )
            total_deleted += reset_notion_database(
                NOTION_APPROVALS_DB_ID, "Approvals DB", args.dry_run
            )
            total_deleted += reset_notion_database(
                NOTION_RUNLOG_DB_ID, "Run Log DB", args.dry_run
            )

    # ── Local reset
    if not args.notion_only:
        print(f"\n{BOLD}Resetting local state...{RESET}")
        reset_sqlite(args.dry_run)
        reset_action_logs(args.dry_run)

    # ── Summary
    print(f"\n{'─' * 60}")
    if args.dry_run:
        print(f"{YELLOW}{BOLD}[DRY RUN] Would have archived {total_deleted} Notion pages.{RESET}")
    else:
        print(f"{GREEN}{BOLD}✓ CLEAN SLATE — system is ready for demo.{RESET}")
        print(f"  → Start backend:     cd backend && uvicorn app.main:app --reload")
        print(f"  → Start AI service:  cd ai-service && uvicorn app.main:app --port 8001 --reload")
        print(f"  → Health check:      python scripts/health_check.py")
        print(f"  → Submit demo req:   python scripts/submit_demo.py --id 1")
    print()


if __name__ == "__main__":
    main()
