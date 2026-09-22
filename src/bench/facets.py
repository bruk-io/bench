"""Facets: a mesh read as triangles, and how thick the material is under each one.

The half of reading a :class:`~bench.kernel.Mesh` that both a check and a survey need, in
one place so they cannot disagree: every triangle as three points, its outward normal, its
centre, and - the measurement the two share - how far a ray from that centre travels straight
into the material before it meets a surface facing back. :func:`bench.checks.wall` asks for
the smallest of those distances and :func:`bench.survey.survey` asks for all of them, and the
number each reports is the same number because it is the same function.

The ray cast runs through a uniform grid over the mesh's box. Every triangle is filed under
each cell its own box touches, and a ray walks the cells it passes through in order, stopping
as soon as it has a hit nearer than the cell it is about to enter. A downloaded model runs to
tens of thousands of triangles, and trying every triangle against every other - which is what
the check did when it only ever saw a script's own bodies - does not finish on one of those.
The grid gives the same answer: the hit a ray finds is the nearest triangle facing back at
it, whichever order the candidates arrive in.

Nothing here knows a ref or a name. A triangle is an index, and it is the caller's business
to say what index ``i`` answers to.
"""

import math
from dataclasses import dataclass

from .geometry import TOL, Point, Vector, cross, unit
from .kernel import Mesh

Triangle = tuple[Point, Point, Point]
"""One triangle as its three corners, wound counter-clockwise seen from outside."""

SKIN = 1e-3
"""How far, in millimetres, a measuring ray must travel before a hit counts. A ray leaving
the middle of a triangle meets its own neighbours at the edges of the same surface; a
thousandth of a millimetre is past those and far under any wall worth measuring."""

_CELLS = 48
"""Cells along the longest side of the grid. The other two sides get fewer in proportion,
so a cell is a cube; enough that a thin plate's rays cross a few cells and a block's a few
dozen, and few enough that filing every triangle stays cheap."""

_Flat = tuple[float, float, float]
"""Three floats, which is what the ray cast works in: a :class:`Point` per corner per
triangle per ray is an object made and dropped tens of millions of times over."""


def triangles(mesh: Mesh) -> tuple[Triangle, ...]:
    """Every triangle of ``mesh`` as three points, in the order ``refs`` counts them."""
    v = mesh.vertices
    out: list[Triangle] = []
    for i in range(0, len(mesh.triangles), 3):
        a, b, c = (mesh.triangles[i], mesh.triangles[i + 1], mesh.triangles[i + 2])
        out.append(
            (
                Point(v[3 * a], v[3 * a + 1], v[3 * a + 2]),
                Point(v[3 * b], v[3 * b + 1], v[3 * b + 2]),
                Point(v[3 * c], v[3 * c + 1], v[3 * c + 2]),
            )
        )
    return tuple(out)


def normal(t: Triangle) -> Vector | None:
    """The outward unit normal of a triangle, or ``None`` for one with no area."""
    a, b, c = t
    n = cross(b - a, c - a)
    return None if abs(n) < TOL else unit(n)


def area(t: Triangle) -> float:
    """How much surface a triangle is, in square millimetres."""
    a, b, c = t
    return abs(cross(b - a, c - a)) / 2.0


def centre(t: Triangle) -> Point:
    """The middle of a triangle: where a measuring ray leaves it."""
    a, b, c = t
    return a + ((b - a) + (c - a)) / 3.0


def thicknesses(mesh: Mesh) -> tuple[float | None, ...]:
    """How far, from the middle of each triangle straight into the material, to the first
    surface facing back - one entry per triangle, ``None`` where the ray met nothing or the
    triangle has no area to leave from.

    Into the material is against the triangle's own normal, so this reads the wall under
    every face of a closed body. An open mesh, or one wound inside out, sends its rays into
    the air and answers ``None`` more than a maker would like, which is the mesh's fault and
    is reported as such rather than repaired.
    """
    corners = triangles(mesh)
    normals = tuple(normal(t) for t in corners)
    grid = _Grid.over(corners)
    out: list[float | None] = []
    for i, t in enumerate(corners):
        n = normals[i]
        if n is None:
            out.append(None)
            continue
        out.append(grid.first_hit(centre(t), -n, normals, i))
    return tuple(out)


def thinnest(mesh: Mesh) -> tuple[float, int] | None:
    """The shortest of :func:`thicknesses`, with the index of the triangle it was measured
    from - the first such triangle, where several tie. ``None`` for a mesh with nothing in
    it, or one no ray of which met anything."""
    best: float | None = None
    at = 0
    for i, through in enumerate(thicknesses(mesh)):
        if through is not None and (best is None or through < best):
            best, at = through, i
    return None if best is None else (best, at)


