---
id: decision-4
title: A reference is placed, and the placement is written down
date: '2026-09-22 21:30'
status: proposed
---

# Proposal - a reference is placed, and the placement is written down

Successor to decision-3, which gave a project a file beside its script and reserved that file
for "what is measured and annotated rather than computed". This is the first thing to go in
it that is not a value. It is task-26, and the task said to consider whether it deserved a
document before code; it does, because the obvious shape is wrong in a way that only shows
once a mesh is rotated.

decision-3 is still `proposed`. Three of its open questions were answered by implementation
rather than by a decision - the panel writes the file on every edit, a clamped value is
written back as built, and the TOML is a rendering the app owns rather than a document the
maker owns (task-18.2). None of that is settled doctrine, and the third one bears on this
proposal directly: it is the reason a maker cannot type the table this proposal introduces
into the app yet. That is said again below, where it costs.

## Why

A dropped mesh arrives in its exporter's space. The systainer foot's box runs from
(606.795, -116.868, 0.000) to (651.795, -78.868, 6.800). Every number the survey reports
about it is true, and none of it is typeable: a maker writing the script wants "the bore is
12 mm in from that corner", not "the bore is at x = 642.137". The survey spent four PRs
(task-14.2, 14.3, 20, 21, 22) refusing to claim more than it measured, and the result is a
report that is honest to the thousandth in a frame nobody wants.

What is missing is a way to say where the mesh's datum is - this face is my XY, this corner
is my origin, this edge runs along X - and to have the survey, the report, the script's
`reference` and the view all speak in those terms afterwards.

### Why it is written down and not inferred

The tempting fix is an auto-centre: drop the mesh and quietly move its box to the origin.
task-24 refused exactly this, and moved only the camera, for a reason worth restating: an
auto-centre is a transform, and an unrecorded transform puts the viewer and the report in
disagreement. The report says 606.795 and the screen says 0, and nothing anywhere says why.

A written placement is different in kind, not in degree. It is a fact in a file: a reader can
check it against the original export, change it, diff it, and see the same numbers on the
screen, in the report and in the file. The move still happens - that is the point - but it
happens because a line says so, and the line is where a reader would look. "Nothing is moved
silently" does not mean nothing is moved; it means every move has a sentence.

## The shape

A `[reference]` table in the same `<script>.toml` as `[values]`:

```toml
# systainer_foot.toml

[values]
draft = 8.4

[reference]
file = "obj_2.stl"
origin = [606.795, -116.868, 0.0]   # this point of the file is (0, 0, 0)
up = "+Z"                           # this direction of the file is +Z
along = "+X"                        # and this one is +X
```

