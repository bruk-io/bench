"""Ops: the flat vocabulary - constructors, the face builder, the two-dimensional
modifiers, selectors and queries. The sketch a part is drawn as, and the questions a sheet
asks of it.

``label``, ``polygon``, ``wire`` and ``face`` are :mod:`topology`'s own, where their
validity checks live; the barrel puts them beside these, so a script writing ``from bench
import *`` has the whole vocabulary whichever module a name comes from.

Every label here may be written as a plain ``str``: it reaches
:func:`bench.topology.label`, which is what refuses an empty one or one holding a ``/``.

The plane of the work: a bare ``Wire`` is taken to lie on ``XY``, a ``Face`` carries
its own plane and every operation on it uses that. Angles are radians, distances
millimetres. Outlines run counter-clockwise and holes clockwise; positive ``d`` in
:func:`offset` moves a counter-clockwise wire outward. Every function returns new
values and carries labels across unchanged.

This is the bottom of the chain the verbs are written in: nothing here knows what a body
is, which is what lets :mod:`bench.nest` and :mod:`bench.export` read it without a body
vocabulary coming in behind it. The bodies are :mod:`bench.solids` and the holes
:mod:`bench.features`, and each is written in terms of what is here.
"""

import math
from dataclasses import replace
from itertools import pairwise
from typing import NamedTuple, assert_never, cast

from .geometry import (
    ORIGIN,
    TOL,
    XY,
    Plane,
    Point,
    Vector,
    Z,
    angle,
    cross,
    distance,
    near,
    plane,
    unit,
)
from .topology import (
    Arc,
    Circle,
    Curve,
    Edge,
    Face,
    Label,
    Line,
    Solid,
    Wire,
    curve_end,
    curve_extremes,
    curve_length,
    curve_start,
    face,
    is_closed,
    polygon,
    wire,
)
from .topology import bounds as _bounds

Geom = Wire | Face | Solid

_CONTAINS_CHORD_ERROR = 0.01
"""How far, in millimetres, a chord may sit inside the arc it stands in for when
:func:`contains` flattens a boundary. The step is driven by the radius, so a 500 mm hole
is no less faithful than a 5 mm one."""


