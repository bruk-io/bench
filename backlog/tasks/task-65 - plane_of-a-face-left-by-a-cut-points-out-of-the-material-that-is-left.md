---
id: task-65
title: plane_of a face left by a cut points out of the material that is left
status: In Progress
assignee: []
created_date: '2026-09-23 17:50'
updated_date: '2026-09-23 17:59'
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
- [ ] #1 plane_of on a face a cut leaves points out of the material that remains
- [ ] #2 A part mated onto a pocket's floor sits in the pocket, not turned over
- [ ] #3 Existing plane_of callers (sketches placed on cut faces) are checked and kept working, with any change they need
<!-- AC:END -->
