---
id: task-31
title: A clearance ask should account for the chord sag of an internal arc
status: Done
assignee: []
created_date: '2026-09-22 22:41'
updated_date: '2026-09-22 13:26'
labels:
  - feature
milestone: Hardening
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A concave arc is meshed as chords lying inside its true circle, so the material sits proud of where the arc is and eats into a gap measured against it. In task-27 the stop lug's concave inner arc read 0.16 mm on `min_gap` against a 0.20 mm ask, and the fix was to add `CHORD` on top of the fit by hand.

That is a silent, systematic underestimate on every internal arc in the repository, and it is only ever noticed when a check happens to fail. `clearance(Fit.SLIDE, PLA)` answers what the fit needs; nothing tells the caller that a concave surface needs the tessellation's sag on top.

Either fold it into the ask or warn when a measured gap is within a chord's sag of the ask - but do not invent a new tolerance, `CHORD` already exists and is the figure task-27 used.

Small and self-contained. Depends on nothing, though it makes the contact and motion work more trustworthy.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A gap asked for across a concave arc is met in the mesh, not only in the ideal geometry
- [ ] #2 A convex or planar pair is unaffected - nothing gets a silent extra allowance it does not need
- [ ] #3 The existing CHORD figure is used rather than a new tolerance invented for this
- [ ] #4 examples/fulcrum_hinge.py stops adding CHORD by hand
<!-- AC:END -->
