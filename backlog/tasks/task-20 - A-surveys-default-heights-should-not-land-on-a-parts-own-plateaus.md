---
id: task-20
title: A survey's default heights should not land on a part's own plateaus
status: Done
assignee: []
created_date: '2026-09-22 02:46'
updated_date: '2026-09-22 03:15'
labels:
  - feature
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by reading report() against real exports (task-14.3, PR #24).

The survey's default section heights are multiples of h/6. Real parts are modelled at round numbers, so those heights land exactly on the part's own flats: the systainer foot has a plateau at z = 3.400 and the handle a 949.9 mm2 flat at exactly z = 15.000. A plane that runs along a face instead of cutting through it leaves zero-area runs - 36 of them on the foot, 30 and 11 on the handle.

The report now explains these rather than claiming a gap in the mesh, which was the misleading behaviour #24 fixed. But it is a description of a problem the survey creates, and the cleaner fix is at source: nudge each default height off any z where a flat lies, so a plane cuts through rather than along. Then the runs never appear and the report has nothing to explain.

The report's handling should stay regardless - a caller passing `at=` explicitly can still land on a plateau, and the mesh can still genuinely have a gap.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A part whose flats sit at round numbers surveys without producing zero-area runs at its default heights
- [x] #2 A height passed explicitly by the caller is still honoured, whatever it lands on
- [x] #3 The nudge is deterministic: the same mesh always surveys at the same heights
- [x] #4 A mesh with a genuine gap still reports one
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Branch survey-heights-and-rounds from 729b9ae, shared with task-21 (one file, one gate). Diagnose on the real exports which default heights coincide with the mesh's own z values, then move each such height off in survey() only when at= is empty, by a rule that reads the vertices alone. Verify on the foot (obj_2), handle (obj_6) and base plate (obj_11) by diffing report(survey(mesh)) before and after.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Diagnosis on the real parts contradicts one word of the brief: the nudge has to key on vertex layers, not on flats. The handle's z = 9.0 is the widest ring of the 18 mm grip - a round's vertices, no flat there - and it produced 7 OPEN outlines and 30 no-area runs exactly as the plateau at 15.0 did. The foot's case is different again: h/2 computed from float32-derived doubles is 2e-9 mm off the plateau at 3.4000000953674316, so the plane cuts slivers shorter than TOL that _meets chains into two-point closed runs - the 36. A plane exactly on a layer touches every wall triangle and crosses none, so it cuts nothing at all (a stacked-box fixture shows this: the middle section was empty).

Rule (survey._clear / _off_layers, documented under "A section's height" in the module docstring): a default height within ROUND (0.01) of any vertex z is moved past the nearer edge of that layer by 2*ROUND, or to the middle of the gap to the next layer when that is nearer; layers closer than 2*ROUND count as one band. Pure function of the sorted distinct vertex z's, so the same mesh always surveys at the same heights (a test surveys the same boxes joined in either order). Heights are sorted and deduplicated after moving. at= given is used as given (test). A band with no gap either side (a body whose vertex layers are all within 0.02 of the next) leaves the height where it is - the one case not solved, and it cannot arise on any part drawn at round numbers.

Before/after on real parts: foot z 3.400 -> 3.420, the 36 no-area runs gone, three closed outlines (1338.4 mm2 and two 12.4 mm2 bores). Handle z 9.000 -> 9.020: was 8 outlines of which 7 OPEN plus 30 no-area runs, now 6 closed outlines; z 15.000 -> 14.980: was 10 outlines of which 8 OPEN plus 11 no-area runs, now 4 closed outlines. Base plate: no default height was on a layer, unchanged. report()'s handling of no-area and OPEN runs is untouched, and its test for a plateau at an explicit height still holds; a box with a missing side still sections open at every moved height (criterion #4 test).

Tests added in tests/unit/test_survey.py (stepped box; the foot's own float32 numbers as a fixture; explicit at= on a layer; determinism; a torn box) and tests/functional/test_survey_report.py (a stepped body reports no runs of no area). No report test needed changing.

Rebased onto 41b6ced (after task-19's #25). Gate on the rebased tree, npm ci + generate first: 759 Python passed twice (+1 pre-existing skip), 169 component, 69 e2e, ALL CHECKS PASSED. Push of the rebased branch was refused by permissions and not worked around; local HEAD c29f85e, tree f6943340ce0cfba4ef34765fd23f0f7a16da7f0d. PR #26 body updated; not merged.

Merged as 6196778 (PR #26, squashed, shared with task-21), with 87e0299 restoring a docstring commit that could not be pushed.

Verification: the branch was based on 729b9ae and first gated at 66 e2e, predating task-19's UI work. After rebasing onto 41b6ced the gate was green at 759 Python x2 (747 + 12 new), 169 component, 69 e2e - all three counts as predicted, nothing lost. The rebased push was refused by permissions and was not worked around; because the rebase added a second commit that never reached origin, a squash of the stale branch would have dropped it - confirmed by tree comparison (squash-of-origin b628244 against the gated f694334, differing by five lines of survey.py). So the PR was merged and the missing commit cherry-picked, leaving main's tree exactly f694334.

What changed: `_clear` / `_off_layers`. A default height within ROUND (0.01) of any vertex z moves 2*ROUND past that layer's nearer edge, or to the middle of the gap to the next layer when that is nearer; layers closer than 2*ROUND count as one band. A pure function of the sorted distinct vertex z values, so it is deterministic - tested by joining the same boxes in either order. An explicit at= is untouched, as criterion #2 requires.

On the real parts: the foot's z = 3.400 section (3 outlines plus 36 runs enclosing no area) becomes z = 3.420 with 3 outlines and no no-area line. The handle's z = 9.000 (8 outlines, 7 OPEN, 30 no-area runs) becomes z = 9.020 with 6 closed outlines, and z = 15.000 (10 outlines, 8 OPEN, 11 no-area runs) becomes z = 14.980 with 4. The base plate is unchanged, no default height having landed on a layer.

Where the brief was wrong: it said to nudge off any z where a FLAT lies. That is not sufficient - the handle's z = 9.0 is the grip's widest vertex ring with no flat there at all, and it produced 7 OPEN outlines and 30 no-area runs. The nudge has to key on vertex layers. The agent also distinguished two failure modes the brief conflated: landing exactly on a layer cuts nothing, while landing a hair off (h/2 derived from float32 vertices sits about 2e-9 from the plateau) leaves sub-tolerance slivers that chain into two-point runs. Both now have fixtures.

Limit not solved: a body whose vertex layers all sit within 0.02 of the next has no band with a gap either side, so the height stays put. Cannot arise on a part drawn at round numbers.
<!-- SECTION:NOTES:END -->
