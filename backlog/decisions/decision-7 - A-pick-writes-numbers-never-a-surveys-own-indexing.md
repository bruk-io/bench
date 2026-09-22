---
id: decision-7
title: A pick writes numbers, never a survey's own indexing
date: '2026-09-22 02:00'
status: proposed
---

# Proposal - a pick writes numbers, never a survey's own indexing

task-37. decision-4 named this its own step 4 and deferred it: "does not begin until the
question of picking on the reference is designed." It now has to begin, because of
something task-18.2 already settled without anyone asking this question at the time.

## Why

**A pick is not a convenience here - it is the only way.** task-18.2 made the project's
`.toml` a rendering the app owns: regenerated from `[values]` on every panel edit, read-only,
"a hand-written comment in an opened `.toml` does not survive the first panel edit." Nobody
argued that as doctrine for `[reference]` specifically, but it is already true of the file a
`[reference]` table would sit in. So today, short of *Open…*-ing a `.toml` written by hand
outside the browser, **a maker cannot place a mesh in the app at all.** decision-4 called the
pick "the named form becomes usable without typing." It is closer to: the named form becomes
*reachable* at all.

**The survey has nothing stable enough to point at.** `Survey.flats` is a tuple of `Flat`,
sorted biggest first and re-segmented whenever the survey's own logic changes - the same
fragility decision-4 already named and rejected for `[[measured]]`'s first sketch:
`between = ["plane-3", "plane-7"]` "would move when the survey did." A pick that stored
"flat 3" would be exactly that mistake, one document later. The only things in `Survey` that
do not move when the code does are numbers: a `Flat`'s own `normal`, `centre`, `low`, `high`;
`Extent.low`, `.high`, and the midpoint between them. decision-4's named origin words -
`"low"`, `"high"`, `"centre"` - are already these numbers, spelled for readability. A pick
has nothing else to reach for.

**There is no "corner" in the survey, and the task's own title assumes one.** `Extent.low`
and `.high` are the mesh's own axis-aligned box corners - true corners only when the mesh
happens to be a box aligned with its own axes, which the systainer foot (decision-4's
running example) is. For an irregular part, `Extent.low` is not a point on the mesh at all -
it is `(min x, min y, min z)` over every vertex, which can come from three different
corners. "Pick a corner" in the view can only ever mean a raycast hit: a real point on a
real face, which is a `Flat`'s own `low`/`high` (its face-local box corner) or an arbitrary
point on it - never, in general, the same thing as `Extent.low`.

## The shape

**A pick resolves to a number at the moment of the click, and the number is what gets
written - never an index, a name, a ref, or anything the survey could later disagree with
itself about.** Two picks, matching the task's own title:

- **Pick a flat** for `up`. A raycast against the dropped mesh's own geometry (see "What
  this costs" for why this needs new plumbing) returns a hit face and its normal.
  `Survey.flats` is searched for the `Flat` whose own `normal` agrees with the hit's within
  a tolerance still to be argued (see "still the owner's call") and whose `low`/`high` box
  contains the hit point - `Flat.facets` is a count,
  not a list, so there is no index from a triangle back to the `Flat` it belongs to, and
  none is added (see "What changes"). Matching by normal and box costs nothing new in
  `survey.py` and is enough: two coplanar `Flat`s never share both a normal and an
  overlapping box, because they would already have been one `Flat`.
- **Pick a corner** for `origin`. The raycast hit's own point, in the mesh's own exported
  coordinates - not `Extent.low`, not the picked `Flat`'s own box corner, the actual point
  the ray met. **Snapped, not required to match exactly**: if the hit point is within
  `bench.topology.ROUND` of `Extent.low`, `.high` or their midpoint, the resolved `origin`
  is written as that word instead of the raw triple, because a maker who clicked a box's
  visible corner meant the corner the report already calls `low`, and the named form reads
  better and survives a small re-export cleanly. Anything else is written as the triple it
  measured - which is most real parts, since a mesh being a perfect axis-aligned box is the
  exception decision-4 happened to pick as its example, not the common case.

**`along` has no pick, and this proposal does not invent a third one.** `placement()` (as
task-26 shipped it) requires `along` explicitly - unlike `bench.geometry.plane()`, which
would happily choose an arbitrary perpendicular, `placement()` never does, because an
arbitrary axis silently chosen is exactly the kind of unrecorded transform decision-4 exists
to prevent. So two picks are not enough to produce a valid `[reference]` table, and the
task's own "a flat and a corner" undercounts by one. **Naming this rather than solving it**:
the two picks above land in the panel's `up`/`origin` fields already showing the resolved
numbers (editable, per "still the owner's call" below), and `along` stays a typed value -
a signed axis word or a triple - the same way all three fields work today via *Open…*.
A maker who has picked two of three still has to type the third. A future pick for `along`
- an edge, say - is a fourth thing to design, not folded into this one because nothing here
argues for what an edge-pick should look like.

**Writing follows task-18.2's own rule, not a new one.** The panel already writes `[values]`
back on every edit; a pick writes `[reference]` the same way, immediately, because the file
is already a rendering the app owns and this is one more field of it. This proposal does not
reopen decision-3's still-unsettled question about whether the app or the maker owns the
TOML - task-18.2 already answered it for `[values]`, in code, and this treats `[reference]`
as the same kind of thing rather than arguing the question again for a second table.

## Rejected

**Storing which flat or which vertex was picked**, so a re-run could show the same pick
highlighted. Rejected for the reason above: a `Flat`'s identity is not stable across a
change to the survey's own segmentation, and a vertex index is not stable across a change to
the mesh's own triangulation. Nothing here is worth remembering past the moment it resolves
a number.

