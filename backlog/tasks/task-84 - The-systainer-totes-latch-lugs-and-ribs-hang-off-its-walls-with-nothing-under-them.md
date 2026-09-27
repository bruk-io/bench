---
id: task-84
title: >-
  The systainer tote's latch lugs and ribs hang off its walls with nothing under
  them
status: To Do
assignee: []
created_date: '2026-09-27 18:33'
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
- [ ] #1 Lugs and ribs print without support: no overhang past the limit on them, measured
- [ ] #2 The tote still fits a Systainer as before (its fit tests pass)
- [ ] #3 Docstring updated to what is true
<!-- AC:END -->
