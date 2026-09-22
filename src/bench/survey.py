"""Survey: what a thing that already exists measures.

A script says what a body *is*. This module answers the opposite question - somebody has a
body already, in a file, and wants to know what it would take to write the script for it.
Everything here measures rather than builds, and everything it measures is a fact about the
triangles it was handed.

A mesh is already triangles, so **no solid modeller is needed anywhere in here**. That is
the whole reason this is worth having: a maker can read a downloaded model and take its
numbers in a browser with no kernel loaded, the same way a run with no kernel still yields
every ref, parameter and cut sheet.

The answer is data. :func:`survey` returns a :class:`Survey` - dumb frozen records, numbers
and nothing else - and turning one into prose for a person, or for a model drafting a first
attempt, is somebody else's job and a separate step. Nothing here phrases, formats or guesses.

**It measures; it does not infer intent.** A bore comes back as a diameter, never as a
clearance hole at a named fit; a gap comes back as a distance, never as a
:class:`~bench.fasteners.Fit`. Which dimension drives which, and which of two numbers is the
nominal and which the compensation, are things a maker decided and a mesh cannot remember.

What counts as what
-------------------

A mesh does not say which of its triangles belong together, so this module decides, and
these are the decisions. Each errs toward reporting less rather than guessing more: a
surface that fails a test below is simply not in the answer, and the triangle count says
how much of the mesh the answer covers.

*Walls.* From the middle of every triangle straight into the material to the first surface
facing back - :func:`bench.facets.thicknesses`, the same measurement
:func:`bench.checks.wall` makes, so the thinnest wall here is the thinnest wall there. The
distribution is those distances gathered into bands a tenth of a millimetre wide, each with
the area of surface that measured it: a 2 mm wall shows as a big band at 2.0, and a solid
block as a spread of bands nobody would call a wall.

*A flat* is a connected run of triangles - joined edge to edge - whose normals all lie
within :data:`FLAT` (a tenth of a degree) of the first one's. Adjacent facets of a curve
tessellated finer than that would be read as one flat, and a face that bows by less than a
tenth of a degree end to end is called flat; both are what the number says. Surfaces
smaller than :data:`LEAST` (one square millimetre), flat or round, are left out, which is
where a chamfer's facets and the scraps of a fillet go.

*A round* is a connected run of facets that turn about one axis: normals all perpendicular
to it, adjacent facets stepping by no more than :data:`TURN` (forty degrees), and every
vertex the same distance from the axis to within :data:`ROUND` (a hundredth). The axis is
the direction the normals turn about, the centre is where the facets' normals cross, and the
radius is measured *from the vertices*: a tessellated arc puts its vertices on the arc and
its chords inside it - by up to :data:`~bench.topology.CHORD` - so a radius read off the
facets would come back small, and one read off the vertices does not. A cone fails the
perpendicular test and a fillet that rounds an edge passes it, reported as the partial round
it is, with its ``turn`` saying how much of a circle it covers. A round must turn at least
:data:`LEAST_TURN` (ten degrees) and have a radius no bigger than the body, or it is a blend
rather than a feature and is left out. A regular polygon of nine or more sides is a round to
this test as it is to the eye; a hexagon or an octagon steps too far and stays a set of flats.

*One round, in pieces.* A tessellation breaks a surface where its own seams fall, and a run
grown edge to edge stops at a seam, so one cylinder can come back as several partial rounds.
Pieces that lie on one cylinder - axes within :data:`FLAT`, each centre on the other's axis
and the radii alike to within :data:`SAME`, material on the same side - and whose reaches
along that axis overlap or meet, to within :data:`SAME`, are one round, measured again over
all their triangles: the turn is the arc the pieces cover together and no more, so two arcs
on opposite sides of a rod are the two arcs and not the rod, and the spread is every vertex
against the one circle fitted through all of them. A turn, of one piece or of several, is
the arc its vertices reach round the axis anywhere along the length - not a cross-section
at one station - so where a piece narrows along its length the turn is the widest it gets,
and two pieces that overlap in angle over part of their length are counted once where they
overlap. Two rounds on one cylinder with a reach of
nothing between them - two bores of one diameter through two walls of a plate - stay two,
because nothing was measured between them and the survey does not fill in what it did not
see.

*A section's height.* Five heights spread evenly through a body land, on a part drawn at
round numbers, on the part's own vertices: a plateau at 3.4 on a foot 6.8 tall, the widest
ring of an 18 mm grip lying at 9. A plane through a layer of vertices leaves runs that
enclose nothing - the plane touches triangles there rather than cutting them, and a plane a
hair off it cuts slivers shorter than the tolerance that joins them. So a default height
within :data:`ROUND` of any vertex is moved off it: past the layer's nearer edge by twice
:data:`ROUND`, or to the middle of the gap to the next layer when that is nearer, layers
closer than that counting as one. The rule reads only the vertices, so the same mesh always
surveys at the same heights. A height the caller asks for is taken as asked, wherever it
lands.

*A repeat* is identical features on a regular spacing: the same kind, the same size within
:data:`SAME`, and centres that step by one vector, or by two, to within :data:`PLACE`. A row
needs three; a grid needs two rows of two. A pair on its own is two features, not a
repetition, because any two things are evenly spaced. Repeated features leave ``flats`` and
``rounds`` and appear once, in ``repeats``, with the step and the count.
"""

import math
import struct
from bisect import bisect_left, bisect_right
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from statistics import median

from .facets import Triangle, area, centre, normal, thicknesses, triangles
from .geometry import TOL, Point, Vector, cross, unit
from .kernel import Mesh

_STL_HEADER = 80
"""Bytes of header before an STL's triangle count - the same eighty :mod:`bench.export` writes."""

_STL_FACET = 50
"""Bytes per triangle: a normal, three corners, and two bytes of attribute nobody reads."""

_Flat = tuple[float, float]
"""A point on a section plane, in that plane's own two coordinates."""

FLAT = math.radians(0.1)
"""How far, in radians, a normal may lean from a flat's first normal and still be part of
it. A tenth of a degree: over a 100 mm face that is under a tenth of a millimetre of bow,
which is less than a printer resolves, and ten times the noise single-precision corners put
on a small triangle's normal."""

TURN = math.radians(40.0)
"""The widest step, in radians, between adjacent facets of a round. Forty degrees admits any
arc cut to :data:`~bench.topology.CHORD` above about a millimetre of radius, and every
regular polygon of nine sides or more; it keeps out a hexagon and an octagon, which a maker
would not call round."""

