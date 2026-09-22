---
id: task-14.3
title: Render a survey as a report a reader can act on
status: Done
assignee: []
created_date: '2026-09-22 13:55'
updated_date: '2026-09-22 02:43'
labels:
  - feature
dependencies:
  - task-14.2
parent_task_id: task-14
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A survey is a record, and a record is not what a person reads or what a model is handed. This turns one into text.

The wording is the whole job. A measurement phrased in bench's own words - an outline of this shape and size, raised this far, a bore of this diameter on this spacing - reads to a person, and to a model drafting a first attempt, as a script waiting to be typed. The same measurement phrased as generic geometry reads as a point cloud and helps nobody.

It offers vocabulary, never conclusions, and it says nothing the survey did not measure.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The report is built from a survey alone, without going back to the mesh
- [x] #2 Measurements are phrased in bench's own vocabulary, offered as candidates rather than as conclusions
- [x] #3 Nothing appears in the report that was not measured
- [x] #4 The same survey always renders the same report
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. New module `src/bench/report.py` with one public function `report(survey: Survey) -> str`; declared in `[tool.pypeeker.import-boundaries]` as `report = ["geometry", "survey"]` - no kernel, no mesh.
2. One block per part of the survey (extent, sections, walls, flats, rounds, repeats) plus a closing NOT MEASURED block. Each measured line is followed by a line marked `candidate:` naming the bench verb that fits the numbers (`cuboid`, `extrude`, `raised(XY, z)`, `plane_of(body, "side-...")`, `hole(diameter=, depth=)`, `cylinder`/`boss`, `rounded_rect` corner, `loft`/`hull`, `pattern`, `grid`).
3. Determinism: every list is sorted inside the report on its numbers; every figure printed to fixed places (`.3f` mm, `.1f` mm2 and %, `.0f` degrees) with negative zero folded.
4. Honesty: the thinnest reading is printed beside the band area that read within 0.05 mm of it and called "one place, not a wall" when that area is under 1% of the surface; outlines give their share of their box with a one-line legend rather than being called a rect or a circle; the wall-band tail under 1% each is summed into one line; the closing block states what was not measured (intent, names, cones/chamfers, spline fragments, one Repeat per surface).
5. Tests: `tests/unit/test_report.py` builds Survey records by hand (no mesh), `tests/functional/test_survey_report.py` runs mesh -> survey -> report on hand-built boxes, tubes and bossed plates.
6. Export `report` from `bench/__init__.py`, README layer entry.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Branch `survey-report`, PR against main. Gate on the final tree (fresh worktree, `npm ci` + `generate` run first): 66 e2e, 169 component, 743 Python passed twice (720 on main + 19 unit + 4 functional; the 1 skip is the pre-existing intentional hello-world skip in test_examples.py).

