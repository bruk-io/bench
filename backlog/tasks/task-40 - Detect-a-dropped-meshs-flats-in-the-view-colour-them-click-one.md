---
id: task-40
title: 'Detect a dropped mesh''s flats in the view: colour them, click one'
status: Done
assignee: []
created_date: '2026-09-22 03:24'
updated_date: '2026-09-22 03:25'
labels:
  - feature
  - web
milestone: Reverse Engineering
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
First piece of the reverse-engineering line of work (a roadmap for it consulted with Fable, see notes): letting a maker see and interact with what `bench.survey` already detects on a dropped reference mesh, in the 3D view itself, rather than only as prose in the report tab.

- `bench.survey.flat_faces(mesh)` - exposes which triangles belong to which detected flat. `_flats()` already computed this internally (via `_grow()`) and discarded it once it reduced each region to its aggregate `Flat` record; this keeps the per-triangle membership instead, for anything that wants to draw or click a face rather than only read a number about it.
- `bench.worker.detected(stl, table)` - the browser's entry point, placed the same way `surveyed()` already is so a detected face's numbers never disagree with the survey's or a run's.
- The web app: a "detect faces" toggle beside the reference chip, colouring the dropped body's flats in coordinated pastels (a golden-angle hue step, not naive even spacing - fixed a real bug where naive spacing made same-index-adjacent flats on a mesh with hundreds of them visually indistinguishable) and letting a maker click a coloured face - gated so ordinary part-clicking is completely unaffected when detection is off, matching the existing invariant that the backdrop was never pickable before this.

Verified live against a real, complex reference (a Festool Systainer face panel, ~90 flats, ~212 fillets) - not just synthetic fixtures.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A dropped body's detected flats can be coloured in the view, each a distinct pastel even on a mesh with hundreds of them
- [x] #2 Clicking a coloured face reports which flat it is, without affecting how an ordinary part click behaves
- [x] #3 Turning detection off returns the backdrop to its plain ghost and stops it from being clickable, exactly as before this existed
- [x] #4 The detection and its colours are placed the same way a survey already is, so nothing disagrees about where the body sits
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Fable's roadmap for this line of work, in full, consulted after this task landed: "0. section_loops (task-41) - cheapest, highest-leverage, do first. 1. Draft the panel's v2 from real section polygons, in the maker's own project script, verified the v1 way (build, mesh, survey, diff against the reference). Not bench core. 2. task-39 (import a mesh as a Solid) after step 1, not before - needs a decision doc, touches topology/kernel/adapters/modeller.ts, has an open non-manifold-input question. Survey-diffing already catches coarse mismatches cheaply; volumetric overlap is the last-mile check once sections/bands already agree. 3. Finish decision-7's pick UI rather than build a separate readout - wire the existing click into writing [reference], add a small panel (normal/centre/area, distance between two picks). Do not build a 'copy as bench code' button - task-14.3/decision-7's own house position is that drafting code from measurements is a person's or a collaborating model's job, never bench's to infer." Order: 0 -> 1 -> 3 -> 2.
<!-- SECTION:NOTES:END -->
