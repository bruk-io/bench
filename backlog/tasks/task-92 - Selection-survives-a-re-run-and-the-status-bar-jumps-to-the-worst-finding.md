---
id: task-92
title: 'Selection survives a re-run, and the status bar jumps to the worst finding'
status: To Do
assignee: []
created_date: '2026-09-28 01:15'
labels:
  - web
  - ui
milestone: m-13
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-12, step 5. Selection is held by ref, so editing a knob or the script and re-running keeps the same part or face selected when its ref still exists, and falls back to the project when it does not. The status bar's count selects the part with the worst finding and lights its first place. Selection goes in the URL hash so a link opens on the same subject.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A selected part or face stays selected across re-runs while its ref exists; otherwise the project is selected
- [ ] #2 Clicking the status bar's count selects the worst part and lights its first place
- [ ] #3 The selection round-trips through the URL
- [ ] #4 e2e covers all three
<!-- AC:END -->
