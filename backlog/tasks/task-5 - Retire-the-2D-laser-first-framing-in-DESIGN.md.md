---
id: task-5
title: 'Retire the "2D, laser-first" framing in DESIGN.md'
status: Done
assignee: []
created_date: '2026-09-22 19:45'
updated_date: '2026-09-22 20:12'
labels:
  - docs
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
DESIGN.md intro and Known limits still describe v1 as "2D, laser-first". Every part is now drawn in one 3D view and the flat drawing is an export.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Intro and Known limits describe the current scope without contradicting the web/ section
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Reword DESIGN.md's intro scope paragraph and Known limits preamble; add the new modules to its layout table.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Intro now says scope began as laser-cut parts, each drawn as the plate it is cut from, beside 3D as a tree; "Flat parts are unchanged" became "The cut files are unchanged"; Known limits no longer frames itself as "2D, laser-first". The layout table gained triangulate.py and plates.py, which it was missing.
<!-- SECTION:NOTES:END -->
