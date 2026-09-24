---
id: task-69
title: 'Imperial fasteners: wood and drywall screws, and inch machine screws'
status: To Do
assignee: []
created_date: '2026-09-24 02:33'
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
- [ ] #1 #6/#8/#10 wood and drywall screws and 1/4-20, #10-24, #8-32 machine screws exist as Screw records with cited figures
- [ ] #2 hole(screw=..., countersink=True) works with them, and a bugle head's angle is honoured or its difference stated
- [ ] #3 The vent's drywall screws can be written as the real size
- [ ] #4 Unit tests pin the figures
<!-- AC:END -->
