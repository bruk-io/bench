# bench - design

Workshop objects as code, in the browser. A user writes a short Python script
against the `bench` vocabulary; the app runs it (Pyodide, Python 3.15), shows
every part in one 3D view - a laser part as the plate it is cut from, a printed
part as its solid - lets them click any face, engraved line or lettering to get
its ref, and downloads nested SVG/DXF cut sheets. The shipped library modules are a
Gridfinity-sized laser-cut drawer cabinet and the printed bin that goes in it.

Scope began as **laser-cut parts**: planar `Face`s in a `Stock`, and that half ships
complete - the cabinet, the nest, the cut sheets - with each part drawn as the plate it is
cut from. Beside it is **3D as a tree**. A `Solid` no longer holds a tuple of faces; it holds a
`Node` - `Extrude`, `Revolve`, `Union`, `Difference`, `Intersection`, `Hull`, `Moved` -
which is the recipe for a body rather than its boundary. `extrude`, `revolve`, `union`,
`cut`, `common` and the thin sugar over them (`cuboid`, `cylinder`, `loft`, `pocket`,
`boss`) build that tree and nothing else.

**The tree is now evaluated, behind a seam.** `kernel.py` says what a solid modeller has to
be able to do - `mesh`, `volume`, `min_gap` - and holds no implementation; `adapters/browser.py`
is the one kernel, in Python, driving Manifold's WASM build in the browser's worker. A kernel
is handed to `run()` the way `show` is. So `import bench` still needs nothing installed, a run
with no kernel still yields every ref, parameter and cut sheet, and a run with one
additionally yields triangles that each know the name of the face they lie on, an STL and a
3MF.

What the tree answers on its own, and exactly, is what everything downstream reads: the name
of every face the body will have, the plane each one lies in, and a bound on where it reaches.
That is `faces_of`, `plane_of`, `bounds` and `index()` over a solid, and it is deliberate that
it came first - click-to-ref is the product, and it was cheapest to get right while there was
nothing to click. What the kernel adds is the other half of the same sentence: which triangles
those names are *on*. The cut files are unchanged - `nest` still leaves a body off the sheets and
`export` still draws no path for one, because there is no honest way to flatten a recipe onto
a sheet.

**The vocabulary is now answerable to five parts.** The maker's-lens review (`doc-3` in `backlog/docs/`)
walks the five things a maker builds in the first month and records where the API stopped
them; those five are now scripts under `examples/`, they run clean through a real modeller,
and what they needed - `hull` as a verb, a grid pattern, a turning one, and a plane on the
side of a cylinder - is what was added rather than the other way round. The printed
Gridfinity bin they start from is `library/gridfinity3d.py`.

## Repository layout

```
src/bench/
  geometry.py    where things are (Point, Vector, Transform, Plane)       [done]
  fasteners.py   the screw, insert, nut and magnet tables; Fit; bore()       [new]
  topology.py    Line|Arc|Circle, Edge->Wire->Face->Solid, label()          [done]
                 + the CSG tree: Node, SolidFace, faces_of, bounds          [new]
  model.py       Stock, Part, Text, Placed, Assembly, Build, Ref, index     [done]
                 + index/refs/resolve over a bare Solid                     [new]
                 + Material, Orient, Volume, Printed, process_of            [new]
  ops.py         constructors, selectors, modifiers, queries                [done]
  solids.py      the body verbs: extrude/revolve/union/cut/common,
                 cuboid/cylinder/loft/pocket/boss, plane_of, move/rotate/
                 mirror/pattern/grid/name                                    [new]
  features.py    hole(), Top, teardrop, bridge_steps, foot_chamfer           [new]
  joints.py      finger-joint edge profiles, open_box -> Box                [done]
  nest.py        kerf compensation + shelf packing onto a Bed              [done]
  kernel.py      the seam a solid modeller is plugged into: Kernel, Mesh     [new]
  meshing.py     which named face each triangle lies on; no modeller         [new]
  triangulate.py ear clipping: a flat region with holes as triangles        [new]
  plates.py      a laser part swept into its plate, walls named by cut path [new]
  checks.py      Severity, Violation, fits/clearance/wall/overhangs          [new]
  export.py      SVG and DXF text for parts and sheets (paths carry refs)   [done]
                 + stl() and three_mf() bytes for a printer                  [new]
  scene.py       the closed TypedDicts a run comes back as                  [done]
  stage.py       where bodies stand in the 3D view, and the floor under them [new]
  script.py      the script runtime: run(source) -> Scene JSON              [done]
                 + run(kernel=), per-part tree and mesh in the scene         [new]
                 + check_* closures, require(), scene violations             [new]
  views.py       what a run collected, built into the scene's records        [new]
  transport.py   the scene as JSON, meshes as buffers beside it, binary()   [new]
  worker.py      the one entry the browser's worker calls into Python        [new]
  adapters/
    browser.py   the Kernel: walks the tree, drives Manifold WASM by handle  [new]
  library/
    gridfinity.py  drawer cabinet sized in Gridfinity units                  [done]
    print.py       the print domain: PLA/PETG/ASA, clearance(), the beds     [new]
    gridfinity3d.py  the printed bin: Spec/derive/validate/bin_()             [new]
examples/        the seven scripts the browser's menu loads; five of them
                 are the maker review's parts, and they are the acceptance
                 test for the 3D vocabulary                                   [new]
tests/           pytest in four layers: unit/ (one file per module),
                 functional/, adapter/, e2e/ - see Testing below          [done]
web/             Vite + TypeScript app; Pyodide in a Worker                  [done]
                 + src/modeller.ts, Manifold's WASM as a table of handles      [new]
                 + src/viewer3d.ts, three.js with click-to-ref on faces        [new]
tools/           check, preview, qa, and stack/kernel_timing: the app's
                 Python and modeller together under Node                     [new]
```

v1 is complete: every module above ships, `tests/` covers it, and `web/` builds and
passes its Playwright run. The rows marked `[new]` are the 3D work so far - the tree and its
names, the kernel seam with the one kernel behind it, and the browser that draws what comes
out. See **Known limits** at the end for what it does not do.

The core install has no dependencies at all and `import bench` never reaches for one. The
modeller is Manifold's WASM build from npm, which only the browser app and the adapter tests
load.

Rules for every module: Python 3.15; frozen dataclasses / NamedTuples / enums /
unions / functions only - the one exception is a private record that a single call
mutates as it works and then drops, like `script._Recorder`, the notebook one `run`
writes its declarations into; no inheritance in domain code; private by default
(`_name`), public only when a caller exists; `list` means mutation, `tuple`
means done; `match` on closed unions ending in `assert_never`; exceptions are
exceptional and every direct `raise` is documented in a `Raises:` section
(ruff DOC501/502 enforce this; do not document propagated exceptions); every
module's public functions have tests. `__init__.py` holds imports and
`__all__` only. Run `uv run tools/check.py` before declaring anything done: it is ruff,
`ruff format --check`, mypy, the suite twice and the `e2e` layer, in that order.

Units are millimetres. `TOL` is the one tolerance. `==` on geometry is exact;
compare with `near()`. Every operation returns new values.

## Labels and refs

