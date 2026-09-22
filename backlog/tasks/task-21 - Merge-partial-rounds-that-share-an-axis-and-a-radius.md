---
id: task-21
title: Merge partial rounds that share an axis and a radius
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

The systainer handle's grip is one 18 mm cylinder. The survey returns it as four partial rounds on the same axis at the same radius - 124, 83, 63 and 39 degrees - because the growth stops where the tessellation breaks the surface up. The report prints four candidates where a maker would write one `cylinder()`.

Merging partial rounds that share an axis and a radius within the existing SAME tolerance would give the one round that is actually there. The pieces are already measured; this is about recognising that they are one surface.

This is survey-side, not report-side: the report should keep printing what the survey found, and what it finds should be the grip.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A cylinder broken into several partial rounds by tessellation comes back as one round
- [x] #2 Two genuinely separate rounds that happen to share an axis and radius are not merged into one
- [x] #3 The merged round's turn, length and residual describe the whole surface, not one piece of it
- [x] #4 The existing SAME tolerance is used rather than a new one invented for this
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Same branch as task-20 (survey-heights-and-rounds). Probe the handle's rounds near r = 9 for what actually shares a cylinder pairwise, then merge at region level inside _rounds so turn, length and spread are re-measured over the union, with a rule that keeps two coaxial bores in two walls apart. Verify against all three real parts and audit every merged spread.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The brief's picture of the grip is wrong, and the record shows it: the grip is already ONE partial round (124 degrees, r 9.000, 351 mm, spread 0.0000) with nothing else on its line. The 83, 63 and 39 degree pieces lie on a second parallel line 17.00 mm from the grip's axis (centre (570.97, -209.72, 9.00)), at r 8.998, 8.996 and 8.922. The first two are coaxial to 0.004 mm with radii 0.0015 apart and merge; the 39 degree piece is 0.075 mm off in radius and 0.03-0.07 off axis, outside SAME, and stays separate - honestly, because its vertices are not on that cylinder to the survey's own standard. The handle's two 180 degree ends share one line 74 mm from the grip with a 283 mm gap between them and do not merge: a real-part instance of criterion #2.

Rule (survey._merged / _one_cylinder / _whole, docstring section "One round, in pieces"): pieces are one round when their axes are within FLAT as lines (either way along - see below), they face the same side, radii within SAME, each centre within SAME of the other's axis line, and their reaches along the axis (centre +/- length/2) overlap or meet within SAME. The reach clause is what separates one interrupted surface from two bores of one diameter through two walls: nothing was measured between the bores, so the survey does not join them (test: a 20 mm block with a 3 mm bore 5 deep in the floor and another in the lid stays two rounds). Grouping is transitive through a shared member. The union is re-fitted: axis by _least_turned over every normal, circle by _circle over every triangle; turn = the union of the pieces' arcs (_arc, refactored out of _turn_of, and _covered), so two 60 degree arcs on opposite sides of a rod give 120 degrees, not the 300 that one piece's widest gap would; length end to end; spread = every vertex against the one refit circle; area and facets summed. A union that cannot be refitted is left as its pieces rather than claimed. SAME is the only size tolerance used (criterion #4).

Real-part results: handle rounds 195 -> 189; the 83 + 63 pieces became one 135 degree round at r 8.999, 282.5 mm long, spread 0.003, 5543 mm2, 182 facets (135 not 146 because the pieces' arcs overlap by about 11 degrees; the union is what is covered). Base plate 199 -> 191: four 62 degree arcs at r 16.500 about one centre became one 248 degree round (605.9 mm2, 56 facets, spread 0.000) - a 33 mm boss with four ribs meeting it; three chains of edge-fillet pieces along +Y merged at spreads 0.009, 0.003 and 0.002; two 53 degree concave pieces along +X became one 91 degree round at spread 0.002. Foot unchanged (20 rounds). Audit: no merged round anywhere has a spread above 0.010, so every merge fits to ROUND, the survey's own standard for a single round.

Side finding fixed in the same function: _signed broke an |x| == |y| tie on float noise, which is why the handle's two ends already printed with opposite axes and why the merged piece's axis flipped sign against its pieces; it now takes the first of components tied within TOL. Test fixtures: _arc_wall builds one stretch of a prism wall with its own vertices, so joined pieces share no edge - the seam a tessellation leaves. Tests: four unwelded quarter walls are one full cylinder equal in area to the welded prism's; two coaxial bores with material between stay two; two arcs on parallel axes 17 mm apart stay two; opposite arcs cover 120 not 300 degrees; pieces meeting end to end are one round the whole length; and functionally a grip in four pieces reports "cylinder: diameter 18.000 mm ... 120.000 mm long" with no partial round in the ROUNDS block. No report test needed changing.

Limit not solved: a piece whose radius sits more than SAME from its neighbours' (the handle's 39 degree piece at 8.922) is left out even when it is visibly part of the same modelled surface; joining it would need a wider tolerance than the survey holds any round to, and would overstate the fit.

