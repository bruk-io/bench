---
id: task-84
title: >-
  The systainer tote's latch lugs and ribs hang off its walls with nothing under
  them
status: Done
assignee: []
created_date: '2026-09-27 18:33'
updated_date: '2026-09-27 19:19'
labels:
  - examples
milestone: m-12
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by task-78 (PR #29): once check_overhangs reported every place, examples/systainer_tote.py showed 18, not only socket-1. Six are bridges (four socket ceilings, two grip tops). Twelve are the two latch lugs and ten ribs, which start at floor height rather than the bed and hang off the wall with nothing under them, so a slicer must support them. The docstring now says so; the geometry is unchanged. Give the lugs and ribs a 45 degree underside (or start the ribs on the bed) so the example prints without support, as an example should.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Lugs and ribs print without support: no overhang past the limit on them, measured
- [x] #2 The tote still fits a Systainer as before (its fit tests pass)
- [x] #3 Docstring updated to what is true
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #32. Latch lugs stand on a gusset whose face leans exactly material.max_overhang; ribs start on the bed. check_overhangs on the shipped kernel: 18 places -> 6 (four socket ceilings, two grip tops). No dedicated Systainer fit test exists; require(check_fits) and the examples-run-clean test pin it.
<!-- SECTION:NOTES:END -->