class BBox(NamedTuple):
    """An axis-aligned extent in the XY plane."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0


# ---- constructors ------------------------------------------------------------------


def rect(w: float, h: float, at: Point = ORIGIN, label: str | Label | None = None) -> Wire:
    """An axis-aligned rectangle, lower-left corner at ``at``, walked counter-clockwise."""
    x, y, z = at
    corners = (Point(x, y, z), Point(x + w, y, z), Point(x + w, y + h, z), Point(x, y + h, z))
    return polygon(corners, label)


def line(a: Point, b: Point, label: str | Label | None = None) -> Wire:
    """An open wire of one straight edge from ``a`` to ``b`` - a reference line to engrave
    or measure against, not a shape to :func:`fill` or :func:`bench.solids.cut`. Without this,
    the same line means dropping to ``wire((Edge(Line(a, b)),))``.

    Raises:
        ValueError: if ``a`` and ``b`` coincide.
    """
    if near(a, b):
        msg = "a line needs two distinct ends"
        raise ValueError(msg)
    return wire((Edge(Line(a, b)),), label)


def circle(r: float, at: Point = ORIGIN, label: str | Label | None = None) -> Wire:
    """A closed wire of one ``Circle`` edge centred on ``at``, counter-clockwise.

    Raises:
        ValueError: if ``r`` is not positive.
    """
    if r <= TOL:
        msg = "a circle needs a positive radius"
        raise ValueError(msg)
    return wire((Edge(Circle(at, r, XY)),), label)


def slot(w: float, h: float, at: Point = ORIGIN, label: str | Label | None = None) -> Wire:
    """A stadium ``w`` long and ``h`` high - two straight sides and a semicircular end
    each side - with the lower left of its extent at ``at``, counter-clockwise.

    Raises:
        ValueError: if ``h`` is not positive, or ``w`` is not longer than ``h``.
    """
    if h <= TOL:
        msg = "a slot needs a positive height"
        raise ValueError(msg)
    if w <= h + TOL:
        msg = "a slot must be longer than it is high; a round hole is circle()"
        raise ValueError(msg)
    x, y, z = at
    r = h / 2
    quarter = math.pi / 2
    edges = (
        Edge(Line(Point(x + r, y, z), Point(x + w - r, y, z))),
        Edge(Arc(Point(x + w - r, y + r, z), r, -quarter, quarter, XY)),
        Edge(Line(Point(x + w - r, y + h, z), Point(x + r, y + h, z))),
        Edge(Arc(Point(x + r, y + r, z), r, quarter, 3 * quarter, XY)),
    )
    return wire(edges, label)


def rounded_rect(
    w: float, h: float, r: float, at: Point = ORIGIN, label: str | Label | None = None
) -> Wire:
    """A rectangle with its corners rounded to radius ``r``, counter-clockwise. A radius
    of zero gives :func:`rect`.

    Raises:
        ValueError: if ``r`` is negative or larger than half of ``w`` or of ``h``.
    """
    if r < -TOL:
        msg = "a corner radius cannot be negative"
        raise ValueError(msg)
    if r <= TOL:
        return rect(w, h, at, label)
    if r > w / 2 + TOL or r > h / 2 + TOL:
        msg = "a corner radius cannot exceed half the shorter side"
        raise ValueError(msg)
    x, y, z = at
    quarter = math.pi / 2
    edges = (
        Edge(Line(Point(x + r, y, z), Point(x + w - r, y, z))),
        Edge(Arc(Point(x + w - r, y + r, z), r, -quarter, 0.0, XY)),
        Edge(Line(Point(x + w, y + r, z), Point(x + w, y + h - r, z))),
        Edge(Arc(Point(x + w - r, y + h - r, z), r, 0.0, quarter, XY)),
        Edge(Line(Point(x + w - r, y + h, z), Point(x + r, y + h, z))),
        Edge(Arc(Point(x + r, y + h - r, z), r, quarter, math.pi, XY)),
        Edge(Line(Point(x, y + h - r, z), Point(x, y + r, z))),
        Edge(Arc(Point(x + r, y + r, z), r, math.pi, 3 * quarter, XY)),
    )
    return wire(edges, label)


# ---- face builders -----------------------------------------------------------------


def fill(outline: Wire, *, on: Plane = XY, label: str | Label | None = None) -> Face:
    """The face bounded by ``outline``, with no holes, drawn on ``on``.

    ``outline`` is read in ``on``'s own frame and lifted into the world, so a sketch is
    written in flat numbers whatever plane it belongs on: ``fill(rect(10, 6),
    on=plane_of(plate, "top"))`` is a ten by six rectangle standing on the plate's top face
    at the plate's own corner. Drawing on ``XY`` lifts nothing.
    """
    return face(outline, on=on, label=label)


# ---- modifiers ---------------------------------------------------------------------

Corner = Label | int
"""One corner of a wire, named the way :func:`edge` finds one edge: by its label, or by
the index of the edge whose *end* it sits at."""


def chamfer(w: Wire, d: float, *, at: Corner | tuple[Corner, ...] | None = None) -> Wire:
    """``w`` with the chosen corners cut back ``d`` along each of the two straight edges
    that meet there - every corner between two straight edges by default, or just the one
    or more named in ``at``.

    Every straight corner by default is what a printed profile mostly wants: the whole
    outline eased alike, the way :func:`bench.solids.cuboid` wants every vertical edge
    softened at once. ``at`` narrows that to the corners a script actually means - a
    tuple for more than one - and is refused if any of them turns out not to be between
    two straight edges, because asking for one by name is a claim it exists; the default
    sweep is not a claim, so it silently leaves out a corner that is already an
    :class:`~bench.topology.Arc` - one drawn round to begin with, or already filleted -
    rather than refusing the whole wire over it; a corner :func:`chamfer` has already cut is
    still between two straight edges, so the default sweep cuts it again, further back.
    Multiple corners are cut back in one
    call, each against the edges as the corners before it in the list left them, so two
    corners sharing an edge only conflict when their two cuts really overlap it.

    Raises:
        ValueError: if ``d`` is not positive, an explicitly named corner is not between
            two straight edges, ``d`` reaches past either edge it cuts, or ``at`` is
            ``None`` and the wire has no corner between two straight edges to chamfer.
    """
    if d <= TOL:
        msg = "a chamfer needs a positive size"
        raise ValueError(msg)
    corners = _corners(w, at)
    if not corners:
        msg = "no corner between two straight edges to chamfer"
        raise ValueError(msg)
    edges = list(w.edges)
    for i in sorted(set(corners), reverse=True):
        edges = _chamfer_one(edges, i, d)
    return wire(tuple(edges), w.label)


def fillet(w: Wire, r: float, *, at: Corner | tuple[Corner, ...] | None = None) -> Wire:
    """``w`` with the chosen corners rounded to radius ``r`` - every corner between two
    straight edges by default, or just the one or more named in ``at`` - by an
    :class:`~bench.topology.Arc` tangent to both edges, exactly where :func:`chamfer`
    would put its straight cut.

    The arc is built directly at the corner - the tangent length ``r / tan(theta / 2)``
    back along each edge, an arc of radius ``r`` between the two tangent points, where
    ``theta`` is the angle the two edges turn through - rather than by growing the whole
    wire with :func:`offset` and shrinking it back, because :func:`offset` mitres a
    straight corner rather than rounding it, and teaching it to round every corner would
    change what kerf compensation means everywhere else that function is used. The two
    constructions reach the geometry decision-11 describes - grow, then shrink back, with
    a round joint at the corner - without touching that machinery. Built this way, the
    corner takes no side on convex or concave: ``theta`` is the unsigned angle between the
    two edges, so a notch is rounded exactly as a bump is, and ``at`` chooses corners the
    same way :func:`chamfer`'s does, including the same silent skip of a corner that is
    not between two straight edges when ``at`` is left as every corner.

    Raises:
        ValueError: if ``r`` is not positive, an explicitly named corner is not between
            two straight edges, the two edges there run straight through the corner or
            fold back on themselves (nothing to round), the tangent length reaches past
            either edge, or ``at`` is ``None`` and the wire has no corner between two
            straight edges to fillet.
    """
    if r <= TOL:
        msg = "a fillet needs a positive radius"
        raise ValueError(msg)
    corners = _corners(w, at)
    if not corners:
        msg = "no corner between two straight edges to fillet"
        raise ValueError(msg)
    edges = list(w.edges)
    for i in sorted(set(corners), reverse=True):
        edges = _fillet_one(edges, i, r)
    return wire(tuple(edges), w.label)


def _corners(w: Wire, at: Corner | tuple[Corner, ...] | None) -> tuple[int, ...]:
    """The edge indices ``at`` names, or every corner between two straight edges when
    ``at`` is ``None``."""
    if at is None:
        return _straight_corners(w)
    items = at if isinstance(at, tuple) else (at,)
    return tuple(_edge_index(w, item) for item in items)


def _straight_corners(w: Wire) -> tuple[int, ...]:
    """Every corner of ``w`` that sits between two straight edges, in edge order. The
    corner wrapping from the last edge to the first is only counted on a closed wire -
    an open wire's two loose ends are not a corner at all."""
    n = len(w.edges)
    last = n if is_closed(w) else n - 1
    return tuple(
        i for i in range(last) if _straight_pair(w.edges[i].curve, w.edges[(i + 1) % n].curve)
    )


