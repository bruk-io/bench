---
id: task-88
title: 'The inspector: one home for knobs, parts, findings, faces and exports'
status: Done
assignee: []
created_date: '2026-09-28 01:14'
updated_date: '2026-09-28 03:01'
labels:
  - web
  - ui
milestone: m-13
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-12, step 1: restructure only, no new features. A right-hand inspector (a Web Component organism) whose content follows the selection: nothing -> project (knobs, parts with status badges, Export all); a part -> its findings as a list of places (click lights the place), how it prints, its faces as a tree (the refs tab), Export this part; a face -> ref, Insert in code, area/normal, findings naming it; a reference mesh -> survey, detect faces, placement (the controls now floating over the view). Remove the duplicates: the rail keeps only the project/files; the Refs, Parameters, Sheets and Problems rail tabs go; the bottom panel keeps only Output (print, log, stderr), folded by default; the view toolbar keeps only ways of looking. The status bar's warning/error count selects the worst part. Split main.ts where this touches it rather than growing it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 An inspector shows the project, a part, a face or a reference mesh according to the selection; clicking empty space returns to the project
- [x] #2 Knobs, parts with badges, findings per part (each place clickable), faces tree, exports and reference-mesh tools all live in the inspector and nowhere else
- [x] #3 Rail, panel and view toolbar lose every duplicate listed in decision-12
- [x] #4 Every existing e2e behaviour still passes (rewritten against the new locations where it pinned the old ones)
- [x] #5 Screenshots of each inspector state on examples and a project
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #36. bench-inspector follows the selection (project / part / face / reference mesh); Escape, empty space or the breadcrumb return to the project. New: bench-exports (absorbs Files and sheets), bench-reference-tools, bench-reference-list; bench-violation shows places as buttons. Rail is project/files only; panel is Output+stderr folded; view bar is colour faces, section, zoom. main.ts 2594 -> 2097 (reference-body.ts, subjects.ts). Not in the scene yet, so not shown: a part's orientation/bed fit, its fits with mates, a face's area - moved to task-89. Polish left: task-94.
<!-- SECTION:NOTES:END -->
