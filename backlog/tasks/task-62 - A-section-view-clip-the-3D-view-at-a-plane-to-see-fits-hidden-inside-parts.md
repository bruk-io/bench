---
id: task-62
title: 'A section view: clip the 3D view at a plane to see fits hidden inside parts'
status: In Progress
assignee: []
created_date: '2026-09-23 17:20'
updated_date: '2026-09-23 17:22'
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
- [ ] #1 A section toggle with an axis choice and a position slider clips every part
- [ ] #2 Cut material reads as cut, so the gap between two parts at the section is visible
- [ ] #3 The section survives a re-run and a knob change
- [ ] #4 Off by default; picking faces still works with it on
- [ ] #5 e2e test and screenshots, including the vent's hook at two Fitting values
<!-- AC:END -->
