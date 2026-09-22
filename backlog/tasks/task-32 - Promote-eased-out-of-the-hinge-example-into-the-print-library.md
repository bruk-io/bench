---
id: task-32
title: Promote eased() out of the hinge example into the print library
status: Done
assignee: []
created_date: '2026-09-22 22:41'
updated_date: '2026-09-22 13:26'
labels:
  - feature
milestone: Hardening
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`examples/hinge.py` defines `eased()` - a prism built as a loft, an extrude and a loft, so a rim is chamfered because the shape was made that way. task-27 needed the same treatment for its rings and rims. Two examples hand-rolling the same helper is one too many.

**This is not a request for a chamfer verb, and that distinction matters.** `hinge.py`'s docstring argues that there is no chamfer verb for the edge of a solid on this kernel and there is not going to be one, and that a rim chamfer should come from how the shape was made rather than from finding an edge afterwards. That argument stands. The ask is only to move the helper somewhere both examples can reach it, most likely `bench.library.print` beside `clearance` and the material table.

Small and self-contained. Depends on nothing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Both examples use one shared helper instead of defining their own
- [ ] #2 The geometry each example produces is unchanged - this is a move, not a redesign
- [ ] #3 No chamfer or fillet verb on a solid edge is introduced, and the reasoning stays recorded where a reader will meet it
- [ ] #4 The helper is documented for the next part that needs an eased rim
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Premise check before implementing: fulcrum_hinge.py (task-27) does NOT define a loft/extrude/loft rim-easing helper or anything equivalent. Its rings/rims are plain section() extrudes with sharp edges (no offset(), no loft(), no eased()); CHORD there is chord-sag margin for a concave arc, unrelated to rim easing. git log confirms fulcrum_hinge.py has had no such code since it was first added (#29). So there is nothing in that file to unify with hinge.py's eased(), and adding easing to it now would be a geometry change AC #2 forbids. Proceeding as: move eased() from examples/hinge.py to bench.library.print (parameterized lead/drop, no globals captured), update hinge.py to import and call it with the same numbers (no geometry change), and leave fulcrum_hinge.py untouched since it has no local copy to remove. AC #1 is satisfied in the 'no example defines its own copy' sense.
<!-- SECTION:NOTES:END -->
