---
id: task-54
title: 'Say what the red dot in the status bar means, or remove it'
status: In Progress
assignee: []
created_date: '2026-09-23 01:18'
updated_date: '2026-09-23 01:19'
labels: []
milestone: m-5
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In tools.qa's screenshots of gridfinity_cabinet.py and gridfinity_bin.py (2026-09-22), the status bar shows "● ok  14 parts on 7 sheets  ●" - a red dot after the part count, on runs that are clean. Nobody looking at it could say what it means. It is not the stale-examples indicator, which is text.

Find what renders it and what state it reflects. If it carries meaning, it says that meaning (label, tooltip or accessible name) and is not red on a clean run; if it is vestigial, it goes. task-52 puts a "has this reached the host" indicator in the same bar, so settle this first.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 What renders the dot and what state it reflects is written in the task notes
- [ ] #2 A clean run's status bar shows nothing that reads as an error
- [ ] #3 Anything left in its place names what it means
- [ ] #4 A screenshot of the status bar after the change is in the PR
<!-- AC:END -->
