# Founder browser replay

From the repository root, run a synthetic end-to-end check on any free loopback port. The runner obtains an ephemeral port, starts a file server and closes it after the checks.

```powershell
uv run --no-project --with playwright python -m playwright install chromium webkit
uv run --no-project --with playwright python tools/replay_founder.py --engine both
```

Browser installation uses network access once. After installation the demo uses resources served from loopback. Chromium uses installed Edge or Chrome when available, then the Playwright browser. Set `FOUNDER_REPLAY_BROWSER` to select a Chromium executable. WebKit uses its Playwright installation. Request screenshots with `--screenshots PATH` to save synthetic desktop and phone images separately from the repository.

## Follow the checks in the source

1. `server()` serves the demo's allowlisted web assets and review API with a temporary SQLite database. Desktop and phone use separate browser contexts.
2. `walkthrough()` visits the interface, uses a keyboard skip link, and replays parcel qualification, document intake, maintenance dispatch, invoice reconciliation and a civic field note.
3. The parcel workflow checks the missing-cash hold and attempts a repeated transition from a second tab. Settlement checks that the final action is unavailable before receipt evidence arrives.
4. The phone imports a desktop draft, rejects a mismatched scope and version, displays the originating device's last step and retains independent events. The recovery check damages one disposable snapshot, archives its contents and verifies a clean restart.
5. The final checks assert twelve coverage entries, three same-scope events, ten module entries, viewports from 320 to 1440 CSS pixels and zero uncaught UI exceptions. Five guided workflows execute. Other coverage entries describe capabilities or future services.

The Chromium run uses a Pixel 7 device profile. The WebKit run uses an iPhone 13 profile. These cover viewport, engine and touch emulation. Native Safari, physical devices, assistive technology, OS file sharing and real services require separate testing. The suite checks specific behaviors and does not certify accessibility compliance.

Use the [physical handset acceptance checklist](../docs/physical-device-acceptance.md) to record those results for issue #12.

Pass `--handoff-fixtures .runs/handset-fixtures` with a fresh output directory to keep the browser-exported draft and the stale-version control after the replay passes. The files are written under the selected engine name. The valid export is also the input for the wrong-workspace test. These files contain fictional evidence and never include the connected service's login keys.

The same replay starts the authenticated loopback service with a disposable database per browser engine. Independent contexts check keyboard sign-in, permitted draft resumption, conflicts, evidence inspection, review and separate founder approval. The replay intentionally discards a committed HTTP response, retries the same operation through the visible control, then checks that the history contains one independent review.