def _straight_pair(a: Curve, b: Curve) -> bool:
    return isinstance(a, Line) and isinstance(b, Line)


def _corner_edges(edges: list[Edge], i: int) -> tuple[int, Line, Line]:
    """The two straight edges meeting at corner ``i``, and the index of the second.

    Raises:
        ValueError: if either is not a :class:`Line`.
    """
    j = (i + 1) % len(edges)
    a, b = edges[i].curve, edges[j].curve
    if not isinstance(a, Line) or not isinstance(b, Line):
        msg = "a corner between two straight edges is needed here"
        raise ValueError(msg)
    return j, a, b


def _chamfer_one(edges: list[Edge], i: int, d: float) -> list[Edge]:
    j, a, b = _corner_edges(edges, i)
    if d >= abs(a.end - a.start) - TOL or d >= abs(b.end - b.start) - TOL:
        msg = "a chamfer cannot be longer than the edges it cuts"
        raise ValueError(msg)
    back = a.end - unit(a.end - a.start) * d
    on = b.start + unit(b.end - b.start) * d
    out = list(edges)
    out[i] = replace(out[i], curve=Line(a.start, back))
    out[j] = replace(out[j], curve=Line(on, b.end))
    out.insert(i + 1, Edge(Line(back, on)))
    return out


