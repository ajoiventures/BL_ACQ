"""Run the bounded local Swarm verification and emit a versioned handoff receipt."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from tools.build_acquisition_ticket_plan import ROOT

TESTS = ("tests/test_swarm.py", "tests/test_filing_inbox.py", "tests/test_signal_flow.py")
TIMEOUT_SECONDS = 60


def verify():
    context = {
        "schema_version": 1,
        "ticket_id": "BR-T011",
        "coordinator": "SW-00",
        "responsible_role": "L2/SW-00",
        "permitted_tool": "local pytest on the fixed Swarm test suite",
        "timeout_seconds": TIMEOUT_SECONDS,
        "stop_condition": "Test execution exits or reaches the time limit",
        "input_hashes": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (*TESTS, "backend/core/swarm.py", "filing/inbox.py")
        },
    }
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *TESTS],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=TIMEOUT_SECONDS, check=False,
    )
    return {
        "schema_version": 1,
        "context": context,
        "actual_mode": "local subprocess",
        "result": {
            "exit_code": result.returncode,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
        "handoff": {"recipient": "SW-00", "condition": "Review the recorded exit code and test output"},
    }


if __name__ == "__main__":
    receipt = verify()
    print(json.dumps(receipt, indent=2))
    sys.exit(receipt["result"]["exit_code"])
