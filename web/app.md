# State and event flow

Read `render()`, then `workspace()` and `task()` in `app.js`. Selection controls the record shown at desktop and phone widths. `state()` validates saved data, while `change()` reloads it under a Web Lock. `advance()` compares the expected event index and checks the parcel funding hold.

1. Reach the final parcel step with funding unknown and inspect the disabled review action.
2. Load the funding fixture, open another tab at the same step, and complete it in the first tab. The stale second tab cannot apply it again.
3. Export a saved draft and import it in a fresh same-scope session. Check the originating step label and the receiving session's independent review history.

The browser constructs nodes with text content. Draft imports check format, scope, fixture version and checkpoint shape. These checks support reproducible simulations in a trusted browser profile. Shared-user operation needs a server and authenticated permissions.
