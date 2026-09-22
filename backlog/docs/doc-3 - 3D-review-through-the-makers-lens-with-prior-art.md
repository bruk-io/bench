---
id: doc-3
title: '3D review - through the maker''s lens, with prior art'
type: other
created_date: '2026-09-22 19:47'
---

# Review: the 3D proposal (decision-1) through the maker's lens

**Verdict up front.** Of the five parts, the proposal as written lets you build **one and a half**. (a) the Gridfinity bin is buildable but ugly; (c) the lid is buildable with one guessed convention; (b) the bracket and (d) the collar are **blocked** on missing primitives, not on polish; (e) the hinge builds two solids that have nowhere to go. The blockers are not kernel problems — they are four unwritten paragraphs: what an operation *returns*, what a solid's faces are *called*, which way is *up*, and where a *fit number* lives.

---

## 1. The five scripts

Full annotated scripts are at `/tmp/claude-0/review-maker3d/scripts/{a..e}_*.py`. Here is what each one taught me.

### Before any of them: the proposal's own example does not compose

```python
plate  = extrude(fill(rounded_rect(80, 40, 4), label="plate"), 6, label="plate")
top    = plane_of(ref("plate/top"))
boss   = extrude(fill(circle(8), on=top), 10, onto=plate)                     # join
pocket = extrude(fill(rect(20, 10, at=Point(5, 5)), on=top), -4, into=plate)  # cut
hole(ref("plate/top"), at=Point(70, 20), screw=M3, fit="clearance", countersink=True)
```

Everything in bench is frozen (`CLAUDE.md`, `DESIGN.md`: "Every operation returns new values"). So `plate` is never modified. If `onto=`/`into=` return the *combined* solid, then `boss` is plate+boss and `pocket` is plate−pocket, and **neither contains the other** — the boss is lost the moment you use `pocket`. If they return the *tool*, then nothing is ever combined. Either way `hole(...)` as a bare statement can only return a value into the void. Nothing is `show()`n. **The canonical five-line example of the proposal produces a set of dangling bindings.**

Two further problems in those five lines:
- `rounded_rect(..., label="plate")` names the wire "plate" and `extrude(..., label="plate")` names the solid "plate". `model.part()` "rejects duplicate refs at build time" (`DESIGN.md`), so this example may not build at all.
- `plane_of(ref("plate/top"))` resolves a `Ref` with no root. `model.resolve(root, ref)` needs an `Assembly | Part`, which does not exist until `show()`. So `ref()`-as-argument requires an implicit global registry — which collides head-on with `CLAUDE.md`'s "modules take data and return data; I/O lives at the edges only" and with the injected-`ref` design in `script.py`. This is an architecture decision the proposal makes silently.

Pick one and write it down. My recommendation: **drop `into=`/`onto=` entirely.** `body = difference(body, extrude(sketch, -4))` reads worse by four characters and has no semantics to explain. Keep `through=` (it is genuinely hard to express otherwise). Make `hole()` take and return a solid: `body = hole(body, on=top, at=..., screw=M3, ...)`.

---

### (a) Gridfinity bin, 2×1×3u, label lip, scoop

```python
foot = hull(                                    # MISSING: `hull` verb — Hull node exists, no verb
    extrude(square_at(35.6, 0.80, 0.00), 0.01),
    extrude(square_at(37.2, 1.60, 0.80), 0.01),
    extrude(square_at(37.2, 1.60, 2.60), 0.01),
    extrude(square_at(41.5, 3.75, 4.75), 0.01))
feet = pattern(foot, 2, X * U)
body = union(*feet, extrude(fill(rounded_rect(2*U-0.5, U-0.5, 3.75, at=...), on=at_z(7.0)), 21.0))
```

| Mark | Finding |
|---|---|
| MISSING | **`hull` has no verb.** `Hull` is listed as a CSG node; the verb list (`extrude, revolve, plane_of, hole, union, difference, intersection, chamfer, fillet, shell, mirror, pattern`) omits it. The Gridfinity base profile, the stacking lip and the baseplate pocket are *all* hulls of stacked rounded rectangles — that is how bench's own `baseplate_scad()` already writes them (`library/gridfinity.py:490`). `Offset` has the same problem: a node with no 3D verb (`ops.offset` is `Wire \| Face` only). |
| MISSING | **No way to raise a sketch plane.** `fill(outline, on=XY)` takes a plane; there is no `XY.at(4.75)` or `offset(XY, 4.75)`. You hand-build `plane(Point(0,0,4.75), Z, X)` at every level of the hull. Also unclear whether `face()` validates that the wire lies *in* the plane it is given — `topology.face()` does not appear to, so `rect(at=Point(x,y,z))` filled `on=XY` is a silent landmine. |
| MISSING | **`rotate` is Z-only.** `ops.rotate(shape, angle, about=Point)` compiles to `rotation(Axis(about, Z), angle)`. The scoop is a quarter-cylinder lying along X. `geometry.rotation(Axis, angle)` and `topology.moved()` already do the general case — `ops.rotate` just doesn't expose it. Every one of the five parts wanted this. |
| MISSING | **No grid pattern.** `pattern(shape, count, step)` is 1D. A 2×1 bin is fine; a 4×3 baseplate needs nested calls, and the auto-labels collide (`base-1` → `base-1-1`). build123d has `GridLocations`/`PolarLocations` as first-class context managers. |
| MISSING | **No sweep/loft.** The stacking lip is a profile swept around a rounded rectangle. Hull-of-slices reproduces it only because every segment happens to be a 45° chamfer. The scoop, a fillet-radius blend, is not so lucky. |
| ??? | **`union` arity.** Variadic? Two-arg? Unstated. |
| ??? | **`into=` return value** (above). |
| MISSING | **Magnet pockets.** 6×2 magnets with crush ribs and a bridged (supportless) top are the single most-used Gridfinity option, and there is no vocabulary for any of the three. |
| Print gap | **No orientation.** A bin must print base-down. The 0.8 mm/45° foot chamfer is an overhang that only works in that orientation. Nothing in the script says so and nothing can check it. |
| Print gap | **No label.** "Labels can be embossed" is a future note under fonttools. A label lip with no label is not the feature. |
| Model gap | `part()` requires `Stock(thickness, material, kerf)`. For a print, all three are meaningless. `Material` is promised in `model.py` but the proposal never says what `Part.stock` becomes. |

### (b) Wall bracket, 40 mm pipe, two M4, fillet ear-to-base — **BLOCKED**

