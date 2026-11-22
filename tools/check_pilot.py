"""Run the same pilot acceptance checks locally and in GitHub Actions."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def main():
    # Keep this sequence identical on a workstation and a hosted runner.
    # Each command must pass before the acceptance suite continues.
    checks = (
        ("lint", ["ruff", "check", "--select", "E9,F63,F7,F82", "pilot", "filing", "tests", "tools", "Python_Asset_Demo"]),
        ("types", [PYTHON, "-m", "mypy", "--follow-imports=silent", "--ignore-missing-imports",
                   "pilot/contracts.py", "pilot/connectors.py", "pilot/cuda_screen.py"]),
        ("reporting tests", [PYTHON, "-m", "unittest", "discover", "-s", "Python_Asset_Demo"]),
        ("pilot tests", [PYTHON, "-m", "unittest", "discover", "-s", "tests"]),
        ("tool tests", [PYTHON, "-m", "unittest", "discover", "-s", "tools", "-p", "test_*.py"]),
        ("source guides", [PYTHON, "tools/check_guides.py"]),
        ("pilot recovery", [PYTHON, "-m", "pilot.acceptance"]),
        ("browser replay", [PYTHON, "tools/replay_founder.py", "--engine", "both"]),
        ("valuation browser replay", [PYTHON, "tools/replay_valuation.py", "--engine", "both"]),
    )
    for label, command in checks:
        print(f"Checking {label}", flush=True)
        try:
            result = subprocess.run(command, cwd=ROOT)
        except FileNotFoundError as exc:
            print(f"{label}: {exc}. Install requirements-checks.txt first.", file=sys.stderr)
            return 1
        if result.returncode:
            print(f"{label} failed with exit code {result.returncode}", file=sys.stderr)
            return 1
    print("Pilot checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
