---
id: task-58
title: >-
  A solid on sheet Stock, or marked CNC, says it cannot be exported rather than
  exporting nothing
status: In Progress
assignee: []
created_date: '2026-09-23 14:35'
updated_date: '2026-09-23 17:22'
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
- [ ] #1 A Solid on Stock produces a violation naming the part, in the app and in tools.build
- [ ] #2 A part with Process.CNC says milling is not modelled yet, rather than exporting nothing
- [ ] #3 tools.build --out never writes an empty SVG for a part it could not draw
- [ ] #4 Tested at the functional layer
<!-- AC:END -->
