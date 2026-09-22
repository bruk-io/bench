---
id: task-22
title: 'The report at export scale: fragment lists and a grid that reads oddly'
status: Done
assignee: []
created_date: '2026-09-22 02:47'
updated_date: '2026-09-22 03:43'
labels:
  - feature
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Two wording problems left after reading report() against real exports (task-14.3, PR #24). Both are honest today - nothing is claimed that was not measured - but both read badly on a real part.

**Fragments listed in full.** 147 of the handle's 195 rounds and 99 of the base plate's 199 are sub-5 mm2 fragments of curves that are not cylinders. They are all printed. The agent deliberately did not add a threshold it could not defend, which was right: the same judgement rejected a '1-2 triangles' cutoff for flats after finding the handle's largest two-triangle flats are real 20 mm-wide faces of 658 mm2. So this needs a rule argued from the data, not a number picked to shorten the output - and summing fragments must not hide a small feature that matters, the way the share-based sliver rule hid a 0.500 mm floor.

**A grid along one axis twice.** The base plate's four foot sockets come back as a 2x2 grid whose steps are both along +Y, 60 mm and 121.5 mm. `grid(one, (2, 2), (Y*60, Y*121.5))` does reproduce the four places, so the candidate is correct - it just reads oddly, and a reader may doubt a correct answer. Either the wording explains it or the survey's grid detection should say what it actually found.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A real export's report is shorter without any measured surface going unreported
- [x] #2 Any threshold that sums or hides surfaces is argued from real part data, not chosen to shorten the output
- [x] #3 A small feature that matters is never summed away, as the 0.500 mm socket floor nearly was
- [x] #4 A grid whose steps share an axis reads correctly to someone who did not measure the part
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Branch report-at-export-scale from origin/main (7aaa347). Re-measure the fragment distribution of rounds (and flats) on the three real exports on current main before deciding any rule; argue any cut from that data and check the four socket floors and every small full-turn bore survive it. Decide report-side vs survey-side for the same-axis grid by reading what _lattice actually found. Verify with the full gate after npm ci + generate.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Re-measured on current main (7aaa347) before deciding anything. The task's numbers were stale but the problem was the same size: rounds are 189 on the handle and 191 on the base plate (foot 20), and 142 of the handle's and 99 of the base plate's are partial rounds under 5 mm2. The task-21 merge did not touch them, because it joins pieces on one cylinder and these are pieces of curves that are not cylinders: the handle's 1 mm round-over coming round the end of each web as a piece per step of the bend (r 0.911-1.007, 1.1-1.9 mm long, 6-22 facets, 8-11 degrees of axis turn between neighbours), and on the base plate the same round the corners of its outline at r 0.5 and r 1.0, plus a long tail of 3-5 facet blend pieces at low turn that are not pieces of anything shared. The flats had the same problem in a form the task did not name: the base plate's four 45 degree countersinks are 96 flats of two triangles (2.21 mm2 each, width 1.03-1.08, so the strip rule does not take them), 192 lines of 'a face that leans is a loft()'.

Rule (report-side, src/bench/report.py, docstring section 'One feature, one entry'): a RUN is pieces that are visibly one feature. Partial rounds run together when each touches the next (boxes meet within PLACE), material is on the same side, radii agree within _DRIFT = 0.1 mm, and the axes turn from one to the next by more than FLAT (or the survey would have merged them) and no more than TURN (a facet's step). Flats run on the same terms with normals for axes and alike areas (the survey's own SAME * max(1, sqrt(area)) measure of the same feature) for alike radii. A run of _RUN = 3 or more prints once: count, radius range or lean, total area, box, the LARGEST PIECE IN FULL with its own candidate, and the rest summed with the smallest named. One or two print as the pieces they are (an entry for two saves nothing). A ring of alike facets all leaning the same angle (1-89 degrees) off one axis is offered as a cone about that axis, candidates hole()'s countersink or chamfer and a loft() between two circles. Every piece still counts against the triangles in NOT MEASURED.

Argued from data, not chosen for length. _DRIFT: SAME (0.02) would leave the 57 mm straight stretch of one handle edge (r 0.926-0.945) out of the run its own corner pieces (0.983-0.997) make; the touching-pair radius-difference histogram on the handle has 108 pairs under 0.005 then a continuous tail to 0.045 with the next at 0.052-0.078, and on the base plate a tail to 0.05 then 0.05-0.065 - no clean gap, so the cut is the survey's own coarse-fit slack (twice CHORD = _COARSE, what a round is gathered at before refitting), and every run it makes on the three exports was audited piece by piece and is one rounded edge. What matters and is never summed: a full turn (a bore or cylinder) is excluded from runs whatever it touches; pieces on parallel axes are different features; repeats are untouched; and the hard constraint is met structurally - a run sums pieces of ONE feature, never a feature into noise, and its largest piece is printed in full.

Tried and rejected on the data. (1) Linking on touch + alike radius + axis turn <= TURN WITHOUT the lower bound of FLAT: chained the handle's 18 mm grip (6812 mm2) to the 17.999 mm round beside it (5543 mm2; parallel axes 17 mm apart, radii 0.001 apart, boxes touching) and the base plate's two r 15 corner pieces of 745 and 248 mm2 - two features each time. (2) Length over diameter as a fragment test: bend pieces on the base plate run to 2.2-2.35 (r 0.499, 2.24-2.35 long) while a genuine r 1.0 fillet 3.5 mm long with spread 0.000 is 1.75 - overlap, so no cut works. (3) 'Pieces have exactly two vertex rings' - a straight extruded fillet has too. (4) Calling a flat run 'facets of a curve, not faces': the handle's run of three 619.3 mm2 flats (6, 17, 28 degrees off horizontal, 249 mm long, 2.5 mm wide) is the coarse top of its grip, but three alike faces at shallow angles could as well be meant as facets, so the header says 'one faceted surface, a curve too coarse for the round test or facets meant as they are' and the largest keeps its own loft()/hull() candidate. (5) A unit test caught that three normals all perpendicular to X 'lean 90 degrees off X alike', which is a cylinder's signature not a cone's; the cone reading is bounded to leans of 1-89 degrees.

Grid on one line: report-side. _lattice found two rows of two sharing a step (Y*60) whose origins are a second step apart (Y*121.5): a lattice, and grid(one, (2, 2), (Y*60, Y*121.5)) puts the copies exactly at 0, 60, 121.5 and 181.5 along Y (solids.grid places along*i + over*j, collinear or not). The record already holds the answer; only the word 'grid' implied two directions, so the survey cannot carry the fix without a new record for something it measured correctly. When the two steps lie within a degree of one line the report now says '4 on one line along +Y, in 2 groups of 2: 60.000 mm apart within a group and the groups 121.500 mm apart, at 0.000, 60.000, 121.500 and 181.500 mm from the first one' and keeps the grid() candidate with a note that grid() takes two steps along one line. The handle has two such lattices too (24.958 and 301.100 along (0.707,-0.707,0)).

Before/after: handle 567 -> 315 lines (ROUNDS 381 -> 131 lines, 7 runs covering 139 of 189 rounds; FLATS one run of 3), base plate 976 -> 734 (FLATS 459 -> 287 with the four countersinks as four cone runs; ROUNDS 385 -> 315 with 6 runs covering 47 of 185 partial rounds), foot 128 -> 128 (no runs; two NOT MEASURED lines reworded). The base plate stays long honestly: its remaining sub-5 mm2 rounds are 138 distinct 3-5 facet blend pieces and the 16 pieces of its four socket corners (r 1.875 x2, 1.977, 2.012 per socket, radii more than SAME apart so task-21 leaves them, centres more than PLACE off the lattice so only 4 of the 16 grid), none of which shares a curve with a neighbour. Tests: 14 unit (hand-built records: run formed, pair not, parallel not, right angle not, other radius/side/place out, full bore never in, triangles still counted, cone ring, shallow alike faces, square faces not a run, collinear grid wording, determinism with runs reversed) and 2 functional (a quarter-round swept round a quarter circle -> 'round-over in 8 pieces'; a 24-sided frustum -> '24 flats in a run ... cone about +Z' with its two caps as faces).

Correction to the before/after note above: the base plate's pieces still listed one by one number 138 in all, of which 62 are under 5 mm2 (46 distinct 3-5 facet blend pieces and the 16 socket-corner pieces); and the unit tests added are 12, not 14 (12 unit + 2 functional = 14 new tests). Gate on the final tree in this fresh worktree, npm ci + generate first: 773 Python passed twice (759 on main + 14 new, the 1 skip the pre-existing hello-world one), 169 component, 69 e2e, ALL CHECKS PASSED. Branch report-at-export-scale from 7aaa347, commit 44eaf81, pushed without incident; PR opened against main and not merged. Criteria: #1 handle 567 -> 315 and base plate 976 -> 734 lines with every piece still printed inside its run's count, area and box and counted in NOT MEASURED; #2 _DRIFT argued from the touching-pair radius histogram and the survey's own coarse-fit slack, _RUN = 3 from the fact that an entry for two is as long as two; #3 full turns never in a run, parallel axes kept apart, largest piece of every run printed in full, the socket-floor rule untouched; #4 collinear steps said as places on a line with the grid() candidate kept.

Merged as 8e19db1 (PR #27, squashed). Branched from 7aaa347, pushed without incident, no rebase needed. Gate: 773 Python x2 (759 + 14 new), 169 component, 69 e2e, ALL CHECKS PASSED. main's tree is exactly the gated f1f4132, and survey.py is untouched - verified by diff, not just claimed.

HOW THE HARD CONSTRAINT WAS MET. The criterion said a small feature that matters must never be summed away, as the 0.500 mm socket floor nearly was. The answer is structural rather than a threshold: a run sums pieces of ONE feature and can never collapse a feature into noise. Full turns are never summed (a bore is a bore whatever it touches), pieces on parallel axes are never joined (different features), repeats are never summed, the largest piece of every run still prints in full with its own candidate, and every piece still counts in NOT MEASURED. That is a better answer than picking a safer number, because it cannot be defeated by an unusual part.

Argued from data, as required. The touching-pair radius-difference histogram has no clean gap (handle: 108 pairs under 0.005, tail to 0.045, then 0.052-0.078), so no natural cut exists; the tolerance chosen is the survey's own coarse-fit slack, 2xCHORD. SAME was tested and rejected because it would have left the 57 mm straight stretch of a handle edge out of the run its own corner pieces form. Every run on all three real parts was audited piece by piece.

Five things tried and rejected with numbers, which is the part worth keeping: (1) linking without the FLAT lower bound chained the 18 mm grip to the 17.999 mm round beside it on a parallel axis - two features; (2) length/diameter as a fragment test overlaps between real fillets and bend pieces; (3) 'two vertex rings' also describes a straight extruded fillet; (4) calling a flat run 'facets of a curve' would have mislabelled three alike shallow faces that might be meant as facets, so the header says both; (5) a unit test caught that normals perpendicular to X 'lean 90 degrees off X alike' is a cylinder's signature, not a cone's, so cone reading is bounded to 1-89 degrees.

The brief was stale as warned (189/191 rounds, not 195/199) but the problem was the same size - task-21's merge joins pieces on one cylinder, and these are pieces of curves that are not cylinders. The brief also missed the bigger problem entirely: on the base plate the FLATS block (459 lines) was longer than ROUNDS, because four 45-degree countersinks are 96 two-triangle flats each drawing 'a face that leans is a loft()'.

Grid wording: decided report-side, correctly. `_lattice` had found two rows of two sharing Y*60 with origins Y*121.5 apart, and `solids.grid` places along*i + over*j, so the candidate was exact - only the word 'grid' implied two directions. The survey had nothing to carry, so it carries nothing.

Line counts: foot 128 -> 128 (no runs, two NOT MEASURED lines reworded), handle 567 -> 315, base plate 976 -> 734. The base plate stays long honestly: its remaining sub-5 mm2 rounds are distinct blend pieces and socket-corner pieces whose radii sit more than SAME apart, which is task-21's declined widening rather than something to hide here.

Limits: a run's pieces lose their individual places (the run gives box, count, area and the largest), so the handle's second 74 mm straight stretch of an edge sits inside 'and 41 more pieces'. And pieces of one surface on parallel axes with radii more than SAME apart stay separate lines.

Raised separately as task-23: the handle's two 345-degree CONCAVE r 2 rounds are offered as 'a rod or a bar ... a fillet', which a concave surface nearly a full turn around is not.
<!-- SECTION:NOTES:END -->
