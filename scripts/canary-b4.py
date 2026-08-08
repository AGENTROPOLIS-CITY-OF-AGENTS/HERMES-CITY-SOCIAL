#!/usr/bin/env python3
"""B4 canary runner: B3 pipeline -> B4 surface (fixture/mock only).

Usage:
    python scripts/canary-b4.py

Exit 0 = canary PASS, 1 = canary FAIL, 2 = harness error.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from surface.ingest import run_canary  # noqa: E402


def main() -> int:
    try:
        report = run_canary()
    except Exception as exc:  # pragma: no cover - harness error path
        print("CANARY HARNESS ERROR:", exc)
        return 2

    # JSON-safe report (drop live service/repo handles)
    printable = {k: v for k, v in report.items() if k not in ("service", "repo")}
    print(json.dumps(printable, indent=2, sort_keys=True, default=str))

    # Assert the invariant that the canary must prove.
    checks = []
    for platform, info in report["platforms"].items():
        checks.append((info["released"] > 0, "platform %s released fixtures" % platform))
    checks.append((report["adversarial"]["quarantined_outcome"]["stored"] is False,
                   "quarantined event never stored"))
    checks.append((report["adversarial"]["credential_event_outcome"]["stored"] is True,
                   "credential/injection event handled by membrane"))
    checks.append((report["draft"]["approval_state"] == "pending",
                   "draft pending approval, never published"))
    checks.append((report["live"]["LIVE_STATUS"] == "LIVE=BLOCKED", "LIVE=BLOCKED"))

    failed = [name for ok, name in checks if not ok]
    if failed:
        print("CANARY FAIL:", failed)
        return 1
    print("CANARY PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
