---
id: task-1
title: Merge the plates branch and delete merged branches
status: Done
assignee: []
created_date: '2026-09-22 19:44'
updated_date: '2026-09-22 20:11'
labels:
  - chore
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`plates` holds 6 commits not on main (project settings, named files, plates, one 3D view, selection colour fix). `named-files` is fully contained in `plates`.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A PR for plates is opened, passes the gate, and is squash-merged into main
- [x] #2 plates and named-files are deleted locally and on GitHub
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Open a PR for plates, run the full gate, squash-merge, delete merged branches locally and on GitHub.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #8 (74ac63c) after the full gate passed (142 component, 651 Python x2, 48 e2e). A git add of already-removed paths left the backlog files out of #8, so #9 (7b032ef) carried backlog/, the CLAUDE.md section and the doc links. plates, named-files and backlog-docs deleted locally and on GitHub.
<!-- SECTION:NOTES:END -->