Rebased onto 41b6ced. Gate on the rebased tree: 759 Python passed twice (+1 skip), 169 component, 69 e2e, ALL CHECKS PASSED. Added a docstring sentence (commit c29f85e) that a turn is the arc reached anywhere along the length, not a cross-section at one station. Push refused by permissions; local HEAD c29f85e, tree f6943340ce0cfba4ef34765fd23f0f7a16da7f0d. PR #26 body now states plainly that the brief's four-piece grip was wrong and names the base plate's 33 mm boss and the fillet chains as what the merge buys, and describes the _signed behaviour change.

Merged as 6196778 (PR #26, squashed, shared with task-20), plus 87e0299. Gate after rebasing onto 41b6ced: 759 Python x2, 169 component, 69 e2e, ALL CHECKS PASSED. See task-20's notes for how the blocked push was handled - the tree was compared rather than forced, and main's tree is exactly the gated f694334.

THIS TASK'S DESCRIPTION WAS WRONG, and the agent caught it by reading the record instead of trusting the brief. I wrote that the handle's grip comes back as four partial rounds at 124/83/63/39 degrees on one axis; I took that from the task-14.3 agent's reading and passed it on without verifying. The grip was ALREADY one 124-degree round with nothing else on its line. The 83/63/39 pieces are a different rounded feature on a parallel line 17.00 mm away. So 'the grip comes back as one round' was true before this change.

What the merge actually buys, which is real but not what the brief claimed: the base plate's 33 mm boss comes back as one 248-degree round instead of four 62-degree arcs (spread 0.000); three edge-fillet chains merge at spreads 0.009/0.003/0.002; two 53-degree concave pieces become one 91-degree at 0.002. On the handle the 83 and 63 pieces merge into one 135-degree round at spread 0.003. Rounds drop 195 -> 189 on the handle and 199 -> 191 on the base plate. No merged round anywhere has a spread above 0.010.

How it decides: pieces lie on one cylinder when their axes agree within FLAT as lines, radii within SAME, each centre within SAME of the other's axis line, and the same side; they merge when their axial reaches overlap or meet within SAME, transitively. That reach clause is what keeps two coaxial bores in two walls apart, which is criterion #2 and is tested - and the handle's two 180-degree ends, sharing one line with a 283 mm gap, are a real-part instance of it. SAME is the only size tolerance used, as criterion #4 required.

Declined deliberately: the 39-degree piece sits at r 8.922, about 0.075 off the others - outside SAME - and stays separate. Widening the tolerance to absorb it would hold a merged round to a looser fit than any single round is held to, which would overstate the measurement. Same judgement that rejected a '1-2 triangles' cutoff in task-14.3.

Unasked-for behaviour change, recorded because someone would otherwise debug it from scratch: `_signed` broke an |x| == |y| tie on float noise, so diagonal axes flipped sign between records (the handle's two ends already printed opposite axes on main). The first of the components tied within TOL now wins. It is in the PR body under its own heading.

Limits: pieces of one modelled surface whose radii differ by more than SAME stay separate (above). And a merged turn is the angular extent of the union of the pieces' arcs - what is covered anywhere along the length, not a cross-section at one station - so a narrowing piece reports its widest reach. That sentence is now in the survey module docstring, which is what commit 87e0299 carried.
<!-- SECTION:NOTES:END -->
