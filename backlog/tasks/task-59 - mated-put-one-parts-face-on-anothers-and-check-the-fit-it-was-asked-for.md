---
id: task-59
title: 'mated(): put one part''s face on another''s, and check the fit it was asked for'
status: Done
assignee: []
created_date: '2026-09-23 17:20'
updated_date: '2026-09-23 17:59'
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
- [x] #1 mated() places a planar pair with normals opposed at the asked gap, with offset and spin
- [x] #2 The pair's contact or clearance is checked by the call itself and reported as measured against asked
- [x] #3 A finding from a mated pair lands on the mated part in the view (identity), shown by a test
- [x] #4 How a mated part prints is written down and tested: moving it into an assembly does not change its print orientation
- [x] #5 The vent rebuilt with mated() lands where the hand placement did
- [x] #6 Unit, functional and adapter tests; no mocks
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #13. src/bench/mate.py: placing(fixed, moving, gap, offset, spin) = to_world(seat) @ turned-over @ to_local(face), seat = fixed face frame moved by offset in its own X/Y, by the gap along its normal, X turned by spin; mating(...) does it to a Part and returns a Mate record (measured vs asked sentence, e.g. 'plate/bottom on base/top: clear by 0.200 mm, asked 0.200 (slide)'); the script's per-run `mated` closure measures it via checks.fit_between (contact_between for CONTACT, else reads the gap to 1 mm past the ask and fails only when tighter). CONTACT is its own enum (Contact) in fasteners.py, not a 7th Fit. check_fit(a, b, fit, material) is new for a second pair. check_clearance_within skips mated pairs by identity.

Print orientation (owner's Q3): mating turns Orient.up with the body and keeps bed_face, so print checks read the turned part right (test: a ridge mated crown-down passes overhangs with the turned up). BUT exports still write the posed mesh - filed as task-64. plane_of on a cut's faces points into the cavity - filed as task-65.

examples/wall_vent.py: a trimmed vent, run by the gate's example layers. The owner's full vent via mated() lands exactly on the hand placement (same box, 916660.392 mm3). Its groove reads 0.199 vs 0.200 slide - an error: the groove's rounded corners want clearance(..., concave=True) (fix in projects/frame).

Reviewed on main: mate.py placing/gap_of/oriented; reran tests/unit/test_mate.py + tests/functional/test_mate_script.py (32 passed) and adapter mate/vent cases (10 passed). Agent's gate after merging task-57: pytest 1018+1 skip x2, vitest 355, e2e 112.
<!-- SECTION:NOTES:END -->