ROUND = 0.01
"""How far, in millimetres, a round's vertices may sit off its fitted radius. A hundredth is
well over single-precision noise at any size bench draws, and well under
:data:`~bench.topology.CHORD`, so a facet's chord midpoint would not pass for a vertex. A
true cylinder off a CAD export fits to a thousandth; the blends round a drafted corner fit to
two hundredths, and are not rounds."""

LEAST = 1.0
"""The smallest surface reported, flat or round, in square millimetres."""

LEAST_TURN = math.radians(10.0)
"""The least arc, in radians, a round must cover to be one. A blend that turns a degree or
two fits a circle as well as anything does, with a radius of metres; it is not a round
feature of the part and is not reported as one - and nor is any arc whose radius is bigger
than the body it is on."""

SAME = 0.02
"""How much, in millimetres, two features may differ in a dimension and still be the same
feature: the same tolerance a round's vertices are held to."""

PLACE = 0.05
"""How far, in millimetres, a repeated feature may sit from where its step says it should be.
The same as :data:`~bench.topology.CHORD`, because a centre read off a tessellation is only
that good."""

BAND = 0.1
"""The width, in millimetres, of one band of the wall-thickness distribution."""

_LOOSE = math.radians(2.0)
"""How far off perpendicular to its seed axis a normal may be while a round is first gathered.
The seed axis is the cross product of two neighbouring normals a few degrees apart and is
only that accurate; the axis is refitted from everything gathered before anything is kept.
It is also how near two seed axes must be for a failure under one to stand for the other."""

_SEED_STEP = math.radians(0.05)
"""The smallest normal step that makes two triangles a seed for a round rather than two
halves of the same facet: half of :data:`FLAT`."""

_COARSE = 0.1
"""How far, in millimetres, a corner may sit off the circle two seed facets describe and
still be gathered. Twice :data:`~bench.topology.CHORD`: the axis two facets give is a few
hundredths of a degree off, which over the length of a long bore is this much, and the axis
is refitted from everything gathered before the test tightens to :data:`ROUND`."""


@dataclass(frozen=True, slots=True)
class Extent:
    """The box a body fills: its lowest corner, its highest, and the span between them."""

    low: Point
    high: Point
    size: Vector


@dataclass(frozen=True, slots=True)
class Outline:
    """One closed run of a body's section, as the box it fills and the area it encloses.

    ``closed`` is false for a run whose ends did not meet, which is what a mesh with a hole
    in it leaves behind - worth reporting rather than quietly dropping, because an open
    outline means the measurement below it is not to be trusted.
    """

    low: Point
    high: Point
    area: float
    closed: bool


@dataclass(frozen=True, slots=True)
class Section:
    """What a body's cross-section is at one height: every outline the plane cuts.

    Two outlines at a height is a wall with an inside and an outside; one is solid; four is
    four posts. The count is often the most useful number here.
    """

    z: float
    outlines: tuple[Outline, ...]


@dataclass(frozen=True, slots=True)
class Band:
    """How much surface, in square millimetres, measured a wall of ``thickness`` under it."""

    thickness: float
    area: float


@dataclass(frozen=True, slots=True)
class Walls:
    """How thick the material runs under the surface: the thinnest place, and the whole
    distribution as :class:`Band` records a tenth of a millimetre wide, most surface first.

    ``thinnest`` is exactly what :func:`bench.checks.wall` measures on the same mesh, and
    ``at`` is the middle of the triangle it was measured from.
    """

    thinnest: float
    at: Point
    bands: tuple[Band, ...]


@dataclass(frozen=True, slots=True)
class Flat:
    """A flat face: which way it faces, where it is, and how big it is.

    ``normal`` points out of the material. ``centre`` is the area-weighted middle of the
    face; ``low`` and ``high`` box its corners; ``area`` is its surface and ``facets`` how
    many triangles made it.
    """

    normal: Vector
    centre: Point
    low: Point
    high: Point
    area: float
    facets: int


@dataclass(frozen=True, slots=True)
class Round:
    """A cylindrical surface: its axis, its size, and which side the material is on.

    ``axis`` is a unit direction, signed so its first non-zero component is positive;
    ``centre`` sits on it halfway along ``length``. ``turn`` is how much of a circle the
    surface covers, in radians - a full bore is two pi, a fillet a quarter of that. ``concave``
    is true where the normals point in toward the axis: a bore, a socket, an inside fillet,
    as against a pin, a boss or an outside one. ``spread`` is how far the vertices strayed
    from ``radius``, which says how well the fit was earned; ``low`` and ``high`` box the
    surface itself, which is where a partial round is.
    """

    axis: Vector
    centre: Point
    radius: float
    length: float
    turn: float
    concave: bool
    spread: float
    low: Point
    high: Point
    area: float
    facets: int


@dataclass(frozen=True, slots=True)
class Step:
    """One direction of a repeat: the vector from each feature to the next, and how many."""

    along: Vector
    count: int


@dataclass(frozen=True, slots=True)
class Repeat:
    """Identical features on a regular spacing, read as one finding.

    ``one`` is the first of them, where it is; ``steps`` has one entry for a row and two for
    a grid, and the rest of the features are ``one`` moved by every combination of them.
    """

    one: Flat | Round
    steps: tuple[Step, ...]


@dataclass(frozen=True, slots=True)
class Survey:
    """Everything measured off one mesh: how big it is, what section it has where, how
    thick it runs, which of its surfaces are flat or round, and what repeats.

    ``walls`` is ``None`` for a mesh no ray of which met anything - an empty one, or one with
    no inside. ``flats`` and ``rounds`` hold the features that stand alone, biggest first;
    the ones that repeat are in ``repeats``, most numerous first.
    """

    triangles: int
    extent: Extent
    sections: tuple[Section, ...]
    walls: Walls | None
    flats: tuple[Flat, ...]
    rounds: tuple[Round, ...]
    repeats: tuple[Repeat, ...]


