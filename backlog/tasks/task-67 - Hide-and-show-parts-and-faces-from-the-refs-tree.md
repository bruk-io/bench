---
id: task-67
title: Hide and show parts and faces from the refs tree
status: Done
assignee: []
created_date: '2026-09-24 01:31'
updated_date: '2026-09-24 02:05'
labels: []
milestone: m-9
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Asked for while modelling the wall vent (2026-09-23): an assembly of four parts - frame, adapter, hood, manifold - hides most of itself; the section view (task-62) slices it, but there is no way to simply take the hood off the view to look at the adapter behind it. Every row in the refs container (parts, and the named nodes/faces under them) gets a visibility toggle (an eye), the way Fusion's browser does.

Rules: hiding a row hides everything under it (a part, a node's faces); the viewer only draws - it filters triangles by the ref membership the scene already carries (ref_index), no geometry in TS; visibility is view state, per browser tab, never written into the script or the host (decision-7's rule is about picks; this is not a pick) - survive re-runs by ref name, and forget refs that no longer exist; hidden triangles are not pickable; a finding on a hidden part still shows in Problems and the row says it is hidden (so nothing is silently out of sight). A quick way to show only one part (isolate) and to show everything again. Works with section view and colour faces.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every part and named face row in the refs tree has a visibility toggle; hiding a row hides everything under it in the 3D view
- [x] #2 Hidden geometry is not pickable; clicking through picks what is behind it
- [x] #3 Visibility survives a re-run and a knob change, keyed by ref, and is never written to the script or the host
- [x] #4 Isolate one part, and show all, are one action each
- [x] #5 A row that is hidden, or has hidden children, says so; a finding on a hidden part is still listed in Problems
- [x] #6 Works together with section view and colour faces
- [x] #7 e2e test and screenshots (the wall vent example with the hood hidden)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #23. Viewer-only: an eye per refs-tree row (refs-tree.ts), 'only' to isolate a part and 'show all' in the header; the viewer rebuilds each body's index without the hidden refs' triangles (applyHidden / filteredIndex), so hidden geometry is neither drawn nor raycast, and the pick loop also skips a hit on a hidden ref (lettering quads ignore visible). State lives in the viewer closure like section/colour faces, pruned to each run's refs in main.ts - never written to the script or host. Rows say 'hidden'.

Fixed a latent picking bug the index rebuild exposed: foundBy used hit.faceIndex / hit.index, which count positions in whatever three.js walked; now the triangle is floor(hit.face.a / 3) (bench sends non-indexed placed vertices, three per triangle) and a line segment reads its vertex through the index. AC#5 tested on enclosure_lid's thin-wall finding (no vent knob reliably makes one). AC#6 holds by construction - hiding touches the index buffer, section the clip plane, colour faces the vertex colours - but has no dedicated e2e test. The AC's 'hood' is the example's 'attachment'. Gate: vitest 365, pytest 1084+1 skip x2, e2e 126.
<!-- SECTION:NOTES:END -->
