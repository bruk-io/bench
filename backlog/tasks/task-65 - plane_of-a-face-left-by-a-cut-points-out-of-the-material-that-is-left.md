---
id: task-65
title: plane_of a face left by a cut points out of the material that is left
status: Done
assignee: []
created_date: '2026-09-23 17:50'
updated_date: '2026-09-23 18:50'
labels: []
milestone: m-7
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by task-59 (2026-09-23): plane_of promises a normal pointing out of the material, but for a face a cut leaves behind (e.g. the vent attachment's groove/top, the ceiling of a pocket cut into it) it answers the cutting tool's own face frame - normal +Z, into the cavity's roof rather than out of the part's material there. So mated() onto the inside of a cut would come out turned over. Decide whether a cut's faces answer the frame turned over (out of the remaining material), keeping X the profile's way as `bottom` already does, and test mating onto a pocket's floor and ceiling.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 plane_of on a face a cut leaves points out of the material that remains
- [x] #2 A part mated onto a pocket's floor sits in the pocket, not turned over
- [x] #3 Existing plane_of callers (sketches placed on cut faces) are checked and kept working, with any change they need
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #18. topology: Moved gains a defaulted cavity=False; the naming walk marks a cut's tool cavity=True and turns every face under it over (normal reversed, X kept the profile's way, Y reversed, a round face's material on its other side); a tool inside a tool turns back. Kernels ignore the field. A pocket's floor now faces up into the pocket, a groove's ceiling faces down, a hole() bore's wall faces its axis - and axis_of is unchanged, so round mates still put a pin into a drilled bore the drill's way (test added).

Callers checked by logging every plane_of on a cut face across the unit and functional suites (every example) plus a grep of adapter/e2e and projects/frame: none relied on the old frame. Three tests pinned the old behaviour and were rewritten (listed in the PR). Merged main (task-60) with keep-both resolutions and a duplicate scan. Gate: pytest 1048+1 skip x2, vitest 355, e2e 120.
<!-- SECTION:NOTES:END -->
