---
id: task-59
title: 'mated(): put one part''s face on another''s, and check the fit it was asked for'
status: To Do
assignee: []
created_date: '2026-09-23 17:20'
labels: []
milestone: m-8
dependencies:
  - task-57
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-10 steps 2. A module `src/bench/mate.py` (named for what it does, never __init__.py; add it to pyproject's import-boundary table) with `mated(fixed, at, moving, onto, *, fit=Fit.CONTACT, offset=Vector(0,0), spin=0.0)` for PLANAR face pairs: the moving body moved rigidly (topology.moved with to_local/to_world of the two faces' plane_of frames) so its face lies on the fixed face, normals opposed, the gap along the normal being 0 for CONTACT or clearance(fit, material) otherwise; offset in the fixed face's plane and spin about its normal correct for origins that do not line up.

The pair is declared and checked with the call: contact (task-57's corrected check) or clearance at the asked gap, reported as measured vs asked. The returned body is the object the part must be made from, so findings reach the part by identity (views._label_of). Every other pair of an assembly is still check_clearance_within's job - provide a way to run that with mated pairs excluded-and-declared.

Before building: find out how a posed part exports today (STL/3MF, print orientation) - decision-10 says print orientation stays apart from where a part sits in an assembly; if moving a body would change how it prints, design around that and write down how.

Acceptance test: projects/frame's vent - rewrite its placement of the attachment with mated() (flange top vs attachment back face) and show it lands exactly where the hand placement did, with the 0.20 mm slide reported. Put a copy of that vent in examples/ if it fits the examples' conventions, so the gate runs it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 mated() places a planar pair with normals opposed at the asked gap, with offset and spin
- [ ] #2 The pair's contact or clearance is checked by the call itself and reported as measured against asked
- [ ] #3 A finding from a mated pair lands on the mated part in the view (identity), shown by a test
- [ ] #4 How a mated part prints is written down and tested: moving it into an assembly does not change its print orientation
- [ ] #5 The vent rebuilt with mated() lands where the hand placement did
- [ ] #6 Unit, functional and adapter tests; no mocks
<!-- AC:END -->