def mesh_from_stl(data: bytes) -> Mesh:
    """Read a binary STL into the mesh record the rest of bench already speaks.

    The exact inverse of :func:`bench.export.stl`: eighty bytes of header, a triangle count,
    then fifty bytes per triangle. The facet normal each triangle carries is *not* kept - it
    is derived from the winding everywhere in bench, and a normal that disagrees with its own
    corners is a lie a file is welcome to tell but this will not repeat.

    Corners that coincide exactly become one vertex, so a body written from a real mesh comes
    back about as small as it went out. Nothing is welded by proximity: two corners a
    thousandth apart stay two corners, because deciding they are one is a repair, not a read.

    An STL has no names in it - no script wrote it - so every triangle's ref is ``None``, and
    that is carried honestly rather than filled in.

    Raises:
        ValueError: if ``data`` is an ASCII STL, is too short to hold a header and a count,
            or does not hold exactly the number of triangles it claims.
    """
    if data[:5].lstrip().lower().startswith(b"solid") and b"facet" in data[: _STL_HEADER * 4]:
        msg = "this is an ASCII STL, and only the binary form is read here"
        raise ValueError(msg)
    if len(data) < _STL_HEADER + 4:
        msg = f"an STL needs {_STL_HEADER + 4} bytes before its first triangle, not {len(data)}"
        raise ValueError(msg)
    (count,) = struct.unpack_from("<I", data, _STL_HEADER)
    want = _STL_HEADER + 4 + _STL_FACET * count
    if len(data) != want:
        msg = f"an STL of {count} triangles is {want} bytes, and this is {len(data)}"
        raise ValueError(msg)

    seen: dict[tuple[float, float, float], int] = {}
    vertices: list[float] = []
    triangles: list[int] = []
    for t in range(count):
        at = _STL_HEADER + 4 + _STL_FACET * t + 12  # past the facet normal
        for k in range(3):
            corner = struct.unpack_from("<3f", data, at + 12 * k)
            found = seen.get(corner)
            if found is None:
                found = len(seen)
                seen[corner] = found
                vertices.extend(corner)
            triangles.append(found)
    return Mesh(tuple(vertices), tuple(triangles), (None,) * count)


def survey(mesh: Mesh, *, at: tuple[float, ...] = ()) -> Survey:
    """Measure ``mesh``: its extent, its section at each height in ``at``, its walls, its
    flat and round surfaces, and what repeats among them.

    ``at`` empty asks for five heights spread evenly through the body, which is enough to
    tell a straight wall from a tapered one without being told where to look - each moved
    off any layer of the body's own vertices it would land on, so the plane cuts through
    rather than along. A height given in ``at`` is taken as given. A height outside the body
    sections nothing and comes back with no outlines, which is an answer.

    Linear in the triangles for the surfaces, and a ray per triangle through a grid for the
    walls: a downloaded model of twenty thousand triangles takes seconds, which is what a
    question a maker asks, the way :func:`bench.checks.wall` is, may cost.
    """
    extent = _extent(mesh)
    heights = at if at else _clear(_spread(extent), mesh)
    corners = triangles(mesh)
    normals = tuple(normal(t) for t in corners)
    centres = tuple(centre(t) for t in corners)
    beside = _adjacent(mesh)
    rounds, taken = _rounds(corners, normals, centres, beside, abs(extent.size))
    flats = _flats(corners, normals, beside, taken)
    flats, rounds, repeats = _repeats(flats, rounds)
    return Survey(
        triangles=len(corners),
        extent=extent,
        sections=tuple(_section(corners, z) for z in heights),
        walls=_walls(mesh, corners),
        flats=flats,
        rounds=rounds,
        repeats=repeats,
    )


def flat_faces(mesh: Mesh) -> tuple[tuple[Flat, tuple[int, ...]], ...]:
    """Every flat :func:`survey` would find, each beside the triangles that grew it -
    biggest first, the same order and the same growth :func:`survey` itself runs.

    ``Survey.flats`` is not this: :func:`_repeats` folds several flats into one
    :class:`Repeat` afterward for the report's sake, and a repeat's own copies are never
    triangles a caller can point at - they are a step and a count. This is the growth
    before that folding, one entry per flat actually found on the mesh, each with the
    triangle indices that are it - for drawing a detected face, or answering a click on
    one, neither of which the report's own shape is for.

    Costs what :func:`survey` costs for the flats alone: the same walk, run again, because
    a second caller wanting only this is not worth carrying the first one's intermediate
    state past its own return.
    """
    corners = triangles(mesh)
    normals = tuple(normal(t) for t in corners)
    centres = tuple(centre(t) for t in corners)
    beside = _adjacent(mesh)
    extent = _extent(mesh)
    _, taken = _rounds(corners, normals, centres, beside, abs(extent.size))
    seen = set(taken)
    found: list[tuple[Flat, tuple[int, ...]]] = []
    for seed, n in enumerate(normals):
        if seed in seen or n is None:
            continue
        region = _grow(seed, beside, seen, _flat_as(normals, n))
        one = _flat(region, corners, n)
        if one.area >= LEAST:
            found.append((one, region))
    found.sort(
        key=lambda item: (-item[0].area, item[0].centre.x, item[0].centre.y, item[0].centre.z)
    )
    return tuple(found)


def section_loops(mesh: Mesh, z: float) -> tuple[tuple[tuple[Point, ...], bool], ...]:
    """Every loop a plane at ``z`` cuts ``mesh`` into, as the polygon it actually is - every
    vertex in order, and whether its ends met - rather than the box and the area
    :func:`survey` reduces a loop to for a `Section`'s own `Outline`.

    The same walk :func:`_loops` already runs for a section, kept instead of thrown away: a
    rib, a lattice, anything a box and an enclosed area cannot tell apart from a different
    shape of the same box and the same area is only readable from these points. Each point
    is placed at ``z``, the height asked for, so a loop returned here is usable directly as
    the outline an ``extrude()`` or a ``loft()`` would be built from at that height - not
    only a measurement of one, the way ``Outline`` is.

    A loop's own winding is whatever the mesh's own triangles left it as; nothing here signs
    it one way for an inside and the other for an outside, the same as ``Section`` itself.
    """
    corners = triangles(mesh)
    return tuple(
        (tuple(Point(x, y, z) for x, y in loop), closed) for loop, closed in _loops(corners, z)
    )


def _extent(mesh: Mesh) -> Extent:
    """The box ``mesh`` fills, or a box at the origin for a mesh with nothing in it."""
    if not mesh.vertices:
        return Extent(Point(0.0, 0.0, 0.0), Point(0.0, 0.0, 0.0), Vector(0.0, 0.0, 0.0))
    xs = mesh.vertices[0::3]
    ys = mesh.vertices[1::3]
    zs = mesh.vertices[2::3]
    low = Point(min(xs), min(ys), min(zs))
    high = Point(max(xs), max(ys), max(zs))
    return Extent(low, high, high - low)


def _spread(extent: Extent, count: int = 5) -> tuple[float, ...]:
    """``count`` heights spread through ``extent``, none of them on its floor or its lid.

    A section taken exactly at the top or the bottom of a body cuts the flat face there and
    answers with whatever the tessellation happens to leave, which is noise. These sit
    strictly inside.
    """
    low, high = extent.low.z, extent.high.z
    if high - low <= TOL:
        return ()
    return tuple(low + (high - low) * (i + 1) / (count + 1) for i in range(count))