```python
base = extrude(fill(rounded_rect(70, 60, 6)), 5, label="base")
top  = plane_of(ref("base/top"))
ear  = extrude(cut(fill(rounded_rect(24, 25, 3), on=top), circle(20.3), label="bore"), 5, onto=base)
fillet(edge(???), 3.0)      # <- there is no way to write this
```

| Mark | Finding |
|---|---|
| **BLOCKED** | **The fillet cannot be named.** The edge where the ear meets the base did not exist before the union. `ops.edges()`/`edge()` are typed `Wire \| Face` — there is no solid selector at all, and no history. This is *the* reason a maker leaves OpenSCAD for Fusion. build123d answers with `part.edges(Select.NEW)`; CadQuery with `.edges("not(<X or >X ...)")`; Onshape with `qCreatedBy(id, EntityType.EDGE)`. bench has nothing, and the proposal's own open question 2 concedes Manifold cannot fillet anyway. |
| **BLOCKED** | The maker's workaround — a swept triangular gusset — needs `sweep` (missing) or a prism rotated about X (missing). |
| ??? | **`plane_of` has no documented frame.** "A plane on a named face, normal outward" gives a normal and nothing else. For `at=Point(12, 30)` to mean anything you must know the plane's **origin** and **x_dir**. Is the origin the original sketch origin lifted, or the face centroid, or the face bbox corner? Unspecified — and this is the coordinate system every subsequent call is written in. |
| ??? | **Face names are never defined.** `ref("base/top")` presumes an auto-naming scheme for an `Extrude`'s faces. What are a `Revolve`'s called? A `Box`'s? A `Hull`'s? What happens to `plate/side` when a boss splits it into two faces? **The entire ref story for solids rests on a naming scheme that is not written down anywhere in the proposal.** |
| MISSING | `countersink=True` exposes nothing: no cone angle (Fusion and SolidWorks both expose it; 82° is the imperial default, 90° the ISO one), no which-side, no head clearance depth. A printed countersink wants 90° and 0.3 mm oversize. |
| Print gap | This must print on its back so the saddle bridges. No orientation, therefore no overhang check. |
| Print gap | **Elephant's foot.** The base must sit flat against a wall; the first two layers spread 0.1–0.3 mm. The fix is a 0.5 mm bottom chamfer — `chamfer` is in the verb list but has no edge selector, so again unwritable. |

### (c) Heat-set-insert lid — buildable, with one guess

| Mark | Finding |
|---|---|
| ??? | **Handedness of `plane_of` on a downward face.** The lip is drawn on `ref("lid/bottom")`. A plane with `normal = -Z` has a flipped x_dir, so `at=Point(3.25, 3.25)` lands on the *opposite* corner from the one you meant. Unspecified. Guaranteed first-week bug, and one that produces a lid that looks right and fits wrong. |
| MISSING | **`fit="insert"` is not in the vocabulary.** The proposal names clearance/press/slide and mentions "heat-set insert bore" in the fastener table. But an insert bore is sized from the *insert's* OD (M3 → 4.0–4.2 mm), not the screw's, so it is a different **kind** of hole, not a *fit* of the M3 hole. Model it as `hole(..., for_=Insert.M3_SHORT)` or `insert_boss(...)`, not as a fit. |
| MISSING | Lead-in chamfer at the bore mouth (so the insert starts straight), and a boss-wall check (an insert needs ≥1.6–2 mm of plastic around it or it splits the boss). |
| MISSING | **Four-corner placement.** `pattern` is 1D; build123d's `Locations(...)`/`GridLocations(...)` do this in one line. |
| MISSING | **`fit` is unreachable outside `hole()`.** The lip's clearance against the box is the mating dimension that matters most, and the only way to get the number is to type `0.25` by hand. There must be a plain function: `clearance(Fit.SLIDE, PLA) -> float`. |
| Open Q1 | `assert_wall(lid, 1.2)` needs an evaluated mesh. Per the proposal's own question 1, that will not run in Pyodide. |

### (d) Depth-stop collar, horizontal M4 set screw — **BLOCKED**

| Mark | Finding |
|---|---|
| **BLOCKED** | **`plane_of` on a cylindrical face is undefined.** A cylinder has no plane. So `hole()` — the proposal's flagship feature — **cannot place a radial hole in a round part**, which is the commonest horizontal hole a maker drills. You fall back to a hand-built cylinder rotated about Y, and `rotate` is Z-only. |
| **BLOCKED** | **"Horizontal" is not computable.** The proposal says "Orientation-aware: a horizontal hole gets a teardrop or a bridged top." Horizontal *with respect to what?* Nothing in the model carries a print orientation. This is the single most load-bearing undefined term in the document: the whole print-awareness claim rests on a word that has no referent. |
| MISSING | **`hole(diameter=)`.** The 6.35 mm drill shank bore is not a fastener, so `hole(screw=...)` refuses it, and the printed-hole compensation living in the material profile is unreachable for the one dimension on this part that must be right. |
| MISSING | `fit="tapped"` for M4 gives a 3.3 mm tap drill — a *metalworking* number. In PLA you want 3.4–3.5, or a printed thread, or a nut trap. None of the three exists. |

### (e) Two-part hinge, printed pin — builds, then has nowhere to go

| Mark | Finding |
|---|---|
| MISSING | **`clearance(Fit.SLIDE, PLA)`** again — and here the *asymmetry* matters: the bore grows, the pin does not shrink. Printed holes come out 0.2–0.4 mm small on diameter (the proposal knows this) while outer features come out slightly large. A single `fit` number applied symmetrically is wrong by 2×. |
| MISSING | **`pattern` has no stride or phase.** Interleaved knuckles fall back to a comprehension, bypassing the `-1`/`-2` auto-label scheme that makes refs stable. |
| MISSING | Chamfer on each knuckle rim so the hinge assembles — no solid edge selector. |
| **Blocked** | **Three parts, one script, nowhere to sit.** `DESIGN.md` "Known limits": `Placed.on` is carried but never used to pose anything, and `nest` refuses solids with a warning. So there is neither an assembled view nor a build-plate arrangement. The proposal adds `Volume` and `assert_fits` but says nothing about *laying parts out on a plate*, which is the 3D equivalent of `nest` and the thing that turns a script into a print job. |
| Print gap | A 4 mm pin printed standing up shears on a layer line; lying down it comes out elliptical. The API cannot express either choice, let alone warn. |

### Where print-specific concerns have no home, collected