# ---- the grid --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Grid:
    """The mesh's triangles filed by the cells of a uniform grid over its box.

    ``low`` is the grid's corner, ``cell`` the side of one cube, ``counts`` how many along
    each axis, and ``cells`` the triangle indices under each occupied ``(i, j, k)`` - only
    the occupied ones, so a hollow body costs what its skin costs. ``pre`` is each
    triangle's first corner and two edge vectors, which is what Moller-Trumbore reads.
    """

    low: _Flat
    cell: float
    counts: tuple[int, int, int]
    cells: dict[tuple[int, int, int], tuple[int, ...]]
    pre: tuple[tuple[_Flat, _Flat, _Flat], ...]

    @classmethod
    def over(cls, corners: tuple[Triangle, ...]) -> _Grid:
        """The grid over ``corners``, its box padded so no ray starts on its face."""
        if not corners:
            return cls((0.0, 0.0, 0.0), 1.0, (1, 1, 1), {}, ())
        xs = [p.x for t in corners for p in t]
        ys = [p.y for t in corners for p in t]
        zs = [p.z for t in corners for p in t]
        low = (min(xs) - SKIN, min(ys) - SKIN, min(zs) - SKIN)
        span = (max(xs) - low[0] + SKIN, max(ys) - low[1] + SKIN, max(zs) - low[2] + SKIN)
        cell = max(max(span) / _CELLS, TOL)
        counts = (
            max(1, math.ceil(span[0] / cell)),
            max(1, math.ceil(span[1] / cell)),
            max(1, math.ceil(span[2] / cell)),
        )
        filed: dict[tuple[int, int, int], list[int]] = {}
        pre: list[tuple[_Flat, _Flat, _Flat]] = []
        for index, (a, b, c) in enumerate(corners):
            pre.append(
                (
                    (a.x, a.y, a.z),
                    (b.x - a.x, b.y - a.y, b.z - a.z),
                    (c.x - a.x, c.y - a.y, c.z - a.z),
                )
            )
            i0, i1 = _range(min(a.x, b.x, c.x), max(a.x, b.x, c.x), low[0], cell, counts[0])
            j0, j1 = _range(min(a.y, b.y, c.y), max(a.y, b.y, c.y), low[1], cell, counts[1])
            k0, k1 = _range(min(a.z, b.z, c.z), max(a.z, b.z, c.z), low[2], cell, counts[2])
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    for k in range(k0, k1 + 1):
                        filed.setdefault((i, j, k), []).append(index)
        return cls(low, cell, counts, {at: tuple(found) for at, found in filed.items()}, tuple(pre))

    def first_hit(
        self, origin: Point, along: Vector, normals: tuple[Vector | None, ...], skip: int
    ) -> float | None:
        """How far a ray from ``origin`` along ``along`` travels before it meets a surface
        facing back at it, never counting triangle ``skip`` - the one it left from."""
        o = (origin.x, origin.y, origin.z)
        d = (along.x, along.y, along.z)
        at = [int((o[axis] - self.low[axis]) // self.cell) for axis in range(3)]
        for axis in range(3):
            if at[axis] < 0 or at[axis] >= self.counts[axis]:
                return None
        step = [0, 0, 0]
        next_at = [math.inf, math.inf, math.inf]
        delta = [math.inf, math.inf, math.inf]
        for axis in range(3):
            if d[axis] > TOL:
                step[axis] = 1
                edge = self.low[axis] + (at[axis] + 1) * self.cell
                next_at[axis] = (edge - o[axis]) / d[axis]
                delta[axis] = self.cell / d[axis]
            elif d[axis] < -TOL:
                step[axis] = -1
                edge = self.low[axis] + at[axis] * self.cell
                next_at[axis] = (edge - o[axis]) / d[axis]
                delta[axis] = -self.cell / d[axis]

        best: float | None = None
        tried: set[int] = {skip}
        while True:
            for j in self.cells.get((at[0], at[1], at[2]), ()):
                if j in tried:
                    continue
                tried.add(j)
                n = normals[j]
                if n is None or n.x * d[0] + n.y * d[1] + n.z * d[2] <= 0.0:
                    continue
                t = _ray_triangle(o, d, self.pre[j])
                if t is not None and (best is None or t < best):
                    best = t
            axis = min(range(3), key=lambda k: next_at[k])
            leaving = next_at[axis]
            if best is not None and best <= leaving:
                return best
            at[axis] += step[axis]
            if at[axis] < 0 or at[axis] >= self.counts[axis]:
                return best
            next_at[axis] += delta[axis]


def _range(lo: float, hi: float, low: float, cell: float, count: int) -> tuple[int, int]:
    """Which cells, first to last, a span from ``lo`` to ``hi`` along one axis touches."""
    first = max(0, min(count - 1, int((lo - low) // cell)))
    last = max(0, min(count - 1, int((hi - low) // cell)))
    return first, last


def _ray_triangle(o: _Flat, d: _Flat, pre: tuple[_Flat, _Flat, _Flat]) -> float | None:
    """Where a ray meets a triangle, in millimetres along it, or ``None``.

    Moller-Trumbore: the ray's parameter and the triangle's own two are solved together, so
    nothing is computed that a miss does not need. Plain floats throughout - this is the
    innermost loop of every measurement made off a mesh.
    """
    a, e1, e2 = pre
    px = d[1] * e2[2] - d[2] * e2[1]
    py = d[2] * e2[0] - d[0] * e2[2]
    pz = d[0] * e2[1] - d[1] * e2[0]
    det = e1[0] * px + e1[1] * py + e1[2] * pz
    if -TOL < det < TOL:
        return None
    inv = 1.0 / det
    sx, sy, sz = o[0] - a[0], o[1] - a[1], o[2] - a[2]
    u = (sx * px + sy * py + sz * pz) * inv
    if u < 0.0 or u > 1.0:
        return None
    qx = sy * e1[2] - sz * e1[1]
    qy = sz * e1[0] - sx * e1[2]
    qz = sx * e1[1] - sy * e1[0]
    v = (d[0] * qx + d[1] * qy + d[2] * qz) * inv
    if v < 0.0 or u + v > 1.0:
        return None
    found = (e2[0] * qx + e2[1] * qy + e2[2] * qz) * inv
    return found if found > SKIN else None
