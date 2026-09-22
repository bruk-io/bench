---
id: task-44
title: 'A dropped body is a row in the refs container, selectable'
status: Done
assignee: []
created_date: '2026-09-22 15:29'
updated_date: '2026-09-22 15:55'
labels: []
milestone: m-4
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-9, step 1. A maker drops an STL on the view and it is reachable only from the chip over the viewer; the refs container, which is where everything a run named is listed and selected, says nothing about it.

Give a dropped body a row of its own in the refs container, in a References group beside what the run named rather than inside it, and let a click on that row select it the way a click on a face selects a ref. This is the half of the sidebar ask that depends on nothing else in the milestone: no file model change, no host route, no migration.

A reference gets one row and no subtree. decision-8 says an imported mesh names nothing under it, and decision-7 refuses a survey's own indexing, so a face list under a dropped STL is already ruled out.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A body dropped on the view appears as a row in the refs container, named for the file it came from
- [x] #2 The References rows are a group distinct from what the run named, and refs-tree's refs property still holds only the run's own names
- [x] #3 Clicking a reference row selects it and lights the dropped body up in the view
- [x] #4 Insert ref is disabled while a reference is selected, and enabled again when a ref is
- [x] #5 Selecting a reference does not put anything resolvable-looking in the selection bar that resolve() would fail on
- [x] #6 The refs container reads sensibly with a body dropped and no run yet, rather than saying the run named nothing
- [x] #7 A reference row and a ref row can each be selected without the other's selection surviving
- [x] #8 Covered by a component test beside refs-tree.ts and an e2e check that drops a body and asserts the row and the disabled Insert
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built on branch `refs-container-references`.

The row was the easy half; the selection model was the work. `main.ts` held one `picked: string | null`, and `showSelection` enabled *Insert ref* straight off it - so every selection was assumed to be something `ref("…")` can name. A dropped body is not: `resolve()` cannot find `ref("bracket.stl")`. Rather than widen `picked` into a union, the page holds a second field, `pickedReference`, and keeps the two mutually exclusive. *Insert ref* still reads `picked` alone, so it is right by construction rather than by a check.

`refs-tree.ts` took `references` and `selectedReference` beside `refs`/`selected`, which keeps the documented contract of `refs` - "every ref the newest run named" - true, since a dropped body was named by no run. The empty state now tells "no run yet" from "nothing at all".

The viewer gained `markReference(lit)`. The backdrop is still never clickable outside detection; this is the other direction only, so the container can say which body is meant. It cooperates with `detect()`: marking does nothing while the flats are coloured, and turning detection off restores the mark rather than the plain ghost. `deferred3d.ts` remembers it the way it remembers `select`.

Checked: 29 component tests on refs-tree (217 across the app), `tsc` and lint clean, and two e2e checks - the row appears and selecting it lights the body with Insert disabled, and a ref and a dropped body never hold the selection at once. Screenshot at `web/e2e/out/31-reference-in-refs.png`.

Follow-on already filed: task-49 makes a project hold several references with one active, which is what the list shape here is for.

Gate green on the second attempt. The first full `uv run tools/check.py` caught a real defect the isolated runs did not: `test_a_ref_and_a_dropped_body_do_not_hold_the_selection_at_once` used `_click_a_face` to get a ref off the drawing, and what sits under a given spot depends on where the camera ended up after the drop framed the body. It now takes the ref off the tree, which is what the check is actually about. PR #49.
<!-- SECTION:NOTES:END -->