def _clear(heights: tuple[float, ...], mesh: Mesh) -> tuple[float, ...]:
    """``heights`` with each one that lands on a layer of ``mesh``'s vertices moved off it,
    lowest first and none repeated."""
    layers = tuple(sorted(set(mesh.vertices[2::3])))
    moved = sorted({_off_layers(z, layers) for z in heights})
    return tuple(moved)


def _off_layers(z: float, layers: tuple[float, ...]) -> float:
    """``z``, or the nearest height clear of every layer in ``layers`` when one lies within
    :data:`ROUND` of it.

    Layers closer together than twice :data:`ROUND` have no clear height between them and
    count as one band. The height moves past the band's nearer edge by twice :data:`ROUND`,
    or to the middle of the gap to the next layer beyond, whichever is nearer - so it is
    clear of the band by that much and of the next layer by at least as much. A band with
    no gap on either side is the whole body, and ``z`` stays where it is.
    """
    first = bisect_left(layers, z - ROUND)
    last = bisect_right(layers, z + ROUND)
    if first == last:
        return z
    while first > 0 and layers[first] - layers[first - 1] <= 2.0 * ROUND:
        first -= 1
    while last < len(layers) and layers[last] - layers[last - 1] <= 2.0 * ROUND:
        last += 1
    options: list[float] = []
    if first > 0:
        edge = layers[first]
        options.append(max(edge - 2.0 * ROUND, (layers[first - 1] + edge) / 2.0))
    if last < len(layers):
        edge = layers[last - 1]
        options.append(min(edge + 2.0 * ROUND, (edge + layers[last]) / 2.0))
    if not options:
        return z
    return min(options, key=lambda found: (abs(found - z), -found))


# ---- sections --------------------------------------------------------------------------


def _section(corners: tuple[Triangle, ...], z: float) -> Section:
    """What the mesh cuts at height ``z``, as the outlines the plane leaves."""
    return Section(
        z=z, outlines=tuple(_outline(loop, closed) for loop, closed in _loops(corners, z))
    )


def _loops(corners: tuple[Triangle, ...], z: float) -> tuple[tuple[tuple[_Flat, ...], bool], ...]:
    """The runs a plane at ``z`` cuts the mesh into, each with whether its ends met."""
    loose = list(_segments(corners, z))
    found: list[tuple[tuple[_Flat, ...], bool]] = []
    while loose:
        start, end = loose.pop()
        run = [start, end]
        closed = False
        while not closed:
            joined = False
            for i, (a, b) in enumerate(loose):
                if _meets(a, run[-1]):
                    run.append(b)
                elif _meets(b, run[-1]):
                    run.append(a)
                else:
                    continue
                loose.pop(i)
                joined = True
                break
            if not joined:
                break
            closed = _meets(run[-1], run[0])
        found.append((tuple(run), closed))
    return tuple(found)


def _segments(corners: tuple[Triangle, ...], z: float) -> tuple[tuple[_Flat, _Flat], ...]:
    """Where each triangle crosses the plane at ``z``, as a flat segment.

    A triangle with one corner exactly on the plane touches rather than crosses it, and
    contributes nothing: two crossings are what makes a segment.
    """
    out: list[tuple[_Flat, _Flat]] = []
    for t in corners:
        cut: list[_Flat] = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            first, second = t[a], t[b]
            if (first.z - z) * (second.z - z) >= 0.0:
                continue
            across = (z - first.z) / (second.z - first.z)
            cut.append(
                (first.x + across * (second.x - first.x), first.y + across * (second.y - first.y))
            )
        if len(cut) == 2:
            out.append((cut[0], cut[1]))
    return tuple(out)


def _meets(a: _Flat, b: _Flat) -> bool:
    """Whether two ends of a section are the same point."""
    return abs(a[0] - b[0]) <= TOL and abs(a[1] - b[1]) <= TOL


def _outline(loop: tuple[_Flat, ...], closed: bool) -> Outline:
    """One run of a section, as the box it fills and the area it encloses."""
    xs = tuple(p[0] for p in loop)
    ys = tuple(p[1] for p in loop)
    return Outline(
        low=Point(min(xs), min(ys), 0.0),
        high=Point(max(xs), max(ys), 0.0),
        area=abs(_shoelace(loop)),
        closed=closed,
    )


def _shoelace(loop: tuple[_Flat, ...]) -> float:
    """Twice the signed area of ``loop``, halved: the area it encloses, sign and all."""
    total = 0.0
    for i, (x, y) in enumerate(loop):
        nx, ny = loop[(i + 1) % len(loop)]
        total += x * ny - nx * y
    return total / 2.0


# ---- walls -----------------------------------------------------------------------------


def _walls(mesh: Mesh, corners: tuple[Triangle, ...]) -> Walls | None:
    """The thickness under every triangle, as the thinnest and the distribution by area."""
    through = thicknesses(mesh)
    best: float | None = None
    at = 0
    by_band: dict[int, float] = {}
    for i, found in enumerate(through):
        if found is None:
            continue
        if best is None or found < best:
            best, at = found, i
        band = round(found / BAND)
        by_band[band] = by_band.get(band, 0.0) + area(corners[i])
    if best is None:
        return None
    bands = sorted(by_band.items(), key=lambda item: (-item[1], item[0]))
    return Walls(
        thinnest=best,
        at=centre(corners[at]),
        bands=tuple(Band(band * BAND, found) for band, found in bands),
    )


# ---- reading which triangles belong together -------------------------------------------


def _adjacent(mesh: Mesh) -> tuple[tuple[int, ...], ...]:
    """Which triangles share an edge with each one, by the vertex indices the edge runs
    between - which is why corners are welded exactly and never by proximity."""
    by_edge: dict[tuple[int, int], list[int]] = {}
    count = len(mesh.triangles) // 3
    for t in range(count):
        a, b, c = mesh.triangles[3 * t], mesh.triangles[3 * t + 1], mesh.triangles[3 * t + 2]
        for p, q in ((a, b), (b, c), (c, a)):
            by_edge.setdefault((p, q) if p < q else (q, p), []).append(t)
    beside: list[list[int]] = [[] for _ in range(count)]
    for sharing in by_edge.values():
        for t in sharing:
            beside[t].extend(other for other in sharing if other != t)
    return tuple(tuple(found) for found in beside)


def _turn_between(a: Vector, b: Vector) -> float:
    """The angle between two unit normals, in radians."""
    return math.acos(max(-1.0, min(1.0, a @ b)))


