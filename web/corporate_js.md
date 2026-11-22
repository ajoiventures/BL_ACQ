# Corporate case browser behavior

`corporate.js` loads `/api/corporate/case`, edits the case JSON and submits it
directly to `/api/corporate/evaluate`. The service owns source facts and all
financial calculations. Browser arithmetic only formats percentages, USD
millions and reported source units for display.

The response is `{case, facts, report}`. Export uses this exact response bundle,
not an older copy of the facts fetched when the page first loaded. This protects
the correspondence between the downloaded inputs, source records and financial
result when the service's evidence changes between requests.

Input edits increment a revision and mark displayed results stale. Calculation
captures the submitted revision; a response is ignored if the inputs changed
while it was in flight. JSON download remains disabled for stale results,
pending calculations and signed-out sessions. Choosing a case preserves other
valid JSON edits; malformed edits must be corrected before the selector can
replace `selected_case`.

Existing same-origin HTTP-only sessions are reused. Access keys are cleared
after submission and are not stored in browser storage. Requests have a
30-second timeout. The client enforces the same 65,536-byte maximum case size
before sending, while the server remains authoritative for authentication,
schema, source ownership, dates and financial validity.

All source text and output values are inserted as text nodes or `textContent`.
Source links accept only credential-free HTTP(S) URLs and use `noopener` and
`noreferrer` when opened separately. Downloads use a locally created JSON Blob
and a sanitized filename. No untrusted source content is evaluated as markup or
code.

Unavailable numeric results display as unavailable rather than zero. Financing
failures and their unpaid principal/liquidity conditions remain visible. The
interface never changes the overall research-review requirement because a
statement check or financing scenario happens to pass.
