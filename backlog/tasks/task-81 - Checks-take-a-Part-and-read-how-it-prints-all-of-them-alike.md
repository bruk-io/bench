---
id: task-81
title: 'Checks take a Part and read how it prints, all of them alike'
status: To Do
assignee: []
created_date: '2026-09-26 16:07'
labels:
  - checks
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found moving the vent onto ducts: check_fits(Part) reads a Printed part's orientation, but check_overhangs (and the others) still want a Solid plus an explicit orient. The same part is passed two ways in one script. Every check that depends on how a part prints should take a Part and read its stock, with orient= still overriding.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 check_overhangs, check_wall and any other orientation-dependent check accept a Part and read its Printed orientation
- [ ] #2 orient= still overrides; a bare Solid works as before
- [ ] #3 Tests
<!-- AC:END -->