**Requiring an exact snap to a named word.** A pick that refused to write anything until the
hit point was exactly `Extent.low` would make the picker nearly useless on every part that
is not a perfect box - which, per above, is most of them. The triple is not a fallback for a
failure; it is the answer for the general case, and the named word is the special case for
the shape decision-4's own example happens to be.

**A form instead of a click** - typed coordinates read off the report's prose, which already
names `Extent.low` and every `Flat`'s own numbers. This is what the app already offers
today (*Open…* a hand-written `.toml`), and it is not what task-37 was asked to design;
naming a flat by clicking it is the whole reason a pick is worth building over typing
numbers a maker would otherwise have to find in the report and retype by hand.

## What this costs, honestly

**Picking the dropped mesh needs a mode, because today it is deliberately unpickable.**
`viewer3d.ts` keeps the dropped body in its own `backdrop` group specifically so it is
*never* hit: "a backdrop cannot be clicked and cannot get in the way of clicking anything
else," and a part's own picking casts only against `parts.children`. A flat/corner pick
needs a second raycast, gated behind an explicit "place this" mode a maker turns on - never
live alongside ordinary part-clicking, or the invariant that line exists to protect breaks
the moment a reference mesh happens to sit where a maker meant to click a part.

**A picked corner is rarely a name, honestly.** The snap-to-named-word case only fires for a
mesh that is an axis-aligned box, or close enough within `ROUND`. Most dropped meshes will
write a triple every time, and that is not a bug in this design - it is what "no corner in
the survey" (above) means in practice. A maker should expect to see numbers, not words, on
most real parts.

**`along` staying typed is half a pick UI, and that is deliberate rather than papered over.**
A maker who has never had to open the `.toml` by hand still has to type one signed axis or
one triple to finish a placement. This proposal accepts that rather than inventing an
edge-pick nobody has asked to design yet.

**The report still cannot be clicked.** `report.py` is prose with no ids; a pick has to work
directly against `Survey` in memory at the moment of the click, never against anything the
report tab shows. A maker cannot click a sentence in the report to place by it - only the
3D view itself.

## What changes

- `web/src/viewer3d.ts` - a placement mode; a raycast against `backdrop.children` gated
  behind it; a resolved hit (point, and the `Flat` it belongs to) handed back to whoever
  asked, the same shape `parts`' own picking already hands back a ref.
- `web/src/main.ts` (or wherever the reference chip and drop flow live after task-26 step 3)
  - the panel gains `up`/`origin` fields a pick fills and a maker can still edit by hand,
    and `along` as a typed field exactly as today; "place this" toggles the viewer's new
    mode; a resolved pick writes `[reference]` through the same path a panel edit already
    writes `[values]` through.
- `src/bench/survey.py` - **nothing.** `Flat.normal`/`.low`/`.high` and `Extent.low`/`.high`
  already carry everything a pick needs; no new field, no new export.
- `src/bench/placement.py`, `web/src/values.ts` - **nothing.** Both already read a resolved
  `origin`/`up`/`along`, named or as a triple; a pick produces exactly the value they already
  accept.

## Sequencing

1. The viewer's placement mode and the backdrop raycast, provable on its own: a mode that
   returns a hit point and its `Flat`, tested against a real mesh with two coplanar faces so
   the normal-and-box match is shown to discriminate between them rather than merely to
   agree with itself on a mesh with only one flat to find.
2. The panel gains `up`/`origin`, filled by a pick or typed by hand, `along` typed as today,
   and writes `[reference]` on every change - the same rule `[values]` already follows.
3. The snap-to-named-word rule, as its own small step: a hit within `ROUND` of `Extent.low`,
   `.high` or their midpoint writes the word: everything else writes the triple it measured.

Step 1 is reviewable with nothing else built - a mode that finds the right `Flat` for a
click is a testable claim on its own, against a real mesh, before any UI reads it.

### Not in step one, deliberately

- A pick for `along`. Stays typed; no edge-pick is designed here.
- Highlighting or remembering which flat or vertex was picked, across a re-run or a reload -
  rejected above, not merely deferred.
- Clicking anything in the report tab. The report stays prose; only the 3D view is pickable.
- Any change to `Survey`, `placement()` or the `[reference]` grammar itself. This is a UI
  that produces the values those already accept, not a reason to grow either.

## Still the owner's call

- **Does a pick immediately write `[reference]`, or does a maker confirm the resolved
  numbers first?** task-18.2's rule for `[values]` is immediate and silent; a placement is a
  bigger claim than one knob's value, and decision-4's own "nothing is moved silently" could
  argue either for showing the resolved numbers before committing them, or for the same
  immediacy `[values]` already gets, on the grounds that the panel already shows the number
  the moment it is written.
- **What does "place this" mode look like when nothing has been dropped yet?** Disabled,
  presumably, but the exact affordance (grey control, hidden control, a message) is a UI
  question this proposal has not answered.
- **Two tolerances here are borrowed, not argued, and decision-5 asks for the latter.**
  `ROUND` stands in for how close a hit point must be to `Extent.low`/`.high`/their midpoint
  to snap to the named word; nothing stands in yet for how close two normals must be to
  count as the same `Flat`, since none of the survey's own tolerances (`SAME`, `PLACE`,
  `CHORD`, `TURN`) is an angle - all of them are millimetres, for a dimension, not a
  direction. Both need a maker's real mouse-and-screen precision measured against them
  before either is more than a placeholder; a pick is not a tessellation, and neither figure
  has been argued from one yet.
