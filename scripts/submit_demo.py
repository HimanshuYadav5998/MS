#!/usr/bin/env python3
"""
scripts/submit_demo.py
=======================
Submits a demo request from demo_data/sample_requests.json to the backend.
Usage:
    python scripts/submit_demo.py                     # submits request #1 (default)
    python scripts/submit_demo.py --id 2              # submits the Hinglish request
    python scripts/submit_demo.py --all               # submits all 5 in sequence
    python scripts/submit_demo.py --id 5 --dry-run    # prints payload, does not send

This is the script to run on stage instead of typing curl commands.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "integrations" / ".env")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
DEMO_DATA = Path(__file__).parent.parent / "demo_data" / "sample_requests.json"
ENDPOINT = f"{BACKEND_URL}/webhook/request"

BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"


def load_requests() -> list[dict]:
    if not DEMO_DATA.exists():
        print(f"{RED}ERROR: {DEMO_DATA} not found.{RESET}")
        sys.exit(1)
    return json.loads(DEMO_DATA.read_text(encoding="utf-8"))


def submit(req: dict, dry_run: bool = False) -> None:
    payload = {
        "text": req["text"],
        "requester_name": req["requester_name"],
        "requester_role": req["requester_role"],
    }

    print(f"\n{BOLD}{CYAN}══ Demo Request #{req['id']}: {req['label']} ══{RESET}")
    print(f"{YELLOW}Category:{RESET} {req['category']}")
    print(f"{YELLOW}Text:{RESET}     {req['text']}")
    print(f"{YELLOW}From:{RESET}     {req['requester_name']} ({req['requester_role']})")
    if req.get("demo_notes"):
        print(f"\n{BOLD}Demo note:{RESET} {req['demo_notes']}\n")

    if dry_run:
        print(f"{YELLOW}[DRY RUN] Payload:{RESET}")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(f"\n{BOLD}→ Submitting to {ENDPOINT} ...{RESET}")
    try:
        resp = requests.post(ENDPOINT, json=payload, timeout=15)
        if resp.status_code in (200, 201):
            data = resp.json()
            request_id = data.get("request_id") or data.get("id", "?")
            print(f"{GREEN}✓ Submitted! request_id = {request_id}{RESET}")
            print(f"  Track it: GET {BACKEND_URL}/requests/{request_id}")
        else:
            print(f"{RED}✗ Failed: HTTP {resp.status_code}{RESET}")
            print(resp.text[:500])
    except requests.ConnectionError:
        print(
            f"{RED}✗ Cannot reach backend at {BACKEND_URL}. "
            f"Is it running? Run: python scripts/health_check.py{RESET}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit demo requests to the backend")
    parser.add_argument("--id", type=int, default=1, help="Request ID from sample_requests.json")
    parser.add_argument("--all", action="store_true", help="Submit all demo requests")
    parser.add_argument("--dry-run", action="store_true", help="Print payload, don't send")
    args = parser.parse_args()

    requests_data = load_requests()
    req_map = {r["id"]: r for r in requests_data}

    if args.all:
        for req in requests_data:
            submit(req, dry_run=args.dry_run)
    else:
        req = req_map.get(args.id)
        if not req:
            print(f"{RED}No request with id={args.id}. Available: {list(req_map.keys())}{RESET}")
            sys.exit(1)
        submit(req, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
