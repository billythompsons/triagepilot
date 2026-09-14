"""Smoke test: runs the full agent loop in demo mode and checks the report.

Usage:  .venv/bin/python scripts/smoke_test.py
"""

import os
import sys

sys.path.insert(0, "src")
os.environ["TRIAGEPILOT_PROVIDER"] = "demo"

from triagepilot.agent import triage_repo  # noqa: E402
from triagepilot.config import Settings  # noqa: E402

report = triage_repo("triagepilot-demo/focusflow", 6, Settings.from_env())

checks = [
    ("#42" in report, "issue #42 present"),
    ("#41" in report, "issue #41 present"),
    ("duplicate" in report.lower(), "duplicate verdict present"),
    ("duplicate of #41" in report, "#42 flagged duplicate of #41"),
    ("priority:high" in report, "priority:high label suggested"),
    ("good first issue" in report, "good first issue suggested"),
    ("Draft reply" in report, "draft replies present"),
    ("dry-run" in report.lower(), "dry-run noted"),
]

failed = [name for ok, name in checks if not ok]
print("\n--- smoke test results ---")
for ok, name in checks:
    print(("PASS" if ok else "FAIL"), "-", name)
if failed:
    print(f"\n{len(failed)} check(s) failed")
    sys.exit(1)
print("\nAll smoke checks passed.")
