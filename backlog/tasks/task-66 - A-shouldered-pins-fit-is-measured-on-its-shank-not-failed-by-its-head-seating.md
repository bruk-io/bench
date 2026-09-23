---
id: task-66
title: >-
  A shouldered pin's fit is measured on its shank, not failed by its head
  seating
status: In Progress
assignee: []
created_date: '2026-09-23 18:41'
updated_date: '2026-09-23 18:41'
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
- [ ] #1 A shouldered pin in a slide-fit bore reports the shank's radial gap and passes
- [ ] #2 The head's seat on the plate is reported as a contact, not as the round fit's gap
- [ ] #3 A pin too fat for its fit still fails on both parts
- [ ] #4 The recorded-limitation test is rewritten against the new behaviour
- [ ] #5 Tested against the shipped modeller
<!-- AC:END -->
