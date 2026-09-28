---
id: task-90
title: 'Context bodies: shown for context, never exported'
status: Done
assignee: []
created_date: '2026-09-28 01:15'
updated_date: '2026-09-28 01:54'
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
- [x] #1 A script API (e.g. context(solid, label=...)) adds a body to the scene as context
- [x] #2 Context bodies are drawn translucent and never reach any export or the part list
- [x] #3 A test proves an export with context bodies is byte-identical to one without
- [x] #4 Documented in README/DESIGN; an example uses it
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #33. context(body, *, label) injected into each run beside show; built after parts/sheets/files; reaches the scene only as OkScene.context and stage.widened. Drawn sand-coloured translucent, clipped by section, named faces pickable with a 'context - not a part, not exported' tooltip; a part along the ray wins a click. Export byte-identical with and without, on the real kernel. Takes a Solid only. Untested: deferred3d replay before three.js loads; context() on an imported body.
<!-- SECTION:NOTES:END -->
