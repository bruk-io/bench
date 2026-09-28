---
id: task-94
title: >-
  Inspector polish: knobs reachable from a part, zoom to a lit place, no empty
  sections
status: Done
assignee: []
created_date: '2026-09-28 03:01'
updated_date: '2026-09-28 06:06'
labels:
  - web
  - ui
milestone: m-13
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
What the task-88 agent and review found still off after the inspector landed (PR #36): knobs show only with nothing selected, so tuning while reading a part's findings means leaving the part; a lit place is never framed and is often on an underside the default camera cannot see; every face shows a mostly empty 'Findings naming it'; the rail now holds a single button; sheet names truncate in the export; the laser cabinet's project view is long with Export far down.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Knobs reachable while a part or face is selected (e.g. a collapsible Knobs section kept at the top, or a pinned strip) without losing the selection
- [x] #2 Clicking a place frames it: the camera turns and zooms to show the lit faces, including undersides
- [x] #3 Sections with nothing in them are not shown
- [x] #4 The one-button rail is removed or earns its place; sheet names are readable; long project views keep Export reachable
- [x] #5 e2e and screenshots

- [x] #6 The lease has one home: the status bar's read-only chip (#standing) goes, the header chip stays
- [x] #7 View layout folds the file tree too, so the view takes everything but the inspector
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #41. Knobs are a foldable section over every subject (open on the project, folded on a selection; one element, so a half-typed value survives). Python sends each face/node/part a box and a look-from direction (faces x2 + out of the part x1.5 + standing view x1); the view reuses Fit's box fitting and, On bed, moves box and direction by the placement matrix (the one small bit of 3D maths in TS, flagged). Empty sections hidden; the rail is gone (a header files button); sheet notes under names; Export heading sticky; #standing removed; View folds the file tree. Left over: task-95.
<!-- SECTION:NOTES:END -->
