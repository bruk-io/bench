---
id: task-81
title: 'Checks take a Part and read how it prints, all of them alike'
status: Done
assignee: []
created_date: '2026-09-26 16:07'
updated_date: '2026-09-27 18:33'
labels:
  - checks
milestone: m-12
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found moving the vent onto ducts: check_fits(Part) reads a Printed part's orientation, but check_overhangs (and the others) still want a Solid plus an explicit orient. The same part is passed two ways in one script. Every check that depends on how a part prints should take a Part and read its stock, with orient= still overriding.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 check_overhangs, check_wall and any other orientation-dependent check accept a Part and read its Printed orientation
- [x] #2 orient= still overrides; a bare Solid works as before
- [x] #3 Tests
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #29. check_overhangs(part) reads the Printed stock's orientation and plastic; orient= and material= override. check_wall takes a Part but only reads its body. No other check depends on orientation.
<!-- SECTION:NOTES:END -->