def _fillet_one(edges: list[Edge], i: int, r: float) -> list[Edge]:
    j, a, b = _corner_edges(edges, i)
    vertex = a.end
    back = unit(a.start - vertex)
    fwd = unit(b.end - vertex)
    theta = angle(back, fwd)
    if theta <= TOL or theta >= math.pi - TOL:
        msg = "a fillet needs a real corner, not edges that run straight through it or fold back"
        raise ValueError(msg)
    reach = r / math.tan(theta / 2)
    if reach >= abs(a.end - a.start) - TOL or reach >= abs(b.end - b.start) - TOL:
        msg = "a fillet cannot reach past either edge it rounds"
        raise ValueError(msg)
    p1 = vertex + back * reach
    p2 = vertex + fwd * reach
    centre = vertex + unit(back + fwd) * (r / math.sin(theta / 2))
    on = plane(centre, cross(back, fwd), p1 - centre)
    arc = Arc(centre, r, 0.0, _angle_of(p2, centre, on), on)
    out = list(edges)
    out[i] = replace(out[i], curve=Line(a.start, p1))
    out[j] = replace(out[j], curve=Line(p2, b.end))
    out.insert(i + 1, Edge(arc))
    return out


def offset[T: Wire | Face](shape: T, d: float) -> T:
    """``shape`` grown by ``d``: straight edges shift along the right-hand normal of
    travel and meet again at mitres, arcs keep their centre and change radius.

    On a wire, positive ``d`` is outward for a counter-clockwise outline and inward
    for a clockwise one. On a face the outer wire grows and every hole shrinks by the
    same ``d`` whichever way its wire runs, which is what kerf compensation wants.
    An offset larger than a feature will self-intersect; nothing repairs that.

    A bare wire is taken to lie on ``XY``, so one standing out of that plane is refused
    rather than offset in some direction of its own. A face carries its own plane and is
    offset in it, whichever way that plane faces.

    Raises:
        ValueError: if a bare wire does not lie in a plane parallel to XY, or ``d`` eats
            an arc or a circle down to nothing.
    """
    match shape:
        case Wire():
            if not _flat_in_xy(shape):
                msg = "offset works on a wire in a plane parallel to XY"
                raise ValueError(msg)
            return cast("T", _offset_wire(shape, d, XY))
        case Face():
            on = shape.plane
            return cast(
                "T",
                replace(
                    shape,
                    outer=_offset_wire(shape.outer, d if _ccw(shape.outer, on) else -d, on),
                    inner=tuple(_offset_wire(h, -d if _ccw(h, on) else d, on) for h in shape.inner),
                ),
            )
        case _:
            assert_never(shape)


# ---- selectors ---------------------------------------------------------------------


def edges(
    shape: Wire | Face,
    *,
    direction: Vector | None = None,
    near_point: Point | None = None,
    label: Label | None = None,
    tol: float = TOL,
) -> tuple[Edge, ...]:
    """The edges of ``shape`` that match every predicate given, in order: a face's
    outer wire first, then each hole.

    ``direction`` keeps straight edges parallel to it, either way round.
    ``near_point`` keeps edges passing within ``tol`` of a point. ``label`` is exact.
    """
    out = _all_edges(shape)
    if direction is not None:
        out = tuple(e for e in out if _is_parallel(e.curve, direction, tol))
    if near_point is not None:
        out = tuple(e for e in out if _distance_to(e.curve, near_point) <= tol)
    if label is not None:
        out = tuple(e for e in out if e.label == label)
    return out


def edge(
    shape: Wire | Face,
    *,
    direction: Vector | None = None,
    near_point: Point | None = None,
    label: Label | None = None,
    tol: float = TOL,
) -> Edge:
    """The one edge matching the predicates.

    Raises:
        LookupError: if no edge matches, or more than one does.
    """
    found = edges(shape, direction=direction, near_point=near_point, label=label, tol=tol)
    if len(found) != 1:
        msg = f"{len(found)} edges match, not one"
        raise LookupError(msg)
    return found[0]


# ---- queries -----------------------------------------------------------------------


def bbox(shape: Geom) -> BBox:
    """The extent of ``shape`` in world X and Y, arc bulges included however the arc's own
    frame is turned.

    A solid is the XY shadow of its :func:`~bench.topology.bounds`, and so inherits that
    bound's conservatism under a cut; a flat shape is exact. This stays two-dimensional
    because that is what a sheet, a bed and a nest are.

    Raises:
        ValueError: if ``shape`` holds no geometry to bound.
    """
    match shape:
        case Solid():
            box = _bounds(shape)
            return BBox(box.x0, box.y0, box.x1, box.y1)
        case Wire() | Face():
            points = _extremes(shape)
        case _:
            assert_never(shape)
    if not points:
        msg = "an empty shape has no extent"
        raise ValueError(msg)
    xs = tuple(p.x for p in points)
    ys = tuple(p.y for p in points)
    return BBox(min(xs), min(ys), max(xs), max(ys))


