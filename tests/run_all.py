#!/usr/bin/env python3
"""Run every Telos test suite and report one number.

Usage:
    DATABASE_URL=postgresql://... python3 tests/run_all.py

The suites need a real PostgreSQL database because the things most worth
testing here (owner scoping, quota counting, transactional deletion) are
enforced in SQL. A mocked database would pass while the real one leaked data
between users, which is exactly the bug class these tests exist to catch.

Point DATABASE_URL at a scratch database. The suites delete rows.
"""

import os
import subprocess
import sys
import pathlib

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent

SUITES = [
    ("core", "test_telos.py", "Database, models, plans, quotas, demo seeding"),
    ("pages", "test_pages.py", "Every page renders for each account type"),
    ("admin", "test_admin.py", "Admin access control and rate limiting"),
    ("auth", "test_app_auth.py", "Sign in, reset, session persistence, sign out"),
    ("account", "test_profile_account.py", "Data export, deletion, cross-user isolation"),
    ("spend", "test_spend.py", "AI cost accounting, monthly cap, error messages"),
]

DEFAULTS = {
    "ANTHROPIC_API_KEY": "sk-test-not-a-real-key",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "OWNER_EMAILS": "patrickbarnsley@gmail.com",
    "ADMIN_PASSWORD": "correct-horse",
}


def main() -> int:
    if not os.getenv("DATABASE_URL"):
        print("DATABASE_URL is not set. Point it at a scratch database and try again.")
        return 2

    env = {**os.environ}
    for key, value in DEFAULTS.items():
        env.setdefault(key, value)
    env["PYTHONPATH"] = str(ROOT)

    total_pass = total_fail = 0
    failed_suites = []

    for name, filename, description in SUITES:
        path = HERE / filename
        if not path.exists():
            print(f"  SKIP  {name}: {filename} not found")
            continue
        result = subprocess.run([sys.executable, str(path)], capture_output=True,
                                text=True, env=env, cwd=str(ROOT))
        out = result.stdout + result.stderr
        passes = sum(1 for line in out.splitlines() if line.strip().startswith("PASS"))
        fails = sum(1 for line in out.splitlines() if line.strip().startswith("FAIL"))
        total_pass += passes
        total_fail += fails

        mark = "ok  " if fails == 0 and result.returncode in (0, None) else "FAIL"
        print(f"  {mark}  {name:<9} {passes:>3} passed, {fails} failed   {description}")
        if fails or result.returncode not in (0, None):
            failed_suites.append(name)
            for line in out.splitlines():
                if line.strip().startswith("FAIL") or "Traceback" in line:
                    print(f"          {line.strip()}")

    print("-" * 74)
    print(f"  {total_pass} passed, {total_fail} failed across {len(SUITES)} suites")
    if failed_suites:
        print(f"  Failing suites: {', '.join(failed_suites)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
