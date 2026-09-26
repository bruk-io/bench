---
id: task-68
title: check_fits measures a printed part the way it prints
status: Done
assignee: []
created_date: '2026-09-24 02:33'
updated_date: '2026-09-26 14:58'
labels: []
milestone: m-10
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-11, operation 1. check_fits(shape, volume) measures the body's box where it sits, so a part that prints on another face fails or passes on the wrong axes: the vent's hood (Orient(up=Y)) read 'y 322.4 mm against 320' although it stands 322 mm tall on a 325 mm-tall volume, and projects/vent rotates every part onto the bed by hand before checking. task-64 already lays exports down by Orient (export.as_printed). Measure the box of the part laid on the bed the same way - one rule shared with export - when the part's stock says how it prints; keep the plain box for a shape with no Orient. Decide how a bare Solid (no Part) states its orientation (an orient= argument?).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A part printed standing is measured on its print axes, using the same laying-down rule as export.as_printed
- [x] #2 The vent's hood passes the H2D check with no hand rotation
- [x] #3 A shape with no print orientation is measured as before
- [x] #4 Unit and functional tests
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
checks.fits(shape|Part, volume, orient=None) lays the part down by the same rule as export (model.laid_down / checks.bed_along), and measures the turned box's corners because topology.bounds under-reads round faces after an oblique turn.
<!-- SECTION:NOTES:END -->
