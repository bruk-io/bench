---
id: task-16
title: Make the refs tree readable at the scale a run actually reaches
status: Done
assignee: []
created_date: '2026-09-22 18:28'
updated_date: '2026-09-22 18:44'
labels:
  - web
  - ux
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The workbench shell shipped with the refs container built for the scenario the design exploration used: 29 refs. A real run of `gridfinity_cabinet.py` names **770**.

The nesting holds up - a part is a branch and its faces hang under it - but two choices made for 29 names are wrong for 770, and the container that was meant to be the centrepiece opens as a wall of text:

1. **Branches start open.** That was a deliberate call, argued in a comment in `refs-tree.ts` and in the PR: "a run's refs are tens of names, not a file system, and a tree that starts shut is a tree nobody reads". The premise was false. Every branch open means hundreds of face rows before the second part.
2. **Rows sort lexicographically**, so `bottom-10`, `bottom-11` ... `bottom-19` all come before `bottom-2`.

What a maker should see when the refs container opens is roughly what the sidebar was drawn for: one row per part, a dozen or so, each openable to the faces under it - and the faces in the order a person counts them.

The bidirectional selection must keep working through the change: clicking a face in the view still has to open the branch above its row and scroll to it, which is the one case where a shut branch must open by itself.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Opening the refs container on gridfinity_cabinet.py shows the parts, not hundreds of face rows
- [x] #2 Faces sort in counting order: bottom-2 comes before bottom-10
- [x] #3 Clicking a face in the 3D view still opens the branch above its row and scrolls to it
- [x] #4 The component tests cover the tree at a run's real scale rather than a handful of names
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Branches start shut, and the state they are kept in inverted with the default: a set of branches somebody opened rather than a set they shut. The reveal in `willUpdate` now adds the ancestors of a selection where it used to delete them - without that the round-trip breaks silently, since a face clicked on the drawing would select a row inside a branch nobody can see. The two e2e round-trip checks exercise exactly that path (they wait for a *face* row to appear and be marked), and both pass.

Sorting is `Intl.Collator` with `numeric: true`. The scene already hands refs over in counting order - `bottom-9` then `bottom-10` - so building the tree was scrambling what arrived sorted.

Two existing tests were found to be asserting nothing: a row inside a shut branch is `undefined`, and `undefined?.querySelector(...)` is `undefined` rather than an error, so the assertions passed vacuously. Added a `drawn()` helper that throws where the row is missing, naming what is on screen.

Checked against the built app rather than inferred: loaded gridfinity_cabinet.py in the real page, opened the refs container from the rail, and counted what it draws. The header reports 770 refs and the container opens with exactly 14 rows - cabinet-back, cabinet-side-left, cabinet-side-right, cabinet-top-bottom, drawer-back, drawer-bottom, drawer-front-1..6, drawer-side, runner - and no face rows at all.

The scale fixture is the real run's shape rather than a stand-in: 770 refs across the actual fourteen part labels, 53 faces each. It caught its own error on widening - the last-face assertion still expected `bottom-19` from the smaller fixture and the natural sort correctly ended at `bottom-53` - which is the kind of thing a fixture of a handful of names cannot tell you.

PR #16. Full gate green before opening it: 674 passed twice, 59 e2e, plus tsc, eslint + lit-analyzer and 148 component tests.
<!-- SECTION:NOTES:END -->