def area(f: Face) -> float:
    """The material area of a face: inside the outer wire, outside every hole."""
    return abs(_signed_area(f.outer, f.plane)) - sum(abs(_signed_area(h, f.plane)) for h in f.inner)


def perimeter(w: Wire) -> float:
    """The length walked along a wire."""
    return math.fsum(curve_length(e.curve) for e in w.edges)


def centroid(f: Face) -> Point:
    """The area centroid of a face, holes taken out.

    Raises:
        ValueError: if the face has no area to balance.
    """
    total = 0.0
    mu = 0.0
    mv = 0.0
    for w, weight in ((f.outer, 1.0), *((h, -1.0) for h in f.inner)):
        a, u, v = _moments(w, f.plane)
        s = weight if a >= 0 else -weight
        total += s * a
        mu += s * u
        mv += s * v
    if abs(total) < TOL:
        msg = "a face with no area has no centroid"
        raise ValueError(msg)
    return _at(mu / total, mv / total, f.plane)


def is_ccw(w: Wire) -> bool:
    """Whether ``w`` is walked counter-clockwise seen from +Z. A wire with no area
    encloses nothing and is not counter-clockwise."""
    return _signed_area(w, XY) > 0.0


def contains(f: Face, p: Point) -> bool:
    """Whether ``p`` lies in the material of ``f``: inside the outer wire and outside
    every hole. Arcs are flattened to chords no further than
    :data:`_CONTAINS_CHORD_ERROR` from the true curve, so a point within that of a curved
    boundary may go either way."""
    if not _inside(f.outer, p, f.plane):
        return False
    return not any(_inside(h, p, f.plane) for h in f.inner)


_GLYPH_ADVANCE = 0.6
"""One character's width as a fraction of its cap height - the one constant
:func:`text_width` estimates from, since a :class:`~bench.model.Text` is a string, a place
and a cap height, not glyph outlines a real width could be measured against."""


def text_width(text: str, size: float) -> float:
    """The estimated width of ``text`` set at cap height ``size``: a flat
    :data:`_GLYPH_ADVANCE` times ``size`` per character. Good enough to centre a label under
    a pull or over a joint; a long run of characters in a proportional font will not sit
    exactly where this says, since nothing here knows the font the machine will use."""
    return _GLYPH_ADVANCE * size * len(text)


# ---- plane coordinates -------------------------------------------------------------


def _uv(p: Point, on: Plane) -> tuple[float, float]:
    v = p - on.origin
    return (v @ on.x_dir, v @ on.y_dir)


def _at(u: float, v: float, on: Plane) -> Point:
    return on.origin + on.x_dir * u + on.y_dir * v


def _at_angle(centre: Point, r: float, on: Plane, theta: float) -> Point:
    return centre + on.x_dir * (r * math.cos(theta)) + on.y_dir * (r * math.sin(theta))


def _angle_of(p: Point, centre: Point, on: Plane) -> float:
    v = p - centre
    return math.atan2(v @ on.y_dir, v @ on.x_dir)


def _branch(theta: float, near_to: float) -> float:
    """``theta`` shifted by whole turns to sit as close to ``near_to`` as it can."""
    turns = round((near_to - theta) / (2 * math.pi))
    return theta + 2 * math.pi * turns


def _frame_sign(c: Plane, on: Plane) -> float:
    """+1 when a curve's own frame turns the same way as the reference plane's."""
    return 1.0 if (c.normal @ on.normal) >= 0 else -1.0


# ---- offset ------------------------------------------------------------------------


def _flat_in_xy(w: Wire) -> bool:
    """Whether ``w`` lies in a plane parallel to XY: straight edges level in Z, arcs and
    circles drawn in a frame whose normal stands along Z. Offsetting a bare wire that does
    not would hand :func:`_right` a direction along its own normal and get "zero vector"
    back; a face says which plane it is on, so it never has to guess."""
    for e in w.edges:
        match e.curve:
            case Line(start, end):
                if abs((end - start) @ Z) > TOL:
                    return False
            case Arc(_, _, _, _, on) | Circle(_, _, on):
                if abs(abs(on.normal @ Z) - 1.0) > TOL:
                    return False
            case _:
                assert_never(e.curve)
    return True


