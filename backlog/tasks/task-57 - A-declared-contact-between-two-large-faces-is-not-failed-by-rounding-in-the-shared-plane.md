---
id: task-57
title: >-
  A declared contact between two large faces is not failed by rounding in the
  shared plane
status: Done
assignee: []
created_date: '2026-09-23 14:35'
updated_date: '2026-09-23 17:50'
labels: []
milestone: m-7
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
check_contact (src/bench/checks.py contact_between) fails when the kernel's intersection volume exceeds _SHARED_SLACK = 1e-6 mm3, a figure measured on a 10 mm cube against a cube and an 8 mm disc with a boss - both read exactly 0.0.

Found modelling a wall vent (projects/frame, 2026-09-23): a 317.5 mm rounded-square frame flange and an attachment whose back face sits exactly on it (both extruded from the same plane, z = flange thickness) read 0.001 mm3 shared, so the app shows a red contact ERROR on a design that is correct. Bisected in the app: it stays with the hook, the countersunk screw holes and all 32 magnet pockets removed, and it disappears when the attachment is lifted 0.001 mm - so it is the coincident plane itself, on large faces with holes and arcs, not any feature. A real one-micron sink read 0.0494 mm3 in the original measurement, so a fixed slack between the two is not obviously safe either.

Decide what the check should measure for large coplanar faces: e.g. a slack that scales with the contact area, a thin-slab test (shared volume divided by the contact face's area = mean penetration depth, compared against a length tolerance), or min_gap on the faces. Keep the existing cube/disc cases and the one-micron sink failing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Two large rounded-square plates with holes, stacked face to face on the same plane, pass check_contact
- [x] #2 A one-micron sink of the same plates, and the existing boss-sunk-one-micron case, still fail
- [x] #3 The tolerance rule is written down in checks.py with the measurements behind it, as _SHARED_SLACK's docstring is today
- [x] #4 Covered by tests against the modeller the app ships
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #14. Rule: shared volume <= _SHARED_SLACK (1e-6 mm3) is a touch outright (small coincident faces read 0.0); above it, shared volume / contact area = mean penetration depth, judged against _DEPTH_SLACK = 1e-6 mm. Contact area = half the surface area of the intersection solid's own mesh (a bounding box was tried and rejected: two 1-micron islands at opposite corners inflate the box and pass a real overlap - regression test added).

Measured on the shipped modeller: cube/disc coincident 0.0; boss sunk 1 um 0.04944 mm3 = 0.001 mm deep; the vent's 317.5 mm plates coincident 0.000505 mm3 = 2.8e-8 mm deep (pass); same plates sunk 1 um 29.62 mm3 = 0.001 mm (fail). The 'existing boss sink case' was only a docstring figure - now a kernel case. projects/frame's check_contact(plate, fitting) passes with it restored. Gate: pytest 971+1 skip x2, e2e 112.
<!-- SECTION:NOTES:END -->
