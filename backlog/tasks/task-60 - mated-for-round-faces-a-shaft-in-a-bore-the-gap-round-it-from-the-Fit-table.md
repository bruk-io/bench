---
id: task-60
title: >-
  mated() for round faces: a shaft in a bore, the gap round it from the Fit
  table
status: Done
assignee: []
created_date: '2026-09-23 17:20'
updated_date: '2026-09-23 18:41'
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
- [x] #1 A pin mated into a bore sits on the bore's axis with the asked radial gap, measured and reported
- [x] #2 Spin and slide are explicit arguments
- [x] #3 A mismatched pair (pin larger than the bore allows for the Fit) is reported as a finding on both parts
- [x] #4 Tested against the modeller the app ships
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #17 (1a913a2). solids.py: face_of (the lookup plane_of and axis_of share), axis_of(solid, ref) - a round face's axis as a frame: origin on the profile's plane, normal the way the sweep ran, X at the face's zero (what spin is measured from). mate.py: coaxial - the moving axis onto the fixed one, running the same way; mating/mated gain along= (slide up the axis); offset refused on a round pair, along on a flat one; round-vs-flat pair raises naming both faces. Radial gap measured by fit_between, never placed; a too-fat pin is an ERROR on both parts.

'Asked' is the table's figure (0.200 PLA slide); concave=True is the size to DRAW a bore at, because a concave wall's chords bulge into the gap: bore drawn concave measures 0.245 (pass), drawn plain 0.196 (error) - same as task-59's groove. Limits: a pin whose head/shoulder seats on the plate always fails (fit_between measures whole bodies, the head's contact reads 0.000) - filed as a follow-up; the end the pin was swept from goes in first, no flip; a hole() bore's axis starts 0.01 mm proud; press/interference fits refused for round pairs. Gate: pytest 1039+1 skip x2.
<!-- SECTION:NOTES:END -->
