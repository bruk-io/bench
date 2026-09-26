---
id: task-72
title: 'Threads: printed screw threads by a twisted extrusion'
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
decision-11, operation 4. Manifold's own extrude takes a twist and a top scale; bench's modeller binding (web/src/modeller.ts, extrude(section, height)) and its recipe tree drop them. Expose twist (and scale) through the recipe and both kernels the tests use, then thread(external/internal, diameter, pitch, length, profile) as the standard twisted extrusion of an offset circle, with the internal thread's clearance from the fit table so a printed bolt goes into a printed nut. Faces: a twisted extrusion's side is one face; say how it is named.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 extrude takes twist and top scale end to end (recipe, browser modeller, test kernel)
- [x] #2 thread() makes external and internal threads with a clearance from the fit table
- [x] #3 A printed bolt and nut pair clears by the fit, measured
- [x] #4 An example (a jar lid or a knob) runs in the gate
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Extrude gains twist and scale end to end; threads.thread(EXTERNAL|INTERNAL, ...). An internal thread is opened by the fit's clearance plus half the hole compensation (the rule hole() uses). Fine pitches are then drawn clear of their bolt (PLA SLIDE below 1.54 mm); threads.drawn_clear warns, as does too_small - both are check findings at the script's line, not console logs.
<!-- SECTION:NOTES:END -->
