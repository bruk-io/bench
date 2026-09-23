---
id: task-63
title: >-
  Colour a built part's faces by name, the way detect faces colours a dropped
  mesh
status: To Do
assignee: []
created_date: '2026-09-23 17:20'
labels: []
milestone: m-8
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
'detect faces' (task-40) colours a dropped mesh's detected flats in golden-angle pastels and lets a flat be clicked; nothing does the same for a part a script builds, although every face of a built part already has a name (the refs the viewer shows on click). A 'colour faces' toggle gives each named face of each built part its own colour from task-40's palette, so neighbouring faces stay distinguishable and a maker can see which face is which before picking one (task-61). Which triangles belong to which face comes from Python, as it already does for picking; the viewer only colours.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A toggle colours every named face of every built part, adjacent faces distinguishable
- [ ] #2 Clicking still reveals the face's ref, and part and finding highlights still show
- [ ] #3 Off by default; the toggle survives a re-run
- [ ] #4 e2e test and a screenshot
<!-- AC:END -->
