# bench

Workshop objects as code. A small parametric vocabulary for describing parts
that get laser-cut, printed or machined, with names that survive regeneration
so a script can say `ref("drawer-3/front/pull")` and mean it every time.

Python 3.15, no dependencies. Building a 3D body needs a solid modeller, and the one bench
uses is Manifold's WASM build, driven from Python inside the browser app: `import bench`
never needs it, and a run with no kernel still yields every ref, parameter and cut sheet.

## Hello, box

A script is ordinary Python that builds some geometry and calls `show()`
once. This one cuts an open box with a hole in one side:

```python
from bench import *

box = open_box(w=120, d=80, h=50, t=3, finger=12.0)
side = cut(box.side_left, circle(10, Point(40, 25)), label=Label("hole"))
stock = Stock(3, "ply", kerf=0.25)
show(
    (
        part(Label("front"), box.front, stock, Process.LASER),
        part(Label("back"), box.back, stock, Process.LASER),
        part(Label("side-left"), side, stock, Process.LASER),
        part(Label("side-right"), box.side_right, stock, Process.LASER),
        part(Label("bottom"), box.bottom, stock, Process.LASER),
    )
)
```

That is `examples/box_with_hole.py` with its parameters hard-coded; run the
real thing (it also engraves a label on the front, sized with `text_width`)
from the browser's examples menu or with `bench.run` directly.

`show()` does not draw anything itself - it hands the browser (or `run()`) the
one assembly, part, tuple of parts or library `Build` the script is showing;
nesting the parts onto a sheet and writing the cut files (SVG and DXF) happens
afterwards, from that. Nesting needs a bed to nest onto: `run()` defaults to a
320 x 320 mm `Bed(w, h, margin=3.0, gap=3.0)` unless the caller passes a
different one.

## Hello, printed part

A body is the other half of the vocabulary. This one is a plate with a countersunk M3
fixing hole, in PLA, checked against the printer's build volume before it is shown:

```python
from bench import *
from bench.library.print import PLA, H2D

pla = Printed(PLA)                       # a filament and a way up (+Z by default)
plate = cuboid(60, 40, 5)
plate = hole(plate, Point(15, 20), on=plane_of(plate, "top"),
             screw=M3, countersink=True, printed=pla, label="fixing")
require(check_fits(plate, H2D))
show(part("bracket", plate, pla))        # the process is read off the stock: print
```

The hole is 3.4 mm because ISO 273 says an M3 clearance hole is, plus the 0.2 mm PLA takes
back off a printed one; the countersink is the screw's own 6.3 mm at 90 degrees; and the
faces it adds are named before anything builds them - `bracket/fixing/side-0`,
`bracket/fixing/head`. Drill the same hole through a side instead and it comes out a
teardrop, because the part says which way up it prints and a bore lying on its side cannot
be printed round. `require()` stops the run on a violation; `check_fits(...)` on its own
records one and lets the run finish.

A library like `gridfinity` is not part of `bench` itself: a script imports it
by name, the same as any other module - `from bench.library import
gridfinity` - and the browser's editor additionally pre-binds `gridfinity`
into scope so a script can reach for it without that import line, the way
`show` is already there without one.

## The examples

`examples/*.py` is what the browser's menu loads, and five of the printed ones are the parts a
maker builds in the first month - the list the maker's-lens review (`doc-3` in `backlog/docs/`) walks,
written against the vocabulary rather than around it. Each runs clean with a real modeller
and says in its own text what it could not do and why.