| Concern | Home in the proposal |
|---|---|
| Orientation (which face down) | **none** |
| Overhang angle / support | **none** (viewer shading only, post-hoc) |
| Bridging | one clause inside `hole`, on an undefined "horizontal" |
| Teardrop | same clause; not a parameter of `hole` |
| Elephant's foot | **none** |
| Seam placement | **none** |
| Layer-direction strength | **none** |
| First-layer footprint / brim need | **none** |
| Plate layout, multiple parts | **none** (`nest` is 2D-only) |
| Filament / mass / time estimate | **none** |

---

## 2. Prior art

### build123d — *what I read*: [key_concepts](https://build123d.readthedocs.io/en/latest/key_concepts.html), [topology_selection](https://build123d.readthedocs.io/en/latest/topology_selection.html), [operations](https://build123d.readthedocs.io/en/latest/operations.html), [objects](https://build123d.readthedocs.io/en/latest/objects.html), [cheat_sheet](https://build123d.readthedocs.io/en/latest/cheat_sheet.html)

**Adopt.** Three things, in order of value. (1) **`Select.LAST` / `Select.NEW`.** "Every operation — a boolean, a fillet, a chamfer, a 2D fillet, a join of connected edges — keeps a record of what it did to the sub-shapes of its inputs: which it left alone, which it rebuilt, which it created and which it removed. The record travels with the shape the operation returns." `part.edges(Select.NEW)` is *exactly* the missing ability in script (b), and it is a property of the *record*, not of the kernel — Manifold's per-face IDs can carry the same information (created/rebuilt/removed), and it costs nothing to define now. (2) **`Mode.{ADD,SUBTRACT,INTERSECT,REPLACE}`** — the proposal already says "the boolean intent is one enum, not three functions," which is the same idea; steal the enum *name space* so `mode=Mode.SUBTRACT` replaces the ambiguous `into=`. (3) **`extrude(..., until=Until.NEXT, target=...)`** — a real, well-named answer to "through", far better than a bare `through=None`. Also note `Kind.{ARC,INTERSECTION,TANGENT}` for offset corners, `Align.{MIN,CENTER,MAX}` for primitive origins (bench's `rect(at=)` is lower-left-only and every 3D primitive will want CENTER), and `Locations`/`GridLocations`/`PolarLocations`.

**Avoid.** The stateful builder context (`with BuildPart() as p:` where bare object constructors mutate an implicit context) is precisely what bench's frozen-records-and-`match` dialect forbids, and build123d itself now offers an algebra mode (`cylinder = extrude(Circle(r), amount=h)`, `tray = Box(20,20,5) - Pos(Z=1.5)*Box(16,16,5)`) as the escape hatch. Take the algebra mode, not the context manager. Also avoid the operator soup (`>`, `<`, `>>`, `<<`, `|`, `@`, `%`, `^` all overloaded on shapes and lists) — it is unreadable to a maker and unsearchable; and avoid `topo_path`/`topo_parent`/`topo_owner`, provenance-by-reference metadata that is "not part of shape equality," which would break bench's promise that `==` is exact so hashing keeps its promise.

### CadQuery — *what I read*: [selectors](https://cadquery.readthedocs.io/en/latest/selectors.html)

**Adopt.** The insight that selectors need **logical combination** — `and`, `or`, `not`, `exc` — and that a two-step narrowing (`.faces(">Z").shell(-0.2).faces(">Z").edges("not(<X or >X or <Y or >Y)").chamfer(0.1)`) is how you actually reach a feature. bench's `edges(shape, direction=, near_point=, label=)` is a conjunction of three predicates with no disjunction and no negation; extend it before it ossifies. Also adopt `ancestors()` / `siblings()` conceptually: "the faces adjacent to this one" is how a maker thinks.

**Avoid.** The string mini-language (`">Z"`, `"|Z and >Y"`). It is a second syntax inside Python with no autocompletion, no type checking and no error line, and CadQuery's own docs carry two warnings about it: "If a face is not planar, selectors are evaluated at the center of mass of the face. This can lead to results that are quite unexpected," and "Non-linear edges are not selected for any string selectors except type (%) and center (>>)." bench's keyword-predicate form is better; keep it and grow it. Also avoid the fluent `Workplane` stack — the implicit "current selection" is the same hidden state as build123d's builder.

### OpenSCAD / SolidPython2 — *what I read*: [OpenSCAD cheat sheet](https://openscad.org/cheatsheet/index.html), and bench's own `baseplate_scad()` at `/home/claude/bench/src/bench/library/gridfinity.py:450-512`

**Adopt.** `hull()` and `minkowski()` earn their place for one reason each. `hull` is how the entire Gridfinity ecosystem expresses a *swept chamfered profile* without a sweep operator — bench's own generated `.scad` does exactly this: `hull() { _slice(36.3, 1.15, 0); _slice(37.7, 1.85, 0.7); _slice(37.7, 1.85, 2.5); _slice(42, 4, 4.65); }`. Three `linear_extrude(eps)` slices and a hull give you the whole 4.65 mm base profile. `minkowski(sphere(r))` is how people round every edge of a part at once when they have no fillet — the poor man's fillet, and worth knowing as the fallback if Manifold really cannot fillet. Ship `hull` as a verb, not just a node.

**Avoid.** The reason people leave OpenSCAD is exactly the reason to be careful here: **CSG-only means no feature has a name after it is made.** You cannot select the edge where two solids meet, so you cannot fillet it, so every OpenSCAD part looks like an OpenSCAD part. The proposal is a CSG tree with per-face ID tagging, which is *better* than OpenSCAD — but only if the naming scheme is designed rather than assumed. Also avoid `minkowski` as a shipped verb: it is catastrophically slow and it silently grows every dimension, which is the wrong mental model for a maker who is trying to hold a fit.

### Gridfinity generators — *what I read*: [gridfinity-rebuilt-openscad](https://github.com/kennetek/gridfinity-rebuilt-openscad) `README.md`, `gridfinity-rebuilt-bins.scad`, `gridfinity-rebuilt-baseplate.scad`, `src/core/standard.scad`, `src/core/gridfinity-rebuilt-holes.scad`

**Adopt — this is the parameter list, verbatim, that a bench `gridfinity3d` must expose.** Bins: `gridx`, `gridy`, `gridz`, plus `gridz_define` as an *enum of four meanings* (7 mm increments excl. lip / internal mm / external mm excl. lip / external mm) — makers genuinely need all four, and offering only one is the commonest complaint about generators. Then `height_internal`, `enable_zsnap`, `include_lip`, `divx`/`divy`, `depth`, `style_tab` (Full/Auto/Left/Center/Right/None), `place_tab`, **`scoop` as a 0–1 float, not a boolean** ("scoop weight percentage… any real number will scale the scoop"), `only_corners`, `half_grid`, `refined_holes`, `magnet_holes`, `screw_holes`, `crush_ribs`, `chamfer_holes`, **`printable_hole_top`**, `enable_thumbscrew`. Baseplates: `style_plate` (thin/weighted/skeletonized/screw-together/screw-together-minimal), `style_hole` (none/countersink/counterbore), and **`distancex`/`distancey`/`fitx`/`fity`** — "Fit to Drawer", which pads a baseplate out to a drawer's real size and lets you choose where the slack goes. That last one is the single most-used feature and bench's current `baseplate_scad(units_x, units_y, floor_t)` has no equivalent.

