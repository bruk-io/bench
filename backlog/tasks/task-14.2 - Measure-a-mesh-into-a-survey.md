---
id: task-14.2
title: Measure a mesh into a survey
status: Done
assignee:
  - claude
created_date: '2026-09-22 13:55'
updated_date: '2026-09-22 02:11'
labels:
  - feature
dependencies: []
parent_task_id: task-14
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The measurements someone needs before they can write a script for a thing that already exists: how big it is, what section it has at a given height, how thick its walls run, which of its faces are flat and which are round, and what repeats.

These are the questions that got asked by hand, one throwaway script at a time, while reading a downloaded model this week - and the answers were what made the difference between guessing a dimension and knowing it. They are worth having once, measured the same way every time.

A mesh is already triangles, so none of this needs a solid modeller, and the answer is data: a record, not a rendering and not a report.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The survey reports the object's extent, its section at a given height, and how its wall thickness is distributed
- [x] #2 Flat faces and round features are reported with the numbers that place and size them
- [x] #3 Repetition is reported as repetition: identical features on a regular spacing read as one finding, not as several
- [x] #4 The wall thickness the survey reports agrees with what the existing wall check measures on the same object
- [x] #5 A survey is produced with no solid modeller present
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Extract the mesh-reading helpers out of checks.py into a new module `facets.py` (layer: geometry, kernel): triangles, normals, centres, a uniform-grid ray cast, per-triangle thickness and `thinnest(mesh) -> (distance, triangle index)`. checks.wall keeps a thin wrapper mapping the index through mesh.refs; overhangs keeps `_lean_of`. Survey and checks share one implementation, so criterion #4 holds by construction and the adapter tests that police wall() police the survey transitively.
2. The grid replaces the quadratic all-pairs scan: the real STLs run to 17k triangles, which the quadratic form cannot survey in pure Python in any useful time. Same answers, same SKIN rule, same facing-back rule.
3. survey.py gains: Walls (thinnest, where, and thickness bands by area), Flat (planar regions grown over shared edges with a fixed normal), Round (cylindrical regions grown with a fixed axis; centre from facet normals, radius from the vertices - which sit on the arc - so CHORD does not under-read it; concave/convex, length, turn, residual), Repeat (identical Flat/Round on a regular spacing: rows of >= 3 or grids of >= 2 x 2, members removed from the singles). Decisions written into the module docstring.
4. Tests: unit tests for facets and survey on hand-built meshes (box, tube, drilled plate, boss grid); the adapter layer's wall cases already assert millimetre answers. Check detection against the systainer STLs in the scratchpad by hand and record what it finds.
5. Declare facets in [tool.pypeeker.import-boundaries]; export the new records from bench/__init__; README layer entry; run `uv run tools/check.py` in full; PR against main, no merge.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Design: the ray cast and the per-triangle thickness moved out of checks.py into a new module facets.py (layer geometry, kernel). checks.wall and survey both call facets.thinnest, so criterion #4 holds because there is one implementation, not two that agree. checks.overhangs keeps _lean_of and reads facets.triangles/normal.

The quadratic all-pairs ray cast was replaced by a uniform grid (48 cells along the longest side, 3D DDA walk, early exit once the best hit is nearer than the next cell). Verified triangle-for-triangle equal to the old scan on two real STLs (1480 and 2988 triangles: zero differing answers); ~100x faster, and the 17k-triangle base plate surveys in about 2.4 s where the old form would have taken the better part of an hour.

Segmentation decisions (all written into the survey module docstring): FLAT = 0.1 deg normal tolerance to the seed; LEAST = 1 mm^2 minimum surface, flat or round; rounds are seed-and-verify - two adjacent facets fix a circle, the region grows only over triangles whose corners lie on it (coarsely at 0.1 mm, then, with the axis refitted by a 3x3 Jacobi eigen solve and the centre by least-squares crossing of facet normals, tightly at ROUND = 0.01 mm), then settles by fit-prune-refit; radius is read off the vertices so CHORD does not under-read it; TURN = 40 deg max facet step (nonagons and finer read as round, hexagons/octagons as flats); LEAST_TURN = 10 deg and radius <= body diagonal so blends of a degree or two on metre radii are not features. Repeats: same kind and size within SAME = 0.02 mm, centres on a lattice within PLACE = 0.05 mm; rows need 3, grids 2x2; a pair is two features. Coincident centres (mirrored fillets) are not a step.

