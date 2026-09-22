---
id: decision-8
title: An imported mesh is a Solid leaf, like any other
date: '2026-09-22 04:00'
status: proposed
---

# Proposal - an imported mesh is a Solid leaf, like any other

**Corrected by implementation (task-43).** This proposal writes the node as `Imported(mesh:
Mesh)` throughout, and that spelling cannot be built: `[tool.pypeeker.import-boundaries]`
has `topology = ["geometry"]` while `kernel = ["geometry", "topology", "model"]` already
imports `topology`, so `topology` importing `kernel.Mesh` is a cycle - and moving `Mesh`
itself down below `topology` is separately blocked, because `Mesh.refs` is
`tuple[Ref | None, ...]` and `Ref` lives in `model`, above `topology` too. There is no edge
in the layer table that makes `Imported(mesh: Mesh)` legal, and this was found by trying to
build it, not by reasoning about it in advance - this proposal's own research missed it.

What shipped instead: `Imported(vertices: tuple[float, ...], triangles: tuple[int, ...])` -
`Mesh`'s own flat layout, unpacked, with `refs` dropped. Dropping `refs` is this proposal's
own argument applied one level down: an import names nothing under it, the same as `Hull`,
so the field that would have carried names has nothing to carry. Read every mention of
`Imported(mesh: Mesh)` or `Solid(Imported(reference))` below as historical - the shape the
proposal first reached for - not as what exists. `src/bench/imported.py`'s `imported(mesh,
*, label=None) -> Solid` is the constructor a script actually calls, and it is the one place
that unpacks a `Mesh` into the two tuples the node holds.

task-39, found while reverse-engineering a real object into bench code. A candidate
`Solid` a script builds cannot be boolean-compared against the raw mesh a maker dropped on
the view - `reference: Mesh | None` is already bound into a script's namespace (decision-4,
task-26), but nothing in `Solid`'s recipe tree can hold one.

## Why

Survey-diffing - comparing two `survey()` reports number by number - already caught a real
mistake cheaply during this reverse-engineering session: a candidate's own section outlines
read as two per height where the reference read one, which is a topology difference no
amount of staring at areas would have named as fast. That check is coarse on purpose and
earns its keep being coarse. What it cannot do is answer "does my candidate occupy the same
volume as the reference" once the coarse numbers already agree - two shapes can share an
identical extent, identical section areas and an identical wall-thickness distribution while
still not being the same shape, and only a boolean intersection tells them apart. That is
the gap this proposal closes.

## The shape

**`Imported` joins `Node`, not beside it.** `Node = Extrude | Revolve | Union | Difference |
Intersection | Hull | Moved` (`topology.py`) is what a dispatch matching the *whole* union
ends in `assert_never` over - checked directly rather than assumed, since several things
that look like a ninth or tenth site turn out not to be. Every `match node:` in the package
was read, not counted from its name: `topology.py`'s `profile_frame`, `_first_side` and
`_flat_frame` each take `Extrude | Revolve`, a narrower type that was already exhaustive and
stays exhaustive - `Imported` cannot reach them and they need nothing. `model.py`'s
`_children` matches over `Named`, and its `Solid` case hands the recipe straight to
`node_children` - it inherits correctness the moment `node_children` has its own case, and
needs no case of its own. **Four sites genuinely match the full `Node` union and need one:**
`node_children` and `_node_points` in `topology.py`, `_extruded_root` in `features.py`, and
`_node` in `adapters/browser.py`'s `JsKernel`. `Imported(mesh: Mesh)` becomes a case at each
of those four, the same shape as adding `Curved` or `SolidFace` already was.

**A fifth site, `_cloud` in `adapters/browser.py`, also matches over `Node` and needs
nothing added - which is worth saying, because it is evidence the design already composes.**
`Hull`'s own point-cloud gathering special-cases `Moved` and a flat `Extrude`, and falls
back to *building the node and reading its mesh's own vertices* for anything else. An
`Imported` leaf inside a `Hull` falls into that fallback automatically and correctly - the
same as any future node this catch-all has never heard of - without anyone having to
remember to add it a fifth time.

```python
Imported(reference)  # a Solid leaf, once wrapped: Solid(Imported(reference))
```

is then a `Solid` like any other, usable everywhere one is: `union`, `difference`,
`intersection`, `hull`, `kernel.volume`, `kernel.min_gap`, `check_clearance`,
`check_contact`. This is not an accident of the implementation - it is the position this
proposal takes on purpose, argued below, because the alternative (a narrower `Imported`
that only `Intersection` and `volume` may touch) turns out to need *more* code, not less.

**Crossing the mesh is `Hull`'s own pattern, not a new one.** `Hull` already crosses a raw
point cloud to the kernel as `array[float]` buffers (`_hulled`, `adapters/browser.py`) -
the module's own established convention for "bulk numbers, not a tree, cross here."
`Imported` crosses the same way: vertices and triangle indices as two buffers, to a new
`Modeller` method. `web/src/modeller.ts` already builds a raw `wasm.Mesh` from arrays for
retagging (`tagged()`) - constructing one from a `Mesh`'s own raw data is not new surface
area in that file, only a new caller of a pattern it already exercises.

**Manifold's own constructor is the validation, and it already exists.** Manifold's JS API
ships `new Manifold(mesh)` / `Manifold.ofMesh(mesh)`, documented to throw when the result is
not an oriented 2-manifold, and a non-throwing `status()` whose result names `NotManifold`
among its failure modes. `adapters/browser.py`'s own module docstring already states the
rule every other kernel call follows: a refusal becomes a `ValueError` naming the call.
`Imported` follows it unchanged - build the Manifold object, let a bad mesh's own rejection
surface the same way a boolean the kernel cannot complete already does. This is not new
validation logic to design; it is the existing rule, applied to one more leaf.

## What "the same as any other Solid" costs, honestly - and why the narrower option costs more

**A boolean against a badly-triangulated import can be slow.** A dropped mesh can be tens
of thousands of triangles; a `Union`/`Difference`/`Hull` against one is real kernel work
that a small parametric body never asked of the machine before. This proposal does not
pretend otherwise, and does not add a triangle-count guard - a maker who asks for a slow
boolean gets a slow boolean, the same honesty `tools/kernel_timing.py` already gives a
script's own timing.

**Manifold's own check answers "is this a valid 2-manifold," not "is this geometrically
sane."** A mesh can be watertight and consistently wound - passing Manifold's own
construction - while still self-intersecting: two lobes of the same body poking through
each other, each locally a fine manifold. Nothing here claims to catch that, because nothing
in the kernel this package drives catches it either. A boolean against a self-intersecting
`Imported` leaf can produce a body that is not what a maker meant, silently, the same way it
always could from bad input to any solid modeller. Disclosed here rather than fixed, because
fixing it is a different, harder proposal this task was never asked to write.

**The narrower alternative - `Imported` restricted to `Intersection` and `volume`,
excluded from `Union`/`Difference`/`Hull` - was considered and rejected.** It reads safer
and is not: Manifold does not distinguish a body by where it came from once it has been
built, so restricting what `Imported` may do would mean bench inventing a check none of the
other dispatch sites need for any other leaf - a special case bolted onto a system
whose whole design is "one verb over the ladder," to guard against a cost (a slow boolean)
that is already visible in the timing the moment it happens, not hidden. The restriction
would also be a promise this proposal cannot keep completely: `Intersection` alone is not
immune to the self-intersecting-input problem above either, so narrowing the operations
does not remove the real risk, it only removes operations a maker might have had a good
reason to want.

## What changes

- `src/bench/topology.py` - `Imported` as a new frozen node beside `Curved`/`SolidFace`;
  `Node` gains it; `node_children` and `_node_points`, the two sites here that match the
  full union, each gain the case - which is where `assert_never` does its job, a case
  missed here is a type error, not a runtime surprise. `_node_points`'s case is free:
  `Mesh.vertices`, transformed by `at`, is exactly the point cloud any other node's case
  already returns, and needs no kernel to compute.
- `src/bench/features.py` - `_extruded_root` gains the case, joining `Revolve`/`Union`/
  `Difference`/`Intersection`/`Hull` in returning `None`: an import has no extruded root by
  construction.
- `src/bench/adapters/browser.py` - `JsKernel`'s `_node` gains the case, crossing
  `mesh.vertices`/`mesh.triangles` as buffers the way `Hull` already crosses a point cloud;
  a `Modeller.imported(vertices, triangles)` method is added to the protocol. `_cloud`
  needs no case, per above.
- `web/src/modeller.ts` - `imported()` implemented on the bound object, built from
  `Manifold.ofMesh`/`new Manifold(mesh)` the way `tagged()` already builds a raw `wasm.Mesh`
  from arrays; a thrown non-manifold error crosses as `JsException` unchanged, the same path
  every other refused call already takes.
- `tests/adapter/kernel_cases.py` - a case function building `Solid(Imported(some_mesh))`,
  exercised through the same `measured(kernel)` harness every other node already is.

## Sequencing

1. `Imported` in `topology.py`, every dispatch site's new case, `JsKernel`'s own case and
   the `Modeller.imported` method, `web/src/modeller.ts`'s implementation. Provable on its
   own: `Solid(Imported(mesh))` builds, meshes and measures a volume against the real
   kernel, with nothing yet asking a script to reach it.
2. Exposed to a script - almost certainly as a small wrapper (`imported(mesh) -> Solid`,
   beside `hole`, `cuboid` and the rest of `bench`'s own constructors) rather than asking a
   script to spell `Solid(Imported(...))` itself, matching how every other leaf already has
   a named constructor a script actually calls.
3. `examples/` or a test showing the motivating use: a candidate's volume compared against
   `reference`'s, as `kernel.volume(Solid(Intersection(candidate, Solid(Imported(reference)))))`
   or whatever the wrapper from step 2 makes that read as.

Step 1 is reviewable with nothing else built - a volume answered off a real dropped mesh,
against the real kernel, before any script-facing surface exists.

### Not in step one, deliberately

- Any repair or simplification of a non-manifold or self-intersecting import. A bad mesh
  fails the way a bad boolean already fails, or silently produces a wrong answer the way bad
  input to any solid modeller can - neither is solved here.
- A triangle-count guard or a warning about a slow boolean. The cost is visible in timing,
  not hidden, and no threshold for "too many triangles to boolean" has been argued from a
  measurement, which decision-5 asks any new one to be.
- Anything about `check_clearance`/`check_contact` treating an `Imported` leaf specially.
  Once it is a `Solid`, those already work on it unchanged - this proposal does not touch
  either function.

## Still the owner's call

- ~~Does the script-facing constructor take a bare `Mesh`...~~ **Settled by task-43:**
  `imported(mesh: Mesh, *, label: str | Label | None = None) -> Solid`, in a new module,
  `src/bench/imported.py` (not `solids.py` - that layer promises no kernel, and `Mesh` lives
  in `kernel`). `mesh` is the only positional argument, exactly as guessed; `label` is
  keyword-only because every sibling constructor (`cuboid`, `cylinder`, `hull`) takes one,
  and this would be the anomaly without it.
- ~~Should there be a cheaper, non-throwing way to ask "would this mesh import cleanly"...~~
  **Settled by task-43, against the real Manifold rather than by preference:** no. A
  `status()` check was written, then measured against `tools/stack.py`'s own kernel before
  keeping it - a lone triangle and an open boundary both throw `Not manifold`, a non-finite
  vertex and an out-of-bounds index each throw by name. The check was a branch nothing could
  reach, so it was deleted. This proposal's argument - Manifold's own constructor is the
  validation, full stop - holds exactly as written.

## Found during implementation (task-43), not by this proposal

- **A mesh wound inside-out is accepted, and measures a negative volume.** Manifold's
  constructor takes it as a valid oriented 2-manifold - the winding is consistent, only
  backwards - so nothing here or in the kernel catches it. In the same class as this
  proposal's own self-intersection disclosure, and left the same way: disclosed, not fixed.
- **An empty mesh imports as an empty body measuring zero**, rather than refusing. Not
  argued for or against here; simply what the constructor does with nothing to build.
