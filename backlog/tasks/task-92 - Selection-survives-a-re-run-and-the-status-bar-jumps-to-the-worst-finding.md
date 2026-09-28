---
id: task-92
title: 'Selection survives a re-run, and the status bar jumps to the worst finding'
status: Done
assignee: []
created_date: '2026-09-28 01:15'
updated_date: '2026-09-28 04:49'
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
- [x] #1 A selected part or face stays selected across re-runs while its ref exists; otherwise the project is selected
- [x] #2 Clicking the status bar's count selects the worst part and lights its first place
- [x] #3 The selection round-trips through the URL
- [x] #4 e2e covers all three
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #39. subjects.ts: keptAcross, worstPlace, linkOf/linked/linkedIn. A part keeps its selection when a run removes its lit place (the real bug found). The count selects the worst part and lights the first place of its worst finding. Hash names only parts and faces (#part=, #face=), written with replaceState, not the project; unknown refs fall back quietly. Gate after merging task-89: 1560 pytest, 152 e2e, 494 vitest.
<!-- SECTION:NOTES:END -->