def _flats(
    corners: tuple[Triangle, ...],
    normals: tuple[Vector | None, ...],
    beside: tuple[tuple[int, ...], ...],
    taken: set[int],
) -> tuple[Flat, ...]:
    """Every flat of at least :data:`LEAST`, grown edge to edge from triangles nobody has
    claimed, biggest first. A flat under :data:`LEAST` still claims its triangles, so a run
    of small facets is not re-grown from each of them."""
    seen = set(taken)
    found: list[Flat] = []
    for seed, n in enumerate(normals):
        if seed in seen or n is None:
            continue
        region = _grow(seed, beside, seen, _flat_as(normals, n))
        one = _flat(region, corners, n)
        if one.area >= LEAST:
            found.append(one)
    found.sort(key=lambda f: (-f.area, f.centre.x, f.centre.y, f.centre.z))
    return tuple(found)


def _flat_as(normals: tuple[Vector | None, ...], of: Vector) -> Callable[[int], bool]:
    """Whether triangle ``k`` faces within :data:`FLAT` of ``of``."""

    def admits(k: int) -> bool:
        n = normals[k]
        return n is not None and _turn_between(n, of) <= FLAT

    return admits


def _grow(
    seed: int,
    beside: tuple[tuple[int, ...], ...],
    seen: set[int],
    admits: Callable[[int], bool],
    start: tuple[int, ...] = (),
) -> tuple[int, ...]:
    """The connected run of triangles from ``seed`` (and ``start``) that ``admits`` allows,
    each marked in ``seen`` as it is reached."""
    region = [seed, *start]
    seen.update(region)
    queue = deque(region)
    while queue:
        here = queue.popleft()
        for k in beside[here]:
            if k not in seen and admits(k):
                seen.add(k)
                region.append(k)
                queue.append(k)
    return tuple(region)


def _flat(region: tuple[int, ...], corners: tuple[Triangle, ...], n: Vector) -> Flat:
    """One flat, as the numbers that place and size it."""
    total = 0.0
    weighted = Vector(0.0, 0.0, 0.0)
    for i in region:
        a = area(corners[i])
        total += a
        weighted = weighted + (centre(corners[i]) - Point(0.0, 0.0, 0.0)) * a
    low, high = _box(region, corners)
    middle = Point(0.0, 0.0, 0.0) + (weighted / total if total > 0.0 else weighted)
    return Flat(normal=n, centre=middle, low=low, high=high, area=total, facets=len(region))


def _box(region: tuple[int, ...], corners: tuple[Triangle, ...]) -> tuple[Point, Point]:
    """The box the corners of ``region`` fill."""
    points = [p for i in region for p in corners[i]]
    return (
        Point(min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)),
        Point(max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)),
    )


# ---- rounds ----------------------------------------------------------------------------


def _rounds(
    corners: tuple[Triangle, ...],
    normals: tuple[Vector | None, ...],
    centres: tuple[Point, ...],
    beside: tuple[tuple[int, ...], ...],
    across: float,
) -> tuple[tuple[Round, ...], set[int]]:
    """Every round in the mesh no bigger than ``across``, biggest first, with the triangles
    they claimed.

    Every pair of neighbouring facets that step is a seed, and a surface that is not a round
    has as many seeds as facets, each gathering the same surface again. So the axis a failed
    attempt was tried about is remembered against the triangles that fitted its circle - they
    fit one rejected circle together, and would again - and against the seed pair, and a seed
    whose axis is that one to within :data:`_LOOSE` is not tried a second time. Triangles an
    attempt merely gathered and then dropped are not marked: they may be the start of a round
    of their own that the wider gathering drowned.

    The pieces a tessellation's seams cut one cylinder into are then put back together by
    :func:`_merged`, so a grip comes back as the one round it is.
    """
    taken: set[int] = set()
    failed: dict[int, list[Vector]] = {}
    found: list[tuple[Round, tuple[int, ...]]] = []
    for seed, n in enumerate(normals):
        if seed in taken or n is None:
            continue
        for other in beside[seed]:
            m = normals[other]
            if other in taken or m is None:
                continue
            step = _turn_between(n, m)
            if not _SEED_STEP <= step <= TURN:
                continue
            axis = _signed(unit(cross(n, m)))
            if any(_turn_between(axis, tried) <= _LOOSE for tried in failed.get(seed, ())):
                continue
            one, fitted = _round_from(
                seed, other, axis, corners, normals, centres, beside, taken, across
            )
            if one is not None:
                found.append((one, fitted))
                break
            for i in (seed, other, *fitted):
                failed.setdefault(i, []).append(axis)
    rounds = sorted(
        _merged(tuple(found), corners, normals, centres),
        key=lambda r: (-r.area, r.centre.x, r.centre.y, r.centre.z),
    )
    return tuple(rounds), taken


def _merged(
    pieces: tuple[tuple[Round, tuple[int, ...]], ...],
    corners: tuple[Triangle, ...],
    normals: tuple[Vector | None, ...],
    centres: tuple[Point, ...],
) -> tuple[Round, ...]:
    """``pieces`` with every set of them that lies on one cylinder and reaches along it from
    one to the next put back as the one round they are, measured over all their triangles.

    A piece joins a group when it shares a cylinder with any member, so three pieces in a
    row along a grip join through the middle one whether or not the two ends reach each
    other. A group whose union cannot be fitted again - which no group of rounds that each
    fitted should be - is left as the pieces it came in as, rather than claimed as one.
    """
    groups: list[list[int]] = []
    for i, (one, _) in enumerate(pieces):
        joined = [g for g in groups if any(_one_cylinder(one, pieces[j][0]) for j in g)]
        if not joined:
            groups.append([i])
            continue
        first, *rest = joined
        first.append(i)
        for g in rest:
            first.extend(g)
            groups.remove(g)
    out: list[Round] = []
    for g in groups:
        if len(g) == 1:
            out.append(pieces[g[0]][0])
            continue
        whole = _whole(tuple(pieces[k] for k in g), corners, normals, centres)
        if whole is None:
            out.extend(pieces[k][0] for k in g)
        else:
            out.append(whole)
    return tuple(out)


def _one_cylinder(a: Round, b: Round) -> bool:
    """Whether two rounds lie on one cylinder and reach each other along it.

    The axes are compared as lines, either way along, because which way an axis is signed
    is settled by which of two equal components noise makes the larger. Each centre must sit
    on the other's axis and the radii agree, both to :data:`SAME`; and the two reaches along
    the axis - each centre half a length either way - must overlap or meet within
    :data:`SAME`, which is what separates one surface in pieces from two bores of one size
    through two walls.
    """
    between = _turn_between(a.axis, b.axis)
    if min(between, math.pi - between) > FLAT or a.concave != b.concave:
        return False
    if abs(a.radius - b.radius) > SAME:
        return False
    if (
        _from_axis(b.centre, a.axis, a.centre) > SAME
        or _from_axis(a.centre, b.axis, b.centre) > SAME
    ):
        return False
    along = (b.centre - a.centre) @ a.axis
    return (
        along - b.length / 2.0 <= a.length / 2.0 + SAME
        and -a.length / 2.0 <= along + b.length / 2.0 + SAME
    )


