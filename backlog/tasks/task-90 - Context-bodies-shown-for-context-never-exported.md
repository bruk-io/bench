---
id: task-90
title: 'Context bodies: shown for context, never exported'
status: To Do
assignee: []
created_date: '2026-09-28 01:15'
labels:
  - web
  - ui
  - export
milestone: m-13
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-12. A script can show a body for context - a reference piece in its seated pose, a ghost of a module's body - without it becoming a part: drawn translucent, pickable for its ref if it has names, never in an STL, a 3MF, the part list or check_fits. Found building projects/tower's fit view, where the Festool pieces could only appear as the app's single reference.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A script API (e.g. context(solid, label=...)) adds a body to the scene as context
- [ ] #2 Context bodies are drawn translucent and never reach any export or the part list
- [ ] #3 A test proves an export with context bodies is byte-identical to one without
- [ ] #4 Documented in README/DESIGN; an example uses it
<!-- AC:END -->