Design: `src/bench/report.py`, one public `report(survey) -> str`, layer row `report = ["geometry", "survey"]` (no kernel, no mesh - criterion #1 by the layer graph). Blocks: SURVEY (extent + cuboid candidate + a one-line legend of what rect/circle/rounded_rect fill of their boxes), SECTIONS (each outline's box, area, share of box, OPEN flag; then whether every measured height is the same section to 0.05 mm -> "candidate: one straight extrude()" or "not one straight extrude(); a loft, a hull or several bodies"), WALLS (bands >= 1% listed, the tail summed into one line; "candidate: a wall of T mm"; the thinnest reading beside the band area that read within 0.05 mm of it, called "one place - not a wall" when that area is under 1%), FLATS / ROUNDS standing alone, REPEATS (pattern / grid candidates, "one as above"), NOT MEASURED (triangle coverage, intent, names, non-cylindrical curves, cones).

Criteria: #1 layer-enforced and unit tests build Survey records by hand with no mesh. #2 every verb is on a line marked `candidate:`. #3 tests assert M4/clearance/fit/nominal/screw absent from the measured body, sliver flagged, open outline flagged, no verbs offered when nothing measured, "as a rect does" never said. #4 render-twice and every-list-reversed tests, fixed-place regex, negative-zero test.

Known limits, unsolved: (1) the report cannot tell a rect from a rounded_rect with small corners, so it never names either - it gives the share and the legend; (2) a hole candidate says `hole(body, ..., diameter=, depth=)` on its axis and cannot say which face it is drilled from; (3) repeats are one per surface as the survey gives them - the report says so but does not group a boss with its crown; (4) a partial round is offered as a rounded_rect corner (axis Z) or a fillet (other axes) with no way to tell a corner from a fillet; (5) not exercised on a real CAD export - only on hand-built boxes, tubes and bossed plates; (6) the sliver rule is by band area share (1%), not by absolute thickness.

Merged as 37f0966 (PR #23, squashed). Branched from current origin/main c1b7632 and pushed without incident, so no rebase and no tree-hash fallback were needed - the brief's 3df4602 was one backlog commit stale and the agent corrected it.

Gate: 743 Python passed twice (+1 skipped), 169 component, 66 e2e, ALL CHECKS PASSED. 743 = 720 on main + 23 new, exactly; the single skip was checked by name (tests/functional/test_examples.py:96, the README hello-world printing nothing) rather than assumed, which matters because a skipped layer is how this task family produced a false green before.

Shape: one public `report(survey) -> str` in src/bench/report.py, layer row `report = ["geometry", "survey"]`, so criterion #1 (built from the survey alone, never back to the mesh) is enforced by test_layer_graph rather than asserted. Every verb it names sits on a line marked `candidate:`, which is how criterion #2 keeps vocabulary from reading as conclusion. Determinism is done inside the report - lists sorted on their numbers, fixed-place figures, negative zero folded - so it does not depend on the survey's ordering.

Worth recording: the agent walked back four phrasings that would have overstated what was measured. 'Filling its box as a rect does' would have called a 60x40 rounded_rect with r=3 a rect (99.7% share), so the report now gives the share and names no shape; the NOT MEASURED block stopped asserting what unlisted triangles were; an off-axis bore stopped claiming the face it is drilled from leans; and 'check_wall() would fail on it' became the narrower true statement. Criterion #3 was the one at risk and it was the one defended.

Known limits, disclosed rather than hidden: cannot tell a rect from a rounded_rect with small corners, or a corner from a fillet; cannot say which face a hole is drilled from (not in the survey); repeats stay one per surface because grouping would be an inference; the sliver rule keys on band area share (<1% of surface) rather than absolute thickness, so a genuine tiny thin wall would also read as 'one place' - the reading and area are always printed so a reader can judge.

Read against real exports (systainer front foot 2988 tris, main handle 7750, base plate 17272), branch `survey-report-real` from 37f0966. Findings: (1) band tail behaves - foot lists 11 bands and sums 221, base lists 9 and sums 852, handle 23 and 417; (2) sliver rule fired correctly on the foot (0.020 mm, 0.2 mm2) and handle (1.194 mm, 0.07 mm2) but WRONGLY on the base plate: 0.500 mm under 44.8 mm2 is the four 3.8 x 3.8 mm socket floors, a real thin floor, and the report called it 'one place, not a wall' - fixed by making the rule absolute (under 1 mm2 = sliver; under 1% share = 'a thin place of that area, not one of the walls above'); (3) NOT MEASURED coverage: foot 78.1%, handle 75.7%, base plate as listed; (4) misleading at export scale: OPEN runs claimed 'the mesh has a gap here' 36 times on the foot at z = 3.400 where the plane runs along a plateau - fixed (no-area runs summed to one line, open runs with area say plane-along-face OR gap); every one-triangle flat (507 of the handle's 592) was offered as a face with a loft() candidate - fixed (one-triangle flats and strips under 0.5 mm summed to one line, no candidate; '1-2 triangles' rejected because the handle's largest two-triangle flats are real 658 mm2 rectangles); the handle's 18 mm grip was offered as 'a fillet' - fixed (rod-or-fillet wording, no-fillet-verb note once per block). Handle report 1716 -> 589 lines, base 1292 -> 992, foot 188 -> 129. Gate on final text: 747 Python x2 (+4 tests), 169 component, 66 e2e, ALL CHECKS PASSED.

Limits worth tracking rather than fixing here: (a) the survey's default section heights (h/6 multiples) land on round-number plateaus of round-number parts and produce no-area runs - a survey-side fix would nudge heights off any z where a flat lies; (b) the handle's 18 mm grip comes back as four partial rounds on one axis and radius (124/83/63/39 degrees) - the survey could merge partial rounds sharing axis and radius within SAME; (c) 147 of the handle's 195 rounds and 99 of the base's 199 are under 5 mm2 fragments of non-cylindrical curves, listed in full - honest but long; (d) the base plate's 2 x 2 'grid' has both steps along +Y (60 and 121.5) - grid(one, (2,2), (Y*60, Y*121.5)) does reproduce the four places, but the wording 'along +Y and along +Y' reads oddly.
<!-- SECTION:NOTES:END -->
