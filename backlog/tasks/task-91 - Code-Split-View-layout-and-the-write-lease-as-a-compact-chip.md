---
id: task-91
title: 'Code | Split | View layout, and the write lease as a compact chip'
status: Done
assignee: []
created_date: '2026-09-28 01:15'
updated_date: '2026-09-28 03:47'
labels:
  - web
  - ui
milestone: m-13
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-12, step 4. A layout control giving the editor or the view the whole centre, or splitting it as today; remembered per browser (localStorage, wrapped in try/catch). The 'open for writing elsewhere' banner, which takes a third of the editor, becomes a compact chip in the header whose popover carries the same text and Take over.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Code, Split and View layouts, switchable by a control and a shortcut, remembered per browser
- [x] #2 The lease notice is a header chip with the same information and Take over in its popover; nothing is lost from what the banner said
- [x] #3 e2e covers both; screenshots
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #37. Header Code | Split | View, Ctrl/Cmd+\ cycles, data-layout on #groups before the first scene, stored as bench.layout with try/catch; a notice up while View is chosen drops the centre back to Split. bench-lease-chip: 'read-only · held elsewhere' / 'taken over' in red; popover has the banner's full text, Take over and its question (words from status.ts readOnlyWords); opens by itself when this tab loses the lease. At <=760 px the parts chip hides. Left for task-94: the status bar's own read-only chip (#standing) repeats the header's; View could fold the file tree too.
<!-- SECTION:NOTES:END -->
