---
id: task-72
title: 'Threads: printed screw threads by a twisted extrusion'
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
decision-11, operation 4. Manifold's own extrude takes a twist and a top scale; bench's modeller binding (web/src/modeller.ts, extrude(section, height)) and its recipe tree drop them. Expose twist (and scale) through the recipe and both kernels the tests use, then thread(external/internal, diameter, pitch, length, profile) as the standard twisted extrusion of an offset circle, with the internal thread's clearance from the fit table so a printed bolt goes into a printed nut. Faces: a twisted extrusion's side is one face; say how it is named.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 extrude takes twist and top scale end to end (recipe, browser modeller, test kernel)
- [ ] #2 thread() makes external and internal threads with a clearance from the fit table
- [ ] #3 A printed bolt and nut pair clears by the fit, measured
- [ ] #4 An example (a jar lid or a knob) runs in the gate
<!-- AC:END -->