| script | what it is | what it is worth reading for |
| --- | --- | --- |
| `box_with_hole.py` | a finger-jointed ply box | the smallest script there is |
| `gridfinity_cabinet.py` | a drawer cabinet, laser-cut | a library `Build` and a cut list |
| `gridfinity_bin.py` | a 2 x 1 x 3 bin, label lip and scoop | `library/gridfinity3d`, and a stacking fit measured rather than asserted |
| `pipe_bracket.py` | a 40 mm pipe bracket, two M4 holes | a bore that comes out a teardrop because the part says which way up it prints, and a lofted gusset where a fillet cannot go |
| `enclosure_lid.py` | a box and its lid | `clearance(Fit.SNUG, PLA)` as the lip's own dimension, four M3 insert bosses, and a lid that prints upside down (`Orient(up=-Z)`) |
| `depth_stop_collar.py` | a collar for a 6.35 mm shank | a radial set screw: `plane_of(collar, "side-0", around=..., along=...)` |
| `hinge.py` | a two-part hinge, printed pin | `Fit.SLIDE` between pin and bore, interleaved knuckles, and rims eased by building the prism that way |
| `systainer_tote.py` | a Systainer-style stacking tote | tapered plugs and their sockets as one `loft`, a wall that thickens into the rim only at the top, and what a hull costs you in names |
| `fulcrum_hinge.py` | one stack of the rolling hinge in US 10,114,424, posed | a planar linkage swept along its axis, a D passageway cut by hand beside a round one from `hole`, every dimension recorded as the script's own, a pose driven in the patent's order and measured pair by pair with `min_gap`, the whole travel sampled at twenty-one deployments with `check_clearance_through`, and a docstring that says what a static model cannot prove |
| `wall_vent.py` | a wall vent frame and the attachment that fits over its collar | `mated`: the attachment drawn where it prints, put on the flange by its back face, the contact measured by the call that made it, and the groove round the collar checked with `check_fit` against the slide the table asks |

## Layers

- `geometry.py` - where things are. `Point` and `Vector` with a typed algebra
  (place + move = place, place - place = move, place + place is a type error),
  `Transform` with `@` overloaded for points, vectors and composition, `Plane`
  as a local frame, and the usual named functions (`unit`, `cross`, `angle`,
  `distance`, `lerp`, `near`).
- `topology.py` - how geometry connects. `Line | Arc | Circle` curves, then
  `Edge -> Wire -> Face -> Solid` with an optional `label` on every rung. A
  `Solid` holds a `Node` - the recipe for a body, not its boundary - and
  `faces_of()` says what every face of it will be called before anything builds
  it. Records are dumb; `label()`, `wire()`, `face()` and `polygon()` are where
  validity is checked and the only things that raise.
- `fasteners.py` - the hole a screw, an insert, a nut or a magnet asks for, as data. One
  `Screw` per size (`M2` … `M8`) with its clearance holes, tap drills, head, counterbore,
  countersink and nut dimensions; `Fit` (`INTERFERENCE PRESS SNUG SLIDE CLEARANCE LOOSE`)
  and `bore(screw, fit)` over it; `Insert`, `NutTrap` and `Magnet` for the parts that are
  not screws and are not fits of one. It imports nothing at all, and every figure in it is
  the nominal *metal* one - printed compensation is the material's to add on top.
- `model.py` - the user's vocabulary. `Part` (label, shape, stock, process,
  engravings), the `Text` that gets engraved on one, `Placed`, `Assembly`, a
  `Build` for what a library hands back, and `Ref` paths. `part()` and
  `assembly()` reject duplicate refs at build time; `index()` is the ref table a
  viewer or editor reads; `resolve()` turns a ref into topology, and
  `moved_part()` moves a part's shape and engravings together. A part is made of
  `Stock | Printed` - a sheet with a thickness and a kerf, or a `Material` and an
  `Orient` - and `process_of()` reads the process off it rather than off a fourth field.