def _whole(
    pieces: tuple[tuple[Round, tuple[int, ...]], ...],
    corners: tuple[Triangle, ...],
    normals: tuple[Vector | None, ...],
    centres: tuple[Point, ...],
) -> Round | None:
    """The one round ``pieces`` make, fitted again over every triangle of every piece: the
    axis and circle from all of them, the turn as the arc they cover between them, the reach
    along the axis from end to end, and the spread of every vertex against that one circle.
    ``None`` when the union does not fit, which leaves the pieces as they were."""
    region = tuple(i for _, part in pieces for i in part)
    axis = _least_turned(tuple(n for i in region if (n := normals[i]) is not None))
    if axis is None:
        return None
    fit = _circle(region, axis, corners, normals, centres)
    if fit is None:
        return None
    centre_at, radius = fit
    arcs = tuple(_arc(part, axis, centre_at, corners) for _, part in pieces)
    along = tuple((p - centre_at) @ axis for i in region for p in corners[i])
    lowest, highest = min(along), max(along)
    low, high = _box(region, corners)
    return Round(
        axis=axis,
        centre=centre_at + axis * ((lowest + highest) / 2.0),
        radius=radius,
        length=highest - lowest,
        turn=_covered(arcs),
        concave=pieces[0][0].concave,
        spread=max(
            abs(_from_axis(p, axis, centre_at) - radius) for i in region for p in corners[i]
        ),
        low=low,
        high=high,
        area=sum(area(corners[i]) for i in region),
        facets=len(region),
    )


def _covered(arcs: tuple[tuple[float, float], ...]) -> float:
    """How much of a circle ``arcs`` - each a start angle and an extent - cover between them,
    in radians: their union, so an overlap is counted once and a gap between two arcs is
    not covered by either."""
    spans: list[tuple[float, float]] = []
    whole = 2.0 * math.pi
    for start, extent in arcs:
        if extent >= whole:
            return whole
        begin = start % whole
        end = begin + extent
        if end <= whole:
            spans.append((begin, end))
        else:
            spans.extend(((begin, whole), (0.0, end - whole)))
    total = 0.0
    reached = -1.0
    for begin, end in sorted(spans):
        begin = max(begin, reached)
        if end > begin:
            total += end - begin
            reached = end
    return min(total, whole)


def _round_from(
    seed: int,
    other: int,
    axis0: Vector,
    corners: tuple[Triangle, ...],
    normals: tuple[Vector | None, ...],
    centres: tuple[Point, ...],
    beside: tuple[tuple[int, ...], ...],
    taken: set[int],
    across: float,
) -> tuple[Round | None, tuple[int, ...]]:
    """The round two neighbouring facets are the start of, or ``None`` when what grows from
    them does not measure as one: fewer than three facets, material on both sides of it, a
    radius bigger than ``across`` - the body itself - less than :data:`LEAST_TURN` of arc, or
    less than :data:`LEAST` of surface. Beside it, the triangles that fitted the circle,
    whether or not it was kept - none, where no circle was fitted.

    Seed, then verify. The two facets alone fix a circle - their normals cross at its centre
    and their corners are on it - and the region grows only over triangles whose corners lie
    on that circle, coarsely at first because an axis read off two facets is only so
    accurate, then, once the axis has been refitted from everything gathered, to
    :data:`ROUND`. A round never gathers more than itself this way, where a region grown on
    normals alone walks off round a fillet on to every wall it joins. Triangles are claimed
    in ``taken`` only for a round that is kept, so a failed seed costs nothing but the time
    it took.
    """
    fit0 = _circle((seed, other), axis0, corners, normals, centres)
    if fit0 is None:
        return None, ()
    gathered = _grow(
        seed,
        beside,
        set(taken),
        _on_circle(axis0, fit0, _COARSE, _LOOSE, corners, normals),
        (other,),
    )
    axis = _least_turned(tuple(n for i in gathered if (n := normals[i]) is not None))
    if axis is None:
        return None, ()
    fit = _circle(gathered, axis, corners, normals, centres)
    if fit is None:
        return None, ()
    on_it = _on_circle(axis, fit, ROUND, FLAT, corners, normals)
    kept = tuple(i for i in gathered if on_it(i))
    if len(kept) < 3:
        return None, ()
    region = _grow(kept[0], beside, set(taken), on_it, kept[1:])
    settled = _settle(region, axis, corners, normals, centres)
    if settled is None:
        return None, ()
    region, centre_at, radius = settled
    sides = {_inward(i, axis, centre_at, normals, centres) for i in region}
    turn = _turn_of(region, axis, centre_at, corners)
    if (
        len(sides) != 1
        or _facets_of(region, normals) < 3
        or radius > across
        or turn < LEAST_TURN
        or sum(area(corners[i]) for i in region) < LEAST
    ):
        return None, region
    taken.update(region)
    along = tuple((p - centre_at) @ axis for i in region for p in corners[i])
    lowest, highest = min(along), max(along)
    low, high = _box(region, corners)
    one = Round(
        axis=axis,
        centre=centre_at + axis * ((lowest + highest) / 2.0),
        radius=radius,
        length=highest - lowest,
        turn=turn,
        concave=sides.pop(),
        spread=max(
            abs(_from_axis(p, axis, centre_at) - radius) for i in region for p in corners[i]
        ),
        low=low,
        high=high,
        area=sum(area(corners[i]) for i in region),
        facets=len(region),
    )
    return one, region


def _settle(
    region: tuple[int, ...],
    axis: Vector,
    corners: tuple[Triangle, ...],
    normals: tuple[Vector | None, ...],
    centres: tuple[Point, ...],
) -> tuple[tuple[int, ...], Point, float] | None:
    """Fit ``region``'s circle, drop the triangles that do not lie on it to :data:`ROUND`,
    and fit again, until nothing drops - so the answer's spread is within :data:`ROUND` of
    the very circle it reports, not of an earlier one. ``None`` when fewer than three
    triangles are left, or the fit never settles."""
    kept = region
    for _ in range(6):
        if len(kept) < 3:
            return None
        fit = _circle(kept, axis, corners, normals, centres)
        if fit is None:
            return None
        centre_at, radius = fit
        still = tuple(
            i
            for i in kept
            if all(abs(_from_axis(p, axis, centre_at) - radius) <= ROUND for p in corners[i])
        )
        if len(still) == len(kept):
            return kept, centre_at, radius
        kept = still
    return None


