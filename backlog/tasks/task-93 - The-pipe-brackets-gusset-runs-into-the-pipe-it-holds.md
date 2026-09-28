---
id: task-93
title: The pipe bracket's gusset runs into the pipe it holds
status: Done
assignee: []
created_date: '2026-09-28 01:54'
updated_date: '2026-09-28 02:35'
labels:
  - examples
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by task-90 (PR #33) the moment the pipe was drawn as context: check_fit(bracket, pipe, Fit.CLEARANCE, PLA) reads 0.000 mm - the gusset rises 10 mm, past the 8 mm of wall under the pipe, and clips the pipe just outside the ear. With the pipe cut 1 mm inside each ear face the check passes, so the pipe is on the bore's axis and the gusset is the fault. Visible in the example's screenshot. An example must not ship a part that cannot hold its own pipe.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The gusset stays clear of the pipe: check_fit(bracket, pipe, CLEARANCE) passes at the fit table's clearance
- [x] #2 examples/pipe_bracket.py asserts that fit with require(), so it cannot regress
- [x] #3 Still prints without support and runs clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #34. The gusset loft climbed to rise past the ear faces where the bore's relief never reaches; it is now built at min(rise, wall) and rise defaults to 8. require(check_fit(bracket, pipe, CLEARANCE, PLA)) reads clear by 0.322 against 0.300. Found on the way: the app's build hash ignored examples/ and templates/, so e2e and qa served a stale example - fixed in PR #35 with a test tying the hash to what bundle-py.mjs reads.
<!-- SECTION:NOTES:END -->
