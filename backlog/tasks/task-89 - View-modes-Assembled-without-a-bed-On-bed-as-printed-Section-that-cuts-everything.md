---
id: task-89
title: >-
  View modes: Assembled without a bed, On bed as printed, Section that cuts
  everything
status: To Do
assignee: []
created_date: '2026-09-28 01:15'
updated_date: '2026-09-28 03:01'
labels:
  - web
  - ui
  - export
milestone: m-13
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-12, step 2. Assembled: parts where the script puts them, no bed grid. On bed: each printed part laid the way it prints on the chosen printer's bed (Python computes the placements - the rule export and check_fits share - and sends them in the scene; the UI does no 3D maths), the build volume drawn, overhang places from check_overhangs painted. Section: the existing clipping as a mode, clipping reference and context bodies as well as parts, with capped cut faces so a foot in its pocket reads in section.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A mode control in the view switches Assembled / On bed / Section; the bed grid appears only On bed
- [ ] #2 On bed places come from Python in the scene and match export.as_printed; parts that do not fit the bed are marked
- [ ] #3 Overhang places are painted On bed
- [ ] #4 Section clips the reference and context bodies too
- [ ] #5 Tests: python scene placement unit tests; e2e switching modes; screenshots on the tower project and an example

- [ ] #6 The scene carries, per printed part, its print orientation and whether it fits the bed, and per face its area (all computed in Python); the inspector shows them in a part's 'How it is made' and on a face
<!-- AC:END -->
