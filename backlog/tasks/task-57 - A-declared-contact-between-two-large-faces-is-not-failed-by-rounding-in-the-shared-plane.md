---
id: task-57
title: >-
  A declared contact between two large faces is not failed by rounding in the
  shared plane
status: To Do
assignee: []
created_date: '2026-09-23 14:35'
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
- [ ] #1 Two large rounded-square plates with holes, stacked face to face on the same plane, pass check_contact
- [ ] #2 A one-micron sink of the same plates, and the existing boss-sunk-one-micron case, still fail
- [ ] #3 The tolerance rule is written down in checks.py with the measurements behind it, as _SHARED_SLACK's docstring is today
- [ ] #4 Covered by tests against the modeller the app ships
<!-- AC:END -->
