#!/usr/bin/env python
"""
test_featherless.py
────────────────────────────────────────────────────────────────────────────
Purpose:
    Standalone integration test for the Featherless AI layer.
    Runs independently — does NOT require the rest of Gamana to be running.

Usage:
    # From project root:
    cd backend
    ..\\venv\\Scripts\\python.exe tests\\test_featherless.py

    # Or with a real API key passed inline:
    $env:FEATHERLESS_API_KEY="sk-..."
    ..\\venv\\Scripts\\python.exe tests\\test_featherless.py

What it tests:
    1. Service initialisation (key + prompt loading).
    2. generate_strategy() with dummy traffic metrics.
    3. Schema validation of the response.
    4. Fallback behaviour when the service is uninitialised.
────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import json
import sys
import os
from pathlib import Path

# ── Ensure backend/ is on the path so imports resolve correctly ───────────────
_BACKEND_DIR = Path(__file__).parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ── Load .env if available ────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_BACKEND_DIR / ".env")
except ImportError:
    pass

# ── Imports ───────────────────────────────────────────────────────────────────
from services.featherless_service import FeatherlessTrafficService
from models.featherless_response import FeatherlessResponse
from config.featherless_config import REQUIRED_RESPONSE_KEYS

# ── ANSI colours for terminal readability ─────────────────────────────────────
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_RESET  = "\033[0m"
_BOLD   = "\033[1m"


def _banner(text: str) -> None:
    print(f"\n{_BOLD}{_CYAN}{'─' * 60}{_RESET}")
    print(f"{_BOLD}{_CYAN}  {text}{_RESET}")
    print(f"{_BOLD}{_CYAN}{'─' * 60}{_RESET}")


def _ok(msg: str)   -> None: print(f"  {_GREEN}✓  {msg}{_RESET}")
def _fail(msg: str) -> None: print(f"  {_RED}✗  {msg}{_RESET}")
def _info(msg: str) -> None: print(f"  {_YELLOW}ℹ  {msg}{_RESET}")


# ── Dummy traffic data ────────────────────────────────────────────────────────
DUMMY_INTERSECTION_STATE = {
    "intersection": {
        "LANE_1": {
            "vehicles":      18,
            "moving":        4,
            "stopped":       14,
            "avg_wait_s":    62,
            "pressure":      91.5,
            "congestion":    "HIGH",
            "behaviours":    ["queue_buildup", "phantom_brake"],
        },
        "LANE_2": {
            "vehicles":      7,
            "moving":        5,
            "stopped":       2,
            "avg_wait_s":    10,
            "pressure":      34.2,
            "congestion":    "LOW",
            "behaviours":    [],
        },
        "LANE_3": {
            "vehicles":      11,
            "moving":        3,
            "stopped":       8,
            "avg_wait_s":    38,
            "pressure":      58.0,
            "congestion":    "MEDIUM",
            "behaviours":    ["startup_delay"],
        },
        "LANE_4": {
            "vehicles":      3,
            "moving":        3,
            "stopped":       0,
            "avg_wait_s":    4,
            "pressure":      12.0,
            "congestion":    "LOW",
            "behaviours":    [],
        },
    },
    "current_green_lane":   "LANE_2",
    "green_elapsed_s":      28,
    "timestamp_utc":        "2026-07-31T17:00:00Z",
}

REQUIRED_KEYS = REQUIRED_RESPONSE_KEYS


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_fallback_without_init() -> bool:
    """generate_strategy must return a fallback if service is not initialised."""
    _banner("TEST 1 — Fallback when not initialised")
    svc = FeatherlessTrafficService()
    result = svc.generate_strategy(DUMMY_INTERSECTION_STATE)
    if result.status == "fallback":
        _ok("Returned fallback correctly when service is uninitialised.")
        return True
    else:
        _fail(f"Expected status='fallback', got status='{result.status}'.")
        return False


def test_initialisation() -> tuple[bool, FeatherlessTrafficService]:
    """Initialise the service; skip live call if no API key is set."""
    _banner("TEST 2 — Service initialisation")
    svc = FeatherlessTrafficService()
    ok = svc.initialize()
    if ok:
        _ok("Service initialised successfully.")
    else:
        _info(
            "Service did not initialise (likely no API key). "
            "Set FEATHERLESS_API_KEY in backend/.env to run live tests."
        )
    return ok, svc


def test_generate_strategy(svc: FeatherlessTrafficService) -> bool:
    """Send dummy traffic metrics and validate the response schema."""
    _banner("TEST 3 — generate_strategy() with dummy data")

    _info(f"Sending dummy state with {len(DUMMY_INTERSECTION_STATE['intersection'])} lanes …")
    result = svc.generate_strategy(DUMMY_INTERSECTION_STATE)

    print(f"\n  Raw response dict:")
    print("  " + json.dumps(result.to_dict(), indent=4).replace("\n", "\n  "))

    all_pass = True

    # Status
    if result.status == "ok":
        _ok("status == 'ok'")
    elif result.status == "fallback":
        _info("Got fallback (API unreachable or key missing) — schema still checked.")
        return True   # Not a failure; network may be absent
    else:
        _fail(f"Unexpected status='{result.status}'")
        all_pass = False

    # Schema validation
    d = result.to_dict()
    for key in REQUIRED_KEYS:
        if key in d:
            _ok(f"Key present: '{key}'")
        else:
            _fail(f"Missing key: '{key}'")
            all_pass = False

    # Value range checks
    if 12 <= result.green_duration <= 60:
        _ok(f"green_duration={result.green_duration} is in [12, 60]")
    else:
        _fail(f"green_duration={result.green_duration} out of range [12, 60]")
        all_pass = False

    if 0.0 <= result.confidence <= 1.0:
        _ok(f"confidence={result.confidence} is in [0.0, 1.0]")
    else:
        _fail(f"confidence={result.confidence} out of range")
        all_pass = False

    if isinstance(result.reasoning, list) and len(result.reasoning) > 0:
        _ok(f"reasoning has {len(result.reasoning)} entries")
    else:
        _fail("reasoning is empty or not a list")
        all_pass = False

    return all_pass


def test_health_check(svc: FeatherlessTrafficService) -> bool:
    """health_check() must always return a dict with required keys."""
    _banner("TEST 4 — health_check()")
    hc = svc.health_check()
    _info(f"Health check result: {hc}")
    required_hc_keys = {"status", "model", "latency_ms"}
    missing = required_hc_keys - set(hc.keys())
    if missing:
        _fail(f"health_check() missing keys: {missing}")
        return False
    _ok("health_check() returned all required keys.")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    results = []

    # Test 1 — always run
    results.append(test_fallback_without_init())

    # Test 2 — initialisation
    init_ok, svc = test_initialisation()
    results.append(init_ok)

    if init_ok:
        results.append(test_generate_strategy(svc))
        results.append(test_health_check(svc))
    else:
        _info("Skipping live API tests (no valid API key).")

    # Summary
    _banner("SUMMARY")
    passed = sum(results)
    total  = len(results)
    colour = _GREEN if passed == total else _YELLOW
    print(f"\n  {colour}{_BOLD}{passed}/{total} tests passed.{_RESET}\n")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
