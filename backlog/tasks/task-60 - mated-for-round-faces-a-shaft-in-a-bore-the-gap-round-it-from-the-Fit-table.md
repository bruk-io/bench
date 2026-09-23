---
id: task-60
title: >-
  mated() for round faces: a shaft in a bore, the gap round it from the Fit
  table
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
decision-10 step 3. A round pair (a cylindrical face on each part - a bore and a shaft/pin) aligns the two axes; the radial gap is what the Fit asks (clearance(fit, material), concave=True where the table says so) and is measured and reported, not assumed. A round pair leaves spin about the axis and slide along it free: they are explicit arguments (spin=, along=), never guessed. One pair per mated(); a second pair (a shoulder on a face) is only a check of where the first put it - bench is not a constraint solver.

Needs the axis of a round face: find what SolidFace/plane_of(around=) already know (the radius is 'read off the body'), and expose an axis the same way, deterministic like plane_of.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A pin mated into a bore sits on the bore's axis with the asked radial gap, measured and reported
- [ ] #2 Spin and slide are explicit arguments
- [ ] #3 A mismatched pair (pin larger than the bore allows for the Fit) is reported as a finding on both parts
- [ ] #4 Tested against the modeller the app ships
<!-- AC:END -->
