---
id: decision-1
title: bench for 3D printing
date: '2026-09-22 19:47'
status: accepted
---

# Proposal - bench for 3D printing (v2, after review)

Status (2026-09-15): steps 1-5 implemented (commits `3d step 1` to `3d step 5`,
2026-09-13/14). Since then step 2's `manifold3d` CLI adapter and its parity test were
removed: the one kernel is Python in the browser driving Manifold's WASM build. Laser
parts are now drawn as plates in the same 3D view (`bench.plates`). What genuinely
remains of step 6 is text via fonttools, a print-bed plate layout (the 3D `nest`), and
closing the `Stock` union. The rest of this record is the proposal as decided.
Reviewed by three opus passes on 2026-09-13 - kernel feasibility (with
measurements), API and dialect fit (with type-checked sketches), and the
maker's lens with prior art. Full notes in `backlog/docs/` (doc-1 to doc-3). This
version records what the reviews settled and what is still the owner's call.

## Settled by evidence

**Kernel: Manifold, evaluated at the edges, called synchronously from Python
in the browser.** 532 KB WASM, 17 ms load, 13-770 ms per model up to a
bed-sized baseplate. Face identity survives `union`, `difference`,
`intersection` and `Moved` exactly (zero mismatches through a boss, a pocket
and a countersink; twenty chained cuts) when keyed on `(runOriginalID,
faceID)` with one reserved ID per labelled primitive. It does not survive
`hull`, Minkowski or `asOriginal`. `Manifold.rayCast` is not usable for
click-to-ref; raycast in three.js against our own geometry instead. CLI
parity with `manifold3d` is exact to three decimals. There is no `manifold3d`
wheel for Pyodide and building one is a research project; but Pyodide's
Python can call the JS-side kernel synchronously in the same worker at 63 us
per round trip, so Python-side checks run in the browser. Manifold writes no
STL and its 3MF is unusable for us; we write both (57 ms and 18 ms).

**Alternatives rejected with numbers.** SDF in Pyodide: 7.3 s and 1.2 GB for
one 100 mm bracket at 0.2 mm, no faces to name. OpenCascade.js: real
fillets and STEP, 65.9 MB and 1.5 s init, no Python path. build123d:
requires-python < 3.15 and splits browser from CLI.

**No true 3D fillet on this kernel, ever.** Vertical-edge fillets and
chamfers are sketch-level (offset the profile with round joins, then
extrude: 0.5 ms, exact, refs survive). Shell of a prism is an inset-profile
subtraction (exact, refs survive). A chamfer on a named straight edge is a
plane trim. A chamfer on a whole convex top rim is a hull-loft that loses
refs. Round-all-edges is Minkowski at 2-6 s and loses refs: not in v1.

## Settled by design review (the API reviewer's twelve, adopted)

1. `Solid` holds a `Node`; `Shape` stays `Face | Solid`. Labels live only on
   `Solid`; combining nodes take `Solid` operands; `Moved` takes a `Node`.
2. Nodes: `Extrude`, `Revolve`, `Union`, `Difference`, `Intersection`,
   `Hull` (leaf for naming), `Moved`. No `Box`/`Cylinder`/`Offset` nodes.
3. `extrude` and `revolve` make bodies. Booleans are explicit: `union(a, b)`,
   `cut(base, tool, *, label)` (the 2D `cut`'s second arm; the label goes on
   the tool), `common(a, b)`. `pocket` and `boss` as a thin sugar tier. No
   `into=`/`onto=`/`through=`.
4. Face naming, computable from the tree alone: `L/top`, `L/bottom`,
   `L/side-<edge label or index>`, `L/<hole label>` for an extrusion;
   `side-<e>`, `start`, `end` for a revolve; operands keep their own paths
   under a boolean; a hull is `L` only; `Moved` renames nothing. A pocket's
   floor is `L/pocket/bottom`. At most one anonymous body per part.
   `side-` is load-bearing because `open_box` edges are already labelled
   `top`/`bottom`.
5. `plane_of(solid, "top")`, never `plane_of(ref(...))` (a `Ref` has no
   root). A named face's local coordinates are the profile's own, so a
   sketch placed `on=plane_of(plate, "top")` uses the plate's numbers.
6. `hole(subject: Shape, at, *, on, screw | diameter, fit, depth, countersink,
   counterbore, top, label) -> Shape` - one verb over the closed union,
   returns the modified subject; cuts a circle in a face, a bore in a solid.
7. Checks return `Violation` records collected like warnings, recorded
   through injected closures with the script's line number; `require()`
   raises for the script that wants to stop; a check that needs a kernel
   answers `UNCHECKED` without one. `solve(residuals, start)` raises on
   non-convergence.
8. `Kernel` is a Protocol (`mesh`, `volume`, `min_gap`) injected into
   `run(..., kernel=None)`; `Mesh` is a flat-float transport record; no
   module under `src/bench` imports a kernel (a pypeeker row). The tree
   crosses the wire as a flat SSA list with refs already resolved; a run
   without a kernel still yields refs, params and cut sheets.
