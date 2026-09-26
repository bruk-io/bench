"""Meshing: which named face every triangle of a freshly built body lies on.

The half of building a :class:`~bench.topology.Solid` that needs no modeller. A modeller
sweeps a profile into triangles and does the booleans; it cannot say that a triangle belongs
to ``plate/pocket/bottom``. This module can, from the triangles it was handed and the recipe
it already has - so a kernel adapter builds, hands the fresh mesh here, and writes the face
ids this returns back onto the body before any boolean can scramble them.

**How a face keeps its name.** Manifold tells you, per output triangle, which *run* it came
from (``run_original_id``) and which face of that run (``face_id``). Neither alone is an
identity: an original id names a whole primitive, and automatic face ids are source-triangle
indices, so a hand-picked face id collides with any primitive holding more triangles than
that. The key is the **pair**. Every swept primitive is marked with one reserved original id
and a face id per triangle saying which :class:`~bench.topology.SolidFace` it lies on, and
:func:`triangle_refs` reads the pair back once the body is built. Which face a source
triangle lies on is decided geometrically - by its normal for an extrusion's cap, by its
position for a revolve's, and by the profile step underneath it for a side - because the
recipe says what the faces are called and the mesh says where they are.

**What loses its name.** A hull is built from a point cloud and hands back surfaces belonging
to nothing that went in, so every triangle of one answers to the enclosing solid and nothing
under it - which is what :func:`~bench.topology.node_children` already says a
:class:`~bench.topology.Hull` names.

**Flat numbers, plain loops.** Everything here takes what a modeller hands back - a vertex
buffer with its stride, a triangle index buffer - and gives back :class:`array.array`, which
crosses into JavaScript as a view rather than a copy. The per-triangle loops read scalars by
index and do arithmetic and ``math`` on them, making no object per triangle: that is what
keeps them quick in Pyodide, and what keeps them inside the subset a loop compiler such as
moji could take.
"""

import math
from array import array
from collections.abc import Mapping, Sequence

from . import triangulate
from .geometry import TOL, Point, Transform, identity, to_world
from .kernel import Mesh
from .model import Ref
from .topology import (
    Extrude,
    Revolve,
    Ring,
    SolidFace,
    Swept,
    chord_step,
    flat_ring,
    node_children,
    profile_frame,
    profile_rings,
    sweep_stations,
    under,
)

_FLAT = 0.5
"""How square to an axis a triangle's normal must be to count as a cap rather than a side.
A sweep's caps are perpendicular to its sides, so anything near a half settles it."""

_SEAM = 1e-4
"""How close, in millimetres, a vertex must be to a cut plane to lie on it. A modeller's mesh
vertices are single-precision, so a tolerance of :data:`~bench.geometry.TOL` would call a
genuine cap a side on a part a few hundred millimetres across."""


# ---- names ------------------------------------------------------------------------------


def face_refs(node: Extrude | Revolve | Swept, prefix: str) -> tuple[Ref, ...]:
    """What each face index of one swept primitive is called, in the order the naming rule
    lists the faces - which is the order :func:`profile_rings` counts them in."""
    return tuple(
        Ref(under(prefix, child.label))
        for child in node_children(node, identity())
        if isinstance(child, SolidFace)
    )


# ---- what a modeller is handed ------------------------------------------------------------


def section(rings: tuple[Ring, ...]) -> tuple[array[float], array[int]]:
    """The rings as one flat run of ``u, v`` pairs and the number of points in each ring - the
    outer wire first and every hole after it, read even-odd by the modeller."""
    flat = array("d", (value for ring in rings for point in ring.points for value in point))
    return flat, array("I", (len(ring.points) for ring in rings))


def segments(rings: tuple[Ring, ...]) -> int:
    """How many facets a full turn of these rings is cut into: enough that the widest part of
    the sweep stays within :data:`~bench.topology.CHORD` of the true circle, by the same rule
    that flattened the rings themselves."""
    reach = max((abs(u) for ring in rings for u, _ in ring.points), default=0.0)
    return max(3, math.ceil(math.tau / chord_step(reach)))