def _from_axis(p: Point, axis: Vector, centre_at: Point) -> float:
    """How far ``p`` is from the line through ``centre_at`` along ``axis``."""
    arm = p - centre_at
    return abs(arm - axis * (arm @ axis))


def _inward(
    i: int,
    axis: Vector,
    centre_at: Point,
    normals: tuple[Vector | None, ...],
    centres: tuple[Point, ...],
) -> bool:
    """Whether triangle ``i`` faces the axis - a bore - rather than away from it."""
    n = normals[i]
    if n is None:
        return False
    arm = centres[i] - centre_at
    return n @ (arm - axis * (arm @ axis)) < 0.0


def _on_circle(
    axis: Vector,
    fit: tuple[Point, float],
    slack: float,
    lean: float,
    corners: tuple[Triangle, ...],
    normals: tuple[Vector | None, ...],
) -> Callable[[int], bool]:
    """Whether a triangle lies on the cylinder ``fit`` describes about ``axis``: every corner
    within ``slack`` of the radius, and its normal within ``lean`` of perpendicular."""
    centre_at, radius = fit
    limit = math.sin(lean)

    def admits(k: int) -> bool:
        n = normals[k]
        if n is None or abs(n @ axis) > limit:
            return False
        return all(abs(_from_axis(p, axis, centre_at) - radius) <= slack for p in corners[k])

    return admits


def _within_plane(n: Vector | None, axis: Vector) -> bool:
    return n is not None and abs(n @ axis) <= math.sin(FLAT)


def _facets_of(region: tuple[int, ...], normals: tuple[Vector | None, ...]) -> int:
    """How many distinct facets a region has: normals more than :data:`FLAT` apart."""
    distinct: list[Vector] = []
    for i in region:
        n = normals[i]
        if n is not None and not any(_turn_between(n, d) <= FLAT for d in distinct):
            distinct.append(n)
    return len(distinct)


