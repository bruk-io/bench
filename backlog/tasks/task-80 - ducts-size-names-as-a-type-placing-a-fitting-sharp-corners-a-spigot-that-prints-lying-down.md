---
id: task-80
title: >-
  ducts: size names as a type, placing a fitting, sharp corners, a spigot that
  prints lying down
status: To Do
assignee: []
created_date: '2026-09-26 16:07'
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
- [ ] #1 A Literal (or equivalent) of size names exported and used by dust_line.py
- [ ] #2 A fitting can be placed by its end on a point and direction (or mated where its faces allow) without hand rotation
- [ ] #3 square_to_round takes a sharp corner, or its refusal is explained and a sharp opening is still reachable
- [ ] #4 Decide and either build or reject a horizontal-printable spigot, with the overhang measured
- [ ] #5 Tests on the shipped kernel
<!-- AC:END -->
