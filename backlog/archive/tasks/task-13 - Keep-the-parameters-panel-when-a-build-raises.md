---
id: task-13
title: Keep the parameters panel when a build raises
status: To Do
assignee: []
created_date: '2026-09-22 20:11'
labels:
  - ui
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A failed run comes back as an ErrorScene, which carries no parameters, so a build that raises for a bad setting takes the parameters panel away - the one place the person would fix it. Still open from decision-2 (confirmed against the code 2026-09-15: ErrorScene has only ok, error, stdout and stderr).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A script whose build raises still shows its declared parameters and their current values
- [ ] #2 Editing a parameter from that state re-runs the script
- [ ] #3 A script that fails before declaring its settings (a syntax error) shows no stale panel
<!-- AC:END -->
