---
id: doc-2
title: 3D review - API design and dialect fit
type: other
created_date: '2026-09-22 19:47'
---

# 3D review - API design and dialect fit (opus, 2026-09-13)

Condensed from the reviewer's report. Two sketches type-checked against the
live repo under mypy --strict: the topology additions and the kernel/checks
signatures.

## Verdict

The paradigm is right; the verb surface is the weakest part. `extrude(sketch,
d, into=, onto=, through=)` is a mutation-shaped API on a frozen core: the
declared subject is the sketch but the value is a modified base, so the
binding lies about what it holds. "One enum, not three functions" is the
dialect misapplied - three mutually exclusive keywords are not an enum, and
exactly-one-of-three has to be policed at runtime. `through=` needs the
kernel (material depth) in the middle of a pure core. The naming rule for
solid faces is asserted, never specified, and collides with `joints`' edge
labels (`top`, `bottom`) on the first extruded panel.

## The tree as data

- `Solid` **holds** a `Node`; it does not become the union. `Shape` stays
  two-armed. `label` lives only on `Solid`; combining nodes take `Solid`
  operands; `Moved` takes a bare `Node` and renames nothing.
- Nodes: `Extrude(profile, distance)`, `Revolve(profile, axis, angle)`,
  `Union(a, b)`, `Difference(base, tool)`, `Intersection(a, b)`,
  `Hull(parts)` (leaf for naming), `Moved(node, at)`. Seven arms. Drop `Box`
  and `Cylinder` as nodes (they are `extrude(fill(rect/circle))`; and
  `topology.Box` would collide with `joints.Box`); drop `Offset` from v1.
- `SolidFace(role, plane | None, label)` is what the tree knows about a face
  before evaluation; `FaceRole` is a StrEnum (`top`, `bottom`, `side`,
  `start`, `end`). Pure `faces_of(solid)` and `node_children(node, at)`
  feed `model._children`; `_walk`, `refs`, `index`, `resolve`, `_checked`
  are untouched. `Named` gains `SolidFace`.
- `Bounds(x0..z1)` and `bounds(shape)` for 3D; **do not widen `BBox`** -
  `bbox(Solid)` is the XY projection.
- The eight `match Solid` sites: `moved` and `mirror` get simpler (`Moved`
  node), `bbox` uses corners of `bounds`, `nest` unchanged, the two `export`
  arms return `()` (stop drawing solids flattened - a fix), `model._children`
  uses `node_children`, `ops.offset` unchanged. Nothing else in 2D changes.

## The verbs

```python
extrude(profile, distance, *, label=None) -> Solid
revolve(profile, axis, *, angle=tau, label=None) -> Solid
cuboid(w, d, h, *, at=ORIGIN, label=None); cylinder(r, h, *, at=ORIGIN, label=None)
loft(bottom, top, *, label=None)                      # the Hull node
union(a, b, *, label=None); cut(base, tool, *, label); common(a, b, *, label=None)
pocket(base, profile, depth, *, label); boss(base, profile, height, *, label)  # sugar
plane_of(solid, at) -> Plane        # face's frame is the profile's own coordinates
hole(subject: Shape, at, *, on=XY, screw, fit=Fit.CLEARANCE, depth=None,
     countersink=False, counterbore=False, label) -> Shape   # Face or Solid, returns
fillet(w: Wire, at, r) -> Wire      # sketch level; twin of chamfer(w, at, d)
shell(solid, t, *, open=(), label=None)   # inset-prism cut; raises unless an extrusion
mirror(shape, across: Axis | Plane); pattern(shape, count, step: Vector | Turn)
```

- `cut` is the existing 2D verb's second arm (`cut(f, hole, *, label)`), and
  the label goes on the tool, which is what makes `plate/pocket`.
- The root extrusion inside a part is unlabelled; the part names it
  (as `gridfinity._plain` does today); `extrude(..., label="plate")` inside
  `part("plate")` would yield `plate/plate/top`.
- `plane_of(ref(...))` cannot work: a `Ref` has no root. `plane_of(solid,
  "top")`; `index()` must accept a bare `Solid`.
