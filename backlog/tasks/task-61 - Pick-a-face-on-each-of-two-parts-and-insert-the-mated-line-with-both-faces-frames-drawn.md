---
id: task-61
title: >-
  Pick a face on each of two parts and insert the mated() line, with both faces'
  frames drawn
status: To Do
assignee: []
created_date: '2026-09-23 17:20'
labels: []
milestone: m-8
dependencies:
  - task-59
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-10 step 4, under decision-7's rule: a pick writes into the script, the app keeps no selection state beyond the pick itself. Click a face, shift-click a face on another part; the view draws each face's frame (origin, normal, X - exactly what plane_of answers, computed in Python and sent to the viewer, which only draws); an 'Insert fit' action writes `mated(<part>, ref("..."), <part>, ref("..."), fit=Fit.CONTACT)` at the cursor. The existing single-face click and Insert ref must keep working unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Shift-click selects a second face on a different part; both are highlighted
- [ ] #2 Both faces' frames are drawn, from numbers Python computed
- [ ] #3 Insert fit writes a mated() line with both refs
- [ ] #4 Single-face click and Insert ref behave as before
- [ ] #5 e2e test drives the pick and asserts the inserted text; screenshot of the frames
<!-- AC:END -->
