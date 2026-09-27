---
id: task-82
title: 'A blind pocket printed opening downward ends in a cone, not a flat ceiling'
status: Done
assignee: []
created_date: '2026-09-26 16:34'
updated_date: '2026-09-27 19:07'
labels:
  - features
milestone: m-12
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found in the vent (2026-09-26): the adapter's 12.5 mm magnet pockets open downward as it prints, so each flat pocket end is a 12.5 mm bridge, past PLA's 10 mm bridge_max. The vent drew a 45 degree cone ceiling by hand with a revolve, narrowing to the magnet's diameter at magnet depth so the magnet still seats flush on a ring. printable_top covers bores lying on their side, not an upright pocket's end. A pocket/hole option (like Top for horizontal holes) should do this when the part's orientation puts the pocket's floor overhead.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 hole()/pocket option gives an upright blind pocket a 45 degree (material max_overhang) cone end, keeping a stated seat depth and diameter
- [x] #2 Chosen automatically from printed= when the pocket's end faces down in print, as Top is for horizontal holes
- [x] #3 Measured on the shipped kernel: no overhang past the limit, seat at the asked depth
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #31. hole(..., end=End.CONE|AUTO): full diameter to depth, then a cone at max_overhang, built as one revolve. AUTO picks it from printed= when the mouth faces down within 30 degrees of the build direction. The seat is where the cut diameter ends (asked + hole compensation); the vent's hand-drawn cone seats at the magnet's own diameter - a seat= option would be needed to port it. A pocket leaning 30 degrees or more keeps a flat end (documented).
<!-- SECTION:NOTES:END -->
