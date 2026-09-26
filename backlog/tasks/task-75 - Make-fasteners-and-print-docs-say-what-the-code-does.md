---
id: task-75
title: Make fasteners and print docs say what the code does
status: Done
assignee: []
created_date: '2026-09-24 19:47'
updated_date: '2026-09-26 14:59'
labels: []
milestone: m-10
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found writing docs/printing.md (2026-09-24), each a place the code and its own docs disagree - decide per item whether the code or the docstring is right, then make them agree:
- LEAD_IN (fasteners.py) is documented as applying to insert bores, but hole() never reads it; only NutTrap uses it.
- Orient.bed_face's docstring says the foot chamfer reads it; foot_chamfer(solid, d) does not - only views.py and export.py do.
- Material.foot is described as what the bottom chamfer takes off, but the one example calling foot_chamfer uses foot * 3.
- check_overhangs reports warnings and require() stops the run on warnings too, so require(check_overhangs(...)) fails designs the check means only to flag; either require() should stop on errors only, or the docs should say not to wrap it.
- The review's 'bench already agrees' on nut traps and crush ribs is only true of data: no public function cuts a nut trap pocket or crush ribs (ribs are private to gridfinity3d._ribs). Decide whether they become public operations (flexures/enclosures will want them).
Update docs/printing.md where it describes any of these.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each of the five items resolved: code or docstring changed so they agree, with the reason in the task notes
- [x] #2 docs/printing.md updated where it described the old behaviour
- [x] #3 Tests pin any behaviour that changed
<!-- AC:END -->