Two more things worth stealing outright: the **constants as named data** (`BASE_PROFILE = [[0,0],[0.8,0.8],[0.8,2.6],[2.95,4.75]]`, `STACKING_LIP_LINE`, `TAB_POLYGON`, `BASE_TOP_DIMENSIONS = [41.5,41.5]` giving a 0.5 mm gap per grid) — these are exactly bench's `_POCKET`/`_Slice` idiom and should become the shared library's public constants; and the **`make_hole_printable(inner_radius, outer_radius, outer_height, layers=3)`** trick, which lays alternating 90°-rotated squares at `LAYER_HEIGHT = 0.2` so the slicer bridges a magnet counterbore with no support. That is the concrete implementation of the proposal's hand-waved "or a bridged top."

**Avoid.** The flat global namespace of 40 customizer variables with `// [0:Full,1:Auto,...]` comment-encoded enums, and the coupling where `style_plate` silently changes the baseplate's *height* (`calculate_offset(sp, ...)`). bench's frozen `Spec` + `derive()` + `validate()` triple (as in `library/gridfinity.py`) is strictly better and should be kept — `validate()` naming the first parameter that does not work is a genuine advantage over OpenSCAD's `assert`. Also avoid `only_corners`-style flags that implicitly force other flags (`half_grid` implies `only_corners`); make it an error, per bench's existing style.

### Onshape FeatureScript — *what I read*: [FsDoc index](https://cad.onshape.com/FsDoc/), [feature-types](https://cad.onshape.com/FsDoc/feature-types.html), [uispec](https://cad.onshape.com/FsDoc/uispec.html), [modeling](https://cad.onshape.com/FsDoc/modeling.html)

**Adopt.** Two ideas, and the second is the important one.

(1) **The feature *is* its parameter declaration.** A FeatureScript feature is `defineFeature(function(context, id, definition) precondition { ... } { ... })`, and "Onshape creates the feature dialog by doing a static analysis (rather than an execution) of the feature declaration, primarily of the precondition… The parameter specification simultaneously serves as a validity check for the feature and a description of the UI for inputting that parameter." bench already has half of this — `param("units_x", 4, min=1, max=7, label="Units across")` in `script.py` generates the panel — but only at the top level of a *script*, never for a *library function*. `gridfinity.Spec` has 20 fields with bounds encoded nowhere. Make `Spec` fields declare their own bounds and labels and the browser gets a real dialog for every library object for free. This is the highest-leverage single idea in this section.

(2) **Queries are recipes, not references.** "A query does not reference entities, it simply encodes criteria… FeatureScript uses queries in place of direct references out of a need for robustness in the face of changes earlier in the feature list. When we reference the top of a cube, we need to be able to find that face again after the user changed the cube's size and drilled a hole through it." And the payoff, stated explicitly: suppressing an upstream extrude "notably will NOT cause the Fillet Everything feature to break with an error like 'missing edges'. This is because no explicit references to the edges are passed into or stored by the feature. Rather, the feature reevaluates the edge Query every time the feature is run." **This is the answer to the proposal's whole ref problem, and it is the opposite of what the proposal proposes.** Manifold face-ID propagation is a *reference* scheme: a tag minted at primitive-construction time, carried through booleans. It works until the primitive that minted the tag is parameterised away, and then `ref("plate/top")` resolves to nothing with no good error. A query scheme — `faces(solid, normal=Z, topmost=True)` re-evaluated each run — never breaks. The right design is probably both: **labels for intent** (the thing bench is already good at, `drawer-front-3/pull`), **queries for topology** (the top face, the new edges, the concave edges). Note also `id is Id` — every operation takes an explicit, hierarchical, author-chosen id (`id + "fillet1"`), which is how a *feature* gets stable names for the sub-features it creates. That maps directly onto bench's `Label`/`Ref`.

**Avoid.** The `Context` — a mutable modelling database threaded through every call — is the opposite of bench's functional core, and adopting it would be adopting Onshape's whole regeneration engine. Also avoid FeatureScript's `isAnything` parameters and arbitrary-expression parameter fields ("Lambda functions: `(function(x) { return (x^2+1) in; })(1)`"): bench's scripts are already Python, so the expression escape hatch is free and needs no mini-evaluator.

### Fusion 360 Hole and SolidWorks Hole Wizard — *what I read*: [Hawk Ridge, "Deep Dive into SOLIDWORKS Hole Wizard"](https://hawkridgesys.com/blog/deep-dive-solidworks-hole-wizard), plus Autodesk's hole-tool support articles

**Adopt.** The Hole Wizard's decomposition is the right one and the proposal is two-thirds of the way there. SolidWorks splits a hole into: **feature style** (Hole / Counterbore / Countersink / Tapered Tap / Straight Tap / …), **standard** (ISO, ANSI, …), **fastener type**, **size**, **fit** (`Close` / `Normal` / `Loose` — "the values for these fit types are built into the Toolbox Configurator and can be adjusted manually if desired"), **end condition** (blind depth / through all / up to next), and an **options** group for head clearance and thread type. Four lessons: (i) **fit is an enum over a table the user can edit**, exactly what a material profile should be; (ii) **end condition is a first-class parameter**, not `depth=None` meaning through — bench should take `depth: float | Through | UpToNext`; (iii) **the standard is explicit**, so an M3 clearance is 3.4 because ISO 273 medium says so, not because someone typed it; (iv) "each unique hole type/size will require its own Hole Wizard feature" — i.e. one feature, many positions, which argues for `hole(solid, at=(p1, p2, p3, p4), ...)` taking a *sequence* of points rather than four calls. And Fusion's hole tool exposes drill-point angle (118°/135°) — irrelevant for printing, which is itself the useful signal: **a printed `hole` needs different parameters from a drilled one**, and the ones it needs are teardrop/bridge/chamfer, not drill point.

**Avoid.** The Toolbox coupling — Hole Wizard's real value is Smart Fasteners, which requires a fastener library and an assembly environment bench will not have. Do not let `hole` become the entry point to an aspirational BOM. Also avoid Fusion's habit of hiding countersink *depth* behind the angle and diameter: expose all three and let two of them be derived.