def divisions(rings: tuple[Ring, ...], twist: float, scale: float) -> int:
    """How many extra copies of the section a twisted extrusion is built with, so that the
    straight run between two of them stays within :data:`~bench.topology.CHORD` of the helix
    the furthest point of the section really follows - the rule :func:`segments` turns a
    revolve by. A sweep with no twist needs none: a taper's sides are straight already.

    What this does not bound is the fold. Each step of the section sweeps a quad whose far
    edge is turned against its near one, and the modeller splits it along one diagonal, so a
    long straight step twisted is off its true surface by up to ``length * sin(turn / 2) / 2``
    - measured, a 4 mm square turned a quarter over 10 mm comes out 9 per cent over its
    volume turned one way and 12 per cent under turned the other. Holding the fold within a
    chord as well was tried and measured worse where it matters: a thread's section is a
    finely chorded circle whose every point slides along the circle as it turns, and copies
    that close together lean the flank's facets to 67 degrees where the flank leans 40.
    """
    if abs(twist) <= TOL:
        return 0
    reach = max((math.hypot(u, v) for ring in rings for u, v in ring.points), default=0.0)
    return max(1, math.ceil(abs(twist) / chord_step(reach * max(1.0, scale)))) - 1


def sweep_frame(node: Extrude | Revolve) -> Transform:
    """Where a primitive built flat, sweeping up ``+Z`` from the origin, belongs."""
    return to_world(profile_frame(node))


def column_major(t: Transform) -> array[float]:
    """``t`` as the sixteen numbers of a column-major 4 by 4 - the order Manifold's JavaScript
    bindings read a matrix in. The twelve row-major numbers a :class:`Transform` holds are
    accepted there too, and silently build the wrong body."""
    r0, r1, r2 = t.rows
    return array(
        "d",
        (
            r0[0], r1[0], r2[0], 0.0,
            r0[1], r1[1], r2[1], 0.0,
            r0[2], r1[2], r2[2], 0.0,
            r0[3], r1[3], r2[3], 1.0,
        ),
    )  # fmt: skip


def flat_points(node: Extrude, at: Transform) -> array[float]:
    """An extrusion of no height as the points a hull stands on, ``x, y, z`` in turn.

    :func:`bench.solids.loft` builds its two profiles as extrusions of no height, which a
    modeller refuses to sweep at all, so a hull takes their ring points directly.
    """
    frame = at @ to_world(node.profile.plane)
    out = array("d")
    for ring in profile_rings(node):
        for u, v in ring.points:
            p = frame @ Point(u, v, 0.0)
            out.extend((p.x, p.y, p.z))
    return out


