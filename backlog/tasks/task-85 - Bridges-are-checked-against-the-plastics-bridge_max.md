---
id: task-85
title: Bridges are checked against the plastic's bridge_max
status: To Do
assignee: []
created_date: '2026-09-27 19:19'
labels:
  - checks
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by task-84 (PR #32): the systainer tote's four socket ceilings span 14.6 mm, past every material's bridge_max (PLA 10, PETG 8, ASA 6 mm), yet nothing says so - check_overhangs reports them as 90 degree places like any ledge, and there is no bridge check. A flat ceiling held on two opposite sides is a bridge, printable up to bridge_max; one held on one side is a ledge that needs support at any size. The vent's README had to tell the two apart by hand. Decide whether check_overhangs classifies a 90 degree place as a bridge (supported on opposite edges) and passes it under bridge_max, warning past it, and fix the tote's sockets if they stay past it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A flat ceiling supported on two opposite edges is told apart from a one-sided ledge, measured on the shipped kernel
- [ ] #2 A bridge within bridge_max is not an overhang finding; one past it is, naming its span and the limit
- [ ] #3 The tote's socket ceilings either fit bridge_max or are reported
<!-- AC:END -->
