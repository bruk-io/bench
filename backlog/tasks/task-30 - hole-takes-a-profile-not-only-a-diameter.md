---
id: task-30
title: 'hole() takes a profile, not only a diameter'
status: Done
assignee: []
created_date: '2026-09-22 22:41'
updated_date: '2026-09-22 13:26'
labels:
  - feature
milestone: Hardening
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`hole()` draws circles. The patent hinge's entire drive train is a D-profile bore - a shaft keyed to one link and free to turn in its neighbour - so task-27 had to build that bore by hand with a boolean, and then apply `PLA.hole_compensation` by hand as well, because going around `hole(printed=...)` loses the one place that knows what a printed hole takes back.

Keyed shafts, hex sockets, slots and T-slots are all the same gap: a bore whose section is not a circle still wants everything `hole()` gives it.

Small and self-contained. Depends on nothing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A bore can be cut from a 2D profile rather than a diameter
- [ ] #2 A profiled bore gets the same printed-hole compensation a circular one does, without the caller applying it by hand
- [ ] #3 The existing circular call is unchanged for every current caller
- [ ] #4 examples/fulcrum_hinge.py's D bore is cut this way instead of by hand
<!-- AC:END -->
