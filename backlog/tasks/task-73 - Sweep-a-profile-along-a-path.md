---
id: task-73
title: Sweep a profile along a path
status: To Do
assignee: []
created_date: '2026-09-24 02:34'
updated_date: '2026-09-24 02:34'
labels: []
milestone: m-10
dependencies:
  - task-70
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-11, operation 5. The modeller has no sweep; the vent faked its 90 degree turn with a hood and could not make an S-bend or an offset. Compare two routes first, with measurements, and write the comparison down: (a) a chain of hulls between successive profile slices along the path - exact for convex profiles (circles and rectangles: every duct and pipe), faces unnamed; (b) a mesh computed in Python (rings along the path, triangulated, watertight) built with imported - any profile, faces unnamed unless tagged. Then build the winner as sweep(profile, path) with the path from lines and arcs, and make shell() (task-70) work on its result.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The two routes are compared with numbers (accuracy, triangle count, time, faces) and the choice written down
- [ ] #2 sweep() takes a profile and a path of lines and arcs
- [ ] #3 A swept duct bend can be shelled and mated
- [ ] #4 Tested against the shipped modeller; an example runs in the gate
<!-- AC:END -->
