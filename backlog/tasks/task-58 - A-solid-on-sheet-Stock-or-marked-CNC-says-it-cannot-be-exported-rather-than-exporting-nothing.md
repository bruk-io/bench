---
id: task-58
title: >-
  A solid on sheet Stock, or marked CNC, says it cannot be exported rather than
  exporting nothing
status: Done
assignee: []
created_date: '2026-09-23 14:35'
updated_date: '2026-09-23 21:33'
labels: []
milestone: m-7
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-09-23: `part("frame", solid, Stock(19.05, "ply"), Process.CNC)` builds with 0 errors and 0 warnings, and `tools.build --out` writes part-frame.svg of 369 bytes with no paths and no mesh. model.py's process_of says a billet to be milled "is the arm of Stocked that does not exist yet"; until it does, a Solid on sheet Stock (or any part marked Process.CNC) is silently dropped from every output.

At minimum the run should say so - an ERROR naming the part and why (a sheet part must be a Face; milling is not modelled yet) - rather than an empty file that looks like success. Whether to add billet stock is a separate, larger decision; this task is only about not failing silently.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A Solid on Stock produces a violation naming the part, in the app and in tools.build
- [x] #2 A part with Process.CNC says milling is not modelled yet, rather than exporting nothing
- [x] #3 tools.build --out never writes an empty SVG for a part it could not draw
- [x] #4 Tested at the functional layer
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #21. checks.exportable(shape, stock, process), kernel-free like fits: a Face (laser or CNC-routed 2D profile) is fine; a Solid marked Process.CNC is an ERROR ('milling is not modelled yet - nothing is exported for this part'); a Solid on sheet Stock is an ERROR (needs Printed stock); a Solid on Printed is fine. Recorded against the part so it shows in the app's Problems panel and in tools.build. tools.build --out never writes an empty part-*.svg - widened beyond the report: every printed part used to get a blank SVG too.

Reviewed: the exportable rule and the Problems-panel screenshot (error names `frame`); PR contains no scratch files. Gate after merging main twice: pytest 1068+1 skip x2, e2e 121, vitest 357. The agent stalled twice waiting on backgrounded gate runs; a foreground run finished it.
<!-- SECTION:NOTES:END -->
