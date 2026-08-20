#!/usr/bin/env python3
"""
scripts/health_check.py
========================
Pings all services and prints a clean OK/FAIL table.
Run this FIRST — 2 minutes before going on stage.

Usage:
    python scripts/health_check.py
    python scripts/health_check.py --watch   # re-checks every 10 seconds

Exit code 0 = all OK, exit code 1 = one or more services FAIL.
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

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8001")
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")

# ANSI colours
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"
DIM = "\033[2m"


def _ok(msg: str = "OK") -> str:
    return f"{GREEN}✓ {msg}{RESET}"


def _fail(msg: str) -> str:
    return f"{RED}✗ {msg}{RESET}"


def _warn(msg: str) -> str:
    return f"{YELLOW}⚠ {msg}{RESET}"


# ── Individual service checks ─────────────────────────────────────────────────

def check_backend() -> tuple[bool, str]:
    """GET /health on the backend."""
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            ai_status = data.get("ai_service", "unknown")
            detail = f"ai_service={ai_status}"
            if ai_status == "unreachable":
                return True, _warn(f"Backend OK but {detail}")
            return True, _ok(detail)
        return False, _fail(f"HTTP {resp.status_code}")
    except requests.ConnectionError:
        return False, _fail(f"Cannot connect to {BACKEND_URL}")
    except requests.Timeout:
        return False, _fail("Timeout after 5s")
    except Exception as exc:  # noqa: BLE001
        return False, _fail(str(exc))


def check_ai_service() -> tuple[bool, str]:
    """GET /health on the AI microservice."""
    try:
        resp = requests.get(f"{AI_SERVICE_URL}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            classifier = data.get("classifier", "unknown")
            return True, _ok(f"classifier={classifier}")
        return False, _fail(f"HTTP {resp.status_code}")
    except requests.ConnectionError:
        return False, _fail(f"Cannot connect to {AI_SERVICE_URL}")
    except requests.Timeout:
        return False, _fail("Timeout after 5s")
    except Exception as exc:  # noqa: BLE001
        return False, _fail(str(exc))


def check_notion() -> tuple[bool, str]:
    """Ping Notion API with a minimal authenticated request."""
    if not NOTION_API_KEY or NOTION_API_KEY.startswith("secret_your"):
        return False, _warn("NOTION_API_KEY not set — update integrations/.env")

    try:
        resp = requests.get(
            "https://api.notion.com/v1/users/me",
            headers={
                "Authorization": f"Bearer {NOTION_API_KEY}",
                "Notion-Version": "2022-06-28",
            },
            timeout=8,
        )
        if resp.status_code == 200:
            user = resp.json().get("name", "unknown")
            return True, _ok(f"authenticated as '{user}'")
        elif resp.status_code == 401:
            return False, _fail("Invalid API key (401)")
        else:
            return False, _fail(f"HTTP {resp.status_code}")
    except requests.ConnectionError:
        return False, _fail("Cannot reach api.notion.com — check internet/WiFi")
    except requests.Timeout:
        return False, _fail("Notion API timeout after 8s")
    except Exception as exc:  # noqa: BLE001
        return False, _fail(str(exc))


def check_email_provider() -> tuple[bool, str]:
    """Check EMAIL_PROVIDER setting and validate it's not a surprise."""
    provider = os.getenv("EMAIL_PROVIDER", "mock").lower()
    if provider == "mock":
        return True, _ok("mock (safe, no network needed)")
    elif provider == "mailtrap":
        # Try a quick TCP connect to Mailtrap's SMTP
        import socket
        host = os.getenv("MAILTRAP_HOST", "sandbox.smtp.mailtrap.io")
        port = int(os.getenv("MAILTRAP_PORT", "2525"))
        try:
            with socket.create_connection((host, port), timeout=5):
                pass
            return True, _ok(f"mailtrap reachable at {host}:{port}")
        except OSError as exc:
            return False, _fail(f"Cannot reach Mailtrap {host}:{port} — {exc}")
    elif provider == "broken":
        return False, _warn("EMAIL_PROVIDER=broken (intentional failure mode — for Test 6 only!)")
    else:
        return False, _warn(f"Unknown EMAIL_PROVIDER={provider!r}")


def check_action_log() -> tuple[bool, str]:
    """Verify the action log directory exists and is writable."""
    log_dir = Path(__file__).parent.parent / "integrations" / "logs"
    try:
        log_dir.mkdir(exist_ok=True)
        test_file = log_dir / ".health_write_test"
        test_file.write_text("ok")
        test_file.unlink()
        return True, _ok(f"{log_dir}")
    except Exception as exc:  # noqa: BLE001
        return False, _fail(f"Cannot write to {log_dir}: {exc}")


# ── Table printer ─────────────────────────────────────────────────────────────

def print_table(results: list[tuple[str, bool, str]], timestamp: str) -> bool:
    """Print the health check table. Returns True if all services are OK."""
    col_name = 28
    col_status = 8

    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════════╗")
    print(f"║   AI College Request Automation — Health Check            ║")
    print(f"║   {timestamp:<55}║")
    print(f"╚══════════════════════════════════════════════════════════╝{RESET}\n")

    header = f"  {'Service':<{col_name}} {'Status':<{col_status}} Detail"
    print(BOLD + header + RESET)
    print("  " + "─" * 70)

    all_ok = True
    for name, ok, detail in results:
        status = f"{GREEN}OK{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  {name:<{col_name}} {status:<{col_status + 9}} {detail}")
        if not ok:
            all_ok = False

    print("\n  " + "─" * 70)
    if all_ok:
        print(f"  {GREEN}{BOLD}✓ All systems GO — safe to go on stage.{RESET}\n")
    else:
        print(f"  {RED}{BOLD}✗ One or more services are down. See docs/troubleshooting.md{RESET}\n")

    return all_ok


def run_checks() -> bool:
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    checks = [
        ("Backend (localhost:8000)", *check_backend()),
        ("AI Service (localhost:8001)", *check_ai_service()),
        ("Notion API", *check_notion()),
        ("Email Provider", *check_email_provider()),
        ("Action Log (write test)", *check_action_log()),
    ]

    return print_table(checks, ts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Health check all services")
    parser.add_argument(
        "--watch", action="store_true",
        help="Re-run checks every 10 seconds until Ctrl+C"
    )
    args = parser.parse_args()

    if args.watch:
        print(f"{DIM}Watching... (Ctrl+C to stop){RESET}")
        try:
            while True:
                all_ok = run_checks()
                time.sleep(10)
        except KeyboardInterrupt:
            print("\nStopped.")
            sys.exit(0)
    else:
        all_ok = run_checks()
        sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