9. `bbox` stays 2D; `bounds(shape) -> Bounds` is the 3D query, conservative
   under `Difference`.
10. `fillet(wire, at, r)` as the twin of `chamfer(wire, at, d)`; `loft` for
    tapers; nothing named `fillet`/`chamfer` takes a `Solid`.
11. `mirror(shape, across: Axis | Plane)`; `pattern(shape, count, step:
    Vector | Turn)` plus a grid form; `rotate` about any axis (today it is
    Z-only, and every maker script wanted the general case).
12. Same package, grown: `kernel.py`, `checks.py`, `fasteners.py`; the print
    domain in `library/print.py` rather than smeared across `model` and `ops`.

## Settled by the maker's review (adopted)

- **A printed part carries an orientation**: `Orient(up: Vector, bed_face)`,
  default `+Z`. Every print-aware behaviour (teardrop, bridge, overhang
  check, elephant's-foot chamfer, layer-direction) refers to it;
  `top=Top.AUTO` on a part with no orientation raises a good error.
- **Fits are a domain, not a string.** `Fit` enum (`INTERFERENCE`, `PRESS`,
  `SNUG`, `SLIDE`, `CLEARANCE`, `LOOSE`), a public `clearance(fit, material)
  -> float` (per side), material profiles with printed-hole undersize,
  first-layer spread, shrink, min wall, max overhang, max bridge, layer
  height, and per-call override. The review's table (PLA/PETG/ASA, 0.4 mm
  nozzle) is the starting data.
- **Holes have kinds beyond fit**: `diameter=` for a non-fastener bore,
  `Insert` keyed on the insert's OD (not a fit of the screw), `NutTrap`,
  self-tap into plastic (not the metal tap drill), countersink angle and
  depth exposed. Horizontal holes: teardrop by default, bridged top when
  roundness matters, thresholds from the material profile.
- **Multi-material is one line of 3MF**: `Body(label, solid, filament: int |
  None, role)` with Bambu's own subtype strings; `Metadata/model_settings.
  config` carries `<metadata key="extruder" value="2"/>` per body; two-colour
  parts are two bodies in one object. Never write `project_settings.config`.
- **Text is a verb, not a footnote**: fonttools glyph outlines ->
  `text_solid`/`emboss`/`deboss`, and `text_outline` retires the 0.6
  estimate.
- **A plate layout is the 3D `nest`** and is missing from v1's plan; it is
  where multi-part prints and the assembled view meet.
- **Missing small primitives every script hit**: `hull` as a verb, a way to
  raise a sketch plane (`XY.at(z)`), grid and polar patterns with stride,
  `sweep`/`loft` for lips and scoops.
- **Library order**: `print.py` (materials, fits, orientation, checks),
  `fasteners.py`, `gridfinity3d.py` (with gridfinity-rebuilt's parameter
  list, including the four meanings of height and printable magnet holes),
  `boxes.py`, `brackets.py`, `mounts.py`, `threads.py`, `text3d.py`,
  `joints3d.py`.

## Sequencing (reconciled)

The three reviews disagreed on what goes first; this order takes the
strongest argument from each.

1. **Tree, naming rule, `faces_of`, `bounds`, `index()` on solids - no kernel.**
   A scene that lists `plate/top` and renders nothing is testable in all
   four layers and pins the contract everything downstream reads. Click-to-
   ref is the product; it is cheapest to get right while there is nothing to
   click. (API reviewer.)
2. **The kernel seam on one trivial part**: `Kernel` protocol, `manifold3d`
   adapter on the CLI, JS Manifold in the worker called synchronously from
   Python, STL out, and the adapter test that runs one tree through both
   kernels and asserts equal volume, triangle count and per-ref area. This
   retires the three biggest risks at once. (Kernel reviewer.)
3. **Two proofs, not one**: the pipe bracket (face plane, a fastener hole
   with a fit, an orientation, an overhang check, a gusset instead of the
   fillet it cannot have) and the Gridfinity bin (hull profiles, patterns,
   a printable magnet pocket). The baseplate alone proves too little.
   (Maker reviewer.)
4. **The print domain**: `Orient`, `Fit`, materials, `fasteners.py`,
   `hole` kinds, the checks.
5. **3MF with bodies and filament slots**, then the three.js viewer with
   click-to-ref on faces.
6. **Text via fonttools; plate layout; close the `Stock` union** (`Plate |
   Filament | Billet`, delete `Part.process`) once the shape has settled.

## Still the owner's call

- Whether `pattern` grows a `Turn` union or a separate `pattern_around`.
- Whether a pocket's floor is called `bottom` (computable) or the naming rule
  stores overrides to allow `floor`.
- Whether to close the `Stock` union now (invasive, correct) or in step 6.
- Whether the first library after `print`/`fasteners` is `gridfinity3d`
  (the proof) or `boxes` (the most-printed object).
- The `Fit` names and the numbers in the table - they are a starting point
  from one reviewer's sources, not measured on the H2D.
