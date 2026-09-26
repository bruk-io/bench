---
id: task-69
title: 'Imperial fasteners: wood and drywall screws, and inch machine screws'
status: Done
assignee: []
created_date: '2026-09-24 02:33'
updated_date: '2026-09-26 14:58'
labels: []
milestone: m-10
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-11, operation 1. fasteners.py knows ISO metric screws only, so the vent's #6 drywall screws were drawn as M4. Add the common imperial sizes a US shop uses - #6, #8 and #10 wood/drywall screws (bugle and flat heads, pilot and clearance holes), and 1/4-20, #10-24, #8-32 machine screws - as the same Screw record, so hole(screw=..., countersink=...) works unchanged. Every figure cited to a published source (ASME B18.6.1 for wood screws, B18.6.3 for machine screws) in the module, the way the metric table is. Note that a bugle head is not a 90 degree countersink.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 #6/#8/#10 wood and drywall screws and 1/4-20, #10-24, #8-32 machine screws exist as Screw records with cited figures
- [x] #2 hole(screw=..., countersink=True) works with them, and a bugle head's angle is honoured or its difference stated
- [x] #3 The vent's drywall screws can be written as the real size
- [x] #4 Unit tests pin the figures
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
WOOD_6/8/10, DRYWALL_6/8/10, MACHINE_8_32/10_24/1_4_20; COUNTERSINK_82, BUGLE 61.5 degrees marked an estimate. hole() now cuts a countersink at the screw's own countersink_angle (measured 90/82/61.5), angle= overrides.
<!-- SECTION:NOTES:END -->
