---
id: task-97
title: A reference's survey takes 155 s on a large mesh
status: To Do
assignee: []
created_date: '2026-09-28 13:56'
labels:
  - worker
  - survey
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by task-96 (PR #42): the survey of projects/tower's reference (5 pieces, ~250k triangles) takes ~155 s, restarts after every run that interrupts it, and so on tower the report lands only after 2.5 minutes of not pressing Run. Native profile: survey._rounds/_round_from ~100 s, facets.thicknesses/first_hit ~43 s, _repeats/_alike ~23 s. Options: make those passes faster (vectorise, spatial index, sample), cache a survey by the mesh's hash so it runs once per file, and/or run the survey in its own worker so runs never wait on or interrupt it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The survey of a ~250k-triangle reference completes in well under a minute, measured, or is cached by the mesh's hash so it runs once per file
- [ ] #2 A run never interrupts or restarts a survey that has already been computed for that mesh
- [ ] #3 Existing survey results unchanged on the test meshes (same rounds, walls, repeats)
<!-- AC:END -->
