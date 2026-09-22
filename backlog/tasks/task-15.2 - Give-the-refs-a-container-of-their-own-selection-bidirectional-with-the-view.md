---
id: task-15.2
title: 'Give the refs a container of their own, selection bidirectional with the view'
status: Done
assignee: []
created_date: '2026-09-22 16:53'
updated_date: '2026-09-22 01:47'
labels:
  - web
  - ux
dependencies: []
parent_task_id: task-15
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The one idea bench has that no other tool does, given a surface built for it instead of a line of status text.

A run names every face, engraved line and line of lettering it makes, and hands that list down as refs - paths like `drawer-front-1/pull`. Today the only way to see one is to click the drawing and read the bar. The refs become a tree in the sidebar, nested on the path separator, so a maker can read what a script named without hunting for it on screen.

Selection is one thing seen from two places. Clicking a face in the 3D view reveals that ref in the tree - its ancestors opened, the row scrolled to and marked. Clicking a row in the tree highlights that face in the view, exactly as a click on the face would. Neither direction may fight the other or loop.

A ref survives a run, because a name is the same name after a rebuild; so what was selected before a run is still selected after it, and what a run no longer names is dropped rather than left pointing at nothing. A ref a check reported is marked on its own row, so a finding in the panel and the name it is about are not two unrelated lists.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The refs a run named are a tree in the sidebar, nested on the path separator
- [x] #2 Clicking a face in the view reveals and marks that ref in the tree
- [x] #3 Clicking a ref in the tree highlights what it names in the view
- [x] #4 The insert shortcut inserts whichever ref is selected, picked from either place
- [x] #5 A ref the newest run no longer names stops being selected rather than pointing at nothing
- [x] #6 A ref a check reported is marked on its row
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`bench-refs-tree` builds the tree from the flat ref paths with `treeOf`, nesting on "/" and giving a path whose parent nothing named a node of its own.

The round-trip has one owner. The tree never selects itself: a click sends `ref-pick` up, the page calls `space.select` and `showSelection`, and `showSelection` sets `tree.selected` back down. So both directions run through the page and cannot loop. `willUpdate` opens whatever ancestors were shut above a new selection and `updated` scrolls the row into view, which is what makes a face clicked on the drawing reveal its row.

Branches are open until shut by hand - a run's refs are tens of names, not a file system, and a tree that starts shut is a tree nobody reads.

A reported ref is marked on its own row and on every row above it (the same "inside" rule the viewer paints by), so a shut branch still shows that something under it was reported.

**Acceptance criterion #6 is NOT met, and it is not closable from the browser.**

The tree does mark a reported ref, and `refs-tree.test.ts` covers it where the names line up. But with the shipped examples nothing is ever marked, because the two sides are speaking different namespaces: a check reports the face it measured from in the namespace of the *solid* it was handed - `check_overhangs` on the tote answers `socket-1` - while the scene's ref table, and so the tree, holds the part-qualified path a maker writes, `tub/socket-1`.

The page cannot close the gap. A `ViolationView` carries a check, a message, a severity, its refs and a line, and never says which part it was about, so there is nothing to qualify the ref with. Matching on the last path segment instead would mark the wrong row the first time two parts share a face name, which is worse than marking none, and changing what the checks report to suit the UI is out of scope.

Two further facts worth keeping, found on the way: `fits` and `clearance` build their violations with no refs at all, and `wall` names a face only when the thinnest wall lands on one that has a name - on the enclosure's lid it does not. So the design canvas's own worked example, a warning on `drawer-back-3` from a `check_fits` violation, is not implementable for that check.

What would close it: a check that reports the ref the rest of the app can find, i.e. the part-qualified one. That is a change to what a check hands back, so it belongs in `bench`, not in `web/`.

Criterion #6 is closed by #19 (task-17), and closed properly rather than by loosening anything. A check is handed a bare shape and names faces in that shape's namespace; the runtime now remembers which shape each check was given, and the scene prefixes the label of the part whose `shape` *is* that shape. Identity, never a suffix - which is what keeps two parts that both have a `bottom` from taking each other's findings.

The e2e assertion that was withdrawn is restored as a real check, verified by hand on merged main at `tests/e2e/test_app.py:1231-1234`: with the enclosure's wall brought down to 1.2 mm, `box`'s row carries exactly one `.flag` and `lid`'s row exists and carries none.

#1 to #4 are each backed by a named e2e check I have watched pass in a full gate run on main: `test_clicking_a_face_reveals_that_ref_in_the_tree`, `test_clicking_the_tree_lights_up_what_it_names`, `test_the_insert_shortcut_writes_the_ref_once`, and `test_the_insert_shortcut_writes_a_ref_picked_off_the_solid`.

#5 is deliberately left unticked pending a check that it is actually tested rather than merely implemented.

On #5, found by checking rather than assuming: the promise was implemented and untested. `viewer3d.ts` drops a chosen ref the new scene no longer names and tells the page (`const lost = chosen !== null && !known(chosen)` ... `hooks.onSelect(null)`), and the page clears the bar and the tree through `showSelection`. But no test anywhere exercised it - not in the e2e suite, not in `refs-tree.test.ts`, not on the page side. Nothing would have caught it breaking.

Two component tests added for the half the tree actually owns: a selection the newest refs no longer hold marks no row, and the page setting `selected` to null puts the mark down. 150 component tests now, up from 148.

The viewer's half - noticing the ref is gone and saying so - is the part that matters and needs a browser, so it wants an e2e check. Anchor established from a real run: dropping the cabinet's `drawers` from 6 to 2 retires 300 refs including four part-level ones, `drawer-front-3` through `drawer-front-6`, so a check can select a ref that genuinely ceases to exist rather than one that might survive the edit and prove nothing.

#5 is now tested rather than merely implemented, and the e2e check is the half that matters - the viewer noticing a chosen ref is absent from the new scene and telling the page.

`test_a_ref_the_newest_run_no_longer_names_stops_being_selected` picks `drawer-front-6` from the tree, drops the cabinet's `drawers` to 2 - which retires 300 of its 770 refs, that part among them - and asserts the bar has fallen back to "click any face to get its ref", Insert is disabled, and the tree no longer holds the row. A part-level ref on purpose: it certainly has geometry to light when picked and certainly ceases to exist afterwards, where a face ref might have survived the edit and proved nothing.

The check puts the cabinet back to six drawers before it ends. `page` is module-scoped - one browser page walks every check in the file in order - so a check that changes a number and leaves it changed hands the next one a scene it did not ask for. Nothing after it happens to care about the drawer count today, which is luck rather than a promise worth resting on.

Full gate green with it in: 690 passed twice, 60 e2e (up from 59), ruff, format, mypy, tsc, eslint and 150 component tests.
<!-- SECTION:NOTES:END -->