def _right(along: Vector, n: Vector) -> Vector:
    """The unit normal to the right of travel, seen from ``n``."""
    return unit(cross(along, n))


def _arc_sign(centre: Point, a0: float, a1: float, on: Plane, n: Vector) -> float:
    """+1 when offsetting to the right of travel leaves the centre, -1 when it
    approaches it - so a convex corner grows and a concave one shrinks."""
    sweep = 1.0 if a1 >= a0 else -1.0
    tangent = (on.x_dir * -math.sin(a0) + on.y_dir * math.cos(a0)) * sweep
    radial = _at_angle(centre, 1.0, on, a0) - centre
    return 1.0 if _right(tangent, n) @ radial > 0 else -1.0


def _offset_curve(c: Curve, d: float, n: Vector) -> Curve:
    """``c`` moved ``d`` along the right-hand normal of travel.

    Raises:
        ValueError: if the offset eats an arc's radius.
    """
    match c:
        case Line(start, end):
            shift = _right(end - start, n) * d
            return Line(start + shift, end + shift)
        case Arc(centre, r, a0, a1, on):
            grown = r + d * _arc_sign(centre, a0, a1, on, n)
            if grown < TOL:
                msg = "offset collapses an arc"
                raise ValueError(msg)
            return Arc(centre, grown, a0, a1, on)
        case Circle(centre, r, on):
            grown = r + d * _arc_sign(centre, 0.0, 2 * math.pi, on, n)
            if grown < TOL:
                msg = "offset collapses a circle"
                raise ValueError(msg)
            return Circle(centre, grown, on)
        case _:
            assert_never(c)


def _offset_wire(w: Wire, d: float, on: Plane) -> Wire:
    if abs(d) < TOL:
        return w
    was = tuple(e.curve for e in w.edges)
    now = [_offset_curve(c, d, on.normal) for c in was]
    labels = [e.label for e in w.edges]
    if len(now) == 1:
        return replace(w, edges=(Edge(now[0], labels[0]),))
    curves = [now[0]]
    keep = [labels[0]]
    for i in range(1, len(now)):
        a, bridge, b = _join(curves[-1], now[i], curve_end(was[i - 1]), on)
        curves[-1] = a
        if bridge is not None:
            curves.append(bridge)
            keep.append(None)
        curves.append(b)
        keep.append(labels[i])
    if is_closed(w):
        a, bridge, b = _join(curves[-1], curves[0], curve_end(was[-1]), on)
        curves[-1] = a
        curves[0] = b
        if bridge is not None:
            curves.append(bridge)
            keep.append(None)
    return wire(tuple(Edge(c, k) for c, k in zip(curves, keep, strict=True)), w.label)


def _join(a: Curve, b: Curve, corner: Point, on: Plane) -> tuple[Curve, Curve | None, Curve]:
    """``a`` and ``b`` trimmed to where they cross, or bridged by a straight edge when
    they do not cross at all."""
    if near(curve_end(a), curve_start(b)):
        return a, None, b
    hits = _crossings(a, b, on)
    if hits:
        p = min(hits, key=lambda q: distance(q, corner))
        return _with_end(a, p), None, _with_start(b, p)
    return a, Line(curve_end(a), curve_start(b)), b


def _with_end(c: Curve, p: Point) -> Curve:
    match c:
        case Line(start, _):
            return Line(start, p)
        case Arc(centre, r, a0, a1, on):
            return Arc(centre, r, a0, _branch(_angle_of(p, centre, on), a1), on)
        case Circle():
            return c
        case _:
            assert_never(c)


def _with_start(c: Curve, p: Point) -> Curve:
    match c:
        case Line(_, end):
            return Line(p, end)
        case Arc(centre, r, a0, a1, on):
            return Arc(centre, r, _branch(_angle_of(p, centre, on), a0), a1, on)
        case Circle():
            return c
        case _:
            assert_never(c)


class _Ray(NamedTuple):
    """An endless straight line in plane coordinates, ``d`` a unit direction."""

    px: float
    py: float
    dx: float
    dy: float


