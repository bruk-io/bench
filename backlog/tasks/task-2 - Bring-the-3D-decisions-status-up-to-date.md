---
id: task-2
title: Bring the 3D decision's status up to date
status: Done
assignee: []
created_date: '2026-09-22 19:44'
updated_date: '2026-09-22 20:12'
labels:
  - docs
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-1 (formerly PROPOSAL-3D.md) has a status line that still lists "plate layout" as remaining and predates dropping the desktop manifold3d path and laser parts becoming plates in the 3D view.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The status line says what is implemented and what genuinely remains
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Read decision-1 against the code and rewrite its status line only; leave the recorded proposal as decided.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
decision-1's status now records that the manifold3d CLI adapter and parity test were removed (one Python kernel over Manifold WASM) and that laser parts are drawn as plates. The task's premise was partly wrong: "plate layout" in the proposal means a print-bed layout for printed parts (the 3D nest), which is still missing, so it stays listed as remaining with fonttools text and closing the Stock union.
<!-- SECTION:NOTES:END -->