Real STLs (systainer clone, 13 parts): front foot 45.00 x 38.00 x 6.80 confirmed; two 4.000 mm bores 6.00 deep found exactly (spread 0.0000); the sides are NOT 30.5 deg each - two are 8.4/10.4 deg off vertical, two are 45.8/52.1 deg, and the hand figure was the average taper (45 -> 36.37 over 6.8). Base plate 204.38 x 296.00 x 150.00 confirmed; 4.0 mm dominant wall band (88k mm^2) then 6.5 mm; the four foot sockets come back as 2x2 repeats at 60.0 x 121.5 mm. Main handle: 18 mm round grip (r=9.000, spread 0.0000) and 4 mm pin bores at both ends. Panels are placed at 45 deg in their files, and the survey reports them so. Not found: cones/chamfers (each facet is a small flat, filtered by LEAST), spline/elliptical surfaces (fragment into several partial rounds of varying radius - honest but noisy), and the thinnest wall on real exports is often a sliver artefact (0.001-0.05 mm) rather than the wall a maker means; the bands carry the real answer.

Repeats on real parts are correct but fragmentary: a feature made of several surfaces (a socket with a chamfer) repeats as several Repeat records, one per surface, because the survey does not know what a socket is. Pairs (2 bores on the foot) are deliberately not repeats.

Gate: `uv run tools/check.py` ALL CHECKS PASSED on branch survey-measures (716 Python tests twice incl. pyodide + shipped-kernel adapter layers, 148 web component tests, 59 e2e). Needed `npm ci` and `npm run generate` in web/ for the worktree first - without them the gate skips the modeller layers and fails e2e on 'no tests ran'. PR opened against main; not merged, awaiting review.

Merged as f97d6b1 (PR #22, squashed), with 3df4602 restoring the README commit that could not be pushed.

How it was verified: the branch was based on f58285a and first gated at 59 e2e, predating both #20 and #21. After rebasing onto ddff5ef the full gate was green at 66 e2e, 169 component, 720 pytest x2 (the Python count rose from 716 because #20 brought four non-e2e tests). The rebased push was refused by permissions and was not worked around. Because the rebase added a second commit that never reached origin, GitHub's squash of the stale branch would have dropped it - confirmed by comparing trees: squash-of-origin gave a875c41 against the gated 0c52d27, differing only by the six README lines. So the PR was merged and the missing commit cherry-picked, after which main's tree is exactly 0c52d27, the gated tree.

Two things worth carrying forward. The ray cast was rewritten from all-pairs to a uniform grid with 3D DDA - unavoidable, since the base plate's 17,480 triangles would have taken most of an hour in pure Python against 2.4 s now - and it is a rewrite of a measurement, verified triangle-for-triangle identical on two real STLs and by the adapter wall cases. And a fresh worktree has no web/node_modules and no generated pysources.ts, both gitignored, so the gate silently skips the modeller layers and the adapter tests policing wall(), then fails e2e on 'no tests ran'; the agent's own first run was a false green this way, which is what the README commit documents.

On the real STLs the survey contradicted the brief: the foot's '30.5 degrees a side' is the average taper, not the draft - the sides are 8.4/10.4 degrees off vertical on two sides and 45.8/52.1 on the others, and the foot is skewed, its top face offset (2.9, 3.7) mm from the bottom's centre. Honest limits recorded by the agent: cones and chamfers are missed as sub-mm2 flats, spline surfaces fragment into several partial rounds, and walls.thinnest on real exports usually lands on a sliver artefact of 0.001-0.05 mm, with the bands carrying the useful answer.
<!-- SECTION:NOTES:END -->
