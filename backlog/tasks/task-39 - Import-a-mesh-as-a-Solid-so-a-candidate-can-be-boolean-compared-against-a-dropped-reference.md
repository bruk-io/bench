---
id: task-39
title: >-
  Import a mesh as a Solid, so a candidate can be boolean-compared against a
  dropped reference
status: Done
assignee: []
created_date: '2026-09-22 02:05'
updated_date: '2026-09-22 13:56'
labels:
  - feature
milestone: Reverse Engineering
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while reverse-engineering a real object (a Festool Systainer face panel) into bench code: there is no way today to boolean-compare a candidate `Solid` against the raw mesh a maker dropped on the view.

`Solid`'s recipe tree (`src/bench/topology.py`) has leaves and combinators - `Extrude`, `Revolve`, `Union`, `Difference`, `Intersection`, `Hull`, `Moved`, `Curved`, `SolidFace` - and none of them wraps an already-triangulated `bench.kernel.Mesh`. `Kernel.volume`/`Kernel.min_gap` (`src/bench/kernel.py`) both take `Solid` only. So `reference: Mesh | None`, the placed dropped body a script already receives (decision-4, task-26), can never be one side of a `kernel.volume(Solid(Intersection(candidate, reference)))` or a `check_clearance`/`check_contact` call - both of which are `Solid`-only.

This matters specifically for reverse-engineering: today's honest, working substitute is comparing two `survey()` reports (the reference's, and one built from `kernel.mesh(candidate)`) number by number - extent, section outlines, wall bands. That is real and usable, and is the workflow in use as this task is filed. But it cannot answer "does my candidate actually occupy the same volume as the reference" the way a boolean intersection could - two shapes can share identical extents, sections and wall-thickness bands while still not being the same shape (a checkerboard of ribs in a different pattern, say), and only a volumetric compare would catch that.

The shape of the fix, not yet designed: a `Solid` leaf - call it `Imported` or similar - holding a `Mesh`, so an adapter's `Kernel` can build it as a manifold the same way it builds every other leaf, and `volume`/`min_gap`/`Intersection` all work on it unchanged. Whether `Union`/`Difference`/`Hull` etc. over an imported mesh need anything special (a mesh from an arbitrary STL may not be a clean 2-manifold the way bench's own kernel output always is - unlike a `Solid` bench built itself, an imported one could have gaps, self-intersections or reversed windings) is the open question a task on this should investigate before implementing, not assume away.

Not milestoned - a real capability, not yet scheduled against a specific piece of work beyond the reverse-engineering session that surfaced it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A dropped/imported mesh can be wrapped as a Solid leaf and used anywhere a Solid is accepted - Union, Difference, Intersection, kernel.volume, kernel.min_gap, check_clearance, check_contact
- [x] #2 Whether an arbitrary imported mesh needs validation or repair before boolean ops (non-manifold input) is investigated and the answer is argued, not assumed
- [x] #3 A script can compute how much of a candidate's volume overlaps a dropped reference's, as a real quantitative fit measure
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
decision-8 (backlog/decisions/decision-8 - An-imported-mesh-is-a-Solid-leaf-like-any-other.md) answers the design question this task asked for: Imported joins Node as a full Solid leaf (not a restricted one), crosses to the kernel the same way Hull's point cloud already does, and Manifold's own constructor (which already throws a nameable NotManifold error) is the validation - no new bench-side check needed. Verified directly against the code: only 4 of the ~9 assert_never(node) sites in the package actually dispatch over the full Node union and need a new case (node_children/_node_points in topology.py, _extruded_root in features.py, _node in adapters/browser.py); the rest either dispatch over the narrower Extrude|Revolve or (browser.py's _cloud) already handle an unrecognized node generically via its existing fallback.

This satisfies AC#2 (validation question investigated and argued). AC#1 and AC#3 are implementation-level and remain open - this task stays In Progress until Imported is actually built per decision-8's sequencing (not yet scheduled), same lesson task-29/task-36 already taught this session: a decision existing is not the same as the capability existing.

Implemented in task-43 (PR #48). decision-8 amended to match: Imported(mesh: Mesh) as originally written was unimplementable (a real layer-boundary cycle, found by trying to build it, not reasoned about in advance), corrected to Imported(vertices, triangles) - Mesh's own flat layout. Proven against the real kernel and the actual Festool panel STL from this session's reverse-engineering work: imported at 439,077.771 mm3, a candidate box's overlap with it correctly changes (100% to 99.8%) when the candidate is moved 5mm - the quantitative fit measure this task asked for, working end to end.
<!-- SECTION:NOTES:END -->
