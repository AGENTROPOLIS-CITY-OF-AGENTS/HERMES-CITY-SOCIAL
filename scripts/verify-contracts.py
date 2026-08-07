#!/usr/bin/env python3
"""HERMES-SOCIAL contract verification gate (B2).

Ordered checks:
  1. PYTHON_SYNTAX  — py_compile every test/script module.
  2. UNIT_TESTS     — schema + policy suites via ephemeral uv deps.
  3. SECRET_SCAN    — gitleaks full history (skipped with warning if unavailable).
  4. GIT_DIFF_CHECK — git diff --check.

Exit 0 = pass; non-zero = fail.
"""
import os
import subprocess
import sys
import py_compile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES = [
    "tests/test_schemas.py",
    "tests/test_policies.py",
    "tests/test_connectors.py",
    "tests/test_membrane.py",
    "scripts/verify-contracts.py",
    "connectors/base.py",
    "connectors/checkpoint.py",
    "connectors/errors.py",
    "connectors/manifest.py",
    "connectors/registry.py",
    "connectors/providers/__init__.py",
    "connectors/providers/x_provider.py",
    "connectors/providers/discord_provider.py",
    "connectors/providers/farcaster_provider.py",
    "connectors/fixtures/fixture_providers.py",
    "membrane/__init__.py",
    "membrane/bus.py",
    "membrane/dedup.py",
    "membrane/metrics.py",
    "membrane/pipeline.py",
    "membrane/policy.py",
    "membrane/quarantine.py",
    "membrane/risk.py",
    "membrane/sanitize.py",
]


def run(cmd, cwd=ROOT):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def main():
    fails = []

    print("== 1. PYTHON_SYNTAX ==")
    for mod in MODULES:
        try:
            py_compile.compile(os.path.join(ROOT, mod), doraise=True)
            print("  ok", mod)
        except py_compile.PyCompileError as exc:
            fails.append("PYTHON_SYNTAX %s: %s" % (mod, exc))
            print("  FAIL", mod)

    print("== 2. UNIT_TESTS ==")
    r = run(["uv", "run", "--with", "jsonschema", "--with", "pyyaml",
             "python", "-m", "unittest", "discover", "-s", "tests", "-v"])
    print(r.stdout[-5000:] if r.stdout else r.stderr[-2000:])
    if r.returncode != 0:
        fails.append("UNIT_TESTS failed (rc=%s)" % r.returncode)

    print("== 3. SECRET_SCAN ==")
    gitleaks = None
    for candidate in ("gitleaks", os.path.expanduser("~/bin/gitleaks"), os.path.expanduser("~/bin/gitleaks.exe")):
        probe = run(["sh", "-lc", "command -v %s" % candidate])
        if probe.returncode == 0 or os.path.isfile(candidate):
            gitleaks = candidate
            break
    if gitleaks:
        r = run([gitleaks, "git", "--no-banner", "."])
        print(r.stderr[-1200:] or r.stdout[-1200:])
        if r.returncode not in (0,):
            fails.append("SECRET_SCAN failed (rc=%s)" % r.returncode)
    else:
        print("  WARN gitleaks not found — skipped (CI runs gitleaks-action)")

    print("== 4. GIT_DIFF_CHECK ==")
    r = run(["git", "diff", "--check"])
    if r.returncode != 0:
        fails.append("GIT_DIFF_CHECK failed")
        print(r.stdout)
    else:
        print("  ok")

    print("\nVERDICT:", "FAIL" if fails else "PASS")
    for f in fails:
        print("  -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