class _Round(NamedTuple):
    """The whole circle an arc runs on, in plane coordinates."""

    cx: float
    cy: float
    r: float


def _host(c: Curve, on: Plane) -> _Ray | _Round:
    match c:
        case Line(start, end):
            x0, y0 = _uv(start, on)
            x1, y1 = _uv(end, on)
            length = math.hypot(x1 - x0, y1 - y0)
            if length < TOL:
                return _Ray(x0, y0, 0.0, 0.0)
            return _Ray(x0, y0, (x1 - x0) / length, (y1 - y0) / length)
        case Arc(centre, r, _, _, _) | Circle(centre, r, _):
            cx, cy = _uv(centre, on)
            return _Round(cx, cy, r)
        case _:
            assert_never(c)


def _crossings(a: Curve, b: Curve, on: Plane) -> tuple[Point, ...]:
    """Where the endless geometries behind two curves meet, in world points."""
    match (_host(a, on), _host(b, on)):
        case (_Ray() as r1, _Ray() as r2):
            found = _ray_ray(r1, r2)
        case (_Ray() as r, _Round() as o):
            found = _ray_round(r, o)
        case (_Round() as o, _Ray() as r):
            found = _ray_round(r, o)
        case (_Round() as o1, _Round() as o2):
            found = _round_round(o1, o2)
        case _:
            found = ()
    return tuple(_at(u, v, on) for u, v in found)


def _ray_ray(a: _Ray, b: _Ray) -> tuple[tuple[float, float], ...]:
    den = a.dx * b.dy - a.dy * b.dx
    if abs(den) < 1e-9:
        return ()
    t = ((b.px - a.px) * b.dy - (b.py - a.py) * b.dx) / den
    return ((a.px + a.dx * t, a.py + a.dy * t),)


def _ray_round(a: _Ray, o: _Round) -> tuple[tuple[float, float], ...]:
    fx, fy = a.px - o.cx, a.py - o.cy
    b = fx * a.dx + fy * a.dy
    disc = b * b - (fx * fx + fy * fy - o.r * o.r)
    if disc < 0.0:
        return ()
    root = math.sqrt(disc)
    steps = (-b,) if root < TOL else (-b - root, -b + root)
    return tuple((a.px + a.dx * t, a.py + a.dy * t) for t in steps)


def _round_round(a: _Round, b: _Round) -> tuple[tuple[float, float], ...]:
    dx, dy = b.cx - a.cx, b.cy - a.cy
    gap = math.hypot(dx, dy)
    if gap < TOL or gap > a.r + b.r or gap < abs(a.r - b.r):
        return ()
    mid = (gap * gap + a.r * a.r - b.r * b.r) / (2 * gap)
    h2 = a.r * a.r - mid * mid
    h = math.sqrt(h2) if h2 > 0.0 else 0.0
    bx, by = a.cx + dx * mid / gap, a.cy + dy * mid / gap
    return ((bx - dy * h / gap, by + dx * h / gap), (bx + dy * h / gap, by - dx * h / gap))


# ---- selector helpers --------------------------------------------------------------


def _all_edges(shape: Wire | Face) -> tuple[Edge, ...]:
    match shape:
        case Wire(edges, _):
            return edges
        case Face(_, outer, inner, _):
            return (*outer.edges, *(e for h in inner for e in h.edges))
        case _:
            assert_never(shape)


def _edge_index(w: Wire, at: Label | int) -> int:
    """The position of an edge in a wire, by index or by label.

    Raises:
        LookupError: if the index is out of range or no edge carries the label.
    """
    if isinstance(at, int):
        if not -len(w.edges) <= at < len(w.edges):
            msg = f"a wire of {len(w.edges)} edges has no edge {at}"
            raise LookupError(msg)
        return at % len(w.edges)
    for i, e in enumerate(w.edges):
        if e.label == at:
            return i
    msg = f"no edge labelled {at!r}"
    raise LookupError(msg)


def _is_parallel(c: Curve, direction: Vector, tol: float) -> bool:
    match c:
        case Line(start, end):
            along = end - start
            if abs(along) < TOL or abs(direction) < TOL:
                return False
            return abs(cross(unit(along), unit(direction))) <= tol
        case Arc() | Circle():
            return False
        case _:
            assert_never(c)


