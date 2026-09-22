---
id: doc-1
title: 3D review - kernel and runtime feasibility
type: other
created_date: '2026-09-22 19:47'
---

# 3D review - kernel and runtime feasibility (opus, 2026-09-13)

Condensed from the reviewer's report; measurements are theirs, taken in
this sandbox with manifold-3d 3.5.3 (npm), manifold3d 3.5.3 (PyPI), Pyodide
314.0.6, Node 22, OpenCascade.js 1.1.1, and scikit-image marching cubes.

## Manifold works, and face identity survives booleans exactly

- `manifold.wasm` is 532 KB; load + setup 17-26 ms. The proposal's plate +
  boss + pocket + countersink: 56 ms cold, 13 ms warm, 840 triangles.
- Tagging: round-trip the mesh through `getMesh()`, write `faceID` per
  triangle, one `reserveIDs(1)` per labelled primitive as `runOriginalID`,
  rebuild with `Manifold.ofMesh`. After union, difference and a countersink
  the tagged top face matched the geometric top face with **zero**
  mismatches at every step; area accounting exact (boss footprint 200.74 =
  pi * 8^2). 20 chained hole cuts: still exact.
- **Key on `(runOriginalID, faceID)`, never `faceID` alone**: auto faceIDs are
  source-triangle indices, so a hand-picked tag collides silently with a
  primitive of more than that many triangles.
- **`Manifold.rayCast` is unusable for click-to-ref** (0/684 correct on a
  composite); raycast in three.js against the geometry built from
  `getMesh()` and index `faceID` by the hit triangle. `minGap` is sound and
  fast (1.8 ms).
- Identity is destroyed by `hull`, `minkowskiSum/Difference`, `asOriginal`;
  preserved by `refine*`, `smoothOut`, `warp`; partially by `simplify`.
- Scale: Gridfinity baseplate 2x2 123 ms, 6x4 337 ms, 8x7 (336 x 294 mm)
  770 ms + 40 ms re-tag.
- CLI parity: `manifold3d` gives identical volume, triangle count and tagged
  areas to three decimals. Gotcha: `np.array(mesh.vert_properties, copy=True)`.

## Do not build manifold3d for Pyodide - call the JS kernel from Python

- No emscripten/pyodide wheel exists on PyPI or in the Pyodide index; upstream
  disables Python bindings under emscripten in CMake; nanobind has no
  emscripten branch. A build attempt hit seven blockers (CMake guards, TBB,
  JSBIND, a wasm32 `size_t` narrowing bug, argument-list limits, and
  SIDE_MODULE feature flags) and would have to be redone against every
  Pyodide alpha bump. Research project, not a task.
- **Pyodide's Python can call a JS-side Manifold synchronously in the same
  worker**: 63 microseconds per round trip including JSON-encoding the tree;
  errors surface as catchable Python `JsException`. So Python-side checks
  (`clearance`, `wall`) run in the browser with no message round trip.
- Recommendation: a `Kernel` protocol (`mesh`, `volume`, `min_gap`) injected
  into `run()` like `param`/`show`/`extras`; the browser binds it to JS
  Manifold, the CLI to `manifold3d`; no module under `src/bench` imports a
  kernel; the adapter layer runs the same tree through both and asserts
  equal volume, triangle count and per-ref area.

## Fillet, chamfer, shell, hull

- Manifold has no fillet and no 3D offset. Vertical-edge fillet/chamfer:
  `CrossSection.offset(r, Round)` on the profile then extrude - 0.5 ms,
  exact, refs survive. Shell of a prism: subtract the inset-profile
  extrusion - 6 ms, exact, refs survive. Chamfer on a named straight edge:
  `trimByPlane` or a knife subtraction - 2-3 ms, refs survive. Chamfer on the
  whole top rim: hull-loft, exact for convex profiles only (silently fills
  concavities) and destroys refs. Round-all-edges via Minkowski: 2.4-6.3 s,
  destroys refs.
- `Hull` and `Offset` must be leaf-forming nodes re-tagged from intent
  (11 ms scan + 28 ms rebuild at 20k triangles). General 3D fillet: not in
  v1; say so.

## Export

- Manifold ships no STL writer and its 3MF writer has no colours, a broken
  `setMaterial`, and one build item for everything. Write both ourselves:
  binary STL 57 ms (volume by divergence theorem equals Manifold's to 0.1
  mm^3), 3MF 18 ms with one object per part and `unit="millimeter"`.

## Alternatives, ranked against browser-without-server / names survive / pure core

1. Manifold at the edges - loses only true fillets.
2. SDF in Pyodide - 100 mm bracket at 0.2 mm: 30 M samples, 7.3 s and 1.2 GB
   on native CPython; no faces to name.
3. OpenCascade.js - 65.9 MB wasm, 1.2-2.1 s init, real fillets (30 edges in
   155 ms) and STEP; TS-only, no Python path.
4. build123d on the CLI - requires-python <3.15, and splits browser from CLI.

## Sequencing and packaging

Kernel seam first on one trivial part with the two-kernel adapter test as
acceptance; then the baseplate; then holes/fasteners/materials; then
sketch-level chamfer/fillet, shell, named-edge chamfer; then text and the
assembled view. Same package, plus `kernel.py` and `checks.py`; the rule
"no module under src/bench imports a kernel" goes in the pypeeker table.

Risks ranked: refs die on hull/offset (so chamfer/fillet must be sketch-level
or leaf-forming); faceID collision (keyed pair fixes it); rayCast trap; Pyodide
pin drift (only bites the wheel route); 770 ms bed-sized parts; broken
`setMaterial`; no true fillet ever on this kernel.
