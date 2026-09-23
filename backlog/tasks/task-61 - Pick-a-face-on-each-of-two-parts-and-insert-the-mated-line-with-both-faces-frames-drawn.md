---
id: task-61
title: >-
  Pick a face on each of two parts and insert the mated() line, with both faces'
  frames drawn
status: Done
assignee: []
created_date: '2026-09-23 17:20'
updated_date: '2026-09-23 18:53'
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
- [x] #1 Shift-click selects a second face on a different part; both are highlighted
- [x] #2 Both faces' frames are drawn, from numbers Python computed
- [x] #3 Insert fit writes a mated() line with both refs
- [x] #4 Single-face click and Insert ref behave as before
- [x] #5 e2e test drives the pick and asserts the inserted text; screenshot of the frames
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #19. views._frames_view calls plane_of once per named planar face (not per triangle) and sends origin/normal/x on PartView.frames; the viewer draws two short arrows and a dot per picked frame in a group outside `parts` (never pickable). Shift-click picks a second face only on a different part (chosenSecond); a plain click resets to one pick; Insert ref untouched. Insert fit writes `mated(<fixed>, ref("..."), <moving>, ref("..."))` with no fit= (CONTACT default); <fixed>/<moving> are the parts' labels as Python identifiers - an honest stand-in for the script's own Part variables, which the app cannot know (decision-7). A face plane_of cannot frame shows no frame and #fit-why says why. views.py gained solids in the import-boundary table.

The frames make decision-10's point visible: they sit at the corner each face was authored from, not its middle. Reviewed: screenshots of the two-face pick and the inserted line; trial-merged current main (with task-65's turned-over cut faces) and reran the shift-click e2e test and the frames-lie-on-their-triangles adapter test - both pass. Agent's gate: vitest 357, pytest 1040+1 skip x2, e2e 121 (its pre-edit baseline run was contaminated by concurrent edits, said so).
<!-- SECTION:NOTES:END -->
