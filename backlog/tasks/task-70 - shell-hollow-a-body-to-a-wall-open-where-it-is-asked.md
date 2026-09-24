---
id: task-70
title: 'shell(): hollow a body to a wall, open where it is asked'
status: To Do
assignee: []
created_date: '2026-09-24 02:33'
labels: []
milestone: m-10
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-11, operation 2. The vent built its funnel and its manifold's hopper as an outer loft minus an inner loft, by hand, twice. shell(body, wall, open=(...faces)) hollows a body bench knows the recipe of - extrude, revolve, loft/hull of faces - by re-running that recipe on the profile inset by offset() and subtracting it, leaving the named faces open. No kernel change. A tapered or hulled body gets its wall measured in the profile's plane, not normal to the surface: say so, and let check_wall measure the real thing. Name the inner faces so they can be picked and mated.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 shell() hollows an extrusion, a revolve and a two-profile loft to a given wall, open at named faces
- [ ] #2 Inner faces are named and pickable
- [ ] #3 A shell thinner than the printer's minimum wall is caught by the existing wall check
- [ ] #4 The vent's funnel and hopper can be written with it (show one in an example)
- [ ] #5 Tested against the shipped modeller
<!-- AC:END -->
