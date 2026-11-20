# Founder review workspace

Start in the repository root and run the local preview.

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory web
```

Open `http://127.0.0.1:8765` in a current browser. The server serves static files on this machine, with no sign-in or API keys. The five guided workflows use fictional records. Use synthetic notes. Anyone with access to the browser profile can read local storage or change the selected workspace.

## Try one acquisition review

1. In **Commercial**, select **Orchard parcel** in the review queue or schematic. Select the parcel and record the underwriting review.
2. Inspect the unavailable approval control. **Evidence and status** identifies the missing funding evidence. Load the verified synthetic funding fixture to make the simulated review available.
3. Approve the simulated bid review, then open **Agents** to see the recorded actions and evidence version. No external action is available.
4. Save a review note and reload. Under **Device handoff**, export the draft. Transfer the file yourself and import it in a second instance of the workspace. The reviewed scope, evidence version, note and originating step travel with the draft. The originating step is read-only. Each browser maintains its own action history.

**Documents** covers sample inbox intake. **Operations** in the Family office workspace covers maintenance dispatch. **Capital** covers separate invoice and settlement evidence. **World Map** in Civic Main Street covers a field note. **System** identifies all twelve journeys and their implementation status. **Network** identifies an unavailable contact lookup. Finance, geo, email and identity integrations remain future services. No live balances or third-party flows are shown.

## Read the implementation

| Source | What to follow | Try it |
| --- | --- | --- |
| `index.html` | The initial DOM supplies the skip link, workspace selector, two navigations and one main panel. Desktop and phone share the same state. | Press Tab and Enter to reach the main panel. |
| `style.css` | Desktop uses a queue beside the inspector. The narrow layout switches between a queue and one task. The map is a synthetic schematic. | Compare a desktop-sized viewport with a narrow viewport, then use Current task and Modules. |
| `fixtures.js` | Each synthetic record has a scope, module, version and ordered events. The coverage map labels guided workflows, local capabilities and future services. | Compare a workflow's step names with its event history and the System page. |
| `app.js` | `render` selects the workspace, `change` takes a same-origin lock, and `advance` verifies the expected step. Draft import checks scope, version and checkpoint shape. | Open the same step in two tabs and try it twice. Only the first transition succeeds. |
| `../tools/replay_founder.py` | Real browser sessions run the visible flows against an isolated loopback origin. | Use the [replay guide](../tools/replay_founder.md). |

## Data and recovery

Local state is keyed by workspace and origin. An invalid snapshot opens a recovery panel. **Archive snapshot and restart** copies the original value to a recovery key in that browser's local storage before resetting the affected workspace. A local simulation offers neither authenticated domain isolation nor cross-user synchronization. Fresh profiles and separate devices have independent approval histories. A production release requires authenticated server-side controls, durable records, service integration and physical-device accessibility checks.
