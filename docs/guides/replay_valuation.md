# Replay valuation in a real browser

[replay_valuation.py](../../tools/replay_valuation.py) drives the actual valuation page and HTTP service with Playwright. It reuses the disposable server and Chromium executable discovery from [replay_founder.py](../../tools/replay_founder.py). Each engine gets a new temporary SQLite database, generated fixture access keys, and separate desktop and mobile browser contexts.

## Run

From the repository root, use a Python environment containing Playwright and the corresponding browser binaries:

```sh
python tools/replay_valuation.py --engine chromium
python tools/replay_valuation.py --engine webkit
python tools/replay_valuation.py --engine both --screenshots .runs/valuation-replay
```

On an environment where dependency installation is permitted, `python -m pip install playwright` installs the Python package and `python -m playwright install chromium webkit` installs the browser binaries. Chromium can also use the existing `FOUNDER_REPLAY_BROWSER` executable override or a locally installed Chromium/Chrome resolved by the shared helper. The replay does not modify sandbox policies, browser security flags, or service permissions.

An exit code of **0** means every requested engine passed. **1** means a replay assertion or interaction failed. **2** means a missing dependency, browser launch, or local service startup prevented execution. A `BLOCKED` result is not a pass. A run with one passing engine and another blocked engine still exits nonzero.

## What the replay proves

The original example travels through the public examples endpoint, the visible form, authenticated server evaluation, immutable storage, and JSON export. The exported input and report must equal the original file and server response. The replay pins these historical example results independently of the evaluator:

| Quantity | Expected value per share |
| --- | ---: |
| Author workbook baseline | $199.49058622677524 |
| Scenario-weighted value | $166.666112841825 |
| Entry ceiling after the example's 30% margin of safety | $116.66627898927749 |

The page must display those as three separate values. The author's recorded $140 threshold remains source metadata. It does not replace the scenario-adjusted entry ceiling.

The replay also verifies these behaviors:

1. A keyboard user can use the skip link, sign in, calculate, and reopen a saved history item. The access-key field is cleared after sign-in.
2. The stored $163 reference price has no observation date. The page labels it **Historical input comparison — price unverified**, uses **Input gap to value**, and explains that it is not current market upside. The dated workbook conflict and source-review hold survive evaluation, storage, and export. The record remains on hold with execution disabled.
3. The example keeps its full-precision annual growth, margin, tax, and discount paths. Revenue and share counts stay in actual dollars and actual shares. The workbook's 2022 input date and the article's 2026 valuation date remain distinct.
4. Editing the reference price from $163 to $164 marks the existing report stale and disables save and export. Recalculation sends the edited packet to the real server, preserves intrinsic values, and produces a different packet digest.
5. The second save reaches the service and commits, but Playwright deliberately drops its response. The visible **Retry save** action sends the identical body and request ID. The server returns the identical saved record, and history contains exactly two revisions, including the untouched original.
6. Reloading the page restores the authenticated history. Opening either revision restores its exact input packet and stored report. A separate mobile context signs in as the other commercial fixture actor and opens the saved revision through touch controls.
7. The populated page has no document-level horizontal overflow at desktop widths of 1440, 1024, and 768 CSS pixels, the emulated device width, and 320 CSS pixels. Chromium uses Pixel 7 emulation; WebKit uses iPhone 13 emulation. This checks responsive layout and touch interaction, not a physical handset or a complete accessibility audit.

The browser's only intercepted operation is the deliberately interrupted save reply. Its upstream request still reaches the real service. Values, authentication, persistence, history, and retry receipts are not mocked. Uncaught browser JavaScript errors fail the replay; the expected network failure for the interrupted reply does not.

## Temporary data and screenshots

Fixture keys stay in memory. The replay does not save credentials, cookies, browser profiles, traces, or HTTP request logs. Downloads are read from Playwright's temporary location and deleted after validation. The helper removes the temporary database when the service closes.

`--screenshots` writes one desktop and one mobile PNG per engine only after that engine's assertions pass, with the access-key fields empty. Screenshots use the supplied historical example and replay edits. Without this option, no screenshot artifact is created. The replay never contacts a quote provider, sends an order, or approves a transaction.

## Workspace execution status

The initial normal invocation, `python tools/replay_valuation.py --engine chromium`, started the disposable service but exited **2 / BLOCKED** when Chromium failed in `process_singleton_posix.cc`: `socket() failed: Operation not permitted (1)`. Python syntax validation and `--help` passed. No browser assertions ran and no screenshots were produced. A subsequent `--engine both` run reached the same Chromium restriction; WebKit was initially unavailable because its browser binary was not installed. Neither attempt completed browser assertions. Installing the WebKit binary succeeded through Playwright's standard installer, but a subsequent normal WebKit launch remained blocked by missing host libraries (GTK 4, Graphene, HarfBuzz ICU, libmanette, libhyphen and GLESv2). No browser assertion or screenshot has been represented as passing.

Run the same command in an environment that permits the normal local service and browser processes to complete the browser checks. Syntax validation alone does not establish that the browser replay passed.
