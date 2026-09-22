---
id: task-25
title: Show where the origin is
status: Done
assignee: []
created_date: '2026-09-22 19:59'
updated_date: '2026-09-22 20:33'
labels:
  - feature
  - web
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The view draws the work, a floor grid and a dropped body, and nothing that says where the origin is or which way the axes run. Most of the time the work sits on the origin and you do not notice. The moment it matters is the moment a dropped mesh lands 600 mm away: there is nothing on screen to tell you which way home is, how far off you are, or whether what you are looking at is the body or the backdrop.

This is what Fusion's origin gives a person day to day, minus the browser tree: a visible datum. X, Y and Z drawn from the origin, and the origin itself marked, so a maker reading a report full of absolute coordinates can see where those coordinates are measured from.

Deliberately NOT part of this: origin planes or datums as objects a script can name. bench already has that vocabulary in code - `raised(XY, z)` is a construction plane, `plane_of(body, ref)` is a datum taken off geometry, `Point(...)` is a datum point. A tree of origin objects exists in Fusion because you are clicking rather than typing, and adding one here would duplicate names that already exist. This task is about seeing, not naming.

Worth deciding rather than assuming: whether the axes are drawn at a fixed size or scale with what is in view (a 10 mm gnomon is invisible beside a 300 mm handle; a scaled one moves as the scene changes), whether they are drawn at the origin or in a corner as an orientation gnomon, and whether the labels survive a dark theme.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The origin and the direction of X, Y and Z are visible in the view
- [x] #2 They stay legible whether the scene is 10 mm or 600 mm across
- [x] #3 They never obscure or get picked instead of the work - a click still selects the face behind them
- [x] #4 Nothing about what is drawn depends on geometry computed in TypeScript
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added in viewer3d.ts: a `datum` group (origin marker + X/Y/Z arrows via THREE.ArrowHelper, plus single-letter sprite labels) added directly to the scene, sized by `layDatum(box)` off the same `bounds` box `fit()` frames from - so it scales with whatever is in view instead of a fixed size or a fixed-orientation corner gizmo. Drawn AT the origin (not a corner gnomon), because the point is showing where home is relative to a body that may have landed hundreds of mm away, which an orientation-only corner gizmo cannot do. `bounds.expandByPoint(ORIGIN)` before framing/sizing, so the origin is always inside the frame even in the (normally moot, work-near-origin) case where it would not otherwise be.

Colours follow the CAD X-red/Y-green/Z-blue convention (no legend needed); labels are drawn with a white halo behind a saturated fill so they read on both the pane's light and dark gradients (styles.css `.canvas-3d` switches background under `prefers-color-scheme` - the datum was checked against both, not just the default).

Criterion #3: the datum group is added directly to `scene`, never to `parts`, and picking only ever raycasts `parts.children` - the same structural guarantee the backdrop/reference mesh already relies on - so a click always reaches the face behind the axes. Verified by an explicit e2e click-through-the-axes check.

Criterion #4: nothing here computes the model's shape in TypeScript - the datum's size comes from the same bounding box (Python's stage.bounds, plus a three.js bbox of an already-placed dropped mesh) already used for camera framing, not from any new geometric analysis.

A `data-datum` attribute (the arm length in mm) was added to the container dataset, following the existing `data-bounds`/`data-distance` convention, so a test can read it directly rather than doing WebGL pixel readback.

e2e coverage added: `test_the_origin_and_its_axes_scale_with_what_is_in_view` (small work vs. a body dropped hundreds of mm away - `data-datum` grows correspondingly; also clicks through the axes onto a real face) and `test_the_origin_and_its_axes_render_in_the_dark_theme`.

Gate: 773 Python passed twice (+1 pre-existing skip), 169 component tests, 73 e2e (69 baseline + 4 new, shared with task-24's two tests).

Merged as 630d264 (PR #28, squashed, shared with task-24). Gate as recorded on task-24: 773 Python x2, 169 component, 73 e2e.

A `datum` group in viewer3d.ts: an origin marker, X/Y/Z arrows in red/green/blue, and single-letter sprite labels with a white halo so they stay legible on both the light and dark canvas gradients.

The three decisions the task asked to be argued rather than assumed:
- Drawn AT THE ORIGIN, not as a corner gizmo. The point is showing where home is relative to a body that may have landed hundreds of mm away, which an orientation-only gizmo cannot do - it tells you which way you are looking, not how far off you are.
- SCALED to what is in view, off the same bounds box `fit()` uses, so a gnomon is neither invisible beside a 300 mm handle nor overwhelming beside a 10 mm part.
- Labels checked against both themes, with an e2e walk for the dark one.

Criterion #3 held by construction: the datum group is added to `scene` and deliberately kept out of `parts`, and picking raycasts only `parts.children`, so a click always reaches the face behind the axes. Criterion #4 likewise - nothing drawn depends on geometry computed in TypeScript, only the same bounding box already used for framing.

Added `data-datum` (arm length in mm) to the container dataset, following the existing data-bounds / data-distance convention that the e2e tests read.

Scope held: this draws the origin, it does not name it. No origin planes or datum objects a script can refer to were added, because bench already has that vocabulary in code - raised(XY, z), plane_of(body, ref), Point(...). Saying where a dropped mesh's own datum is remains task-26.
<!-- SECTION:NOTES:END -->
