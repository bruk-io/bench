---
id: task-64
title: 'A printed part exports in the way it prints, not where an assembly put it'
status: Done
assignee: []
created_date: '2026-09-23 17:50'
updated_date: '2026-09-23 22:19'
labels: []
milestone: m-7
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by task-59 (2026-09-23): a printed part's STL and 3MF are its mesh written exactly where the script put it, and nothing on the way out reads Orient. So a part posed in an assembly - the enclosure example's lid (Orient(up=-Z)), or anything mated() turns over - exports in its assembly pose, not lying on the bed the way it prints. decision-10 says print orientation stays apart from where a part sits in an assembly; task-59's mating turns Orient.up with the body so the checks read it right, but the files still come out posed.

Export each printed part laid on the bed by its Orient (up, and bed_face when given): rotated so `up` is +Z and moved so its lowest point is z = 0, in the STL and in each 3MF object - while the app's view keeps showing the assembly pose.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A printed part's STL and 3MF lie on the bed the way its Orient says, whatever the assembly pose
- [x] #2 The enclosure lid exports lip-up, and a part mated upside down exports as it was authored
- [x] #3 The 3D view still shows parts where the assembly put them
- [x] #4 Functional tests on the exported bytes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #22. export.as_printed(mesh, up, bed_along=None): rotate so Orient.up is +Z (to_local of plane(ORIGIN, up, bed_along) - bed_along, an Orient.bed_face's authored X, settles the free spin about up), then drop the lowest point to z = 0 and centre X/Y on the origin (slicer convention; needs no bed size). views._as_printed applies it only when building scene['files'] (STL/3MF); PartView.mesh - what the 3D view draws - stays in the assembly pose. A bad bed_face propagates plane_of's error, failing the run like any bad ref. Stale docstrings in mate.py/DESIGN.md/README ('exports the posed mesh verbatim') corrected.

Tests: 8 pure-transform unit tests; 8 adapter tests on real STL/3MF bytes from the shipped kernel - enclosure lid lip-up, box unchanged, both 3MF objects, a part mated upside down checked by which NAMED face lands at z = 0 (a cube's box alone cannot tell a turn from a drop), a named bed_face and a bad one; view mesh confirmed still posed. Reviewed as_printed; reran tests/unit/test_export.py + tests/adapter/test_export_as_printed.py (39 passed). Gate: pytest 1084+1 skip x2, vitest 357, e2e 121.
<!-- SECTION:NOTES:END -->
