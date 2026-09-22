---
id: task-24
title: A dropped body is framed even when the camera has been moved
status: Done
assignee: []
created_date: '2026-09-22 19:59'
updated_date: '2026-09-22 20:33'
labels:
  - bug
  - web
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Drop an STL and it is usually nowhere to be seen. Not off-centre - absent. Real exports carry the coordinates their author worked in: the systainer foot's extent runs from (606.795, -116.868, 0.000) to (651.795, -78.868, 6.800), so a mesh dropped beside a script whose work sits near the origin lands several hundred millimetres outside the view.

`viewer3d.ts` already does the right thing and is defeated by one guard. `drawn()` unions the standing body's bounding box into `bounds` (the comment there makes the case exactly: "a backdrop framed out of view or drawn as a speck in the corner is the same as one that never arrived"), but the call that acts on it reads `if (!touched && (bodies.length > 0 || standing !== null)) fit();`. `touched` is set the moment anybody orbits or zooms. So the reference is measured into the frame and then never framed, and the only way back is the Fit button in the viewer bar - which works, but nothing tells a maker it is what they need.

A drop is not like a run. Running is something the app does continuously as you type, and refusing to yank a camera somebody has aimed is right there. Dropping a body is a deliberate act that means "look at this", and it should frame, `touched` or not.

Worth deciding while in there: whether a re-run that changes the reference (a different file dropped over the first) frames again, and whether clearing the reference frames back to the work.

Do not move the mesh to fix this. Where the body sits is what the survey reports, and a transform nobody wrote down would put the viewer and the report in disagreement - see task-26, where placing it is done properly.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A body dropped after the camera has been orbited or zoomed is in view without touching Fit
- [x] #2 A run that draws new geometry still does not yank a camera the maker has aimed
- [x] #3 The dropped body's coordinates are unchanged - nothing is silently moved to bring it into frame
- [x] #4 Covered by an e2e walk that moves the camera first, so the guard cannot come back unnoticed
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Fixed in viewer3d.ts: `show()` now tracks the reference it last drew (`referenceDrawn`), compared by content (`sameReference()`) rather than object identity, since every run resends the same reference freshly deserialised from the wire. A drop is treated as "arrived" whenever the content differs from what was last drawn - a first drop, a different file dropped over an existing one, or clearing the reference back to null - and frames the camera (`fit()`) regardless of `touched`. A run that only resends the *same* reference does not force a fit, so an aimed camera survives a run exactly as before (criterion #2).

Decisions made, as asked: (1) dropping a different file over an existing reference DOES frame again - it is the same deliberate act, matching the brief's own view; verified in the e2e walk by dropping a second, differently-shaped/positioned body after zooming in and checking the camera pulls back out. (2) clearing the reference DOES frame back to the work - also verified in the e2e walk.

Only the camera moves - `fit()` only ever touches `camera`/`controls`, never the mesh's geometry; the e2e test also asserts the survey report's own printed coordinates (606.795, -116.868, 0.000) to (651.795, -78.868, 6.800) match exactly what was dropped, unchanged.

e2e coverage added in tests/e2e/test_app.py: `test_a_dropped_body_is_framed_even_after_the_camera_has_moved` (orbits the camera first, then drops a body built with the exact systainer-foot coordinates from the brief; also covers the different-file-refits and clear-refits-to-work decisions) and `test_a_run_after_a_drop_does_not_yank_a_moved_camera` (criterion #2: types a comment after a drop and orbit, and asserts the camera is untouched by the resulting run).

Gate: 773 Python passed twice (+1 pre-existing skip), 169 component tests, 73 e2e (69 baseline + 4 new, shared with task-25's two tests).

Merged as 630d264 (PR #28, squashed, shared with task-25). Branched from b414189, pushed without incident, no rebase needed. Gate: 773 Python x2 (+1 pre-existing skip) and 169 component - both exactly baseline - and 73 e2e (69 + 4 new). main's tree is the gated aa7c3e5.

The diagnosis in the description was right, but it missed a subtlety the agent found: comparing the reference by object identity would never work, because every run resends the same reference freshly deserialised from the wire, so identity always looks new. The fix keeps `referenceDrawn` and a `sameReference()` helper that compares by CONTENT (the positions array). A body counts as arrived - and forces a fit regardless of `touched` - only when its content differs from what was last drawn. That is what keeps criterion #2 intact: a keystroke-run redraws the same reference, sees no change, and leaves a camera the maker has aimed alone.

Both open questions answered yes, as the description leaned: a different file dropped over an existing reference frames again, being the same deliberate act, and clearing the reference frames back to the work.

Criterion #3 is verified rather than asserted: the e2e checks that the survey report prints the dropped body's exact unmoved coordinates. Only the camera moves.

Two findings from writing the tests, neither a bug, both worth knowing. The app's default startup script with no bench.files in localStorage is gridfinity_cabinet.py (14 parts, about 570x490 mm), not the small STARTER template - STARTER is only used for a file created with the + button, so anyone assuming the startup scene is small will be surprised. And replacing editor content then calling settle() immediately can observe the pre-edit 'not running' state and return before the new run starts; the existing _ran() helper waits out the 300 ms debounce first for exactly that reason.
<!-- SECTION:NOTES:END -->
