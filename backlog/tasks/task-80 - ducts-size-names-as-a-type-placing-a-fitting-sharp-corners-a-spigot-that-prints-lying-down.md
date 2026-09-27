---
id: task-80
title: >-
  ducts: size names as a type, placing a fitting, sharp corners, a spigot that
  prints lying down
status: Done
assignee: []
created_date: '2026-09-26 16:07'
updated_date: '2026-09-27 18:55'
labels:
  - library
milestone: m-11
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found moving the vent onto ducts (2026-09-26), each worked round by hand in the vent and in examples/dust_line.py:
- No exported Literal of SIZES' names, so every script copies the list to make a knob choice.
- No way to place a fitting on an axis or a face: each is drawn upright at the origin and was rotated and moved by hand, directions checked by bounds.
- square_to_round refuses corner=0, so a sharp-cornered opening cannot be matched (the vent rounded its chamber to 2 mm and clamps its corner knob).
- No spigot that prints lying on its side (outside chamfered or teardropped underneath), for a port that has to be horizontal as printed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A Literal (or equivalent) of size names exported and used by dust_line.py
- [x] #2 A fitting can be placed by its end on a point and direction (or mated where its faces allow) without hand rotation
- [x] #3 square_to_round takes a sharp corner, or its refusal is explained and a sharp opening is still reachable
- [x] #4 Decide and either build or reject a horizontal-printable spigot, with the overhang measured
- [x] #5 Tests on the shipped kernel
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #30. SizeName Literal; place(fitting, end, *, at, toward, across) and end_of(fitting, end) - matches the vent's hand rotations exactly; square_to_round(corner=0) sharp inside, wall-sized corner outside. Lying spigot rejected (its outside leans 87 degrees, where the hose seals); built keyed_socket (teardrop hole to cut) + keyed_spigot (prints standing) instead, 0.201 mm at the 0.200 slide. dust_line now a posed line off the wye's tap. The vent still has its own size list and hand rotations - moving it is optional (projects/vent).
<!-- SECTION:NOTES:END -->