def placed(vertices: Sequence[float], stride: int, at: Transform) -> array[float]:
    """Every vertex of a mesh moved by ``at``, ``x, y, z`` in turn."""
    (xx, xy, xz, xt), (yx, yy, yz, yt), (zx, zy, zz, zt) = at.rows
    out = array("d", bytes(8 * 3 * (len(vertices) // stride)))
    for n in range(len(vertices) // stride):
        x = vertices[stride * n]
        y = vertices[stride * n + 1]
        z = vertices[stride * n + 2]
        out[3 * n] = xx * x + xy * y + xz * z + xt
        out[3 * n + 1] = yx * x + yy * y + yz * z + yt
        out[3 * n + 2] = zx * x + zy * y + zz * z + zt
    return out


# ---- which named face a source triangle lies on -------------------------------------------


def walls(rings: tuple[Ring, ...]) -> tuple[array[float], array[int]]:
    """Every step of every ring as the segment it sweeps - ``u0, v0, u1, v1`` in turn - and
    the face each segment belongs to."""
    ends = array("d")
    faces = array("I")
    for ring in rings:
        points = ring.points
        for i, (u, v) in enumerate(points):
            u1, v1 = points[(i + 1) % len(points)]
            ends.extend((u, v, u1, v1))
            faces.append(ring.faces[i])
    return ends, faces


def extruded_faces(
    vertices: Sequence[float],
    stride: int,
    triangles: Sequence[int],
    distance: float,
    rings: tuple[Ring, ...],
    twist: float = 0.0,
    scale: float = 1.0,
) -> array[int]:
    """One face index per triangle of a fresh extrusion: ``top`` and ``bottom`` by the
    triangle's normal, every side by the profile step underneath it.

    ``top`` is the face at ``distance`` however the sweep runs, so a negative distance makes
    the ``+Z``-facing cap the bottom one - the naming rule's own words, read off the mesh.

    A twisted or tapered extrusion is :func:`_twisted_faces`'s instead: a thread's flank can
    lean further than any normal test would still call a side.
    """
    if abs(twist) > TOL or abs(scale - 1.0) > TOL:
        return _twisted_faces(vertices, stride, triangles, distance, rings, twist, scale)
    up, down = (0, 1) if distance >= 0.0 else (1, 0)
    ends, owners = walls(rings)
    count = len(triangles) // 3
    out = array("I", bytes(4 * count))
    sqrt = math.sqrt
    for t in range(count):
        p = stride * triangles[3 * t]
        q = stride * triangles[3 * t + 1]
        r = stride * triangles[3 * t + 2]
        ax, ay, az = vertices[p], vertices[p + 1], vertices[p + 2]
        bx, by, bz = vertices[q], vertices[q + 1], vertices[q + 2]
        cx, cy, cz = vertices[r], vertices[r + 1], vertices[r + 2]
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        length = sqrt(nx * nx + ny * ny + nz * nz)
        if length > 0.0 and nz > _FLAT * length:
            out[t] = up
        elif length > 0.0 and nz < -_FLAT * length:
            out[t] = down
        else:
            out[t] = _nearest(ends, owners, (ax + bx + cx) / 3, (ay + by + cy) / 3)
    return out


def _twisted_faces(
    vertices: Sequence[float],
    stride: int,
    triangles: Sequence[int],
    distance: float,
    rings: tuple[Ring, ...],
    twist: float,
    scale: float,
) -> array[int]:
    """One face index per triangle of a fresh twisted or tapered extrusion, built from
    ``z = 0`` to ``z = distance`` with its far end turned ``twist`` about the sweep.

    A cap is decided by position, the way a revolve's is: all three corners on ``z = 0`` is
    ``bottom`` and all three on ``z = distance`` is ``top``, because a side triangle always
    spans two copies of the section. A side is decided by the profile step underneath it once
    each corner is turned back and shrunk back by as much as its height turned and grew it,
    which puts it on the step it was swept from. A section whose every step belongs to one
    face - an offset circle, a thread - needs no search at all.
    """
    ends, owners = walls(rings)
    only = owners[0] if len(set(owners)) == 1 else None
    turn = twist if distance >= 0.0 else -twist
    count = len(triangles) // 3
    out = array("I", bytes(4 * count))
    cos, sin = math.cos, math.sin
    for t in range(count):
        az = vertices[stride * triangles[3 * t] + 2]
        bz = vertices[stride * triangles[3 * t + 1] + 2]
        cz = vertices[stride * triangles[3 * t + 2] + 2]
        if abs(az - distance) < _SEAM and abs(bz - distance) < _SEAM and abs(cz - distance) < _SEAM:
            out[t] = 0
        elif abs(az) < _SEAM and abs(bz) < _SEAM and abs(cz) < _SEAM:
            out[t] = 1
        elif only is not None:
            out[t] = only
        else:
            u = v = 0.0
            for k in range(3):
                p = stride * triangles[3 * t + k]
                f = vertices[p + 2] / distance
                back = -turn * f
                grow = 1.0 + (scale - 1.0) * f
                x, y = vertices[p] / grow, vertices[p + 1] / grow
                u += x * cos(back) - y * sin(back)
                v += x * sin(back) + y * cos(back)
            out[t] = _nearest(ends, owners, u / 3, v / 3)
    return out


def revolved_faces(
    vertices: Sequence[float],
    stride: int,
    triangles: Sequence[int],
    angle: float,
    rings: tuple[Ring, ...],
    caps: int,
) -> array[int]:
    """One face index per triangle of a fresh revolve: ``start`` and ``end`` where a partial
    turn leaves the profile showing, and every side by the profile step underneath it.

    ``caps`` is how many faces the revolve names, the last two of which are its ends. A cap is
    decided by position rather than by normal, because a revolve's sides are curved and their
    normals sweep through every direction a cap's could take. A side triangle spans two steps
    of the turn, so only a cap has all three vertices on one half-plane.
    """
    ends, owners = walls(rings)
    whole = angle >= math.tau - TOL
    sin, cos = math.sin(angle), math.cos(angle)
    count = len(triangles) // 3
    out = array("I", bytes(4 * count))
    hypot = math.hypot
    for t in range(count):
        p = stride * triangles[3 * t]
        q = stride * triangles[3 * t + 1]
        r = stride * triangles[3 * t + 2]
        ax, ay, az = vertices[p], vertices[p + 1], vertices[p + 2]
        bx, by, bz = vertices[q], vertices[q + 1], vertices[q + 2]
        cx, cy, cz = vertices[r], vertices[r + 1], vertices[r + 2]
        if not whole and _on_half_plane(ax, ay, bx, by, cx, cy, 0.0, 1.0):
            out[t] = caps - 2
        elif not whole and _on_half_plane(ax, ay, bx, by, cx, cy, sin, cos):
            out[t] = caps - 1
        else:
            x = (ax + bx + cx) / 3
            y = (ay + by + cy) / 3
            out[t] = _nearest(ends, owners, hypot(x, y), (az + bz + cz) / 3)
    return out


def _on_half_plane(
    ax: float, ay: float, bx: float, by: float, cx: float, cy: float, sin: float, cos: float
) -> bool:
    """Whether all three corners lie on the half-plane at the turn whose sine and cosine are
    given: across the cut is zero, and along it is not negative."""
    return (
        abs(ax * sin - ay * cos) < _SEAM
        and ax * cos + ay * sin >= -_SEAM
        and abs(bx * sin - by * cos) < _SEAM
        and bx * cos + by * sin >= -_SEAM
        and abs(cx * sin - cy * cos) < _SEAM
        and cx * cos + cy * sin >= -_SEAM
    )


def _nearest(ends: array[float], owners: array[int], u: float, v: float) -> int:
    """The face of the profile step closest to ``(u, v)``.

    A side triangle's centre projects exactly onto the step it was swept from, so the nearest
    one is that step and the distance is zero; nothing here has to guess unless two steps of
    the same profile sit on top of each other, which is a profile that folds through itself.
    """
    best = owners[0]
    gap = math.inf
    hypot = math.hypot
    for w in range(len(owners)):
        u0 = ends[4 * w]
        v0 = ends[4 * w + 1]
        du = ends[4 * w + 2] - u0
        dv = ends[4 * w + 3] - v0
        span = du * du + dv * dv
        along = 0.0 if span <= 0.0 else ((u - u0) * du + (v - v0) * dv) / span
        along = 0.0 if along < 0.0 else 1.0 if along > 1.0 else along
        here = hypot(u - (u0 + du * along), v - (v0 + dv * along))
        if here < gap:
            best = owners[w]
            gap = here
    return best


# ---- the result, read back ----------------------------------------------------------------


def triangle_refs(
    run_index: Sequence[int],
    run_original_id: Sequence[int],
    face_id: Sequence[int],
    tags: Mapping[tuple[int, int], Ref | None],
) -> list[Ref | None]:
    """The ref of every triangle of a built body, read through its ``(run_original_id,
    face_id)`` pair; ``None`` for a triangle whose pair names nothing."""
    refs: list[Ref | None] = [None] * len(face_id)
    get = tags.get
    for run, mark in enumerate(run_original_id):
        for t in range(run_index[run] // 3, run_index[run + 1] // 3):
            refs[t] = get((mark, face_id[t]))
    return refs


def mesh(
    vertices: Sequence[float], stride: int, triangles: Sequence[int], refs: Sequence[Ref | None]
) -> Mesh:
    """A built body as the package's transport record: positions only, whatever else a
    modeller keeps per vertex."""
    positions = (
        tuple(vertices)
        if stride == 3
        else tuple(
            vertices[stride * n + k] for n in range(len(vertices) // stride) for k in range(3)
        )
    )
    return Mesh(positions, tuple(triangles), tuple(refs))


# ---- a sweep, as rings along its path ---------------------------------------------------------

_START = 0
_END = 1
_SIDES = 2
"""Where a sweep's faces stand among the ones :func:`~bench.topology.node_children` names:
``start``, ``end``, then a ``side-`` per outer edge and one per hole wire."""

_STRAIGHT = 1e-9
"""Twice the area, in square millimetres, below which three ring points are in a line - the
figure :mod:`bench.triangulate` drops a corner at, so a ring cleaned here keeps every corner
the cap is clipped from and the cap and the walls share every vertex."""


def swept(node: Swept) -> tuple[array[float], array[int], array[int]]:
    """A swept body as a closed mesh built here, not by a modeller: ``x, y, z`` per vertex,
    three vertex indices per triangle wound counter-clockwise seen from outside, and the face
    each triangle lies on - its index among the faces the naming rule lists.

    The profile is flattened once, the way every profile is (:func:`~bench.topology.flat_ring`,
    arcs cut within :data:`~bench.topology.CHORD`), and a ring of it stands at every station
    :func:`~bench.topology.sweep_stations` gives. Neighbouring rings are joined step by step,
    each step's two triangles on the face its profile edge sweeps, and the first and last ring
    are capped with the profile's own region, triangulated on the same vertices - so the mesh
    is closed without a vertex being merged, which is what a modeller asks of a mesh it is
    handed.
    """
    on = node.profile.plane
    rings = tuple(
        _cleaned(ring, facing=k == 0)
        for k, ring in enumerate(
            (
                flat_ring(
                    node.profile.outer,
                    on,
                    tuple(_SIDES + i for i in range(len(node.profile.outer.edges))),
                ),
                *(
                    flat_ring(w, on, (_SIDES + len(node.profile.outer.edges) + k,) * len(w.edges))
                    for k, w in enumerate(node.profile.inner)
                ),
            )
        )
    )
    flat = [point for ring in rings for point in ring.points]
    per = len(flat)
    stations = sweep_stations(node)
    vertices = array("d")
    for t in stations:
        frame = t @ to_world(on)
        for u, v in flat:
            p = frame @ Point(u, v, 0.0)
            vertices.extend((p.x, p.y, p.z))
    triangles = array("I")
    faces = array("I")
    first = 0
    for ring in rings:
        count = len(ring.points)
        for k in range(len(stations) - 1):
            here, there = k * per + first, (k + 1) * per + first
            for j in range(count):
                a, b = here + j, here + (j + 1) % count
                c, d = there + (j + 1) % count, there + j
                triangles.extend((a, b, c, a, c, d))
                faces.extend((ring.faces[j], ring.faces[j]))
        first += count
    cap = triangulate.triangles(rings[0].points, tuple(ring.points for ring in rings[1:]))
    last = (len(stations) - 1) * per
    for i, j, k in cap:
        triangles.extend((i, k, j, last + i, last + j, last + k))
        faces.extend((_START, _END))
    return vertices, triangles, faces


def _cleaned(ring: Ring, *, facing: bool) -> Ring:
    """``ring`` walked counter-clockwise when ``facing`` - an outline - and clockwise when not
    - a hole - with every point that repeats the one before it or stands in a line between its
    neighbours left out, its step merged into the step before it."""
    points = list(ring.points)
    owners = list(ring.faces)
    if (triangulate.signed_area(points) > 0.0) != facing:
        count = len(points)
        points = points[::-1]
        owners = [owners[(count - 2 - j) % count] for j in range(count)]
    k = 0
    while len(points) > 3 and k < len(points):
        count = len(points)
        (au, av), (bu, bv), (cu, cv) = points[k - 1], points[k], points[(k + 1) % count]
        if abs((bu - au) * (cv - av) - (bv - av) * (cu - au)) <= _STRAIGHT:
            del points[k]
            del owners[k]
            k = max(k - 1, 0)
        else:
            k += 1
    return Ring(tuple(points), tuple(owners))