def _distance_to(c: Curve, p: Point) -> float:
    match c:
        case Line(start, end):
            along = end - start
            length = abs(along)
            if length < TOL:
                return distance(p, start)
            t = max(0.0, min(1.0, ((p - start) @ along) / (length * length)))
            return distance(p, start + along * t)
        case Arc(centre, r, a0, a1, on):
            lo, hi = min(a0, a1), max(a0, a1)
            theta = _branch(_angle_of(p, centre, on), (lo + hi) / 2)
            if lo - TOL <= theta <= hi + TOL:
                return distance(p, _at_angle(centre, r, on, theta))
            return min(distance(p, curve_start(c)), distance(p, curve_end(c)))
        case Circle(centre, r, on):
            return distance(p, _at_angle(centre, r, on, _angle_of(p, centre, on)))
        case _:
            assert_never(c)


# ---- query helpers -----------------------------------------------------------------


def _extremes(shape: Wire | Face) -> tuple[Point, ...]:
    match shape:
        case Wire(edges, _):
            return tuple(p for e in edges for p in curve_extremes(e.curve))
        case Face(_, outer, inner, _):
            return (*_extremes(outer), *(p for h in inner for p in _extremes(h)))
        case _:
            assert_never(shape)


def _moments(w: Wire, on: Plane) -> tuple[float, float, float]:
    """Signed area and first moments of the region a closed wire encloses, in plane
    coordinates: the chord polygon plus one circular segment per arc."""
    ring = tuple(_uv(curve_start(e.curve), on) for e in w.edges)
    a = 0.0
    mu = 0.0
    mv = 0.0
    for (x0, y0), (x1, y1) in pairwise((*ring, ring[0])):
        twice = x0 * y1 - x1 * y0
        a += twice / 2
        mu += (x0 + x1) * twice / 6
        mv += (y0 + y1) * twice / 6
    for e in w.edges:
        match e.curve:
            case Line():
                continue
            case Arc(centre, r, a0, a1, cp):
                sweep = (a1 - a0) * _frame_sign(cp, on)
                half = (a0 + a1) / 2
            case Circle(centre, r, cp):
                sweep = 2 * math.pi * _frame_sign(cp, on)
                half = 0.0
            case _:
                assert_never(e.curve)
        cu, cv = _uv(centre, on)
        bulge = r * r * (sweep - math.sin(sweep)) / 2
        arm = 2 * r**3 * math.sin(sweep / 2) ** 3 / 3
        mx, my = _uv(_at_angle(centre, 1.0, cp, half), on)
        a += bulge
        mu += bulge * cu + arm * (mx - cu)
        mv += bulge * cv + arm * (my - cv)
    return a, mu, mv


def _signed_area(w: Wire, on: Plane) -> float:
    return _moments(w, on)[0]


def _ccw(w: Wire, on: Plane) -> bool:
    return _signed_area(w, on) > 0.0


def _flat_step(radius: float) -> float:
    """The widest turn whose chord stays within :data:`_CONTAINS_CHORD_ERROR` of the arc,
    so a big hole is cut into as many steps as a small one needs per millimetre."""
    if radius <= _CONTAINS_CHORD_ERROR:
        return math.pi
    return 2.0 * math.acos(1.0 - _CONTAINS_CHORD_ERROR / radius)


def _flat(w: Wire, on: Plane) -> tuple[tuple[float, float], ...]:
    """A wire as a ring of plane coordinates, arcs chopped into short straight steps."""
    out: list[tuple[float, float]] = []
    for e in w.edges:
        match e.curve:
            case Line(start, _):
                out.append(_uv(start, on))
            case Arc(centre, r, a0, a1, cp):
                count = max(2, math.ceil(abs(a1 - a0) / _flat_step(r)))
                out += [
                    _uv(_at_angle(centre, r, cp, a0 + (a1 - a0) * k / count), on)
                    for k in range(count)
                ]
            case Circle(centre, r, cp):
                count = max(3, math.ceil(2 * math.pi / _flat_step(r)))
                out += [
                    _uv(_at_angle(centre, r, cp, 2 * math.pi * k / count), on) for k in range(count)
                ]
            case _:
                assert_never(e.curve)
    return tuple(out)


def _inside(w: Wire, p: Point, on: Plane) -> bool:
    """Crossing count against a flattened wire: odd means in."""
    x, y = _uv(p, on)
    ring = _flat(w, on)
    crossings = 0
    for (x0, y0), (x1, y1) in pairwise((*ring, ring[0])):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            crossings += 1
    return crossings % 2 == 1
