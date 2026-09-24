---
id: task-71
title: 'Rounded and chamfered profiles, and eased rims on extrusions'
status: To Do
assignee: []
created_date: '2026-09-24 02:33'
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
- [ ] #1 fillet and chamfer a wire's corners (convex and concave), all or chosen ones
- [ ] #2 An extrusion's top or bottom rim eased round or chamfered, with the overhang it leaves checkable
- [ ] #3 library/print.eased() either becomes a use of it or is explained
- [ ] #4 Tested; an example shows it
<!-- AC:END -->
