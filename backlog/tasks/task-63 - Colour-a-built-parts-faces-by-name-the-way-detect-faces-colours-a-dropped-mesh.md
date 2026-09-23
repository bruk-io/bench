---
id: task-63
title: >-
  Colour a built part's faces by name, the way detect faces colours a dropped
  mesh
status: Done
assignee: []
created_date: '2026-09-23 17:20'
updated_date: '2026-09-23 18:29'
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
- [x] #1 A toggle colours every named face of every built part, adjacent faces distinguishable
- [x] #2 Clicking still reveals the face's ref, and part and finding highlights still show
- [x] #3 Off by default; the toggle survives a re-run
- [x] #4 e2e test and a screenshot
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #16. Viewer-only: task-40's pastels() golden-angle palette, one index run across every part's named faces (from the scene's existing mesh.refs / ref_index); a face's pastel is one more `base` for shade(), so selection/cursor/hover/finding highlight priority is unchanged and picking untouched. 'colour faces' toggle beside 'section', state in the viewer closure, survives re-runs. 4 e2e tests; e2e 120 after merging main (task-62).

Known limit, by design: laser sheet parts' large faces stay grey - they are unnamed (ref_index 0; plates.py names only cut features like holes, pulls, engravings), and colour faces paints named faces only, the same rule a click follows. Reviewed on main: the bin off/on (every face distinct) and the vent with section + colour faces together.
<!-- SECTION:NOTES:END -->
