---
id: task-41
title: 'Expose a section''s real polygon vertices, not just its box and area'
status: Done
assignee: []
created_date: '2026-09-22 03:25'
updated_date: '2026-09-22 03:25'
labels:
  - feature
milestone: Reverse Engineering
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Roadmap item 0 of the reverse-engineering line of work (consulted with Fable - see task-40's notes for the roadmap in full). The highest-leverage, cheapest item: `bench.survey._loops()` already walks a mesh's cross-section at a height into ordered polygon vertices, and `_outline()` immediately reduces each loop to a bounding box and an enclosed area for `Section.outlines` - the same "computed and discarded" pattern task-40's `flat_faces()` found for detected flats.

`section_loops(mesh, z)` keeps the polygon instead: every vertex in order, at the real height asked for (usable directly as an `extrude()`/`loft()` outline), and whether the loop's ends met. This is what lifts the structural limit found while reverse-engineering the Festool panel - a bounding box and an area cannot tell a sparse rib lattice apart from a different shape of the same box and the same area, and only the actual points can. Verified against the real panel: a section through its lattice at z=61mm comes back as one real, connected 263-point closed polygon.

A real, honest finding from testing this against a triangulated hexagonal prism: a mesh's own triangulation can put genuine collinear points into a loop (a diagonal edge crossing the section plane at a chord's midpoint, not a true corner) - not a bug, just what the mesh's own triangles produced at that height, and nothing here simplifies or dedupes that away.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A caller can get a section's actual polygon vertices in order, not only its bounding box and enclosed area
- [x] #2 Each returned point is at the real height asked for, so a loop is directly usable as an extrude/loft outline
- [x] #3 Whether a loop's own ends met is still reported, the same as Outline.closed already does
- [x] #4 Verified against a real, complex mesh - not only synthetic test fixtures
<!-- AC:END -->
