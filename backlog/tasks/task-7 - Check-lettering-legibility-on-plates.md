---
id: task-7
title: Check lettering legibility on plates
status: Done
assignee: []
created_date: '2026-09-22 19:45'
updated_date: '2026-09-22 20:12'
labels:
  - ui
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Engraved text is drawn as a textured quad on a plate top. On the cabinet at default zoom the drawer numbers are tiny and were not inspected closely.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Lettering is readable when zoomed to a single plate, or a fix is filed
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Build the app, open box_with_hole.py, pan the front plate - engraved "screws" - to the middle of the view, and screenshot it at three zoom levels; look at the whole cabinet fitted as well.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Readable: with the front plate panned to the middle, "screws" reads clearly at three zoom-in steps and sharply at six and nine, dark ink on the plate top, the right way round and following the plate's perspective. At whole-scene fit it is a small dark mark, as expected at that scale - the cabinet's single-digit drawer numbers are likewise marks until zoomed. No fix needed; no browser test added, since legibility was judged by eye from screenshots (scratch script, not kept in the repo).
<!-- SECTION:NOTES:END -->
