# Physical handset acceptance

Use this checklist for GitHub issue #12. A product reviewer performs each row on a physical iPhone in Safari and a physical Android phone in Chrome. An independent reviewer checks the results and linked defects. The automated baseline is available in the [browser replay guide](../tools/replay_founder.md).

## Prepare the run

1. Record the commit SHA from the tested artifact, test date, device model, OS and browser versions, display settings, tester and independent reviewer. Record the approved origin and access method in the private run record. Use a test profile and fictional records.
2. Open the existing, authorized HTTPS test origin serving this checkout’s `web/` assets. Check that the page identifies a local simulation and that a draft save succeeds. The four workflow and file-handoff checks below use the static simulation. The separate authenticated review requires a separately provisioned test environment if included in a handset run. The development server binds to Windows loopback. A handset’s localhost points to the handset.
3. On Windows at the same tested revision, switch to Family office and open Pump maintenance. Complete **Review request**, save a distinct synthetic note, and export the draft from **Device handoff**. Record the expected scope, record ID, evidence version, note and originating step. Transfer the file through the approved test-device file channel. Prepare one copy with an obsolete evidence version for the stale-input case.
4. Start each handset with fresh site data using a dedicated test profile. Run the handoff checks before the maintenance workflow so that the incoming origin checkpoint can be compared with an empty local action history.

You can also prepare the drafts using the Windows replay at the tested revision. Run `uv run --with-requirements requirements-checks.txt python tools/replay_founder.py --engine chromium --handoff-fixtures .runs/handset-fixtures` with a fresh output directory. The `chromium` subdirectory contains `valid-draft.json` and `stale-draft.json`. For this export, the workstation completed three steps through **Approve simulated dispatch**, and the note is **Synthetic checkpoint A**. Record that the desktop setup used this replay. Transfer the JSON files through the approved device channel and run the same physical acceptance matrix. [Replay guide](../tools/replay_founder.md)

## Device evidence matrix

Fill each cell with pass, fail or blocked, the date, and an evidence or defect reference. The initial entries below reserve space for physical results.

| Journey | Expected result | iPhone Safari | Android Chrome |
| --- | --- | --- | --- |
| Cross-scope handoff | Import the Family office draft in Commercial. An explicit rejection is visible, and the selected commercial record retains its prior note and action history. | Pending | Pending |
| Stale handoff | In Family office, import the obsolete-version copy. The status explains that the evidence version changed. Current note and events survive. | Pending | Pending |
| Valid handoff | Import the original file in Family office. Pump maintenance, its evidence version, note, completed step count and last originating step match the Windows record. The handset retains its own action history. | Pending | Pending |
| Parcel review | In Commercial, open Orchard parcel. Select it and record underwriting. Confirm the unavailable approval and visible funding hold, then load the verified synthetic funding fixture and record one simulated approval. Reload and inspect the history. | Pending | Pending |
| Document intake | In Commercial, ingest the sample message, review the extracted document and create the review task. Its history shows the sequence and current evidence reference. | Pending | Pending |
| Maintenance | In Family office, open Pump maintenance, review the request and estimate, and authorize simulated dispatch. The imported note survives. | Pending | Pending |
| Settlement | In Commercial, review the service invoice. Attach the separate receipt before reconciliation becomes available. Reload and verify one reconciled history. | Pending | Pending |
| Touch and reflow | Use portrait and landscape. Open the evidence disclosure and bottom navigation. Increase text size to 200% where supported and record the actual setting. Essential controls, focus and validation text remain reachable without horizontal page scrolling. | Pending | Pending |
| Assistive navigation | Use VoiceOver on iPhone and TalkBack on Android, or document the external keyboard alternative. Traverse scope, queue, evidence, note, action and error feedback. Record spoken labels, focus after action, activation and any clipped controls. | Pending | Pending |

Capture short screenshots, recordings or timestamped observation notes in the approved location. Include steps, actual versus expected behavior, device, orientation and commit for each defect. Keep temporary keys, personal notifications and account details outside shared evidence. Attach the matrix and defect references to [issue #12](https://github.com/ajoiventures/BL_ACQ/issues/12) through the authorized project workflow. Close the ticket after both physical-device columns have results and blocking defects have passed retest.
