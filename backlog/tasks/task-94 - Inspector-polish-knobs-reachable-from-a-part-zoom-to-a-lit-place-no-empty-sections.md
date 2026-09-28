---
id: task-94
title: >-
  Inspector polish: knobs reachable from a part, zoom to a lit place, no empty
  sections
status: To Do
assignee: []
created_date: '2026-09-28 03:01'
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
- [ ] #1 Knobs reachable while a part or face is selected (e.g. a collapsible Knobs section kept at the top, or a pinned strip) without losing the selection
- [ ] #2 Clicking a place frames it: the camera turns and zooms to show the lit faces, including undersides
- [ ] #3 Sections with nothing in them are not shown
- [ ] #4 The one-button rail is removed or earns its place; sheet names are readable; long project views keep Export reachable
- [ ] #5 e2e and screenshots
<!-- AC:END -->