- No `fillet`/`chamfer` taking a `Solid` in v1: Known limits says edges are
  rounded by rounding the sketch.
- `fasteners.py` beside `geometry` in the layer graph (imports nothing);
  `Screw` records, `Fit` enum, `bore(screw, fit)` as a `match` ending in
  `assert_never`.

## The naming rule

```
Extrude under Solid L:  L/top, L/bottom, L/side-<edge label or index>, L/<hole label> (hole-0.. if unlabelled)
Revolve:                L/side-<e>, L/start, L/end (when angle < tau)
Union/Difference/Intersection: each operand's faces under its own label path
Hull:                   L only
Moved:                  the node's faces, planes transformed; renames nothing
```

`side-<edge label>` is load-bearing: `open_box` panels have edges labelled
`top`/`bottom`. A pocket's floor is `plate/pocket/bottom` (the tool's own
role); renaming it `floor` needs the kernel. Rule to document: at most one
anonymous body per part - `union` of two anonymous bodies yields two `top`s
and `_checked` rejects it (give that error a better message).

## The kernel seam

```python
@dataclass(frozen=True, slots=True)
class Mesh:  vertices: tuple[float, ...]; triangles: tuple[int, ...]; refs: tuple[Ref | None, ...]
class Kernel(Protocol):
    def mesh(self, solid: Solid) -> Mesh: ...
    def volume(self, solid: Solid) -> float: ...
    def min_gap(self, a: Solid, b: Solid, *, upto: float) -> float: ...
run(source, overrides, *, bed, extras, kernel: Kernel | None = None) -> Scene
```

The tree crosses the wire as a flat SSA list of `OpView`s (one TypedDict,
back-references by index, refs already resolved, rings pre-flattened);
`PartView` gains `tree` and `mesh`; `OkScene` gains `violations`.
`checks.py` holds pure functions taking `kernel` as a parameter; `script`
injects bound closures (`check_clearance`, `check_fits`, `check_wall`,
`check_through`) that record a `Violation(check, message, severity, refs,
line)` into the notebook and return it - like `param` - and a `require()`
that raises for the script that wants to stop. Checks needing a kernel
answer `UNCHECKED` without one rather than passing. `solve(residuals, start,
*, tol, steps)` raises on non-convergence, which is exceptional.

## Materials

Not `Material` beside `Stock` (three sources of one truth). Close the union:
`Stock = Plate | Filament | Billet`, `process_of(stock)`, delete
`Part.process`. Most invasive change; do it after the tree and kernel, never
the halfway version. Rename `nest.Sheet` to `Layout` so `Plate` can be
`Sheet` if wanted.

## Pragmatism calls

Cut: `into=/onto=/through=`, `Box`/`Cylinder` nodes, `Offset` node in v1,
`assert_*` naming, `Material` beside `Stock`, a roles-override table to
rename `bottom` to `floor`. Bend: `Kernel` is a Protocol class; `Mesh` is a
flat-float transport record built from lists inside one function (like
`_Recorder`); `bounds` is conservative under `Difference`; `Violation.line`
walks the stack at the edge; `run(kernel=None)` still yields refs, params
and cut sheets.

## Ranked decisions for the owner

1. `Solid` holds the tree (recommend) or becomes it.
2. `label` only on `Solid`.
3. Three boolean verbs plus a thin feature tier, not `extrude(into=...)`.
4. The face-naming table, including `side-<edge label>` and `pocket/bottom`.
5. The tree crosses the wire; `run(kernel=None)`; prototype the sync bridge.
6. `Violation` records, not raising `assert_*`.
7. Close the `Stock` union later, never the halfway `Material`.
8. Keep `BBox` 2D, add `Bounds`.
9. No solid-level fillet/chamfer; `fillet(wire)` and `loft`.
10. `mirror(shape, Axis | Plane)`; `pattern(step: Vector | Turn)`.
11. Same package, grown.
12. Order: tree + naming + `index()` first with no kernel, then the CLI
    kernel and STL, then the worker and viewer, then fasteners and materials.
