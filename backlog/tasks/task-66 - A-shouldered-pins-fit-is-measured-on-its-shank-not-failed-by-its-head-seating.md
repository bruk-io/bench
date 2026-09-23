---
id: task-66
title: >-
  A shouldered pin's fit is measured on its shank, not failed by its head
  seating
status: Done
assignee: []
created_date: '2026-09-23 18:41'
updated_date: '2026-09-23 19:08'
labels: []
milestone: m-8
dependencies:
  - task-60
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by task-60 (2026-09-23): fit_between measures the whole moving body against the whole fixed body, so a pin or screw whose head or shoulder sits on the plate reads 0.000 mm (the head's contact) and the round fit fails even when the shank's slide gap is right - the common case for screws and shouldered pins, and it undercuts decision-10's 'a second pair is only a check'. tests/unit (test_a_pin_whose_head_sits_on_the_plate_reads_the_heads_zero) records the current behaviour, not the wanted one.

Measure a round pair's radial gap over the length the two faces share: e.g. intersect each body with a slab/cylinder around the fixed face's axis spanning the bore's length (kernel booleans the app already has) before min_gap, or measure face-to-face distances if the kernel can expose them per face. Declare the head's seat as the contact it is (a planar pair on the head's underside), checked separately.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A shouldered pin in a slide-fit bore reports the shank's radial gap and passes
- [x] #2 The head's seat on the plate is reported as a contact, not as the round fit's gap
- [x] #3 A pin too fat for its fit still fails on both parts
- [x] #4 The recorded-limitation test is rewritten against the new behaviour
- [x] #5 Tested against the shipped modeller
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #20. A round mating attaches a RoundPair (bore axis + both round faces named as each body's mesh names them); fit_between(..., pair=) reads each face's extent along the axis off the kernel's mesh (only that face's tagged triangles - the mesh, not the recipe, because hole()'s cutter overshoots 0.01 mm), clips both bodies to a square prism round the axis over the shared length inset _INSET = 0.01 mm at each end, and runs min_gap on the clipped bodies. Inset 0 / 1e-4 / 1e-3 / 0.01 / 0.1 mm all read the same to 12 places. Guards: any shared material between the whole bodies still fails (a head sunk into the plate: 17.000 mm3); faces sharing no length is a warning, never a fall-back to the whole-body gap.

The head's seat is declared by the script (check_fit(fitted.part.shape, plate.shape, CONTACT) -> 'touch, asked contact'), not detected - one pair per mated(), per decision-10. Measured: headed pin, concave-slide bore 0.2445 (was 0.000); plain-slide bore 0.1956; too fat 0.000 with 6.19 mm3 shared; in a hole() bore 0.305. Cost: each round mate meshes both bodies, a clipped min_gap and an intersection volume per run. Reviewed: trial-merged main (task-61) and reran tests/adapter/test_mate_measured.py + tests/unit/test_mate.py (51 passed, real shipped runtime via tools.stack). Gate: pytest 1055+1 skip x2, vitest 355, e2e 120.
<!-- SECTION:NOTES:END -->