### 3MF for Bambu Studio — *what I read*: [BambuStudio `src/libslic3r/Format/bbs_3mf.cpp`](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/Format/bbs_3mf.cpp) and `src/libslic3r/Model.cpp`

**Adopt.** The file layout is small and stable, and bench can write all of it from pure Python. From `bbs_3mf.cpp:150-190`: `3D/3dmodel.model` (the geometry; "this is the only format of the string which works with CURA"), `Metadata/model_settings.config`, `Metadata/project_settings.config`, `Metadata/slice_info.config`, `[Content_Types].xml`, `_rels/.rels`. The one that matters is **`model_settings.config`**, whose writer (`bbs_3mf.cpp:8208-8265`) emits per object `<object id="N"><metadata key="name" value="…"/>` then every config key as `<metadata key="…" value="…"/>`, then per volume `<part id="M" subtype="normal_part" uuid="…"><metadata key="name" value="…"/>…</part>`. The subtypes are exactly five (`Model.cpp:3633`): `normal_part`, `negative_part`, `modifier_part`, `support_enforcer`, `support_blocker`. And **`extruder` is just another config key**, read back per-object at `bbs_3mf.cpp:2285/2377` and per-volume at `:2390`. So: object names, per-body names, per-body filament, and support blockers are **four metadata lines**, not a project. Write those and a bench 3MF opens in Bambu Studio with the right names in the object list and the right AMS slots pre-assigned.

**Avoid.** Three traps. (i) `paint_color` (`MMU_SEGMENTATION_ATTR`) is per-triangle MMU painting encoded as a base64-ish triangle-split tree — do not generate it; express two-colour parts as **two bodies in one object**, which is both simpler and what the slicer prefers. (ii) `Metadata/project_settings.config` is a full slicer-profile JSON; writing a partial one will silently override the user's process settings. Write no project settings at all, or the smallest possible set, and never a printer profile. (iii) `Metadata/slice_info.config`, thumbnails, `plate_1.png`, gcode — do not fake any of it; that is the slicer's output, and a 3MF that claims to be sliced and is not will confuse the printer's file browser. Also note the `p:UUID` production-extension attributes: Bambu assigns stable `part_guid`s ("Assign one to every model part now so the identity persists across reloads") — bench should mint these **from its own refs**, which is a free win: a ref survives regeneration *and* survives a reload in Bambu Studio.

---

## 3. Tolerances and fit

### Where the numbers live — three layers, and the proposal currently has only a sliver of one

| Layer | Holds | Example |
|---|---|---|
| **`Material` profile** (`model.py`) | Physical facts about the filament + machine: shrink %, printed-hole compensation, minimum wall, max unsupported overhang, max bridge, first-layer spread, layer height | `PLA(hole_comp=0.15, foot=0.25, max_overhang=45°, bridge_max=10.0, layer=0.2)` |
| **`Fit` enum** (`ops.py`) | Intent: how tight this joint should be, as a nominal gap the material scales | `Fit.SLIDE`, `Fit.PRESS` |
| **Per-call override** | The one joint that is special | `hole(..., fit=Fit.SLIDE, clearance=0.35)` |

And critically: **`clearance(fit, material) -> float` must be a public function**, not something only reachable through `hole()`. Scripts (c) and (e) both needed the number for a non-hole feature.

### The table — clearance **per side**, 0.4 mm nozzle, 0.2 mm layer, calibrated flow