That is a `bench.geometry.Plane` written as three lines - `plane(origin, normal=up,
x_dir=along)` - and the placement is `to_local()` of it: the origin lands on the origin, `up`
becomes +Z, `along` becomes +X. Nine numbers at most, never a matrix, and every one of them
is a number the report already prints: the foot's report says `from (606.795, -116.868,
0.000)` on its first line, and its bottom face says `facing -Z (down) at z = 0.000`.

Two things are sayable by name, because they are the two things the survey reports that do
not depend on how it segmented the mesh:

- **The box.** `origin = "low"`, `"high"` or `"centre"` is that corner or the middle of the
  extent, which is min and max over the vertices and nothing else. The common case - an
  export that is already the right way up, somewhere far away - is one line:
  `origin = "low"`.
- **The world axes.** `up` and `along` take `"+X"` … `"-Z"` or a triple. An export placed
  lying on its side is `up = "-Y"`.

Everything else is a triple, and the triple is read off the report. `along` is projected onto
the plane perpendicular to `up` before it is used, as `plane()` already does, so a direction
that is only roughly along the edge is fine; what was actually used is what the host says
when it reads the file (below).

### Why the named form stops at the box and the axes

The task's obvious first shape was to name a flat: "put flat-3 on XY". This repository
already knows what that costs, from `refs-tree` and task-15: a name that is an index into a
list the code produces is stable only while the code is. The survey's `flats` are sorted
biggest first and re-segmented on every change to the survey - task-20 moved the section
heights, task-21 merged rounds, and either could reorder a list on a real part. A placement
that named "the third flat" would have moved the origin across those two PRs without anybody
touching the file. That is the silent transform again, arriving through a name.

So a placement in the file is **numbers, always**, and the name that chose them is how the
app helps you type them, not what the file holds. A pick - click this face, click this corner
- resolves against the survey once, at the moment of the click, and writes the resolved
numbers with a comment saying what was picked. If a later survey no longer finds that flat,
the numbers still stand, because the placement is a fact the maker settled, not a query the
survey answers. This is the same reason a measurement is data a maker collected and not a
formula (decision-3), applied one step earlier.

### What is placed, and where: the real design fork

There are three places the placement could take effect, and the choice is the substance of
this document.

**The report places.** The survey measures the raw mesh; the report takes the placement and
prints every number through it. Rejected, and not for taste: it does not work. A section is
cut at a raw height in raw Z and its outlines are boxed in raw XY (`Outline.low`, `.high`);
a wall's `at` is a point but its bands are not; `_direction()` names `+Z` off a raw normal.
For a translation the report could shift every point; for a rotation it cannot rebuild a
section it never had, and a leaning face becomes a flat one or the reverse. It would also
make `report()` a function of two things, which task-14.3's first criterion - the report is
built from a survey alone - was written to prevent, and the layer graph enforces.

**The survey places.** `survey(mesh, placed=plane)` transforms the mesh on the way in.
Rejected too, more narrowly: the survey would then answer differently for the same mesh
depending on an argument that is not the mesh, and the script's `reference` and the viewer
would still need the placed mesh for the screen and the report to agree - so the host would
be placing it anyway, and the survey doing it again is the same transform in two places.

**The mesh is placed once, at the edge, before anything sees it.** Chosen. The host reads
the file, builds the plane, moves the mesh's vertices through it, and hands that mesh to
`run()` as `reference` - exactly as it hands `[values]` as `overrides`, and as the task's
own criterion #5 puts it. From there everything is already true: `survey(reference)` in a
script measures placed numbers; the app's survey request surveys the same placed mesh; the
scene's `reference` is the placed mesh, so the viewer draws it there; the origin task-25 drew
now sits on the corner the maker named. There is exactly one mesh in the system after the
edge, and the survey and the report do not change at all.

## Why this is smaller than it looks, and where it is not

decision-3's strongest argument was that `configured(cls, values)` already took an untrusted
mapping, so a TOML table was that mapping and nothing under `src/bench` changed. The same
argument does **not** carry here, and it is better to say why than to pretend.

Moving a `Mesh` through a `Transform` is geometry. bench has `Transform`, `plane()`,
`to_local()` and `Mesh`, and no function that puts the first three to the last: `moved_part`
moves topology, not triangles. The function is ten lines - each vertex triple through the
transform, `triangles` and `refs` untouched - but it has to exist, and it has to exist once,
in Python, because both hosts need it and the browser is forbidden geometry of its own: a
placement applied by TypeScript and one applied by `tools/build.py` would be two
implementations that could disagree, which is the disagreement this whole proposal exists
to prevent.

So `src/bench` changes, by one module:

- `placement.py` - layer row `["geometry", "kernel"]`, beside `facets`. `placement(table,
  mesh) -> Plane` reads an untrusted mapping into a plane, resolving `"low"` and `"+Z"`
  against the mesh's own box and the world axes, and raises naming the key it cannot read,
  as `configured` does. `placed(mesh, plane) -> Mesh` is the move.
- `survey.py`, `report.py`, `script.py`, `params.py` - nothing.
- `worker.py`'s runner takes one more argument beside `stl`: the table, as JSON, or nothing.
  It is a host and this is its edge.

That is the whole of it in the package, and it is honest to call it small. It is not nothing,
and the difference from decision-3 is exactly that a placement has to reach the survey and
the survey is inside the package.

A rigid transform is all this can say - `plane()` builds a right-handed frame by `cross`, so
a mirror is unsayable by construction and a scale has no key. That is deliberate: a mirror
would turn every "material inside" into "material outside" and a scale would change every
number the survey reports; both are different problems from "where is the datum", and a mesh
in inches is not placed, it is converted. Floating noise from a rotation by an arbitrary
angle is on the order of 1e-13 mm, four orders under `ROUND`; an axis-aligned placement is
exact, and a translation alone is a subtraction.

## Rules

- **No table, no move.** A project with no `[reference]` behaves exactly as today, in the
  file's own coordinates. Criterion #3.
- **A placement names the body it places.** `file` is required. In the browser it must match
  the name of the dropped file; on the command line it names the STL to read, beside the
  TOML. A placement for `obj_2.stl` is never applied to `obj_6.stl` because that happened to
  be dropped - the host says "placed for obj_2.stl; obj_6.stl was dropped" and leaves the
  body where the file put it. Applying it anyway would be a move nobody wrote down.
- **The host says what it did.** `tools/build.py` already prints `cabinet.toml: units_x=4`
  before a run; it prints the placement it read the same way, with the frame actually used
  after `along` was projected. The app's reference chip says `placed` beside the file name.
  That is the sentence every move has.
- **A placement is not a parameter.** It is not in `[values]`, not in the panel, not sent as
  an override, and the script cannot see it; the script sees a mesh. It is about the body,
  not the thing being built.
- **The file is untrusted input.** A `[reference]` that is not a table, an `up` that is not a
  direction, an `along` parallel to `up`, an `origin` that is neither a triple nor one of
  the three words - each fails the run naming the key, as a bad value does now. It does not
  fall back to no placement, because "silently not moved" is as bad as silently moved.
- **Numbers in the file are the file's own.** `origin`, `up` and `along` are in the mesh's
  coordinates as exported, and `"low"` is the low corner of the box as exported. One frame in
  the file, never two.

## What this costs, honestly

- **`src/bench` changes.** One module, two functions, one layer row, and a second argument on
  the worker's runner. Said above; said again here because decision-3 promised the opposite
  and this proposal cannot.
- **The command line has no reference today.** `tools/build.py` reads `[values]` and runs
  with `reference=None`; it has never been handed an STL. Step 1 gives it one, read from the
  path `file` names. Modest, and it is what makes the placement provable outside a browser,
  the way task-18.2 proved the values by running a downloaded project with `tools.build`.
- **The app's file model grows again, and this is the real expense.** The project record is
  `{ name, source, values }` with `values` the TOML text; the table must go in beside it and
  survive `serialized`/`restored`. `values.ts` is a deliberate subset reader that passes
  every other table over and cannot read an array - a triple is new grammar. The drop path
  must match `file`; the survey request must carry the table; the runner and the worker's
  one-line survey entry each take one more argument. **All of it is in `web/`**, and none of
  it is geometry - TypeScript ships nine numbers and never does arithmetic on them.
- **A maker cannot type the table in the app.** The TOML tab is read-only and regenerated
  from the values table on every edit (task-18.2's third answer). So in the browser the only
  way a `[reference]` arrives in step 2 is *Open…* on a `.toml` written elsewhere, and the
  app must carry the table through its regeneration untouched. This proposal does not decide
  whether the TOML becomes editable; it notes that a second pressure on that question has
  arrived, and that a pick (step 4) is the alternative that keeps the file a rendering.
- **The pick is the largest step and the last.** "Click this face, click this corner" needs
  picking on the reference mesh, and the viewer keeps the backdrop out of `parts` precisely
  so it is never picked (task-25 criterion #3 relies on it). Making the reference pickable
  without letting it swallow clicks meant for the work is UI design of its own, and it is why
  the named form is a convenience layered on numbers rather than the file's grammar.
- **The body is not part of the project.** The reference lives in memory and a reload forgets
  it (task-19, limit 4). A placement therefore outlives the thing it places: a project can
  hold `[reference]` for a file nobody has dropped, and the app needs a state that says so -
  `obj_2.stl: not dropped` - rather than an error. Whether the STL should travel with the
  project is a separate question with a real cost (a megabyte of binary in `localStorage`,
  and in the download zip), left open below.
- **A placement changes what leans.** Place an export by a face that is not axis-aligned
  and every face that was `+Z` in the file is reported at its lean in the new frame, with a
  `loft()` candidate instead of an `extrude()`. That is the truth of the placement chosen, and
  the report saying it is the report working; it is worth knowing before picking a datum on
  a drafted part.

## What changes

- `src/bench/placement.py` - new: `placement(table, mesh) -> Plane` and
  `placed(mesh, plane) -> Mesh`. Exported from `bench` so a script can do it by hand today.
- `src/bench/worker.py` - the runner takes the table beside the STL and places the mesh
  before binding `reference`.
- `tools/build.py` - reads `[reference]`, reads the STL it names, places it, hands it to
  `run()`, and prints the frame it used.
- `web/` - the project keeps the table; `values.ts` reads and writes it; the drop matches
  `file`; the chip says `placed`; the survey request carries the table. The viewer changes
  nothing: it draws the reference where the scene puts it, as it does now.
- `examples/` - one project with a placement, once a small reference is worth committing;
  the systainer exports are not in the repository and this proposal does not add them.
- `README.md` - a layer entry for `placement`.

## Placement and measurement are two decisions

A measurement a maker takes by hand on a dropped mesh wants the same file and the same
reasoning, and `[[measured]]` is decision-3's fifth step. They are related in one way that
matters: a measurement is a number in a frame, and a placement is what fixes the frame. So
the placement comes first, and a `[[measured]]` written into a project with a `[reference]`
is in placed coordinates, which is the only reading under which "the bore is 12 mm from the
corner" means anything.

They are otherwise different halves of the report's rule. A placement changes what the survey
*measures* - the same triangles, moved, and every number still measured. A measurement adds
what the maker *claims* - a number the survey did not produce and cannot check. Keeping them
apart in the file keeps that line visible, and this proposal deliberately does not draft the
second table. One correction to decision-3's sketch of it is worth recording now, since it is
the argument above: `between = ["plane-3", "plane-7"]` names survey findings by index, and a
measurement that did that would move when the survey did. A measurement should carry the
numbers that identify what it was taken between, for the same reason a placement does.

## Sequencing

1. `placement.py`, its tests, the layer row and the export. Usable at once from a script:
   `survey(placed(reference, plane(Point(606.795, -116.868, 0.0), Z, X)))` reports the foot
   from the origin today, with no file and no UI. Nothing else changes.
2. `tools/build.py` reads `[reference]`, reads and places the STL, prints the frame. A file
   on disk drives a placed run, provable without a browser.
3. The app carries the table: read on *Open…*, kept through regeneration, sent with the run
   and the survey, `file` matched against the drop, the chip saying `placed`. The report tab
   and the view now agree with the file for a project opened from disk.
4. A pick: choose a flat and a corner off the survey in the view, and the app writes the
   resolved numbers. The named form becomes usable without typing.

Steps 1 and 2 are independently useful and independently reviewable, and step 1 answers
whether the numbers come out typeable before any of the expensive work starts. Step 4 does
not begin until the question of picking on the reference is designed.

### Not in step one, deliberately

- The pick (step 4), and any placement said by name in the file.
- `[[measured]]`, for the reason above.
- The STL as part of the project.
- Scale, units, mirroring. Not placements.
- More than one reference. `file` is singular because the drop is.
- The `Survey` carrying its own frame. Today the host says the placement and the survey
  measures what it is handed; if a report ever has to stand alone, away from its file and
  its chip, a `frame: Plane | None` on `Survey` and one line in the report's first block is
  the additive fix, and `report()` stays a function of the survey alone.

## Still the owner's call

- **`up` and `along`, or `normal` and `x_dir`?** The first is what a maker means; the second
  is what `plane()` is called with, and bench prefers its own words over friendlier ones.
- **Is `file` required?** This proposal says yes, so a placement can never land on the
  wrong body. The cost is that a project cannot hold "place whatever is dropped", which a
  maker trying three exports of one part might want.
- **Should the host's sentence be in the report too?** The report tab could carry the frame
  as a first line written by the host, which is the same pattern as `build.py`'s print. It
  keeps the report file-independent at the cost of the host writing one line of prose.
- **Does the TOML become editable, or does the pick come first?** Step 3 is only reachable
  through *Open…* while the tab is a rendering. Either the tab becomes a document (task-18.2's
  open question, decided) or step 4 is the way a maker sets a placement in the browser, and
  that orders the work.
- **Does the body travel with the project?** A placement for a file the project does not
  hold is odd to look at and honest about what the app keeps. Keeping the STL makes the
  project self-contained and makes it a megabyte.
