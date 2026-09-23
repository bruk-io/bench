---
id: task-62
title: 'A section view: clip the 3D view at a plane to see fits hidden inside parts'
status: Done
assignee: []
created_date: '2026-09-23 17:20'
updated_date: '2026-09-23 18:17'
labels: []
milestone: m-8
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-10 names this as where 'show the user' runs out: the vent's tongue under the collar's hook is inside the attachment, invisible from outside at every pose. A toggle in the view that clips the scene at a plane (X, Y or Z, through the scene's middle, with a slider for where) using three.js clipping planes - drawing only, no geometry in TS (the project's rule). Cut faces should read as cut (capped or clearly coloured) so a gap between two parts is visible. It stays on while knobs change, so dragging a pose knob (like the vent's Fitting) animates the section.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A section toggle with an axis choice and a position slider clips every part
- [x] #2 Cut material reads as cut, so the gap between two parts at the section is visible
- [x] #3 The section survives a re-run and a knob change
- [x] #4 Off by default; picking faces still works with it on
- [x] #5 e2e test and screenshots, including the vent's hook at two Fitting values
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #15 (09b510b). Viewer-only: one shared THREE.Plane toggled via renderer.localClippingEnabled (no shader recompiles); cut faces read as cut through a second BackSide mesh sharing the front mesh's geometry, tinted flat red; picking filters hits against the plane (Raycaster ignores clipping); section state lives in the viewer closure so it survives re-runs and pose-knob redraws. Toolbar: 'section' toggle, axis X/Y/Z, position slider. 4 e2e tests; gate e2e 116.

Reviewed the vent sectioned on X at Fitting 1.0: clipped, cut edges red. Honest limit: on a 317 mm part the 4 mm hook/drop is small at full-scene zoom - zoom in to read it.
<!-- SECTION:NOTES:END -->