| Fit | PLA | PETG | ASA | Feel / use |
|---|---|---|---|---|
| `Fit.INTERFERENCE` | −0.05 | −0.05 | 0.00 | Hole *smaller* than the part. Crush-rib magnet pockets, a dowel that must never move. gridfinity-rebuilt uses exactly this: 6.5 mm magnet hole with ribs at 5.9 mm, "experimentally chosen for a press fit." |
| `Fit.PRESS` | +0.05 | +0.05 | +0.075 | Needs a firm push; friction holds it. Bearings, dowel pins, the fixed end of a hinge pin. |
| `Fit.SNUG` (transition) | +0.10 | +0.125 | +0.15 | Goes together by hand, no slop. Locating pins, a lid registration lip. |
| `Fit.SLIDE` (running) | +0.20 | +0.25 | +0.30 | Moves freely with minimal wobble. Hinge pin in a bore, drawers, the collar on a drill shank. |
| `Fit.CLEARANCE` (free) | +0.30 | +0.35 | +0.40 | Drops in. A bolt through a bracket, a bin in a baseplate (Gridfinity's own 0.5 mm grid gap = 0.25/side). |
| `Fit.LOOSE` | +0.50 | +0.55 | +0.60 | Alignment features that must never bind, cable pass-throughs. |
| `Fit.SNAP` | +0.30 **and a flexure** | — | — | The gap is not what latches; arm length, wall count and deflection are. Do not let a fit enum pretend otherwise. |
| print-in-place | 0.30–0.40 **total**, and never on layer 1 | | | The first layer squishes sideways and fuses. Raise the joint off the plate or add elephant's-foot compensation. |

Non-fit constants that belong in the material profile:

| Quantity | PLA | PETG | ASA | Note |
|---|---|---|---|---|
| Printed-hole undersize (diameter) | 0.20 | 0.25 | 0.30 | Arc compression: the extruder pulls inward tracing a circle. The proposal's "0.2–0.4 mm small" is right; make it per-material. Applies to the **hole only**, never to the pin. |
| First-layer spread (elephant's foot) | 0.15 | 0.20 | 0.25 | Fix with an automatic 0.4–0.6 mm × 45° bottom chamfer on the footprint, exposed as `foot_chamfer` on a Part — **not** as a number the maker sprinkles. |
| Thermal shrink | 0.3 % | 0.4 % | 0.7 % | Matters past ~150 mm. On a 350 mm H2D part, 0.7 % is 2.4 mm. |
| Min wall (0.4 nozzle) | 0.86 (2 perim) | 0.86 | 1.2 | `assert_wall` should default to this, not to a guess. |
| Max unsupported overhang | 45° from vertical | 45° | 40° | |
| Max reliable bridge | 10 mm | 8 mm | 6 mm | |

### Fastener table (the numbers `hole(screw=...)` must contain)

| | M2 | M2.5 | M3 | M4 | M5 | M6 |
|---|---|---|---|---|---|---|
| Clearance, close | 2.2 | 2.7 | 3.2 | 4.3 | 5.3 | 6.4 |
| Clearance, normal | 2.4 | 2.9 | 3.4 | 4.5 | 5.5 | 6.6 |
| Clearance, loose | 2.6 | 3.1 | 3.6 | 4.8 | 5.8 | 7.0 |
| Tap drill (metal) | 1.6 | 2.05 | 2.5 | 3.3 | 4.2 | 5.0 |
| **Self-tap into plastic** | 1.7 | 2.2 | 2.6 | 3.4 | 4.3 | 5.2 |
| **Heat-set insert bore** | 3.1 | 3.8 | **4.0–4.2** | **5.6** | **6.8** | 8.2 |
| Socket-cap head Ø | 3.8 | 4.5 | 5.5 | 7.0 | 8.5 | 10.0 |
| Counterbore Ø × depth | 4.3×2.2 | 5.0×2.7 | 6.2×3.2 | 7.6×4.2 | 9.2×5.2 | 10.8×6.2 |
| Countersink Ø (90°) | 4.4 | 5.5 | 6.3 | 8.4 | 10.4 | 12.6 |
| Hex nut A/F (trap) | 4.0 (4.1) | 5.0 (5.1) | 5.5 (5.6) | 7.0 (7.2) | 8.0 (8.2) | 10.0 (10.2) |
| Nut trap depth | 1.7 | 2.1 | 2.6 | 3.4 | 4.4 | 5.4 |

Insert bores cross-checked against [InsertGuide](https://insertguide.com/guides/heat-set-insert-hole-size/) (M2 3.1, M2.5 3.8, M3 4.2, M4 5.6, M5 6.8, M6 8.2), with the caveat their guide makes explicitly and bench should surface in a docstring: *"Design the hole from the insert's outer diameter and external geometry,"* not from the screw size — so the table entry must be keyed on an insert *part*, not on `M3`.

Note: every clearance figure above is the nominal metal number. The printed-hole compensation is applied **on top**, by the material profile, which is why it must be a separate field and not baked into the table.

### The horizontal-hole rule, stated so it can be implemented

**Precondition:** the part must carry a print orientation (`up: Vector`). Without it this rule is not computable — see gap 3.

Let θ be the angle between the hole axis and the build direction `up`.

- **θ < 30°** — near-vertical. Nothing needed; the hole is a stack of circles.
- **θ ≥ 30°** — the top of the bore has an unsupported arc. Two remedies, chosen by diameter and by whether roundness matters:

  - **Teardrop** (default, use when the hole is a clearance hole). Replace the upper arc with two lines tangent to the circle at the ±45°-from-top points, meeting at an apex directly above the centre at **r·√2**. Every surface is then ≤45° from vertical. Optionally truncate the apex flat (a "flat-top teardrop") so it does not leave a ridge where it breaks a top surface.
  - **Bridged top** (use when the hole must stay round — a bearing seat, a magnet pocket, a dowel bore). Keep the circle and add a stepped cutout above it so the slicer has a straight span to print onto: `n = 3` layers of `layer_height`, each a square rotated 90° from the last, stepping from the bore diameter out to the counterbore diameter. This is `make_hole_printable(inner_radius, outer_radius, outer_height, layers=3)` in gridfinity-rebuilt, and it is the technique behind their `printable_hole_top` flag.

- **Diameter thresholds** (material-profile numbers, not constants): Ø ≤ 4 mm — neither is needed, the unsupported span is short enough. 4 < Ø ≤ `bridge_max` (10 mm PLA) — bridge if round matters, teardrop otherwise. Ø > `bridge_max` — teardrop is mandatory.

**API shape:** `hole(solid, on=..., at=..., screw=M4, fit=Fit.CLEARANCE, top=Top.AUTO)` where `Top ∈ {AUTO, ROUND, TEARDROP, BRIDGE}` and `AUTO` applies the rule above. `AUTO` on a part with no declared orientation should **raise**, with the message "this part has no print orientation, so `top=Top.AUTO` cannot tell which way is up" — that is an excellent error, and exactly the kind of thing the proposal's assertion philosophy is for.

---

## 4. Multi-material and the AMS

**Does the proposal accommodate it? No — nothing at all.** The only mention is one clause: `export.py: binary STL and 3MF (part names, multi-body)`. Multi-body means several meshes in one file; it says nothing about which filament any of them prints in. There is no colour, no extruder, no AMS slot, and — separately — **no way to make the second body in the first place**, because there is no `text_solid` / `emboss` verb (fonttools is listed as giving "glyph outlines" so "labels can be embossed", which is a note, not an API).

### The minimum that would work

Four small changes, and they compose:

1. **A `Body` record and an `Object` that holds several.**
   ```python
   Role = Literal["part", "negative", "modifier", "support_blocker", "support_enforcer"]
   @dataclass(frozen=True, slots=True)
   class Body:
       label: Label
       solid: Solid
       filament: int | None = None      # 1-based AMS slot
       role: Role = "part"
   ```
   Those five role values are Bambu's own `subtype` strings (`Model.cpp:3633`), so no translation layer is needed. `Part` gains `bodies: tuple[Body, ...]` or, cleaner, a `Printed` sibling of `Part` whose `stock` is a `Material` and whose shape is a tuple of `Body`.

2. **One new verb: `text_solid(text, size, depth, *, on: Plane, at: Point) -> Solid`**, built on the fonttools glyph outlines the proposal already plans for. Emboss = `Body(glyphs, filament=2)`; deboss = `difference(body, glyphs)`.

3. **`export.write_3mf(objects, path)`** emitting exactly:
   - `3D/3dmodel.model` — one `<object>` per printed object; each `Body` a `<component objectid=… transform=…/>` pointing at its own mesh object, each with a `p:UUID` minted **from the bench ref** (stable across regeneration *and* across reloads in Bambu Studio).
   - `Metadata/model_settings.config`:
     ```xml
     <object id="1">
       <metadata key="name" value="bin-2x1x3"/>
       <part id="1" subtype="normal_part"><metadata key="name" value="body"/></part>
       <part id="2" subtype="normal_part">
         <metadata key="name" value="label"/>
         <metadata key="extruder" value="2"/>
       </part>
     </object>
     ```
     That `extruder` line is the entire multi-material feature. BambuStudio reads it per-volume at `bbs_3mf.cpp:2390` and writes every object/volume config key the same way at `:8225`/`:8258`.
   - `[Content_Types].xml` and `_rels/.rels` — boilerplate.
   - **No** `project_settings.config`, **no** `slice_info.config`, **no** thumbnails. Those are the slicer's, and writing partial ones overrides the user's process.

4. **A `filament=` keyword on `part()`/`Body`** and nothing else. Do not model the AMS: an integer slot is the whole contract, and the user maps slots to spools in the slicer, where they can already see the colours.

That is roughly 150 lines of pure-Python XML + zip, no dependencies, runs in Pyodide, and it is the difference between "exports a mesh" and "opens in Bambu Studio ready to print in two colours."

**One caveat to write into the docstring:** per-body `extruder` only applies to bodies *within one object*. Two separate objects each carry their own. So "the bin and its label" must be one object with two bodies, not two objects.

---

## 5. The first month's library

Ordered by value, with dependencies noted. The first two are not glamorous and everything else needs them.

**1. `library/print.py` — the print domain itself.** *Must be first; (3) through (9) all import it.*
`Material` profiles (PLA, PETG, ASA, PETG-CF) carrying `shrink`, `hole_comp`, `foot`, `min_wall`, `max_overhang`, `bridge_max`, `layer`, and the fit table; `Fit` enum; `clearance(fit, material) -> float`; `Orient(up, bed_face)`; `Volume(350, 320, 325)` for the H2D plus a `BEDS` table; `teardrop(d)`, `bridge_top(d, layers, layer_h)`, `foot_chamfer(solid, d)`; `assert_fits`, `assert_overhangs`, `assert_wall`, `assert_bridges`.

**2. `library/fasteners.py` — the table as data.**
`M2…M8` with clearance close/normal/loose, tap, self-tap, insert bore, socket/button/flat head Ø and height, counterbore Ø×depth, countersink Ø and angle, hex nut A/F and thickness. Plus objects, not just numbers: `Insert(kind, od, length, bore)` (because an insert bore is keyed on the insert, not the screw), `NutTrap(size, style=hex|square, captive=True, lead_in=0.4)`, `Magnet(d=6, h=2, hole=6.5, ribs=8, rib_d=5.9)`.

**3. `library/gridfinity3d.py` — bins and baseplates.** *The proof, and the thing that retires `baseplate_scad()`.*
Bins: `units_x`, `units_y`, `height` as a union of four meanings (`Units(n)` / `Internal(mm)` / `External(mm)` / `ExternalWithLip(mm)`), `lip`, `wall=1.2`, `floor`, `divisions=(x, y)` or explicit compartments, `scoop: float 0..1`, `label_tab: none|left|center|right|full` with `tab_width`, `tab_depth=15.85`, `tab_angle=36°`, `magnets`, `screws`, `crush_ribs`, `chamfer_holes`, `printable_hole_top`, `only_corners`, `half_grid`, `solid`, `fit=Fit.CLEARANCE`. Baseplates: `style: thin|weighted|skeletonized|screw_together|screw_together_minimal`, `magnets`, `mount_hole: none|countersink|counterbore` with screw size, and **`fit_to(width, depth, align=(x, y))`** — pad out to a drawer and choose where the slack lands. Expose the profile constants publicly (`BASE_PROFILE`, `STACKING_LIP`, `GRID = 42`, `BASE_TOP = 41.5`) so other modules can build against them.

**4. `library/boxes.py` — parametric enclosure.** *The most-printed shop object after bins.*
`outer_w/d/h`, `wall`, `floor`, `corner_r`, `lid: lip|step|tongue|slide` with `lip_height` and `lip_fit=Fit.SLIDE`, `insert_bosses` (count/positions/insert/boss_wall), `pcb(hole_points, standoff_h, standoff_d, screw)`, `vents(pattern, area)`, `cutouts(tuple of (face, rect|circle, at))`, `foot_chamfer`, `split: none|horizontal(z)`.

**5. `library/brackets.py` — L-brackets, shelf brackets, pipe clamps.**
`legs=(a, b)`, `t`, `width`, `gusset: none|triangle(h)|fillet(r)`, `holes(count, pitch, screw, fit, countersink)`, `saddle(od, wrap_angle, split, pinch_screw)`, `orient` (because a bracket's strength is entirely about which way the layers run — this module is where `Orient` earns its keep).

**6. `library/mounts.py` — how a thing attaches to a wall.**
Pegboard (1 in / 25 mm hook geometry), French cleat (30°/45°, length), VESA 75/100, DIN rail clip, Gridfinity back-plate, keyhole slot (screw head Ø, shank Ø, drop).

**7. `library/threads.py` — printed threads.**
ISO metric external and internal (M4…M40), trapezoidal, and a bottle/jar thread. Parameters: `d`, `pitch`, `length`, `handedness`, `starts`, `clearance` (a *printed* thread needs 0.15–0.25 mm of flank clearance or it binds), `lead_in_chamfer`. Justification: "thread a knob / a levelling foot / a lid" is week-two work, and `hole(fit="tapped")` is a metalworking answer to a plastic question.

**8. `library/text3d.py` — embossed and debossed labels.**
`emboss(solid, text, *, font, size, depth, on, at, align)` and `deboss(...)`, returning a `Body` so the second-filament path in §4 is one keyword away. Also `text_outline(text, size, font) -> Wire`, which retires `text_width`'s 0.6-of-cap-height estimate and its known limit in `DESIGN.md`.

**9. `library/joints3d.py` — printed joinery.**
Hinge (knuckle count, pin Ø, `Fit.SLIDE`, leaf thickness, rim chamfer), cantilever snap-fit sized from *deflection and strain limit* rather than from a guessed gap (this is the calculation makers get wrong and the one place a library adds real engineering), dovetail, nut-trap join, dogbone for a CNC-cut mate.

---

## 6. Ranked gaps the proposal must close

Ranked by "would a maker choose this over Fusion for these five parts."

1. **Solids have no named faces or edges, and nothing names what a boolean creates.** `ref("plate/top")` is asserted five times and defined nowhere. Needed: (a) a documented auto-naming scheme for every primitive's faces (extrude → `top`/`bottom`/`side`; revolve → `start`/`end`/`lateral`; box → `x-`/`x+`/…; and what happens to `side` when a boss splits it); (b) predicate selectors on solids — `faces(solid, normal=Z, topmost=True)`, `edges(solid, convexity=CONCAVE, between=(a, b))` — because Onshape is right that queries survive parameter changes and stored references do not; (c) a `Select.NEW`-equivalent for edges a boolean created. Blocks (b) and (d); degrades all five.

2. **`fillet`/`chamfer` on solid edges is in the verb list with no kernel and no selector.** This is the reason people leave OpenSCAD. If Manifold really cannot do it (proposal's own Q2), say so in the document and give the maker the honest alternative — fillet the profile before extruding, gussets instead of fillets, `minkowski`-style rounding for the whole part — rather than listing a verb that cannot be implemented. A bracket without a fillet at the ear is an OpenSCAD part, and a maker can already get one of those for free.

3. **No print orientation in the model.** Every print-specific behaviour the proposal claims — orientation-aware holes, teardrops, overhang shading, elephant's foot, support, layer-direction strength — needs one vector per part. Without it, "a horizontal hole gets a teardrop" is a sentence with no referent. Smallest fix: `Orient(up: Vector, bed_face: Ref | None)` on a printed part, defaulting to `+Z`, and `Top.AUTO` raising a good error when it is absent.

4. **Operation composition is unstated, and the proposal's own example does not compose.** Frozen records with a mutating-looking API (`into=`, `onto=`, bare `hole(...)`) is a trap. Decide and write it down. My recommendation: delete `into=`/`onto=`, keep `through=`/`until=`, make `hole(solid, ...) -> Solid`.

5. **No tolerance surface outside `hole()`.** `fit` is a bare string with three named values, reachable only through one function, and every mating feature that is not a fastener hole — a lid lip, a hinge bore, a nut trap, a snap — is left to hand-typed millimetres. Needed: a `Fit` enum, a `Material` profile that owns the table, and a public `clearance(fit, material)`. Plus `hole(diameter=)` for bores that are not fasteners, and an insert *kind* separate from the fit.

6. **No multi-body / multi-material 3MF.** One `<metadata key="extruder" value="2"/>` line is the difference between "exports a mesh" and "prints in two colours on the AMS." Needs a `Body` record with `filament` and `role`, and a `text_solid` verb to make the second body with.

7. **No plate, no print job.** `nest` refuses solids; `Placed.on` poses nothing (`DESIGN.md`, Known limits). Printing 12 bins or a three-part hinge has nowhere to happen. `Volume` and `assert_fits` are a start but not a layout. This is the 3D analogue of `nest` and it is missing from the plan entirely — as is any filament/mass/time estimate, which is the first number a maker looks at.

8. **The assertions do not run where the product is.** Open question 1 is the right question and the answer matters more than the proposal implies: if `assert_clearance`/`assert_wall`/`assert_fits` only run on the CLI, the browser — which *is* the product — loses the half of the pitch that says "an assertion in a script is a property test on the physical object." Recommendation: tier them explicitly. Tree-level checks (bbox, parameter rules, wall thickness known by construction, build-volume fit) in Python, everywhere. Mesh-level checks in the worker, reported back onto the scene as warnings with the script line attached. Say which tier each `assert_*` is in, in the signature.

9. **Missing primitives, each small, each blocking.** `hull` (verb for an existing node), 3D `offset` (same), `sweep`/`loft`, 3D `rotate` about an arbitrary axis (`ops.rotate` is hard-coded to Z while `geometry.rotation(Axis, angle)` already generalises), a grid/polar `pattern`, a pattern with stride, and a way to raise a sketch plane (`XY.at(z)`). Every one of the five scripts hit at least two of these.

10. **`Part` has no shape for a printed thing.** `Part.stock: Stock(thickness, material, kerf)` — none of the three means anything for a print. The proposal says `Material` goes "beside `Stock`" but not what `Part` holds. Decide: `stock: Stock | Material`, or a separate `Printed` record.

11. **No threads, no nut traps.** `fit="tapped"` gives a metal tap drill. Makers use printed threads, heat-set inserts or captive nuts, in roughly that order of frequency, and only the middle one is in the plan.

12. **Text is an estimate.** `text_width`'s flat 0.6-of-cap-height is a documented limit for engraving, and it is fatal for embossing, where the glyph outline *is* the geometry. fonttools is already in the plan; make it a verb, not a footnote.

**On the proposal's sequencing question (its Q4):** "baseplate first as proof, then WASM+viewer, then fasteners and materials, then text" puts materials and fasteners third. They should be **first**. The baseplate is not actually a proof of anything a maker cares about — it has no fasteners, no fits, no orientation problem and no named edges. The honest proof-of-concept is **part (b), the pipe bracket**: it needs a face plane, a named new edge, a fillet, two fastener holes with a fit, an orientation and an overhang check. If the architecture can build the bracket, it can build everything else. If it cannot, the baseplate ships and the product still is not usable for shop parts.

**On its Q5 (separate `bench3d` package):** same layers grown, but with the print domain factored into `library/print.py` rather than smeared across `model.py` and `ops.py`. The fit table, the material profiles and the orientation record are a *domain*, not a handful of fields — and keeping them in a library module means the layer-graph test in `tests/unit/test_layer_graph.py` enforces that `ops` does not quietly learn about filament.

---

### Sources

- [build123d — Key Concepts](https://build123d.readthedocs.io/en/latest/key_concepts.html), [Topology Selection and Exploration](https://build123d.readthedocs.io/en/latest/topology_selection.html), [Operations](https://build123d.readthedocs.io/en/latest/operations.html), [Objects](https://build123d.readthedocs.io/en/latest/objects.html), [Cheat Sheet](https://build123d.readthedocs.io/en/latest/cheat_sheet.html)
- [CadQuery — Selectors](https://cadquery.readthedocs.io/en/latest/selectors.html)
- [gridfinity-rebuilt-openscad](https://github.com/kennetek/gridfinity-rebuilt-openscad) — `README.md`, `gridfinity-rebuilt-bins.scad`, `gridfinity-rebuilt-baseplate.scad`, `src/core/standard.scad`, `src/core/gridfinity-rebuilt-holes.scad`
- [Onshape FeatureScript documentation](https://cad.onshape.com/FsDoc/) — [Defining feature types](https://cad.onshape.com/FsDoc/feature-types.html), [Feature UI](https://cad.onshape.com/FsDoc/uispec.html), [Modeling](https://cad.onshape.com/FsDoc/modeling.html)
- [Hawk Ridge Systems — Deep Dive into SOLIDWORKS Hole Wizard](https://hawkridgesys.com/blog/deep-dive-solidworks-hole-wizard)
- [BambuStudio — `src/libslic3r/Format/bbs_3mf.cpp`](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/Format/bbs_3mf.cpp) and [`src/libslic3r/Model.cpp`](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/Model.cpp)
- [OpenSCAD cheat sheet](https://openscad.org/cheatsheet/index.html)
- [Sovol — FDM 3D Printing Tolerances & Clearances](https://www.sovol3d.com/blogs/news/fdm-3d-printing-tolerances-clearances-how-to-design-parts-that-fit)
- [InsertGuide — Heat Set Insert Hole Size Guide](https://insertguide.com/guides/heat-set-insert-hole-size/)

Notes and the five annotated scripts: `/tmp/claude-0/review-maker3d/`.