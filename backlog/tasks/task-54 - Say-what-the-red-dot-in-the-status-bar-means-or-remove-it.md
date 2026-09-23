---
id: task-54
title: 'Say what the red dot in the status bar means, or remove it'
status: Done
assignee: []
created_date: '2026-09-23 01:18'
updated_date: '2026-09-23 02:01'
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
- [x] #1 What renders the dot and what state it reflects is written in the task notes
- [x] #2 A clean run's status bar shows nothing that reads as an error
- [x] #3 Anything left in its place names what it means
- [x] #4 A screenshot of the status bar after the change is in the PR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #4 (fa0a10f). The dot was #stale-bundle (web/index.html, class state, data-state=error, hidden toggled by bundleStale() in staleness.ts). `.state { display: inline-flex }` is an author rule and outranks the UA's [hidden] { display: none }, so the hidden indicator kept its box and ::before dot on every run. Fixed with `.state[hidden] { display: none }`, the guard .badge/.container already had. When the bundle really is stale it still shows its text 'stale examples' with a title - unchanged.

Regression test: tests/e2e/test_app.py::test_the_stale_bundle_indicator_is_invisible_when_nothing_is_stale (visibility, not the attribute); agent confirmed it fails with the rule removed. Gate: vitest 250, pytest 914+1 skip x2, e2e 82. Reviewed the bin screenshot: status bar reads '● ok 1 part' with no dot.
<!-- SECTION:NOTES:END -->
