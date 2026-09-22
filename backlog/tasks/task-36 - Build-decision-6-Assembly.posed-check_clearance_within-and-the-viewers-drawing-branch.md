---
id: task-36
title: >-
  Build decision-6: Assembly.posed, check_clearance_within, and the viewer's
  drawing branch
status: Done
assignee: []
created_date: '2026-09-22 19:19'
updated_date: '2026-09-22 02:35'
labels:
  - feature
milestone: Assemblies & Motion
dependencies:
  - task-29
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-6 (`backlog/decisions/decision-6 - An-assembly-is-a-scene-not-a-part.md`, task-29) is a decision document only - status `proposed`, no code. Nothing tracked building it, and that gap was discovered the hard way: task-34 was briefed assuming `Assembly.posed` and `check_clearance_within` already existed on main, and they do not. This task is that missing implementation, against decision-6's own "Sequencing" section, verbatim:

1. `Assembly` gains `posed: bool = False` in `src/bench/model.py`, and `check_clearance_within(assembly, least, *, exclude=())` in `src/bench/script.py` (or wherever `check_clearance` lives), built on the existing `check_clearance`/`clearance_between`/`_recorded` machinery. Provable without touching `web/`.
2. The viewer's branch: a `posed=True` assembly is drawn as given (no `stage.layout()` re-layout, no row-wrapping) rather than a `posed=False` one, which is unchanged.
3. `examples/fulcrum_hinge.py` adopts both: `stack-posed` and its union are deleted, the twelve real parts are wrapped in `Assembly(..., posed=True)`, and the `combinations()`-based clearance loop (which task-34's PR #39 already split into `check_clearance`/`check_contact` by `id()`-matched pairs, since there was no label vocabulary yet) becomes `check_clearance_within` calls keyed by the parts' own `Part.label` instead of object identity.

Read decision-6 in full before starting - it also argues two rejected alternatives (giving the dead `Placed.on: Plane` this meaning, and a new `Scene` type separate from `Assembly`) that this task should not revisit without a reason decision-6 didn't already consider.

task-35 (clearance through motion) depends on this landing, not on decision-6's document alone - it needs an actual posed `Assembly` to sweep.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Assembly.posed exists and check_clearance_within reads a labelled assembly's parts pairwise, with an exclude list for pairs task-34's check_contact already declares
- [x] #2 A posed=True assembly is drawn by the viewer exactly as the script placed its parts, with no stage.layout() re-layout; a posed=False assembly is completely unaffected
- [x] #3 examples/fulcrum_hinge.py's stack-posed fake part is deleted; its twelve real parts are wrapped in a posed assembly and its clearance/contact loop is keyed by Part.label rather than id()
- [x] #4 Manufacture (cut sheets, quantities, export) reads Assembly.parts exactly as before, regardless of posed - decision-6's claim that stage.layout() was never on the export path is verified again against current main before relying on it, not re-assumed
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged (PR #40). All three of decision-6's sequencing steps:

1. `Assembly.posed: bool = False` (model.py) - a pure drawing flag, documented as such.
2. `stage.as_given(bodies)` - the sibling of `layout()` with the identical return shape (every offset zero, box = union of what's already there). `views.scene()` branches on `assembly.posed` to call `as_given` or `layout` - this IS decision-6's "viewer's branch"; it turned out to live in Python (`views.py`), not TypeScript, because `views.py` is the only importer of `stage` anywhere in the codebase and `viewer3d.ts` only ever consumes already-placed positions. Verified, not assumed.
3. `check_clearance_within(assembly, least, exclude=())` in script.py - walks an assembly's parts pairwise by their own `Part.label`, refusing (not silently skipping) an `exclude` label the assembly doesn't hold or a non-Solid part, since a silently-skipped pair reads as a pair that passed (the exact task-34 AC#4 failure mode).
4. `examples/fulcrum_hinge.py`: `stack-posed` and its fusing union deleted; twelve real parts wrapped in `assembly("stack", parts, posed=True)`; task-34's `id()`-matched combinations loop replaced by `check_clearance_within(stack, fit, exclude=seats)` + `check_contact` over the same `seats` tuple, read twice so the two can't drift.

AC#4 (manufacture independence) re-verified against current main directly, with a new test (`test_a_posed_assembly_is_manufactured_exactly_as_an_unposed_one`) that runs the same parts posed and unposed and asserts files/sheets/refs/violations/summary/every part's qty+bbox are byte-identical, with only `stage` differing.

Two advisor passes: caught that all `check_clearance_within` tests ran with no kernel (where the check answers `unchecked` and can't show a real finding naming both parts) - fixed with a real-kernel adapter test.

Known limits, stated in the PR rather than papered over: a posed assembly is drawn exactly as given, not re-grounded to z=0 (the fulcrum stack straddles the grid plane, since re-grounding would be a layout by the back door); `viewer3d.ts`'s camera-frame still expands to include the origin, so a posed assembly far from the origin would stretch the frame; and decision-6's "tall thin mechanism" camera-framing concern is unsolved (the camera uses the union of world bounds, decision-6's own "obvious answer," explicitly not claimed to be the final one).
<!-- SECTION:NOTES:END -->
