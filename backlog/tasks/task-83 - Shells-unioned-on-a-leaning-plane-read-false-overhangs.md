---
id: task-83
title: Shells unioned on a leaning plane read false overhangs
status: To Do
assignee: []
created_date: '2026-09-26 16:37'
labels:
  - operations
  - checks
dependencies:
  - task-77
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Left from task-77 (PR #27): a 60 mm spigot shelled onto an elbow's leaning `end` and unioned still reads 87, 79 and 50 degrees at elbow turns of 20, 33 and 40 degrees. The two cavities' walls meet along a leaning line that no 32-bit float lands on exactly, so the grid rounding that fixed axis-aligned joins cannot. Workaround, in shell's docstring: overlap by a wall, or sweep the run in one piece (what ducts does). Fix only if a real design needs it: e.g. shell() taking several pieces and cutting one cavity, or joining along a leaning plane by a small overlap automatically.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The three measured cases from test_seams_measured read no false overhang, or the limit stays documented with a reason it cannot be fixed
- [ ] #2 A real overhang on the same construction is still found
<!-- AC:END -->
