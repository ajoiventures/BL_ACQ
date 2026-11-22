# Valuation visual system

The page uses a restrained navy and cream system with teal for valuation and gold for entry discipline. Serif headings establish the research hierarchy; compact sans-serif labels and tabular numerals keep financial data readable. Backgrounds and rules separate sections without decorative dashboards or fake market activity.

Desktop uses two columns: a bounded-width input form and a wider report. At 850 pixels the reading order becomes a single column. At 520 pixels the entry ceiling spans the full metric row, scenarios stack, and tables retain horizontal scrolling inside their own container. Document-wide horizontal overflow should not occur at 320 pixels.

Interactive controls have visible keyboard focus and practical touch targets. The palette does not carry meaning by itself: qualification cards name their status, sensitivity cells show numeric values, and warnings include explanatory text. A reduced-motion preference disables transitions. Print styles isolate the report; the underlying report data remains available in JSON export.

Inspect desktop and phone layouts after changes, particularly long asset IDs, large whole-business equity values, empty reference prices, invalid sensitivity cells, and long source URLs. The most important reading sequence is baseline value → event-adjusted value → entry ceiling → source and qualification holds.
