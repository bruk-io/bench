---
id: task-14.1
title: Read a mesh into bench
status: Done
assignee: []
created_date: '2026-09-22 13:55'
updated_date: '2026-09-22 16:28'
labels:
  - feature
dependencies: []
parent_task_id: task-14
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
bench can write a body out - as an STL, as a 3MF - but it cannot take one in, so an object that exists anywhere else cannot be brought in to be looked at. The arrow only points outward.

This gives bench the inbound half, so a mesh from somewhere else becomes an ordinary bench mesh: the same record the kernel already hands back, and everything downstream that reads one works on it unchanged.

An imported mesh knows nothing about names - no script wrote it - and that is a fact to carry honestly rather than a gap to fill in.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A mesh bench wrote reads back with the same triangle count and the same bounds
- [x] #2 A mesh that carries no face names is read without inventing any
- [x] #3 A file bench cannot read is refused with a reason that names what was wrong with it
- [x] #4 Reading a mesh needs no solid modeller
- [x] #5 No new runtime dependency is added
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Done as `mesh_from_stl` in the new `survey` module, the exact inverse of `export.stl`. Coincident corners collapse to one vertex; nothing is welded by proximity, because deciding two corners a thousandth apart are one is a repair rather than a read. An imported mesh carries `refs` of `None` throughout - no script wrote it - and that is left as it is rather than filled in. An ASCII STL and a truncated file are each refused by name. Covered by `tests/unit/test_survey.py`, which builds `Mesh` records by hand so the whole path is tested with no solid modeller present. Verified against real files: the three Festool STLs read back at exactly the sizes measured off them by hand.
<!-- SECTION:NOTES:END -->