A `Label` is one path segment: `label(text)` is the constructor, and it refuses an
empty string or one holding a `/`. Every public entry point that takes a label -
`part`, `assembly`, `name`, the `ops` constructors, `wire`, `face`, `polygon`,
`jagged_edge` - accepts a plain `str` and puts it through `label()`. Every topology
record (`Edge`, `Wire`, `Face`, `Solid`) has an optional `label`; a `Part` and an
`Assembly` have a required one. A `Ref` is the `/`-joined path of labels from the assembly root;
unlabelled nodes are transparent (their children keep the parent's prefix).
`part()` and `assembly()` reject duplicate refs at build time. `index(root)`
is the `frozendict[Ref, Named]` table that the viewer and editor use.

Labels attach to intent, not topology: an op on a labelled face returns a face
with the same label, and holes cut into it are new labelled inner wires.

A `Solid`'s faces are named by the tree, not by the geometry, so every ref under a body
is known before anything builds it. `faces_of(solid)` and `node_children(node, at)` are
that rule, and `index()` walks them like any other rung:

| node | what it names under the enclosing `Solid` |
| --- | --- |
| `Extrude(profile, distance)` | `top` (the face at `distance`), `bottom` (on the profile's plane), `side-<edge label or index>` per outer-wire edge, and one face per profile hole wire under that wire's label (`hole-0`, `hole-1` ... unlabelled). A side swept from an arc or a circle has no plane and carries a `Curved` - the axis it turns about, its radius, where zero points, and which side the material is on - which is what `plane_of(..., around=, along=)` builds a tangent plane out of |
| `Revolve(profile, axis, angle)` | the same `side-` and hole faces, none of them planar, plus `start` and `end` when `angle` is less than a full turn |
| `Union` / `Difference` / `Intersection` | nothing of its own: each operand keeps its own label path, so a tool labelled `pocket` puts its floor at `plate/pocket/bottom` |
| `Hull(parts)` | nothing at all. Face identity does not survive a hull, and the parts are unreachable as refs |
| `Moved(node, at)` | what is under it, planes transformed. It renames nothing |

`side-` is load-bearing: `joints.open_box` already labels a panel's edges `top`,
`bottom`, `right` and `left`, and an extruded panel has a `top` and a `bottom` of its
own. A pocket's floor is `bottom` because that is the tool's own role; calling it `floor`
would take a kernel, to say which face of the tool survived the cut.

**At most one anonymous body per part.** An unlabelled `Solid` is transparent like every
other unlabelled node, so two of them under one part both offer a face called `top` and
`part()` refuses the pair by name. The root body of a part is the one that stays
anonymous - the part names it - and every feature joined to or cut out of it is labelled
as it enters the tree.

## model.py - what a part is made of

`Part.stock` is `Stock | Printed`: a sheet with a thickness, a material and a kerf, or a
filament with a way up. A print has none of the three things a sheet has, and
`Stock(0.0, "PLA")` was three lies in one record. `process_of(stock)` reads the process off
the arm - a sheet is cut, a filament is printed - and `part(label, shape, stock,
process=None)` uses it when a script does not say, so `part("lid", body, Printed(PLA))` is
a printed part and `part("side", panel, Stock(3, "ply"))` is a laser one. `Part.process` is
still carried and still honoured, because a milled panel is cut from sheet stock and is
nobody's laser job; deleting it, and closing the union into `Plate | Filament | Billet`, is
the step this defers.

`nest` passes over a printed part before it ever asks whether the shape is planar, because a
nest is sheets and a filament has no thickness to group a series by. It says nothing about
it: a scene of five bodies is not five mistakes, and a warning is for something that went
wrong. A part cut from *sheet* stock that is not a planar face still is one, and still says
so. (It used to warn about every printed part, which made the hinge open with three
warnings and nothing wrong.)

`Material`, `Orient` and `Volume` live here too, beside `Stock`, because a part carries one
and a check measures against another. What fills them in - PLA, PETG, ASA, the fit table,
the beds - is the print domain's, in `library/print.py`. Records here, numbers there: that
is what lets `hole` compensate a bore for the filament without `features` ever importing a
library.

## ops.py, solids.py, features.py [done] - the primitive operations

Constructors (geometry in, topology out). All but `line` return closed
`Wire`s on the XY plane, counter-clockwise for outlines; every `label` may be
a plain `str`: `rect(w, h, at=ORIGIN, label=None)`, `polygon(points,
label=None)`, `circle(r, at=ORIGIN, label=None)` (a single `Circle` edge),
`slot(w, h, at=ORIGIN, label=None)` (stadium: two lines, two arcs),
`rounded_rect(w, h, r, at=ORIGIN, label=None)`, `line(a, b, label=None)` (an
*open* wire of one straight edge - a reference line to engrave or measure
against, not a shape to `fill` or `cut`).

Face builders, subject first and the structure keyword-only:
`face(outer, *, holes=(), on=XY, label=None)` (in `topology`, where the checks are),
`fill(outline, *, on=XY, label=None)` (a face with no holes),
`cut(subject, tool, *, label)` (the label goes on the tool).

**`on=` means drawn on, not checked against.** Every wire handed to `face`, `fill` or `cut`'s
face arm is read as coordinates *in that plane's own frame* and lifted into the world by
`to_world(on)` - that is `topology.lifted`, and `topology.holed` is the same for a hole added
to a face that already exists. So `fill(rect(10, 6), on=plane_of(plate, "top"))` is a ten by
six rectangle standing on the plate's top face at the plate's own corner, which is what
`plane_of`'s promise ("a point that was `Point(5, 5)` on the profile is `Point(5, 5)` on
`top`") has always said and what the sketch builders now actually do. `XY`'s frame is the
world's, so its lift is the identity and the very wire object comes back: every flat drawing
in the package is byte for byte what it was. `raised(on, d)` in `geometry` is the other half a
maker needs - a plane offset `d` along its own normal, so `raised(XY, 5)` is the flat plane at
`z = 5` and a sketch on it keeps its flat numbers. `cuboid` and `cylinder` take `at`'s height
that way too, or the lift would apply it twice.

Body verbs (a tree in, a tree out; nothing evaluated): `extrude(profile, distance, *,
label=None)`, `revolve(profile, axis, *, angle=tau, label=None)`, `union(a, b, *,
label=None)`, `cut(base, tool, *, label)` - the second arm of the same verb, which is
what makes `plate/pocket` - `common(a, b, *, label=None)`, and the sugar over them:
`cuboid(w, d, h, *, at=ORIGIN, label=None)` (its rectangle's edges are labelled
front/right/back/left so its faces read `side-front`), `cylinder(r, h, *, at=ORIGIN,
label=None)`, `hull(*shapes, label=None)`, `loft(bottom, top, *, label=None)` (a hull of
two), `pocket(base, profile, depth, *, label)` and `boss(base, profile, height, *, label)`.

`hull(*shapes: Face | Solid, label=None)` is the `Hull` node as a verb, and on a kernel with
no sweep and no fillet it is how a changing profile is written at all: a stack of flat
slices with a hull round them is the Gridfinity base, the stacking lip, the flare under a
compartment's mouth and the countersink under a screw head. A `Face` enters as an extrusion
of no height, so a slice needs no thickness of its own. Every straight run between two
slices is exact; a curve has to be sliced finely enough to stand in for itself. `loft` is
`hull` of exactly two, under the name a maker knows it by.

`plane_of(solid, at, *, around=None, along=0.0)` is the query that closes the loop: the
plane of one named face, normal pointing out of the material, in the frame the face was
authored in - a point that was `Point(5, 5)` on the profile is `Point(5, 5)` on `top`, so a
sketch placed `on=plane_of(plate, "top")` uses the plate's own numbers. It raises
`LookupError` for a name no face answers to and `ValueError` for a face with no plane.

**A round face has a plane at every point of it**, and `around` is how you ask for one -
the answer to the review's blocked part (d), the radial set screw. `plane_of(collar,
"side-0", around=0.0, along=6.0)` is the plane tangent to the collar's side, a turn of
`around` radians from the profile's own X and `along` millimetres up the sweep: origin at
that point of the surface, normal out of the material, X running round it and Y up it,
which is the same frame a flat side gets. The radius comes off the body, so the seat follows
the part when the part changes - a helper taking an axis and a radius would be a second way
of naming a face that the editor could never insert and that would silently go stale. A hole
wire that is one circle is round the other way round: its normal points *at* its own axis,
because that is out of the material. Asking a flat face for a turn, or a round one for a
plane, is a `ValueError` that says which.

Modifiers (topology in, topology out; labels preserved):
`offset(wire_or_face, d)` - outward for positive `d` on outlines, inward on
holes; lines become shifted lines, arcs change radius, corners between lines
get a sharp intersection (miter). Used for kerf compensation, so it must be
correct for outlines with concave corners (finger joints).
`mirror(shape, across: Axis | Plane)` (an axis means the plane through it standing along
Z), `move(shape, vector)`, `rotate(shape, angle, *, about: Point | Axis = ORIGIN)` (a
point means the Z axis through it), `pattern(shape, count, step: Vector | Turn)` -> tuple of
shapes with `-1`, `-2` ... appended to labels, `grid(shape, (across, up), (along, over))`,
`name(node, to)`,
`chamfer(wire, edge_label_or_index, d)`. A solid records a move rather than doing one:
`moved` wraps its node in `Moved`, so a reflection is the one transform in the tree that
is not rigid.
`offset(wire_or_face, d)` takes a bare wire only in a plane parallel to XY, because
nothing says which plane a wire is on; a face carries its own and is offset in it.

**One pattern verb, two kinds of step, and a grid of its own.** A pattern is a step repeated,
so a `Turn(axis, angle)` steps round an axis exactly as a `Vector` steps along a line - eight
crush ribs round a magnet pocket, which is what the polar form is actually for here. A grid
is *not* a second pattern nested inside the first: nesting them would name the second copy of
the second row `foot-1-1`, and a ref that reads like a mistake is one. `grid` lays its copies
row by row along the first step and stacks the rows along the second, and numbers them in one
flat run - `foot-1` to `foot-12` for a four by three - which keeps the `-1`/`-2` rule intact
and the refs unique. Its users are the bin's feet and the lid's four insert bosses.

Selectors (predicates over a face's or wire's edges; return tuples):
`edges(wire_or_face, *, direction=None, near_point=None, label=None, tol=TOL)`,
`edge(...)` (exactly one, raises `LookupError` on zero or many).

Queries: `bbox(shape) -> BBox` (two-dimensional, because that is what a sheet and a bed
are; a solid is the XY shadow of its bounds), `bounds(shape) -> Bounds` in `topology`
(x0, y0, z0, x1, y1, z1 - exact for a face, an extrusion, a full revolve, a hull, a move
and a union, and conservative under a `Difference` (the base's bound), an `Intersection`
(the first operand's) and a partial revolve (the whole turn), because a bound that is too
big never passes a part that will not fit), `area(face)`, `perimeter(wire)`,
`centroid(face)`, `is_ccw(wire)`, `contains(face, point)`, `text_width(text,
size) -> float` (the same 0.6-of-cap-height-per-character estimate
`library/gridfinity.py` uses to centre a drawer label, generalised so any
script can centre an engraving without knowing the estimate itself).

Text: `Text(text, at, size, label=None)` lives in `model.py` - it is named, not
cut - and a `Part` carries `engravings: tuple[Engraving, ...] = ()`, where an
`Engraving` is a `Wire | Text`. Engravings are drawn, not cut, and never
kerf-compensated. `moved_part(part, t)` in `model.py` moves a part's shape and its
engravings together, which is the one thing `nest` and `export` both need.

## joints.py [done]

Finger joints for boxes cut from sheet stock:

- An edge joint is a *partition*: an odd number `n >= 3` of equal segments
  along a parent length. Even-indexed segments are material on the female
  panel; odd-indexed are where the male panel's tabs land.
- Female edge: notches of depth `t` cut into the panel's nominal rectangle at
  odd segments. Male edge: tabs of depth `t` grown outward at the parent's odd
  segments, expressed in the panel's coordinates through an `offset` so an
  inset panel (a box bottom) lines up with a wall that spans the full width.
- Corner rule: every partition starts and ends with material, so the corner
  cube of each box edge is owned by exactly one panel. A tab that would reach a
  panel corner is refused - `male_intervals` raises `ValueError`.
- `open_box(*, w, d, h, t, finger) -> Box` returns a `NamedTuple` of the five
  labelled faces - `front`, `back`, `side_left`, `side_right`, `bottom`, labelled
  `side-left` and `side-right` where a ref needs the hyphen - with edges labelled
  `bottom`, `right`, `top`, `left`. The dimensions are keyword-only: two of the five
  faces are twins of the other two, and nothing about the order `w, d, h` is written
  in says which is which. Tested by virtually assembling the box and sampling every
  joint strip: each point is material on exactly one panel.

## nest.py and export.py [done]

`nest(parts, bed) -> (sheets, warnings)` where `Bed(w, h, margin=3.0, gap=3.0)` is
the stock: kerf-offset every face by `stock.kerf / 2` (outlines out, holes in),
shelf-pack tallest first, rotate a part a quarter turn only when it does not grow
the shelf, one sheet series per stock thickness. Parts too big for the bed are
reported as warnings, never dropped silently. A `Placement` carries the `part` the
script made and the `placed` part that gets cut - kerf-compensated and translated
into sheet coordinates - so nesting knows nothing about SVG and the arrow runs
`nest -> export` only.

`face_paths(face, prefix) -> tuple[SvgPath, ...]` where each path carries `ref`,
`kind` (`outer` | `hole` | `engrave`) and a `d` string in mm; `part_paths` and
`part_texts` do the same for a whole part, and `export` calls them on
`placement.placed`. `part_svg(part)`, `sheet_svg(sheet, title)` and
`sheet_dxf(sheet)` produce text; SVG paths carry `data-ref` attributes. Y is
flipped in SVG so the workpiece reads origin bottom-left. DXF comes off the same
topology the SVG does - every wire walked once, arcs flattened to chords - rather
than out of a re-read of the path strings.

## The print domain [new] - fasteners.py, model's records, features' holes, library/print.py

What makes a printed part a printed part is four things - a fastener table, a fit, an
orientation and a material - and the layer graph decides where each of them lives. The rule
is **records low, numbers high**: the records a part carries sit in `model.py` beside
`Stock`, the geometry that builds with them sits in `features.py`, above the `ops.py` that holds
`slot` and `rounded_rect`, and every *number* - the filament profiles, the fit table, the beds - sits
in `library/print.py`, which is the one module a script imports to get the lot.

`fasteners.py` is the bottom of the graph beside `geometry.py`: **it imports nothing at
all.** One frozen `Screw` per size (`M2 M2_5 M3 M4 M5 M6 M8`) carrying the three ISO 273
clearance holes, the metal tap drill, the self-tap-into-plastic drill, socket/button/flat
head diameter and height, counterbore diameter and depth, countersink diameter and angle,
hex nut across-flats and thickness, and the nut-trap depth. Beside them the parts that are
not screws, because none of them is a fit of one: `Insert` (`INSERT_M3`, `INSERT_M4`,
`INSERT_M5`) keyed on the *insert's* own outside diameter, `NutTrap` with its lead-in, and
`Magnet` with gridfinity-rebuilt's 6x2 pocket and crush ribs. `Fit` is the six-armed enum -
`INTERFERENCE PRESS SNUG SLIDE CLEARANCE LOOSE` - and `bore(screw, fit)` is a `match` over
it ending in `assert_never`, each arm reading one column of the record, so a seventh fit
cannot be added without a column to read it from and a column cannot be dropped without a
fit losing its answer. A test asserts exactly that: six fits, six *different* columns, all
of them the screw's own.

**Every number in that table is the nominal metal one** - the clearance holes are ISO's,
the tap drill cuts a thread in steel - and the printed compensation is applied on top of it
by the material. That is why the table is its own layer: the screw does not change when the
filament does.

`library/print.py` holds the material profiles. A `Material` is `name`, `shrink`,
`hole_compensation`, `foot` (first-layer spread), `min_wall`, `max_overhang` (radians),
`bridge_max`, `layer` and the per-fit clearance table; `PLA`, `PETG` and `ASA` fill it in
with the review's figures for a 0.4 mm nozzle at 0.2 mm layers. `clearance(fit, material)`
is **public and per side**, which was the maker review's decisive point: a lid lip, a hinge
bore and a nut trap all need the number and none of them goes through `hole()`. `Volume`
and `H2D` (350 x 320 x 325) are the build volume a check measures against.

A printed part carries `Printed(material, orient)` where `Orient(up=Z, bed_face=None)` is
the build direction and, optionally, the ref of the face on the bed. `Part.stock` is
`Stock | Printed` - see **model.py** below.

Printable-hole geometry is in `features.py`, because `hole` builds with it:

- `teardrop(d, at=ORIGIN, *, up, label=None) -> Wire` - the upper arc replaced by two lines
  tangent at the points a quarter turn either side of `up`, meeting at an apex `r*sqrt(2)`
  above the centre, so nothing on it exceeds 45 degrees. `up` is read in the plane the wire
  is drawn on. A test measures every chord of the flattened wire and fails at 45.000001.
- `bridge_steps(bore_d, outer_d, layers, layer_h, *, at=ORIGIN) -> tuple[Wire, ...]` -
  gridfinity-rebuilt's `make_hole_printable`: rectangles `bore_d` by `outer_d`, each turned
  a quarter turn from the last, that a slicer can bridge onto. They come back drawn flat,
  because a wire carrying its own height would be lifted twice; the caller raises the plane
  it fills each on by `layer_h`.
- `foot_chamfer(solid, d)` - the elephant's foot, cut once at the bottom rather than
  sprinkled through the sketch: the wedge between the footprint and the footprint inset by
  `d` is taken away under the label `foot`.
- `Top` is `AUTO | ROUND | TEARDROP | BRIDGE` and `printable_top(top, *, axis, diameter,
  printed, round_matters)` is the review's rule in one place. Let theta be the angle between
  the hole's axis and `up`: under 30 degrees the bore is a stack of circles and stays round;
  at or over it, a diameter up to 4 mm still needs nothing, up to the material's
  `bridge_max` a bridged top is available to a hole that has to stay round, and past that
  only a teardrop will do. `Top.AUTO` with no orientation raises **"this part has no print
  orientation, so top=Top.AUTO cannot tell which way is up"**.

```python
hole(subject: Shape, at, *, on=XY, screw=None, diameter=None, insert=None,
     fit=Fit.CLEARANCE, depth=None, countersink=False, counterbore=False,
     angle=COUNTERSINK, top=Top.AUTO, printed=None, label) -> Shape
```

One verb over the closed union, a `match` ending in `assert_never`, and the subject's own
type back. On a `Face` it cuts a circle - a laser part, and `hole(box.side_left, Point(40,
25), diameter=20, label="hole")` is exactly the `cut(..., circle(...))` the README always
wrote. On a `Solid` it cuts a bore into `on`, whose normal points out of the material, with
`at` read in that plane's own frame like every other sketch. **Exactly one of `screw`,
`insert` and `diameter`** says how wide, and giving none or two is a documented `ValueError`;
the diameter is `bore(screw, fit)`, the insert's own bore, or the number given, plus the
material's `hole_compensation` when `printed` is handed in. `depth=None` is through, sized
off the body's own `bounds`. `countersink` and `counterbore` build the head's recess from
the screw's table - a cone at `angle` (90 degrees, the ISO one, and what a printer can hold)
or a flat-bottomed bore - and land under `<label>/head`; the bridging steps land under
`<label>/bridge-1`. A face refuses all of those by name rather than ignoring them, because
a cutter has one depth and cannot sink a head.

`printed=` is the one argument that makes `features` print-aware, and it is the same record the
part will carry, so a hole and its part cannot disagree about the filament. A body is a
thing to be printed, so `Top.AUTO` on one asks for it; `top=Top.ROUND` is how a bore says it
does not care.

## checks.py [new] - what has to be true, as records rather than raises

```python
class Severity(StrEnum): ERROR; WARNING; UNCHECKED
@dataclass(frozen=True, slots=True)
class Violation: check: str; message: str; severity: Severity
                 refs: tuple[Ref, ...] = (); line: int | None = None

fits(shape, volume) -> Violation | None
clearance_between(a, b, least, *, kernel) -> Violation | None
wall(solid, least, *, kernel) -> Violation | None
overhangs(solid, orient, material, *, kernel) -> Violation | None
```

Pure functions that take the kernel as a **parameter**, exactly as `kernel.py` takes no
implementation. Two tiers, and the signature says which: `fits` reads the tree's own
`bounds` and runs anywhere, including a browser with no modeller; the other three measure a
built body and, handed `kernel=None`, answer `Severity.UNCHECKED` rather than passing. That
distinction is the point - "I could not tell" is not "it is fine", and a check that quietly
passed in the browser and failed on the desk would be worse than no check at all.

`wall` is measured on the mesh: from the middle of every triangle, straight into the
material, to the first surface facing back. The smallest of those is the thinnest wall and
the ref it comes back with is the face it was measured from. Every triangle is tried against
every other, which is quadratic, and is why it is a check a maker asks for rather than one
that runs by itself. `overhangs` classifies each triangle's normal against `up` - a surface
leaning theta from the build direction has a normal theta off the horizontal - and leaves
out everything within one layer of the lowest point, because the first layer is not an
overhang, it is what the part stands on.

**Two slacks, both named, both because a measurement off a mesh is not exact arithmetic.**
A mesh's vertices are single precision, so two faces drawn 0.10 mm apart measure 0.099998
and a surface drawn at exactly 45 degrees measures 45.00001: compared against `TOL` - a
millimetre tolerance, 1e-6 - a part that is right fails. `clearance_between` allows
`_GAP_SLACK` of a thousandth of a millimetre and `overhangs` allows `_ANGLE_SLACK` of a
hundredth of a degree. No printer holds either, so nothing real is hidden, and the geometry a
maker actually draws at the limit - a chamfer, a teardrop's flank, a countersink's cone -
passes deterministically rather than on the day.

`script.run` injects `check_fits`, `check_clearance`, `check_clearance_within`,
`check_clearance_through`, `check_contact`, `check_wall` and
`check_overhangs` as
per-run closures over the notebook and this run's kernel, exactly as `show` is a closure
over the notebook: they record a `Violation` **with the line number of the script's
own frame** and return it. `require(violation)` is how a script turns one into a stopped
run; it raises for an `ERROR` or a `WARNING` and lets `UNCHECKED` through, or a script would
refuse to draw itself in the one place it most needs to. A failed check never aborts a run
by itself: the geometry, the refs and the sheets all still come back, and the violation sits
beside them in `scene["violations"]`, the way `nest` already reports a part too big for the
bed as a warning.

## kernel.py [new] and adapters/ [new] - the seam a solid modeller is plugged into

```python
@dataclass(frozen=True, slots=True)
class Mesh:
    vertices: tuple[float, ...]      # x, y, z per vertex
    triangles: tuple[int, ...]       # three vertex indices per triangle
    refs: tuple[Ref | None, ...]     # one per *triangle*

class Kernel(Protocol):
    def mesh(self, solid: Solid) -> Mesh: ...
    def volume(self, solid: Solid) -> float: ...
    def min_gap(self, a: Solid, b: Solid, *, upto: float) -> float: ...
```

Three methods, because three are what the package asks for: what is drawn and printed, what
is measured, and how close two bodies come. `Mesh` is a transport record - flat tuples,
because that is what a renderer, an STL writer and a JSON scene all want - and is the one
place besides `script._Recorder` where lists are filled inside a single function and frozen
at the end of it. `refs` runs per triangle, and is the whole reason the mesh is built here
rather than in the viewer: a click on a triangle is a click on `plate/top`. It is `None`
where a triangle belongs to no named face, which is what a hull leaves behind.

**No module under `src/bench` imports a modeller, or anything only Pyodide has.** That is a
pypeeker row and a test of its own in `tests/unit/test_layer_graph.py`, and it is what keeps
`import bench` free of an install.

**There is one kernel, and it is Python.** `adapters/browser.py`'s `JsKernel` walks the tree
with a `match` ending in `assert_never` and drives Manifold's WASM build - `manifold-3d` from
npm, loaded in the same worker as Pyodide - by handle, **synchronously**. There is no
`manifold3d` wheel for Pyodide and there will not be one, so Manifold stays in JavaScript; but
everything decided about a body is decided here, and `web/src/modeller.ts` is a table of
handles that forwards calls and does no geometry. `bench.meshing` holds the decisions that
need no modeller at all, as pure functions over flat buffers. The part that matters is how a
face keeps its name:

- **The identity of a face is the pair `(run_original_id, face_id)`, never `face_id` alone.**
  An original id names a whole primitive; auto face ids are source-triangle indices, so a
  hand-picked face id collides silently with any primitive holding more triangles than that.
- Every swept primitive is meshed, given one reserved original id and a face id per triangle,
  and rebuilt *before* it meets a boolean - a face id can only be written on the way in.
  Which face a source triangle lies on is decided geometrically in `meshing`: by the
  triangle's normal for an extrusion's cap, by its position for a revolve's, and by the
  profile segment underneath it for a side. `topology.profile_rings` says which segment
  belongs to which face, and `topology.profile_frame` is where the result goes.
- Booleans keep every operand's tags, which is what makes `plate/pocket/bottom` a thing the
  mesh can answer to. `Moved` is applied after tagging, and the tags ride along.
- **A hull destroys identity**, so every triangle of one carries the enclosing solid's own
  ref and nothing under it. The naming rule already said a `Hull` names nothing beneath it;
  this is the same fact on the other side of the seam, and a test asserts them together.

**What crosses the bridge.** Handles, single numbers, and bulk numbers as buffers - an
`array.array` goes out as a view onto Python's memory and a mesh comes back as Manifold's own
typed arrays - so the number of calls grows with the tree and never with the triangles. One
trap is kept on the Python side: `Manifold.transform` takes a **column-major 4 by 4** in the JS
bindings, and handed the twelve row-major numbers of a `Transform` it neither throws nor
complains, it builds the wrong body; `meshing.column_major` writes the sixteen it wants. A
call the modeller refuses raises Pyodide's `JsException`, which the worker hands `JsKernel` as
`refused` so the adapter imports nothing Pyodide-only, and it becomes a `ValueError` - an
error scene on the script's own line. Every kernel call ends by freeing what it made, because
WASM memory is not garbage-collected.

The kernel is measured where it runs: `tests/adapter/` boots Pyodide under Node with the
app's own `modeller.ts` and Manifold WASM (`tools/stack.py`) and checks what comes back
against arithmetic done by hand. `tools/kernel_timing.py` times a run the same way.

## telemetry.py [new] - logs and spans, in the standards a collector reads

Nothing here names a vendor. **Logs** are `logging`, one logger per module under `bench`, and
importing the package configures none of it - no handler, no level, nothing at import at
all: a library's records go where a host routes them, and the worker is the host that does;
structured fields ride in `extra` under one key, named the
OpenTelemetry way (`bench.parts`, `code.lineno`). **Spans** are `Span(name, start, duration,
attributes)` - wall-clock start, OpenTelemetry-style names and attributes, and `error.type`
on a span whose work raised - handed to a `Tracer` injected into `run()` and `JsKernel` the
way a kernel is. `SILENT`, the default, keeps nothing.

What is timed: `bench.run` around everything; `bench.script.compile` and `bench.script.exec`;
every `bench.check.*`; `bench.scene.nest`, a `bench.scene.mesh` per part, `bench.stage.layout`
and `bench.scene.files`; and in the kernel every `bench.kernel.mesh|volume|min_gap`, with
`bench.mesh.triangles` on a mesh. One `bench.script` record per run says how it ended; a
modeller's refusal is a warning from `bench.adapters.browser`.

In the app, `bench/worker.py`'s `start` - the one function the browser's worker calls into
Python - wires both to `web/src/telemetry.ts`: a handler on `bench` and a tracer that call two
plain functions. The worker posts every record to the page with its own
(`bench.boot.*`, `bench.worker.*`). The page adds `bench.run.roundtrip` - asking to answering,
with `bench.run` inside it - and
`bench.view.geometry` for the draw, and hands everything to its sinks: the console, levelled
by `bench.log` in localStorage, and User Timing, where the Performance panel draws the spans
and where Datadog RUM, Grafana Faro or OpenTelemetry's web instrumentation already look. A
collector is one more `attach` in `main.ts`. Times are milliseconds since the epoch, so a span
timed in the worker lands in the right place on the page's timeline.

Every answer that crosses is an object carrying either a result or an `error`, so a
modeller that refused arrives as a `ValueError` on the script's own line rather than as a
JavaScript exception surfacing through the foreign-function boundary.

## export.py [new] - what a printer reads

`stl(mesh) -> bytes` is binary STL: eighty bytes of header, a triangle count, fifty bytes a
triangle, little-endian floats in millimetres. The facet normal is computed from the winding
rather than trusted, so it can never disagree with the corners beside it. Names do not
survive - an STL is a bag of triangles.

`three_mf(objects) -> bytes` takes `(name, mesh)` pairs and writes a 3MF package: a zip of
exactly `[Content_Types].xml`, `_rels/.rels` and `3D/3dmodel.model`, the model carrying
`unit="millimeter"`, one `<object>` per part with its name, and one `<build><item>` each.
Nothing else goes in - in particular **no `project_settings.config` and no
`slice_info.config`**: those are one slicer's settings for one printer, and writing them
means telling a maker how to print a thing we were only asked to describe. Every entry
carries one fixed date, so the same model is always the same bytes.

Both are pure functions returning bytes. Writing files is `script`'s job, or a browser's.

## script.py [done] - the runtime the browser calls

The user's script is ordinary Python that uses `bench`. It declares its settings as one
frozen dataclass, builds from them in a function, and ends by calling `show(build)`:

```python
from dataclasses import dataclass

from bench import *
from bench.library import gridfinity


@dataclass(frozen=True, slots=True, kw_only=True)
class Cabinet:
    units_x: int = knob(4, min=1, max=7, label="Units across")
    height_u: int = knob(3, min=1, max=12)
    baseplate: bool = True
    kerf: float = knob(0.25, step=0.01)


def build(p: Cabinet) -> Build:
    spec = gridfinity.Spec(units_x=p.units_x, units_y=2, height_u=p.height_u, drawers=6,
                           kerf=p.kerf, baseplate=p.baseplate)
    return gridfinity.cabinet(spec)


show(build)
```

The parameters decision (`decision-2` in `backlog/decisions/`) says why this replaced the `param("units_x", 4, ...)` calls a script
used to make one at a time.

`run(source, overrides=frozendict(), *, bed=Bed(320.0, 320.0), extras=frozendict(),
kernel=None) -> Scene` executes the script in a fresh namespace. `show` is built per
run as a closure over that run's notebook and injected into the namespace by name, so
it is not `bench.__all__`'s to export and `from bench import *` cannot replace
it; `ref` is injected too and is `model.ref`. `bed` is the stock everything nests
onto, margins and all. `extras` binds modules by name for a host with scripts already
written - the browser worker passes `{"gridfinity": gridfinity}` so a saved script
that never imported it still runs - but a script of one's own imports what it uses.

`kernel` is a `Kernel` or nothing, injected for the same reason `show` is: this
module names the protocol and never imports an implementation. With one, a part whose shape
is a `Solid` gains a `mesh` of triangles that each know their face's ref, a `<part>.stl`
among the files, and - once there is at least one body - one `<assembly>.3mf` holding all of
them named. Without one, `mesh` is `None` and everything else - refs, parameters, cut
sheets, and the `tree` that says how each body is built - is exactly what it was.

`run` never raises for user errors: syntax errors, exceptions, and a missing or
repeated `show()` come back as `{"ok": false, "error": {...}, "stdout": str, "stderr": str}`
with a line number. The two streams are on that scene as much as on a good one: a script
prints its way to the line that breaks, so the run that failed is the one whose output is
worth the most. Both are empty for a syntax error, which happens before anything ran.
A setting's kind is its field's type (`int`, `float`, `bool`, `str`, or a `Literal` of one
of those for a menu). A value outside a `knob`'s `min` and `max` is held at the nearer end,
and one its field cannot read stops the run at the `show(build)` line, naming the field. `show` takes a closed union - an `Assembly`, a `Part`,
a tuple of parts, or a `Build` - or a one-argument function annotated with a dataclass, and
refuses anything else by name.

Scene (JSON-shaped dict; the shapes are `scene.py`'s, each a `TypedDict(closed=True)`):

```
{
  "ok": true,
  "params": [{"name", "label", "kind", "default", "min"?, "max"?, "step"?, "choices"?}],
  "values": {name: value},
  "parts": [{
     "ref", "label", "qty", "stock": {"thickness", "material", "kerf"}, "process",
     "bbox": [x0, y0, x1, y1],
     "mesh": {"positions": [...], "ref_index": [...], "refs": [...]} | null,
                                           # a laser part's plate, or a printed part's body
     "marks": {"segments": [...], "ref_index": [...], "refs": [...]} | null,
                                           # engraved wires on a plate, as line segments
     "lettering": [{"text", "ref", "corners": [12 numbers]}]
  }],
  "stage": {"bounds": [x0, y0, z0, x1, y1, z1], "grid": {"size", "divisions", "centre"}},
  "summary": {"parts", "sheets", "errors", "warnings", "error_line", "solid", "unbuilt"},
  "refs": [ref, ...],
  "sheets": [{"name", "thickness", "svg", "preview", "parts": [ref, ...]}],
                                         # preview: the same drawing, lines a thumbnail shows
  "files": {filename: content},          # sheet SVG/DXF, one SVG per part, a build's own,
                                         # one STL per printed body, and one 3MF
                                         # holding every one of them, named
  "violations": [{"check", "message", "severity", "refs": [ref, ...], "line"}],
  "warnings": [str], "stdout": str, "stderr": str
}
```

`violations` is what the script's own checks found, each with the line that asked for it -
a warning with somewhere to point. `stdout` and `stderr` are what the script printed on
each stream, kept apart rather than woven together: the order between the two is lost, and
what that buys is a panel that can say which is which. `stderr` is here because there is
nowhere else for it to go - a script that writes to it, or calls `warnings.warn`, is saying
something it did not expect to have to say, and in a browser the alternative to showing it
is losing it. A printed part's `stock` still carries the three fields
the app has always read: the filament's name, and zeroes for a thickness and a kerf it does
not have. `process` is what tells the two apart.

A scene is JSON, so every file is a string. A binary one - today the STLs and the 3MF,
which is to say everything a printer reads and nothing a cutter does - is its bytes in
base64, and `transport.binary(filename)` is the one place that says which strings have to be
decoded before they are written to disk.

The refs in `mesh` carry the part's own label, so they read the same as the scene's `refs`
table. A kernel is handed the bare solid and answers `boss/top`; the scene says
`plate/boss/top`.

## library/gridfinity.py [done]

`Spec(units_x=4, units_y=2, height_u=3, drawers=6, columns=1, drawer_t=3.0,
carcass_t=6.0, kerf=0.25, finger=12.0, baseplate=True, labels=(), ...)` is the
frozen parameter record and `cabinet(spec) -> Build` builds it entirely from `ops`,
`solids` and `joints`. A `Build` is `model.py`'s, not this module's: the `assembly` (one part
per *distinct* panel), a `quantities` table of ref to count, and `files`, which here
holds `baseplate.scad` when the spec asks for a baseplate. `derive(spec) -> Dims` is
the arithmetic and `validate(spec)` the opinions.

Fit rules: drawer interior = 42 x units + 1 mm; interior height = 7 x height_u
+ 4.4 mm lip + 3 mm clearance (+ 4.65 mm with a baseplate); pitch = carcass_t +
drawer height + 1.5 mm gap; runners are strips with tabs through slots in the
cabinet sides; the right side is the left flipped, so its slots are mirrored.
Every part and every meaningful wire is labelled (`drawer-front-3/pull`,
`cabinet-side-left/slot-2`). Also `baseplate_scad(units_x, units_y,
floor_t=0.0) -> str`.

## library/gridfinity3d.py [new] - the printed bin

The same `Spec` / `derive` / `validate` / build triple as the cabinet, for the object the
whole ecosystem is built on: `bin_(spec) -> Build` with one printed part in it. The baseplate
is the other half of the module and is deliberately not here yet.

```python
Spec(units_x=2, units_y=1, height=Units(3), lip=True, wall=1.2, floor=1.2,
     divisions=(1, 1), scoop=0.0, label_tab=Tab.NONE, tab_width=None, tab_depth=15.85,
     tab_angle=radians(45), magnets=False, screws=False, magnet=MAGNET_6X2, screw=M3,
     fit=Fit.CLEARANCE, material=PLA)
```

**Height is a union of the four things it means**, because makers use all four and offering
one is the commonest complaint about every generator: `Units(n)` of 7 mm excluding the lip,
`Internal(mm)` of usable depth, `External(mm)` excluding the lip, `ExternalWithLip(mm)`.
`derive` matches over them and ends in `assert_never`.

**The constants are the standard's own**: `GRID = 42`, `BASE_TOP = 41.5` (the half
millimetre that lets a bin drop into a baseplate, a quarter a side), `BASE_PROFILE =
((0, 0), (0.8, 0.8), (0.8, 2.6), (2.95, 4.75))`, `BASE_HEIGHT = 4.75`, `CORNER_R = 3.75`,
`MAGNET_AT = 13`. They are public, because a baseplate and a back-plate will want them.

**The stacking lip is the base profile plus a fit, not a second table.** A bin's top is a
baseplate pocket for the bin above and a baseplate pocket is the base with clearance round
it, so the lip's void is `BASE_PROFILE` widened by `clearance(spec.fit, spec.material)` a
side - and, because every flank of it is at 45 degrees, shortened by the same amount, which
is why a 4.75 mm foot drops into a 4.45 mm void. The standard's own lip is 2.6 by 4.4, which
is this rule at 0.35 mm. That is what makes `fit` a real parameter instead of a decoration,
and it is measured in the adapter layer rather than asserted: a second bin one body height up
clears the first everywhere.

Everything else is the vocabulary doing its job: each foot is a `hull` of the four slices of
`BASE_PROFILE` and the feet are a `grid`; the mouth of each compartment is flared back to
meet the lip at 45 degrees with a `hull` of two rects, because a ledge with nothing under it
is an overhang and a flare is not; the scoop is a square with a quarter circle taken out of
it, swept, which is the fillet this kernel cannot make; the label tab is a wedge whose
underside is `tab_angle` (45 by default, where the standard's 36 leaves a 54 degree overhang
the slicer has to bridge); a magnet pocket is cut from underneath with `bridge_steps` over it
so the slicer has something straight to span, and its crush ribs are a `pattern` with a
`Turn` in it. `validate` names the first parameter that will not print - `wall` under the
material's own `min_wall`, `divisions` that close a compartment up, a `height` that leaves
less inside than the flare under its own mouth takes.

## web/ [done]

Vite + TypeScript, no framework. Pyodide 315.0.0-alpha.2 from npm (Python
3.15), self-hosted: a prebuild script copies `node_modules/pyodide/{pyodide.mjs,
pyodide.asm.mjs,pyodide.asm.wasm,python_stdlib.zip,pyodide-lock.json}` into
`public/pyodide/`. Another prebuild script bundles `src/bench/**/*.py` into a
generated TS module; the worker writes them into Pyodide's FS.

Manifold 3.5.3 from npm, self-hosted the same way: `scripts/copy-manifold.mjs` copies
`manifold.js` and `manifold.wasm` into `public/manifold/`, and the worker loads it beside
Pyodide and hands it to `run` as the kernel.

Layout: left, a CodeMirror 6 editor (`@codemirror/lang-python`) with the
script; right, the viewer and below it a parameters panel generated from `scene.params`. A
status bar shows run state and errors (with line highlighted in the editor).

The viewer is **one view of every part** (three.js). A laser part is drawn as the plate it
is cut from, swept in Python (`bench.plates`) to its stock's thickness with its engravings
on top, and a printed part as the body the kernel built; they lie in wrapping rows on one
stage. The flat drawing is an export, not a view: what a cutter reads is the sheet SVG and
DXF, and the Export menu shows each sheet as a thumbnail of that same file. A plate is swept
here rather than by the kernel because its names are settled already - a kernel calls a
wall `side-3`, and a plate's wall answers to the ref its cut path carries - and because a
laser part then needs no modeller to be drawn.

`three.js` is behind a dynamic import, fetched while the first scene is on its way, so the
editor's first paint does not wait for a renderer.

Interactions that define the product:
- Edit -> debounce 300 ms -> `run` in the worker -> re-render. Params panel
  edits re-run with overrides without touching the source.
- Click a face of a plate or a solid, an engraved line or a line of lettering: it
  highlights and the status bar shows its ref, and `Ctrl/Cmd+I` (and an "Insert ref"
  button) inserts `ref("...")` at the editor cursor. Picking is a three.js raycast against
  the geometry built from the scene's own mesh, indexed by the hit triangle -
  `Manifold.rayCast` was measured and is not usable for this - which is why that geometry
  is non-indexed: a triangle index is a ref index, a highlighted face cannot bleed colour
  into its neighbours, and the facets shade flat.
- Cursor inside a `ref("...")` string in the editor highlights that geometry
  in the viewer; hover over geometry shows its ref as a tooltip.
- Downloads: per-sheet SVG/DXF; one `.stl` per body and one `.3mf` for all of them; any
  extra files; and an "everything" zip. The two the printer reads are bytes carried as
  base64 - `transport.binary(name)` is the one place that says which - and are decoded on the
  way out, in the archive as well as on their own.
- Violations: what the checks found, with severity, message, refs and the line that asked.
  An `error` marks that line in the editor exactly as a raised exception does. `UNCHECKED`
  reads **not checked**, never as a pass - the whole point of the third severity.
- Projects are directories on the host that serves the page (decision-9), under the root
  `$BENCH_PROJECTS` names: each its scripts and one `bench.toml` - `[project] entry`, the
  values as the TOML `tools/build.py` reads, the `[reference]` placement, and whatever else a
  newer bench wrote there, kept - shown as a tab beside the script and written on every panel
  edit with what the run built (decision-3). Which project, and which of its scripts, a browser
  has open is that browser's own, and one tab at a time writes a project: it holds the
  project's write lease, and every other tab on it reads - runs, exports, turns knobs that are
  not kept - and is told whose it is, and can take it over (task-47). The Project container is a switcher and a tree (task-48):
  one line naming the open project, behind which the others are listed with New (starting as
  `templates/untitled.py`), Open… from disk and Download (its scripts and a `.toml` in one
  archive); and under it the open project's own files - `bench.toml`, its scripts, the meshes
  dropped into it - each opening in the editor group on a click, with rename, duplicate and
  delete on the row they act on. A delete moves a file or a whole directory into `.trash/`
  under the root and says so first; a browser holding projects from before is asked, once,
  whether to write them to the host.
  An examples menu opens bundled scripts, each as a file of its own so it never
  replaces the one being written, from `examples/*.py` at the repository root - the prebuild script bundles the directory,
  so the five printed parts appear in the menu beside the two flat ones with nothing in
  `web/` changed.
- Keyboard: `Ctrl/Cmd+Enter` runs now.

Theme: light and dark via `prefers-color-scheme`; system font; the view is a light or dark
gradient with parts in grey and engravings in ink, and the sheet thumbnails keep the cut
files' white with red cut lines and blue engrave lines.

## Testing

Four layers under `tests/`, one directory and one marker each, written outside-in:
`unit/` is one module, pure, one file per module; `functional/` is several modules through
the public API, still pure; `adapter/` is a real boundary with nothing standing in for it -
the scene JSON read back against the TypedDicts it is typed from, and `bench` inside the
Pyodide runtime the app ships, driven by Node; `e2e/` is the built app in a browser, which
the default run deselects and `-m e2e` selects. No doubles anywhere: `tests/conftest.py`
parses every `*.py` under `tests/` with `ast` - not only `test_*` files and `conftest.py`,
so a helper module used from more than one test file is read too - and exits the session if
one imports `unittest`, `unittest.mock` or the standalone `mock` backport, or if any function
in it takes a `monkeypatch` or `mocker` argument; a plain text search over the same files
also flags `pytest.MonkeyPatch(` constructed directly and `importlib.import_module(`, which
would otherwise load a real module as an unchecked stand-in. At the world boundary a fake
asserting on state would be allowed, a mock never - and this guard is a tripwire, not a
proof: it is mechanical, and it does not read what a fake actually does once it is a class
rather than an import. `tests/support.py` holds the plain data builders shared between test
files (no doubles of its own) so the guard has something to scan there too.
Every script under `examples/` is itself a test twice over: `tests/functional/test_examples.py`
runs each one the way the browser does - no kernel - and fails on a warning, an error-severity
violation or a missing part, and `tests/adapter/test_examples_measured.py` runs each one
through the real modeller and measures the mesh that comes back **through its refs**, since a
triangle knows the name of the face it lies on. A new example has to be listed in the first of
those or the suite says so. `tools/check.py`
runs the default suite twice in one process, popping every `bench` and `bench.*` module out
of `sys.modules` between the runs - and every test module that already imported names out of
them, so nothing is left comparing the second run's fresh instances against the first run's
classes - so the second run imports the package from scratch: that catches both a global the
first run left dirty and anything a module does once at import time, which only a fresh
import exercises again. `tests/unit/test_layer_graph.py` gates the layer graph:
every bench-to-bench import must be in that module's allow-list under
`[tool.pypeeker.import-boundaries]`, and a new module under `src/bench` fails the test until
it is declared there. It also gates the one rule that table cannot state, because it is about
the outside world rather than about bench: **no module under `src/bench` imports a solid
modeller or anything only Pyodide has**, and `kernel.py` imports no adapter. The adapter
layer is where the real modeller is exercised - `tests/adapter/test_kernel.py` and
`test_examples_measured.py`, marked `adapter`, boot Pyodide under Node with the app's own
`modeller.ts` and Manifold WASM through `tools/stack.py` - and they skip, with the reason,
only where `node` or `web/node_modules` is missing. `web/` is a shell, tested through `e2e/`
only; its screenshots land in
`web/e2e/out/`.

## Known limits

What bench deliberately does not do yet. None of these is a bug to be filed; each is a
line drawn at the edge of what is built so far.

- **A body is built only where a kernel is handed in.** With no kernel a run still yields
  every ref of a body and its whole recipe, and draws no path for it - `export` returns
  nothing for a solid and `nest` passes over a printed part in silence rather than putting
  it on a sheet, because a recipe cannot be flattened onto a sheet. With one it also yields
  triangles, an STL and a 3MF, and the browser now has one, so a printed part is drawn.
  `bounds` is the only measurement the tree answers by itself, and it is conservative under
  a cut. There is still no assembled view - a `Build` is a cut list, not an arrangement in
  space, and `Placed.on` is carried but never used to pose anything; the view lays parts
  out in wrapping rows, flat on the floor, which is a cut list seen from above and not an
  assembly.
- **A mesh kernel has no circles.** Every arc and circle is cut into chords by one rule,
  `topology.CHORD` - 0.05 mm of sag, the step driven by the radius - so a boss of radius 8
  is a 29-gon and its footprint is 199.49 mm², not 201.06. That is what the DXF has always
  written and what the mesh, the STL and the browser now write too; it is a quarter of a
  percent, it is deliberate, and it is the same number everywhere rather than three
  different approximations. There is no analytic volume or area anywhere.
- **The kernel runs where Pyodide runs.** There is no `manifold3d` wheel for Pyodide, so the
  one kernel drives Manifold's WASM build in JavaScript and there is no desktop kernel: a
  script run in plain CPython builds no body, exactly as a run with no kernel does, and the
  adapter tests reach the modeller by booting Pyodide under Node. What that costs is speed on
  the naming loops - Python in WASM, not TypeScript on the JS engine - which
  `tools/kernel_timing.py` measures rather than guesses at.
- **The print domain describes a part; it does not lay one out or slice it.** There is no
  plate layout (the 3D `nest`), no filament, mass or time estimate, no text, and no
  assembled view. The 3MF carries one named object per part and places each one, which is
  what a slicer needs to open it - but no filament slots, no `Body`, no colours. `Part.stock` is `Stock | Printed` and not
  yet the closed `Plate | Filament | Billet`, so `Part.process` is still carried beside it.
- **`foot_chamfer` is a wedge cut from an extrusion, and its taper is a hull.** It needs a
  body whose footprint the tree knows, so it refuses anything that is not an extrusion
  (under any number of moves) by name; and because the taper between the footprint and its
  inset is a `loft`, which is a hull, it is exact for a convex footprint and leaves a
  re-entrant corner under-cut.
- **A bridged top needs somewhere to step out to.** `Top.BRIDGE` is the stepped square under
  a counterbore's floor, so `hole` builds it only for a counterbored hole; `Top.AUTO` never
  chooses it otherwise. A leaning hole with no counterbore gets a teardrop, which is the
  remedy that needs nothing but the profile.
- **`check_wall` is quadratic and `check_overhangs` reads triangles.** Both walk the mesh -
  the wall check tries every triangle against every other - so they are checks a script asks
  for at the sizes a part actually is, not something that runs on every keystroke. Neither
  can run at all without a kernel, and both say `unchecked` rather than passing when there
  is none. `check_fits` is the one that always runs.
- **The fit and material numbers are a starting point, not a measurement.** They come from
  one reviewer's sources for a 0.4 mm nozzle at 0.2 mm layers; nothing here has been
  measured on the machine in the room. They are data in one file so that measuring them
  changes one file.
- **No fillet or chamfer on a body.** Vertical edges are rounded by rounding the sketch
  and extruding it; there is no solid-level `fillet` or `chamfer`, and on the kernel this
  is heading for there never will be a general one - a fillet needs a name for an edge that
  did not exist until the boolean made it, and a CSG tree keeps no such name. What there is
  instead, and what the five example scripts use, is the shape a maker would have drawn
  anyway: a `hull` of stacked slices for a chamfered sweep, a `loft` from a wide footprint to
  a narrow one for a gusset where an ear meets a base, a loft-extrude-loft prism for a
  knuckle whose rims are eased, a quarter circle taken out of a square and swept for a
  scoop, `chamfer` on the sketch before it is extruded, and `foot_chamfer` for the one edge
  every printed part has. `loft` is a hull, and a hull loses every name under it.
- **The overhang check measures an angle, not a span.** A face that leans past the material's
  limit is reported however far it has to reach, so the half millimetre of floor that bridges
  the gap between a multi-unit bin's feet - the standard's own gap - reads as a 90 degree
  overhang, and so does the first millimetre of a hinge knuckle lying on the bed. Both are
  real overhangs and both print. Two of the five examples say in their own text why they do
  not call the check, rather than bending the part into a shape that would pass it.
- **The wall check measures to a knife edge.** `wall` casts a ray from the middle of every
  triangle, so a feature that comes to a point - a teardrop's apex, a label tab's tip - is
  nought millimetres thick and the check says so. It is the right answer to the question
  asked and the wrong question for those parts; the collar's example says as much where it
  leaves the check out.
- **No self-intersection repair in `offset`.** Each edge is offset and
  neighbours are mitred or bridged. An offset larger than a feature folds the
  wire through itself; nothing repairs it, and what notices is limited - `wire()`
  refuses a fold between two straight edges, an arc or circle eaten right down to
  nothing raises, and a fold involving a curve goes through unseen. Kerf is half a
  millimetre against features of tens, so
  it holds in practice - a kerf big enough to close a slot is the user's to
  avoid. An offset that collapses an arc surfaces as an error scene with no line
  number, because it happens in `nest` after the script has finished.
- **Text width is estimated.** A `Text` is a string, a place and a cap height,
  not glyph outlines: SVG and DXF hand the lettering to the machine's own font.
  Centring uses a flat 0.6 x size per character, so a long label in a
  proportional font will not sit exactly where the arithmetic says, and
  engraved text is drawn, never cut, and never kerf-compensated.
- **Single sheet size, one pass.** `nest` takes one `Bed`
  and shelf-packs tallest-first, left to right, bottom to top, turning a part a
  quarter turn only when that does not grow its shelf. It is a first-fit pass,
  not an optimiser: offcuts are not reused, a part is never revisited, and
  thickness series are independent. A rotated part's engraved text moves with it
  but is not turned with it.
- **The browser build lags CPython.** The app runs whatever Python Pyodide has
  published; a `bench` that needs a newer language feature than the pinned
  Pyodide ships cannot run in the browser until Pyodide catches up. The pin is
  exact (`pyodide@315.0.0-alpha.2`) and self-hosted, so the app never silently
  changes interpreter underneath a script.
- **One script, one `show`.** A run shows a single thing once; a person may
  keep many scripts, but one is open and runs at a time, there are no imports
  between them, and no way for a script to read a file. Scripts live in their project's
  directory on the host; a project may hold several, and the one open is the one that runs
  (task-50 is what lets one import another).
