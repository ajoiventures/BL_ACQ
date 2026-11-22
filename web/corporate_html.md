# Corporate case workspace

Open `/corporate.html` through the local founder service. The page reuses the
valuation workspace's visual conventions and links back to the acquisition and
valuation pages. A current reviewer or founder session is required to load the
case or calculate its financials.

Choose Base, Downside or Upside, or edit the complete assumption packet. The
packet uses actual USD, decimal rates and actual shares. Reported source facts
are loaded separately and cannot be replaced through these inputs.

The report shows DCF value per share, a dated historical reference price,
acquisition IRR where available, linked forecast statements, comparable
companies, financing schedules, investor cash flows, historical source controls
and source links. Reported August fiscal periods are distinguished from the
hypothetical October opening and annual model periods. Forecast COGS/gross
margin are explicitly before D&A. Displayed statements use USD millions;
underlying export values retain actual USD and calculation precision.

A failed financing case has a visible failure explanation and its investor
returns are unavailable. Null IRR/MOIC is never displayed as zero. The overall
status remains research requiring review even when numerical checks reconcile.
Source, forecast, model and financing limitations are shown before the detailed
tables.

The debt schedule distinguishes scheduled principal, maturity before exit and
the balloon due at final-year exit. A final-year maturity settlement is shown as
a memo subset of the exit debt payoff, never an additional deduction.

The only download is research JSON containing the evaluated case, exact
server-supplied facts and report together. This page has no saved-run, approval,
order or settlement action. Editing an input marks displayed results stale and
disables downloading until a fresh calculation completes.

Controls have labels and keyboard focus styling. Tables provide text values
with row/column headers, and service errors use alerts. A narrow viewport keeps
inputs before the report and allows wide financial tables to scroll. Browser
behavior and visual presentation still need verification in a supported browser
environment; static checks are not a substitute for that gate.
