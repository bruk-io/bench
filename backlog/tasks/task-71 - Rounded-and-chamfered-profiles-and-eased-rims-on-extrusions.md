---
id: task-71
title: 'Rounded and chamfered profiles, and eased rims on extrusions'
status: Done
assignee: []
created_date: '2026-09-24 02:33'
updated_date: '2026-09-26 14:58'
labels: []
milestone: m-10
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-11, operation 3. A mesh kernel cannot fillet an arbitrary 3D edge, and decision-11 does not promise it. What a printed part mostly wants it can have: fillet(wire, r) and chamfer(wire, d) on a 2D profile's corners before it is extruded (offset out and back in for fillets), and an extrusion's top or bottom rim eased - rounded or chamfered - by a hull of slices, generalising library/print.eased(). Faces stay named where a hull does not erase them; say where they are not.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 fillet and chamfer a wire's corners (convex and concave), all or chosen ones
- [x] #2 An extrusion's top or bottom rim eased round or chamfered, with the overhang it leaves checkable
- [x] #3 library/print.eased() either becomes a use of it or is explained
- [x] #4 Tested; an example shows it
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
ops.fillet/chamfer(wire, r, *, at=None) handle concave corners; chamfer's old (w, at, d) order is gone (no callers). library/print.rim and eased() are hull-based, so convex and hole-free only - they now refuse anything else rather than fill it in.
<!-- SECTION:NOTES:END -->
