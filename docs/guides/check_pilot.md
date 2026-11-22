# Run the release checks from the same entry point

[The check runner](../../tools/check_pilot.py) executes the same checks on a local workstation and in GitHub Actions. Install the project’s pinned tools and both browser engines first. Then run `code-map.cmd verify` on Windows or `uv run --with-requirements requirements-checks.txt python tools/check_pilot.py` from the repository root.

Follow the ordered list in the runner. It stops on the first failed stage and names the stage in the terminal. The runner executes pinned lint and type tools, unit tests, simulated backup recovery, the founder browser replay and the [valuation browser replay](replay_valuation.md). Device-emulated browser checks provide repeatable evidence. Physical-device acceptance is tracked separately. A blocked browser launch is a failed gate, not a substituted syntax-only pass.
