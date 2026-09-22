---
id: task-26
title: >-
  Place a reference mesh against the script's origin, and write the placement
  down
status: Done
assignee: []
created_date: '2026-09-22 19:59'
updated_date: '2026-09-22 16:09'
labels:
  - feature
  - project
milestone: Mesh Placement
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A dropped mesh arrives in whatever space its exporter used. The systainer foot's box starts at (606.795, -116.868, 0.000). Every number the survey reports about it is true and none of it is typeable: a maker writing the script wants "the bore is 12 mm in from that corner", not "the bore is at x = 642.137".

What is missing is a way to say where the mesh's datum is - this face is my XY, this corner is my origin, this edge runs along X - and to have the survey and the report speak in those terms afterwards.

**Where the placement lives.** In the project's TOML beside the script, not in the script. decision-3 established that file as the home for what is measured and annotated rather than computed, and deferred `[[measured]]` until the survey produced measurements worth writing down. It now does (task-14). A placement is the same kind of thing: data a maker settled on, versioned, diffable, and no business of a script that must also run in a browser with no filesystem. The host reads it and hands the script a mesh already placed, exactly as it already hands over values.

**Why it must be written down rather than inferred.** An auto-centre - drop the mesh and quietly move it to the origin - is a transform nobody recorded, and it would put the viewer and the report in disagreement: the report says 606.795 and the screen says 0. The survey spent four PRs refusing to claim more than it measured; a silent transform would undo that. A placement that is written in the file is a fact a reader can check, change, and diff.

**The obvious first shape**, to be argued rather than assumed: derive a placement from what the survey already found - put a named flat on XY, put the box's corner or centre at the origin - so the common case is one line in the TOML rather than a hand-typed matrix. A matrix should remain sayable for the case nothing named fits.

This is the third of the three things that came out of "the dropped STL does not centre", and the only one that is not small. It is also the natural home for the annotations raised earlier in the session - a measurement a maker takes by hand on a dropped mesh wants the same file and the same reasoning. Consider whether this deserves a decision document before code.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A maker can say where a dropped mesh's origin and orientation are, and the placement is a fact in the project file rather than a transform in code
- [x] #2 The survey and the report speak in the placed coordinates, so a reported number is one a maker could type into the script
- [x] #3 A mesh with no placement behaves exactly as it does today, in its own coordinates
- [x] #4 Nothing is moved silently: what the viewer draws and what the report says always agree
- [x] #5 The script never reads the file - the host hands it a placed mesh, as it already hands over values
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The decision this task asked for already exists and is merged: `backlog/decisions/decision-4 - A-reference-is-placed-and-the-placement-is-written-down.md` (task-26, PR #30, 2026-09-17), status `proposed`. It answers every question in this task's body: placement lives as a `[reference]` table in the project TOML beside `[values]`, numbers only (origin as "low"/"high"/"centre" or a triple, up/along as signed axes or a triple, never a face name by index since survey flat indices reorder); a mesh is placed once at the host edge before survey/report/script ever see it; the script never reads the file; rigid transform only, no mirror/scale.

Remaining work is decision-4's own "Sequencing" section (steps 1-4), none of which is implemented yet:
1. `src/bench/placement.py` — `placement(table, mesh) -> Plane` and `placed(mesh, plane) -> Mesh`. Does not exist yet. `src/bench/geometry.py` already has `Plane`, `plane()`, `to_local()` to build it from; `src/bench/meshing.py`'s `placed(vertices, stride, at: Transform)` is a raw-array helper, not the Mesh-level function decision-4 specifies, and `src/bench/model.py`'s `moved_part()` moves topology not triangles, so neither is sufficient as-is.
2. `tools/build.py` reads `[reference]`, places the STL, prints the frame.
3. The web app carries the table through the project model (read on Open, kept through regen, `file` matched against the drop, a "placed" chip).
4. A pick UI (choose a flat and corner off the survey in the view) — decision-4 explicitly defers this until picking-on-the-reference is itself designed.

Steps 1-2 are decision-4's own recommended starting point: independently useful and reviewable, no browser needed. This task's acceptance criteria should be read against decision-4's text rather than re-litigated from scratch.

Steps 1-2 of decision-4 (placement.py, tools/build.py's [reference] handling) implemented and merged (PR #38). Steps 3 (web/ carrying the table through the project) and 4 (the pick UI) remain, per decision-4's own sequencing - left open, not closed as Done, since the task's acceptance criteria (survey/report speaking in placed coordinates from an app-opened project) need step 3 to be fully met.

Step 3 (web/ carrying the [reference] table) implemented in this PR: web/src/values.ts reads/writes [reference] (words and triple-of-numbers grammar, its own unit tests), web/src/files.ts's Project gained a `reference` field threaded through serialized/restored/created/duplicated/renamed/single, src/bench/worker.py's Runner now takes a `table` argument and applies placement()/placed() before binding `reference`, a new bench.worker.surveyed(stl, table) replaces the inline SURVEY lambda in web/src/worker.ts so the survey path places the mesh the same way a run does, and main.ts's existing drop flow now matches the open project's [reference].file against the dropped file's name, applies the placement, and the chip says 'placed' only when a placement was actually applied. pyproject.toml's layer graph updated to let worker import kernel/placement/report. Full gate (uv run tools/check.py, including e2e) passes. Step 4 (pick UI) confirmed still out of scope per decision-4's own sequencing - not started.

All five acceptance criteria are satisfied by decision-4's steps 1-3 (merged: PR #38, #42). Step 4 (a pick UI choosing a flat and corner off the survey in the view) was never one of this task's acceptance criteria - decision-4 names it as a natural next step, explicitly deferred until picking-on-the-reference has its own design. Filed separately as task-37 rather than folded into this task's scope.
<!-- SECTION:NOTES:END -->
