---
id: task-3
title: Check whether params on ErrorScene is still open
status: Done
assignee: []
created_date: '2026-09-22 19:44'
updated_date: '2026-09-22 20:12'
labels:
  - docs
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-2 (formerly PROPOSAL-PARAMS.md) lists `params` on `ErrorScene` as still open, so a build that raises would keep the parameters panel. Not verified whether this was since done.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Confirmed done or not against the code
- [x] #2 decision-2's status reflects the answer; if not done, a follow-up task exists
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Check ErrorScene and views.failed in the code; update decision-2's status; file a follow-up if still open.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Not done: ErrorScene (src/bench/scene.py) carries only ok, error, stdout and stderr, and views.failed builds nothing else. decision-2's status says so with the date, and the work is task-13.
<!-- SECTION:NOTES:END -->
