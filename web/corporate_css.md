# Corporate case presentation

`corporate.css` adds compact financial summaries, readable source records and
statement totals to the existing [valuation stylesheet](valuation.css). It does
not change the original valuation page's styles.

Tables remain horizontally scrollable where their annual columns exceed the
viewport. Row labels can wrap without shrinking financial numbers. Failed
financing uses the existing error notice treatment. Responsive rules reduce the
summary grid to two columns and allow the masthead to wrap. Print rules omit
interactive actions.

The stylesheet requires browser and visual verification in the supported
deployment environment. Syntax and static DOM checks alone do not establish
that every browser layout has passed.
