---
id: task-43
title: >-
  Build decision-8: an Imported Solid leaf, so a candidate can be
  volume-compared to a dropped mesh
status: Done
assignee: []
created_date: '2026-09-22 03:36'
updated_date: '2026-09-22 13:56'
labels:
  - feature
milestone: Reverse Engineering
dependencies:
  - task-39
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-8 (`backlog/decisions/decision-8 - An-imported-mesh-is-a-Solid-leaf-like-any-other.md`, task-39) is a decision document only - the design question is answered, nothing is built. This task is that implementation, against decision-8's own sequencing:

1. `Imported(mesh: Mesh)` as a new `Node` variant in `src/bench/topology.py`; the four dispatch sites decision-8 verified actually need a new case (`node_children`, `_node_points` in `topology.py`; `_extruded_root` in `features.py`; `_node` in `adapters/browser.py`'s `JsKernel`) each gain one. `_cloud` in `adapters/browser.py` needs no case - its existing fallback already handles an unrecognized node correctly, per decision-8's own verification; do not add one out of habit.
2. `Modeller.imported(vertices, triangles)` on the protocol; `web/src/modeller.ts` implements it via `Manifold.ofMesh`/`new Manifold(mesh)`, letting a non-manifold mesh's own thrown error cross as `JsException` unchanged - no new validation logic, per decision-8's own argument.
3. A script-facing constructor - decision-8 leaves the exact signature as its own "still the owner's call" (probably `imported(reference)` needing no other argument, but not settled) - this task settles it.
4. `tests/adapter/kernel_cases.py` gains a case building `Solid(Imported(some_mesh))`, exercised through the existing `measured(kernel)` harness.
5. The motivating use proven: a script can compute how much of a candidate's volume overlaps a dropped reference's - `kernel.volume(Solid(Intersection(candidate, Solid(Imported(reference)))))` or whatever the step-3 constructor makes that read as.

Read decision-8 in full before starting, including "What this costs, honestly" (a boolean against a large import can be slow, deliberately no guard; Manifold's manifold-check is not a self-intersection check, deliberately not fixed here) and "Not in step one, deliberately" (no repair/simplification of bad input, no triangle-count guard, no special-casing of check_clearance/check_contact - they already work once Imported is a real Solid).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A dropped/imported mesh can be wrapped as a Solid leaf and used anywhere a Solid is accepted - Union, Difference, Intersection, kernel.volume, kernel.min_gap, check_clearance, check_contact - exercised against the real kernel, not only asserted
- [x] #2 A non-manifold import fails the way any other refused kernel call already does - a ValueError naming what went wrong, not a new bench-side validation path
- [x] #3 A script can compute how much of a candidate's volume overlaps a dropped reference's, as a real quantitative fit measure, proven against a real example
- [x] #4 The script-facing constructor's exact signature is settled, not left open a second time
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. `Imported(vertices, triangles)` in `topology.py` - NOT `Imported(mesh: Mesh)` as decision-8
   wrote it. The layer table forbids it: `topology = ["geometry"]` and `kernel = [..., "topology"]`,
   so topology cannot see `kernel.Mesh`, and `Mesh.refs` is `tuple[Ref | None, ...]` so moving
   `Mesh` down is blocked by `model.Ref` too. Same flat layout as `Mesh`, refs dropped honestly
   (a file has no names, exactly as a `Hull` keeps none).
2. The four dispatch sites decision-8 named - confirmed by mypy, not by reading: `node_children`,
   `_node_points` (topology), `_extruded_root` (features), `_node` (browser). `_cloud` needs
   nothing, its fallback handles it. mypy found zero further src sites and two test-side ones
   (the fake `_Modeller`, `_kinds` in the adapter test).
3. `Modeller.imported(vertices, triangles)` + `web/src/modeller.ts` via `new wasm.Manifold(...)`,
   no validation beside it.
4. Script-facing constructor settled: `imported(mesh: Mesh, *, label=None) -> Solid`, in a new
   module `src/bench/imported.py` (layer `["geometry", "topology", "kernel"]`) - not in `solids.py`,
   whose own docstring promises no kernel and which would leak the seam to `features` and every
   library above it.
5. `kernel_cases.py` gains `dropped()` in `CASES`, a `_fit(kernel)` overlap measure and a
   `_refusal(kernel)`; `test_shipped_kernel.py` asserts the arithmetic.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Probed the real Manifold before designing around it (tools/stack.py, 4 inputs): a lone triangle and an open boundary both throw `ManifoldError: Not manifold`; a non-finite vertex throws `Non-finite vertex`; an index past the end throws `Vertex index out of bounds`. So decision-8's prediction holds and a `status()` check after the constructor would be a branch nothing reaches - I wrote one, proved it dead, and removed it.

Two findings worth disclosing rather than fixing: an empty mesh imports as an empty body measuring 0, and a mesh wound INSIDE-OUT is accepted by Manifold as a valid 2-manifold and measures a NEGATIVE volume (-1000 for the test cube). Nothing catches the latter, in the same class as decision-8's own self-intersection disclosure.

Criterion 3 proven on the real Festool STL (obj_13_前面板.stl, 16,328 triangles): imports as a Solid, measures 439,077.771 mm3; intersected with a candidate box of its own extent the overlap is 439,077.771 (fraction 1.000 - the box wholly contains it, which is the right answer and a sanity check on the boolean); the same candidate slid 5 mm along X drops the overlap to 438,155.193 (99.8%), so the measure moves with the geometry.

PR: https://github.com/bruk-io/bench/pull/48 (branch `task-43-imported-solid`, commit 7caed07). Full gate green: 207 vitest, 874 pytest twice, 75 e2e, exit 0. NOT merged and task left In Progress - the main session verifies and merges.

OPEN QUESTION FOR THE OWNER: `backlog/decisions/decision-8` still specifies `Imported(mesh: Mesh)` under 'The shape' and 'What changes'. That spelling is unimplementable (topology may import only geometry; kernel imports topology; Mesh.refs needs model.Ref), so the node holds Mesh's flat layout - vertices + triangles - instead. I did not edit the decision file; whether to amend it is the owner's call.
<!-- SECTION:NOTES:END -->