def _least_turned(normals: tuple[Vector, ...]) -> Vector | None:
    """The direction every one of ``normals`` is nearest to perpendicular to, signed so its
    first non-zero component is positive - or ``None`` when they do not turn at all.

    The smallest eigenvector of the normals' scatter, found by Jacobi rotations on the
    three-by-three matrix, which is all the linear algebra a cylinder needs.
    """
    if len(normals) < 2:
        return None
    m = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    for n in normals:
        parts = (n.x, n.y, n.z)
        for r in range(3):
            for col in range(3):
                m[r][col] += parts[r] * parts[col]
    v = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    for _ in range(50):
        p, q = max(
            ((p, q) for p in range(3) for q in range(p + 1, 3)), key=lambda pq: abs(m[pq[0]][pq[1]])
        )
        if abs(m[p][q]) < 1e-15:
            break
        theta = 0.5 * math.atan2(2.0 * m[p][q], m[q][q] - m[p][p])
        c, s = math.cos(theta), math.sin(theta)
        for k in range(3):
            mkp, mkq = m[k][p], m[k][q]
            m[k][p], m[k][q] = c * mkp - s * mkq, s * mkp + c * mkq
        for k in range(3):
            mpk, mqk = m[p][k], m[q][k]
            m[p][k], m[q][k] = c * mpk - s * mqk, s * mpk + c * mqk
        for k in range(3):
            vkp, vkq = v[k][p], v[k][q]
            v[k][p], v[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    least = min(range(3), key=lambda k: m[k][k])
    axis = Vector(v[0][least], v[1][least], v[2][least])
    if abs(axis) < TOL:
        return None
    return _signed(unit(axis))


def _signed(v: Vector) -> Vector:
    """``v`` or its negative: whichever has a positive largest component, so an axis that
    is ``Z`` to within noise is ``+Z`` and never ``-Z`` on the strength of the noise. Two
    components the same size to within :data:`~bench.geometry.TOL` - a diagonal - are a tie
    the first of them settles, so the noise does not choose between them either."""
    parts = (v.x, v.y, v.z)
    biggest = max(abs(p) for p in parts)
    largest = next(p for p in parts if abs(p) >= biggest - TOL)
    return v if largest >= 0.0 else -v


def _frame(axis: Vector) -> tuple[Vector, Vector]:
    """Two unit directions perpendicular to ``axis`` and to each other."""
    seed = Vector(1.0, 0.0, 0.0) if abs(axis.x) < 0.9 else Vector(0.0, 1.0, 0.0)
    u = unit(seed - axis * (seed @ axis))
    return u, cross(axis, u)


def _circle(
    region: tuple[int, ...],
    axis: Vector,
    corners: tuple[Triangle, ...],
    normals: tuple[Vector | None, ...],
    centres: tuple[Point, ...],
) -> tuple[Point, float] | None:
    """The circle about ``axis`` that ``region`` lies on: its centre, as a point on the axis,
    and its radius - or ``None`` when the facets do not turn enough to cross.

    The centre is where the facets' normals cross, each triangle one vote whatever its size,
    so a flat gathered by mistake cannot pull it far. The radius is the median distance of
    the corners from that centre, for the same reason: a tessellated arc puts its corners on
    the arc, and the median ignores the few that are not.
    """
    u, v = _frame(axis)
    origin = Point(0.0, 0.0, 0.0)
    crossing = _lines_cross(
        tuple(
            ((centres[i] - origin) @ u, (centres[i] - origin) @ v, n @ u, n @ v)
            for i in region
            if (n := normals[i]) is not None
        )
    )
    if crossing is None:
        return None
    cu, cv = crossing
    centre_at = origin + u * cu + v * cv
    radius = median(_from_axis(p, axis, centre_at) for i in region for p in corners[i])
    return centre_at, radius


def _lines_cross(
    lines: tuple[tuple[float, float, float, float], ...],
) -> tuple[float, float] | None:
    """The point nearest every line ``(px, py, dx, dy)`` in the plane, in the least-squares
    sense, or ``None`` when the lines are all parallel."""
    a = b = c = 0.0
    rx = ry = 0.0
    for px, py, dx, dy in lines:
        mx, my = -dy, dx
        a += mx * mx
        b += mx * my
        c += my * my
        along = mx * px + my * py
        rx += mx * along
        ry += my * along
    det = a * c - b * b
    if abs(det) < 1e-12:
        return None
    return ((c * rx - b * ry) / det, (a * ry - b * rx) / det)


def _turn_of(
    region: tuple[int, ...], axis: Vector, centre_at: Point, corners: tuple[Triangle, ...]
) -> float:
    """How much of a circle ``region`` covers, in radians: the whole of it when the biggest
    gap between its vertices, seen around the axis, is no more than a facet."""
    return _arc(region, axis, centre_at, corners)[1]


def _arc(
    region: tuple[int, ...], axis: Vector, centre_at: Point, corners: tuple[Triangle, ...]
) -> tuple[float, float]:
    """The arc ``region`` covers about ``axis``, as the angle it starts at and how far it
    goes on, in radians: the full circle when the biggest gap between its vertices is no
    more than a facet - one and a half of the median step, to allow the tessellation its
    unevenness - and otherwise everything but that gap, starting just past it."""
    u, v = _frame(axis)
    angles = sorted(
        {math.atan2((p - centre_at) @ v, (p - centre_at) @ u) for i in region for p in corners[i]}
    )
    if len(angles) < 2:
        return 0.0, 0.0
    gaps = [b - a for a, b in pairwise(angles)]
    around = angles[0] + 2.0 * math.pi - angles[-1]
    widest = max(*gaps, around)
    facet = median(gaps) if gaps else around
    if widest <= facet * 1.5 + FLAT:
        return angles[0], 2.0 * math.pi
    if widest == around:
        return angles[0], 2.0 * math.pi - widest
    after = gaps.index(widest) + 1
    return angles[after], 2.0 * math.pi - widest


# ---- repeats ---------------------------------------------------------------------------


def _repeats(
    flats: tuple[Flat, ...], rounds: tuple[Round, ...]
) -> tuple[tuple[Flat, ...], tuple[Round, ...], tuple[Repeat, ...]]:
    """The features that repeat, taken out of the two lists and put back as one each."""
    features: tuple[Flat | Round, ...] = (*flats, *rounds)
    used: set[int] = set()
    found: list[Repeat] = []
    for group in _alike(features):
        for members, steps in _lattice(tuple(features[i].centre for i in group)):
            if len(members) < 2:
                continue
            first = group[members[0]]
            used.update(group[k] for k in members)
            found.append(Repeat(one=features[first], steps=steps))
    found.sort(key=lambda r: (-math.prod(s.count for s in r.steps), -r.one.area, r.one.centre.x))
    return (
        tuple(f for i, f in enumerate(flats) if i not in used),
        tuple(r for i, r in enumerate(rounds) if i + len(flats) not in used),
        tuple(found),
    )


def _alike(features: tuple[Flat | Round, ...]) -> tuple[tuple[int, ...], ...]:
    """Groups of features that are the same feature, by kind and by size within :data:`SAME`."""
    groups: list[list[int]] = []
    for i, one in enumerate(features):
        for group in groups:
            if _same(one, features[group[0]]):
                group.append(i)
                break
        else:
            groups.append([i])
    return tuple(tuple(g) for g in groups if len(g) > 1)


def _same(a: Flat | Round, b: Flat | Round) -> bool:
    """Whether two features are the same feature, size for size, whatever their place."""
    match a, b:
        case Flat(), Flat():
            return (
                _turn_between(a.normal, b.normal) <= FLAT
                and abs(a.area - b.area) <= SAME * max(1.0, math.sqrt(a.area))
                and _near_size(a.high - a.low, b.high - b.low)
            )
        case Round(), Round():
            return (
                _turn_between(a.axis, b.axis) <= FLAT
                and a.concave == b.concave
                and abs(a.radius - b.radius) <= SAME
                and abs(a.length - b.length) <= SAME
                and abs(a.turn - b.turn) <= LEAST_TURN
            )
        case _:
            return False


def _near_size(a: Vector, b: Vector) -> bool:
    return abs(a.x - b.x) <= SAME and abs(a.y - b.y) <= SAME and abs(a.z - b.z) <= SAME


def _lattice(
    places: tuple[Point, ...],
) -> tuple[tuple[tuple[int, ...], tuple[Step, ...]], ...]:
    """The rows and grids among ``places``: each as the indices in it, first one first, and
    its steps. A row needs three; a grid two rows of at least two, sharing a step."""
    rows = _rows(places)
    grids: list[tuple[tuple[int, ...], tuple[Step, ...]]] = []
    used: set[int] = set()
    for i, (members, step) in enumerate(rows):
        if i in used or len(members) < 2:
            continue
        alike = [
            j
            for j, (others, other) in enumerate(rows)
            if j not in used and j != i and len(others) == len(members) and _same_step(step, other)
        ]
        candidates = (i, *alike)
        origins = tuple(places[rows[j][0][0]] for j in candidates)
        for chain, across in _rows(origins):
            if len(chain) < 2:
                continue
            row_ids = tuple(candidates[k] for k in chain)
            used.update(row_ids)
            first = rows[row_ids[0]]
            grids.append(
                (
                    tuple(m for j in row_ids for m in rows[j][0]),
                    (Step(first[1], len(first[0])), Step(across, len(chain))),
                )
            )
            break
    singles = [
        (members, (Step(step, len(members)),))
        for i, (members, step) in enumerate(rows)
        if i not in used and len(members) >= 3
    ]
    return (*grids, *singles)


def _same_step(a: Vector, b: Vector) -> bool:
    return abs(a - b) <= PLACE


def _rows(places: tuple[Point, ...]) -> tuple[tuple[tuple[int, ...], Vector], ...]:
    """``places`` cut into rows: from the lowest place left, toward its nearest neighbour,
    as far as places keep landing one step further on. A place with no row is a row of one."""
    left = sorted(range(len(places)), key=lambda i: (places[i].x, places[i].y, places[i].z))
    rows: list[tuple[tuple[int, ...], Vector]] = []
    while left:
        first = left.pop(0)
        if not left:
            rows.append(((first,), Vector(0.0, 0.0, 0.0)))
            break
        nearest = min(left, key=lambda i: abs(places[i] - places[first]))
        step = places[nearest] - places[first]
        if abs(step) <= PLACE:
            # Two features in the same place - a fillet and its mirror image about one
            # axis - are not a repetition, and a step of nothing repeats nothing.
            rows.append(((first,), Vector(0.0, 0.0, 0.0)))
            continue
        members = [first]
        for sign in (1.0, -1.0):
            k = 1
            while True:
                want = places[first] + step * (sign * k)
                hit = next((i for i in left if abs(places[i] - want) <= PLACE), None)
                if hit is None:
                    break
                left.remove(hit)
                if sign < 0.0:
                    members.insert(0, hit)
                else:
                    members.append(hit)
                k += 1
        rows.append((tuple(members), step if len(members) > 1 else Vector(0.0, 0.0, 0.0)))
    return tuple(rows)