- `ops.py`, `solids.py`, `features.py` - what you can do, in three files that import only
  downward. Constructors (`rect`, `circle`, `slot`,
  `rounded_rect`), the face builder (`fill`), the flat modifiers (`offset` for kerf,
  `chamfer`), selectors (`edges`, `edge`) and queries (`bbox`, `bounds`, `area`,
  `perimeter`, `centroid`, `is_ccw`, `contains`) are `ops.py`; the body verbs (`extrude`,
  `revolve`, `union`, `cut`, `common`, `hull`, and the sugar `cuboid`, `cylinder`, `loft`,
  `pocket`, `boss`) and the verbs a body takes as readily as a sketch (`mirror`, `move`,
  `rotate`, `pattern`, `grid`, `name`) are `solids.py`; the hole and what makes one
  printable is `features.py`. Together they are
  the one public home for the verbs a script writes. Every label
  may be a plain string. A sketch's `on=` is where it is *drawn*: `fill(rect(10, 6),
  on=plane_of(plate, "top"))` reads the rectangle in that plane's own frame and lifts it onto
  the plate's top face at the plate's own numbers. `raised(XY, 5)` is the flat plane five
  millimetres up, and `plane_of(collar, "side-0", around=0.0, along=6.0)` is the plane tangent
  to a cylinder's side, which is where a set screw goes; `axis_of(pin, "side-0")` is that
  side's axis, as a frame whose X is where `around` counts from. `hull(*shapes)` wraps faces and
  bodies alike - a stack of flat slices with a hull round it is how a chamfered sweep is
  written on a kernel that cannot sweep - and `pattern(shape, count, step)` takes a `Turn` as
  readily as a vector, while `grid` numbers a rectangular array in one flat run.
  `hole(subject, at, *, on, screw | insert | diameter, fit, depth,
  countersink, counterbore, angle, top, printed, label)` is one verb over the `Face | Solid`
  union - a circle in a flat part, a bore in a body - and `Top`, `teardrop`, `bridge_steps`,
  `printable_top` and `foot_chamfer` are the printable-hole geometry it builds with.
- `checks.py` - what has to be true of a part, answered as a `Violation` rather than a
  raise: `fits(shape, volume)`, `clearance_between(a, b, least, *, kernel)`,
  `fit_between(a, b, fit, asked, *, kernel)` - how a pair put together at a fit really sits,
  a `Fitted` whose sentence is the measured gap beside the asked one,
  `contact_between(a, b, *, kernel)` - the check a pair gets *instead* of `clearance_between`
  once a maker declares the two are meant to seat against each other, which asks whether they
  share material rather than whether they stand apart, because `min_gap` reads a touch and a
  collision alike as zero -
  `wall(solid, least, *, kernel)` and `overhangs(solid, orient, material, *, kernel)`. The
  kernel is a parameter, never an import, and a check that needs one and has none answers
  `Severity.UNCHECKED` instead of passing. `Sampled` and `sampling(over, samples)` are what a
  question asked of a whole motion answers with and where its poses are - a record that says
  how many poses were measured and how far apart, because a check made at twenty-one poses
  has not proved anything about the travel between two of them.
- `mate.py` - one part's face put on another's. `mating(fixed, at, moving, onto, *, fit=CONTACT,
  offset, spin, along)` lays the moving part's face on the fixed one's, normals opposed, in the frame
  each face was *authored* in - `plane_of`'s - so two parts drawn from the same corner go
  together with nothing more said, and `offset`/`spin` are the written correction when they
  were not. The gap along the normal is nothing for `CONTACT` and the fit's own per-side figure
  in the moving part's filament otherwise. The moved part keeps its print orientation: its
  `Orient.up` turns with the body, so a part mated upside down still prints the way it was
  drawn to. Two round faces - a pin and its bore - are a round pair instead: the moving axis
  goes on the fixed one (`axis_of`'s frames), running the same way, `along` it and turned `spin`
  about it, both explicit and never guessed; the gap round the pin is what the radii make it,
  and is measured against the fit's figure rather than placed. A round face against a flat one
  is refused. The measuring is the script's `mated`.
- `joints.py` - how panels hold together. A `partition` of an edge into an odd
  number of fingers, the `female_intervals` / `male_intervals` either side of
  it, `jagged_edge` to walk one side of a panel, and `open_box` for the `Box` of
  five panels of a finger-jointed box where every corner belongs to one panel.
- `nest.py` - where parts sit on the stock. `nest(parts, bed)` grows every part by
  half its kerf, shelf-packs it tallest first onto a `Sheet` series per thickness,
  turns a part a quarter turn only when that helps, and reports what will not
  fit rather than dropping it. A printed part is passed over without a word - a nest is
  sheets, and a body among bodies is not a mistake. A `Bed` is the sheet with its margin and gap; a
  `Placement` carries the part as the script made it and the `placed` part that
  gets cut, in sheet coordinates, and `sheet_name` names the sheet.
- `kernel.py` - what a solid modeller has to be able to do, and nothing behind it. A
  `Kernel` is a `Protocol` of exactly three methods - `mesh`, `volume`, `min_gap` - and a
  `Mesh` is a flat transport record whose `refs` run one per *triangle*, so a click on a
  triangle is a click on `plate/top`. No module under `src/bench` imports a modeller; a
  kernel is handed to `run()` the way `show` is.
- `meshing.py` - the half of building a body that needs no modeller: which named face each
  triangle of a freshly swept primitive lies on, by its normal or position for a cap and the
  profile step under it for a side, and what each triangle of a finished body answers to,
  read back through `(run_original_id, face_id)` - the pair, never the face id alone. Flat
  buffers in and out, and per-triangle loops that make no object per triangle.
- `adapters/browser.py` - the kernel. `JsKernel` walks the tree, asks a Manifold living in
  JavaScript for each sweep and boolean by handle, and decides every name with `meshing`. A
  hull destroys identity, so a hull's triangles answer to the hull and nothing under it,
  which is what the naming rule said before anything was built. It imports no modeller and
  nothing only Pyodide has: the modeller - `web/src/modeller.ts` in the app, a hand-written
  fake in a unit test - and the exception a refusal raises are handed to it.
- `facets.py` - a mesh read as triangles: each one's corners, normal, centre and area, and how
  thick the material is under it - a ray from its middle straight in to the first surface facing
  back, found through a uniform grid over the mesh so a downloaded model of twenty thousand
  triangles is measured in seconds. `checks.wall` and `survey` both measure with it, which is
  what makes the wall a check fails and the wall a survey reports the same number.
- `placement.py` - where a dropped mesh's own datum sits, read from a `[reference]` table
  rather than inferred: `placement(table, mesh) -> Plane` resolves `origin` (`"low"`, `"high"`,
  `"centre"` or a triple), `up` and `along` (`"+X"` .. `"-Z"` or a triple) against the mesh's
  own box, and `placed(mesh, plane) -> Mesh` is the rigid move itself - every vertex through
  the plane's local frame, triangles and refs untouched. A host applies both once, at the edge,
  before the survey or anything else sees the body; a project with no table calls neither.
- `imported.py` - a mesh somebody else made, as a body: `imported(mesh, label=...)` wraps the
  `Mesh` a host dropped - the `reference` a script already has bound - as a `Solid`, and from
  there it is a solid like any other. That is the point of it: a candidate can be *boolean*
  compared against a real object instead of only survey-diffed against one, so how much of a
  candidate lies inside the reference is `kernel.volume(common(candidate, imported(reference)))`.
  Its own triangles are the recipe - an `Imported` node, a leaf that names nothing under it the
  way a hull does, because a file somebody else wrote has no names in it to keep. It validates
  nothing: whether a mesh is a body at all is Manifold's own question, asked when something
  builds it and answered as the `ValueError` every other refusal already is. See `decision-8`.
- `survey.py` - what a thing that already exists measures, with no modeller anywhere:
  `mesh_from_stl` reads a binary STL into the kernel's `Mesh`, and `survey(mesh)` answers with a
  `Survey` of its extent, its sections at chosen heights, its walls (the thinnest, and the
  distribution by area), its flat and round surfaces with the numbers that place and size them,
  and what repeats among them on a regular spacing. Data, not prose; measured, never inferred - a
  bore is a diameter, not a clearance hole at a fit. The module docstring writes down what counts
  as flat, as round and as a repeat.
- `report.py` - a survey written out for a reader: `report(survey)` takes the record and
  returns text, never seeing the mesh. Every measurement is put in bench's own words - an
  outline this big at this height, a bore of this diameter, so many on this spacing - and
  every verb it names is marked a candidate that fits the numbers, not a conclusion. It says
  nothing the survey did not measure: a 4.000 mm bore stays a 4.000 mm bore, the thinnest
  single reading is printed beside the area that read anything like it so a sliver of the
  tessellation is not called a wall, and a closing block says what a survey cannot see. A
  rounded edge that bends comes back from the survey as a piece per step of the bend, and a
  countersink as a flat per facet of the cone; pieces that touch, agree in size and turn a
  step from one to the next are written as one entry - how many, how much, the largest in
  full - so a real export's report is a page and not a hundred lines of one round-over. Lists
  are sorted on their numbers and every figure printed to fixed places, so one survey renders
  one report.
- `plates.py` - a laser part as the plate it is cut from: its face swept to its stock's
  thickness, every wall named by the ref its cut path already carries - so
  `drawer-front-1/pull` is the pull's wall - and its engraved wires and lettering laid on its
  top. No kernel: a laser part is drawn whether or not the modeller loaded. `triangulate.py`
  is the ear clipping that fills its top and bottom.
- `stage.py` - where bodies stand in the view: rows along X, front edges on the row's line
  and lying on the floor, a row wrapping before it runs past 600 mm, with the grid under
  them. Done here so the viewer is handed places already worked out.
- `telemetry.py` - what a run says about itself, in the standards a collector already
  reads. Logs are the standard library's `logging`, one logger per module under `bench`;
  importing the package configures none of it, and routing records is the host's job. Spans
  are timed stretches of work with
  OpenTelemetry-style names - `bench.run`, `bench.script.exec`, `bench.kernel.mesh`,
  `bench.check.wall` - and a `Tracer` is handed to `run()` and to the kernel the way a
  kernel is; the default keeps nothing.
- `worker.py` - the two functions the browser's worker calls into Python. `start(telemetry,
  refused)` routes `bench`'s logs and spans to the page and gives back the runner that runs a
  script with the kernel and puts its scene on the wire; the worker hands in Pyodide's
  `JsException` as `refused`, so nothing here imports Pyodide. `surveyed(stl, table)` is the
  worker's other entry, for the report of a body dropped on the view. Both place `reference`
  by the project's `[reference]` table before anything measures it - `placement.py`'s move,
  applied at this edge exactly as `tools/build.py` applies it at its own - so a run's
  `reference` and a survey's report never disagree about where the mesh sits.
- `export.py` - the text and bytes a machine reads. `face_paths`, `part_paths` and
  `part_texts` turn topology into `SvgPath` and `SvgText` records that keep their
  refs; `part_svg`, `sheet_svg` and `sheet_dxf` write the files, in millimetres
  with the workpiece reading origin bottom-left. `stl(mesh)` is a binary STL and
  `three_mf(objects)` a 3MF package - one object per part, `unit="millimeter"`, and no
  slicer settings of anybody's. Both are pure functions returning bytes.
- `params.py` - a script's settings as one frozen dataclass. `knob(default, *, label, min,
  max, step)` puts the panel's hints on a field without changing its type, and a `Literal`
  field is a menu. `declared(cls)` reads the class into the panel's `ParamView`s before
  anything is built; `configured(cls, values)` reads an untrusted mapping - the panel's table,
  JSON off a wire - into an instance, coerced to each field's type and held at the nearer end
  of its range, or raises naming a field it cannot read. It knows nothing of a run, so any
  host can use it.
- `script.py` - the runtime the browser calls. `run(source, overrides, *, bed, extras,
  kernel=None)` executes a script in a fresh namespace and returns a `Scene`: the parameters,
  parts, refs, nested sheets, files, warnings and what the script printed on each of its
  two streams - `stdout` and `stderr`, because a browser has no terminal for the second one
  to fall down - or `{"ok": False, "error": ...}` with the line that went wrong and the two
  streams as far as the script got. A script ends `show(build)`, where `build(p: Settings)`
  makes what it shows from its settings dataclass; the run declares the settings' fields as
  its parameters and calls `build` with the overrides read into them. `show` - the one name a
  script talks through - is built per run and injected into that namespace,
  so it is not a name of this package and `from bench import *` cannot clobber it. So
  are `check_fits`, `check_clearance`, `check_clearance_within`,
  `check_clearance_through`, `check_contact`, `check_fit`,
  `check_wall`, `check_overhangs`, `mated` and
  `require`: a
  check records a `Violation` with the line of the script that asked and hands it back, and
  a failed check never aborts the run - the geometry, the refs and the sheets still come
  back with the violation beside them. A check is handed a bare solid, usually before the
  part it becomes exists, so it answers in the solid's own names - `socket-1` - and the run
  keeps the shapes each check measured beside its answer, so the scene can say `tote/socket-1`.
  Each part that is a body carries its `mesh` when the run was given a kernel.
  `check_clearance_through(at, least, over=, samples=, contacts=)` is the same question asked
  of a motion rather than a pose: `at(t)` is the script's own "give me the assembly posed
  there", it is built and measured at every one of `samples` values across `over`, and the
  pairs `contacts` names are asked `check_contact` at each of them instead of being left
  unmeasured. It **samples**; the `Sampled` it answers with says so and at what spacing, so
  "clear at 21 poses, one every 0.05" is never read as "clear throughout", and nothing about
  it is a claim about force, friction or binding.
  `mated(fixed, at, moving, onto, *, fit=CONTACT, offset, spin, along)` is `bench.mate.mating` and its
  check in one call: it puts the part in place, measures the pair at the fit it was asked for,
  records a finding on the moved part when the pair overlaps or comes in tight, and hands back
  a `Mate` whose `part` is what the assembly shows and whose sentence - "attachment/base/bottom
  on frame/flange/top: touch, asked contact" - says what was measured against what was asked.
  `check_clearance_within` leaves every mated pair out, by identity, because the mate already
  asked it the right question; `check_fit(a, b, fit, material)` is how a second pair beside a
  mate is checked, with the same sentence.
- `views.py` - what a run collected, built into its scene: the parts nested onto sheets,
  each body built with the kernel and laid out on the stage, every file a run offers, each
  finding's refs put under the part whose shape the check was handed - matched by identity,
  never by a face's last name, so two panels with a `bottom` keep their findings apart - and
  each record as the view the wire carries. It runs no script and knows nothing of one.
- `transport.py` - a scene as it crosses to the browser: `scene_json`, `scene_wire` (a mesh's
  long lists as buffers beside the JSON), and `binary(filename)`, the one place that says
  which files are bytes.
- `scene.py` - the shape of that answer, and nothing that builds one: `OkScene`,
  `ErrorScene` and the views under them, each a closed `TypedDict` so a key that is not in
  the contract is a type error rather than something the browser finds out about. It is a
  file of its own because `web/src/scene.ts` mirrors it field for field, and a change on
  either side then has one file to be made to match on the other.
- `library/print.py` - the print domain: the `PLA`, `PETG` and `ASA` material profiles
  (shrink, printed-hole compensation, first-layer spread, minimum wall, maximum overhang,
  longest bridge, layer height and the per-fit clearance table), the public
  `clearance(fit, material)` **per side** that a lid lip and a hinge bore need as much as a
  hole does, and the build volumes (`H2D`, `BEDS`). One import for the whole print
  vocabulary: the records it fills in live in `model.py` and the geometry in `features.py`,
  and it re-exports both.
- `library/gridfinity3d.py` - the printed Gridfinity bin: a frozen `Spec` (units, a height
  that is a union of the four things "how tall" means, wall, floor, divisions, scoop, label
  tab, magnets, screws and the `Fit` it stacks at), `derive()` for the millimetres,
  `validate()` naming the first parameter that will not print, and `bin_(spec)` returning a
  `Build`. The standard's own constants are public - `GRID`, `BASE_TOP`, `BASE_PROFILE` - and
  the stacking lip is that base profile with the fit round it rather than a second table.
- `library/gridfinity.py` - the first shipped object: a drawer cabinet sized in
  Gridfinity units. A `Spec` of units and stock, `derive()` for the millimetres it
  implies, `validate()` for the specs that will not cut, and `cabinet()` returning a
  `Build` - one part per distinct panel, how many of each to cut, and the `.scad` text
  for a printed baseplate among its files.

## Conventions

Millimetres, floats, one tolerance (`TOL`). Everything frozen; every operation
returns new values. `==` is exact so hashing keeps its promise; compare
geometry with `near()`. Unions of frozen dataclasses instead of inheritance;
consumers `match` and end in `assert_never`.

## Check

```
uv run tools/check.py
```

Runs ruff, mypy, the pytest suite twice (to catch state leaking between runs) and finally the
`e2e` layer, stopping at the first failure. Pass `--fast` (or `--no-e2e`) to skip the `e2e`
layer, which drives a real browser and is slow. The checks that measure the real solid
modeller boot Pyodide under Node with the app's own Manifold WASM, and skip, saying so, where
`node` or `web/node_modules` is missing.

A skip is not a pass. In a fresh clone or a fresh worktree `web/node_modules` is missing and
`web/src/generated/` has never been built, so the modeller layers skip, the `e2e` layer runs
nothing and fails on that, and `tsc` cannot find `./generated/pysources`. Run
`npm ci --prefix web && npm --prefix web run generate` first, then the gate; a green run that
did not include the adapter and `e2e` layers has not checked the kernel at all.

The same command is what makes a script merged into `examples/` loadable in the browser app:
`web/src/generated/pysources.ts` is gitignored, so a `git pull` or merge never touches it on
its own. Run `npm ci --prefix web && npm --prefix web run generate`, then (re)start `npm run
dev` or rebuild with `npm run build` before `npm run preview` - see `web/README.md`'s "Run
it" section for the full story, including the status bar's **stale examples** indicator when
this has been skipped.

Looking at the app rather than checking it is the other command:

```
uv run python -m tools.qa [example.py ...]
```

It builds the app if anything it is made from has changed, serves it, walks the examples
named (three representative ones by default), and leaves a screenshot of each beside a log
of everything the app said - the console, anything the page threw, any request that failed,
and the panels a person reads: what was built, what the script printed, what was violated
and what went wrong. It asserts nothing and fails at nothing; the answer is in `web/qa/out`
for someone to read. Both it and the `e2e` layer drive the same built app through
`tools/preview.py`.

Running a script without a browser at all is the third command:

```
uv run python -m tools.build <script.py> [--out DIR]
uv run python -m tools.build --project NAME <script.py> [--out DIR]
```

The second form reads the script from a project under the host's projects root -
`$BENCH_PROJECTS` (an absolute path), or `projects/` here when it is unset - the same root the
app's `/__bench/projects` route serves, resolved by the same rule (`tools/projects.py` and
`web/server/projects.ts`), so the command line and the app cannot disagree about where a
project is. See `web/README.md` for what the route does and refuses.

It runs the script, says what was made and what the checks found, and with `--out` writes
every file the run produced - the sheet SVGs and DXFs, a printed part's STL and 3MF, whatever
the build brought with it. No solid modeller is loaded, so a printed part comes back with
every ref, parameter and violation and no triangles; cut sheets need no kernel, which is what
makes this worth having.

A TOML beside the script says which one of that thing to build:

```toml
# gridfinity_cabinet.toml
[values]
units_x = 4
drawers = 6
```

The dataclass in the script declares the settings and holds the defaults; the file says which
instance you are making, and a field it leaves out keeps the script's own default. Those
values become `run()`'s `overrides` - the same mapping the app's panel sends - so nothing
under `src/bench` knows the file exists. A script with no file beside it runs on its
defaults, which is what every example does. See `decision-3` in `backlog/decisions/`.

The app keeps the same file. A project in the browser is a script and its values, and the
values are kept, shown and handed over as that TOML: an edit in the parameters panel is a line
in it at once, it opens as a tab beside the script, and the explorer's Download is the two
files in one archive - which `tools.build` runs as they are. Open… takes them back in, and a
value the file holds outside a knob's range is written back as the run built it, so the file
never says something the run did not do.

The tests come in four layers, one directory and one marker each: `tests/unit` (one module,
pure), `tests/functional` (several modules through the public API, still pure),
`tests/adapter` (a real boundary - the scene JSON contract, the real solid modeller, `bench`
in the shipped Pyodide runtime - with no doubles) and `tests/e2e` (the built app in a browser,
deselected unless you ask for `-m e2e`). Every example script is run in both of the middle two
layers: without a modeller it has to come back clean, and with one its mesh is measured
through the refs its own script wrote. There are no mocks or monkeypatching anywhere; `tests/conftest.py`
fails the session if any appears. See **Testing** in `DESIGN.md`.

## License

GNU Affero General Public License v3.0 or later - see `LICENSE`. A changed bench, whether
handed over or served to people over a network, comes with its source.
