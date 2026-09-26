"""Shell: a body hollowed to a wall, open where it is asked.

A mesh kernel has no offset of a surface, so nothing here offsets one. What bench has instead
is the recipe: a body it knows the making of - an extrusion, a revolve, a loft of two
profiles, a sweep - is made again from its profile inset by the wall, and that second body is taken
out of the first. The cavity is a body like any other, under a label of its own, so its faces
are named the way every tool's are and face into the hollow the way every face a cut leaves
does (see :func:`bench.solids.plane_of`): a cup's inner floor is ``inside/bottom``, facing up.

**Where the wall is measured.** An extrusion's wall is its profile's inset, and its floor and
roof are the same figure along the sweep, so every wall is ``wall`` exactly. A revolve's
profile holds its axis, so an inset in the profile's plane is the inset normal to the surface
it turns, and the wall is exact there too. **A loft's is not**: its two profiles are inset in
their own planes, so ``wall`` is measured across the loft, level with the profiles, and a side
leaning ``a`` off square to them is ``wall * cos(a)`` thick along its own normal - a
45 degree funnel shelled at 2 mm is 1.41 mm through. :func:`bench.checks.wall` measures the
real thing through the side; at an open end of a leaning loft it also reads the knife edge
where the side meets the flat end - a tenth of a millimetre or so, true of any edge that
sharp and not of the wall - so its thinnest figure there is the rim's, not the side's.

**Opening.** A face named in ``open`` is not walled: the cavity runs past it, so the body is
open there. An extrusion opens at ``top`` and ``bottom``, a loft at the words its two
profiles were given in - ``bottom`` the first, ``top`` the second - a revolve at any of its
``side-`` faces, and at ``start`` and ``end`` when it is a partial turn, and a sweep at its
``start`` and ``end``. A sweep's inset is carried along its own path, so its wall is exact.
"""

import math
from collections.abc import Collection
from dataclasses import replace
from typing import assert_never

from .geometry import TOL, Axis, Plane, Point, Transform, Vector, identity, plane, raised, unit
from .ops import fill, offset, rect
from .solids import cut, extrude, hull, move, name, rotate, union
from .topology import (
    Curve,
    Difference,
    Edge,
    Extrude,
    Face,
    Hull,
    Imported,
    Intersection,
    Label,
    Line,
    Moved,
    Node,
    Revolve,
    Solid,
    Swept,
    Union,
    Wire,
    bounds,
    curve_end,
    curve_start,
    face,
    faces_of,
    moved,
    straight,
    sweep_stations,
    wire,
)
from .topology import label as _label

PAST = 1.0
"""How far, in millimetres, a cavity runs past a face left open, so the opening is a cut
through the wall and never a face lying exactly on the body's own."""


def shell(
    body: Solid,
    wall: float,
    *,
    open: Collection[str] = (),
    inside: str | Label = "inside",
    label: str | Label | None = None,
) -> Solid:
    """``body`` hollowed to ``wall`` millimetres, open at the faces named in ``open``.

    ``body`` is an extrusion, a revolve, a two-profile :func:`~bench.solids.loft` or a
    :func:`~bench.sweep.sweep`, as made or moved: the recipe is run again on its profile
    inset by ``wall`` and the result cut out under ``inside``, so the inner faces answer to
    ``inside/...`` - an extrusion's inner floor is ``inside/bottom`` and its inner walls
    ``inside/side-...``, a revolve's inner walls ``inside/side-...`` named after the outer
    edges they follow, a sweep's ``inside/start``, ``inside/end`` and ``inside/side-...``. A
    loft's inner wall is a hull, which keeps no names, so all of it answers to ``inside``; a
    closed end of one is ``inside/bottom`` or ``inside/top``. Every inner face faces into the
    hollow, so a part mated onto one sits inside.

    A loft's wall is measured level with its profiles and not square to its side - see the
    module's own note - and a revolve's profile has straight edges only.

    A twisted or tapered extrusion - a :func:`~bench.threads.thread`, a draft - is refused:
    its cavity would be the inset profile swept straight, which neither turns with the
    twist nor narrows with the taper, so the wall would run thin and thick round it.

    Raises:
        ValueError: if ``wall`` is not positive, if ``body`` is not a recipe that can be run
            again (a union, a cut, a hull of anything but two profiles, an import), if it is
            an extrusion that twists or tapers, if a name in ``open`` is not a face that can
            be opened on it, or if the wall is too thick for the body - the inset profile
            collapses or the floor meets the roof.
    """
    if wall <= TOL:
        msg = f"a shell needs a wall to leave, not {wall}"
        raise ValueError(msg)
    node, at = _recipe(body.node)
    opened = frozenset(open)
    match node:
        case Extrude():
            cavity = _extrusion_cavity(node, wall, opened)
        case Revolve():
            cavity = _revolved_cavity(node, wall, opened)
        case Hull(parts):
            cavity = _lofted_cavity(parts, wall, opened)
        case Swept():
            cavity = _swept_cavity(node, wall, opened)
        case Union() | Difference() | Intersection() | Imported() | Moved():
            msg = (
                "shell hollows an extrusion, a revolve, a loft of two profiles or a sweep by "
                f"making it again; a {type(node).__name__.lower()} has no one profile to inset"
            )
            raise ValueError(msg)
        case _:
            assert_never(node)
    placed = cavity if at == identity() else moved(cavity, at)
    hollowed = cut(body, placed, label=inside)
    return hollowed if label is None else name(hollowed, label)


def _recipe(node: Node) -> tuple[Node, Transform]:
    """The recipe under any moves, and the moves it stands under."""
    match node:
        case Moved(inner, t):
            found, under = _recipe(inner)
            return found, t @ under
        case _:
            return node, identity()


def _refused(kind: str, asked: frozenset[str], allowed: Collection[str]) -> None:
    """Refuse a name in ``open`` the body cannot be opened at.

    Raises:
        ValueError: if ``asked`` holds a name ``allowed`` does not.
    """
    stray = sorted(asked - frozenset(allowed))
    if stray:
        can = ", ".join(sorted(allowed)) or "nothing"
        msg = f"{kind} cannot be opened at {', '.join(stray)}; it opens at {can}"
        raise ValueError(msg)


# ---- an extrusion ----------------------------------------------------------------------


def _extrusion_cavity(node: Extrude, wall: float, opened: frozenset[str]) -> Solid:
    """The same sweep of the profile inset by ``wall``, from ``wall`` above the bottom to
    ``wall`` below the top - or ``PAST`` beyond either where it is open.

    Raises:
        ValueError: if the extrusion twists or tapers, since the inset profile swept straight
            would not follow it; if ``opened`` names a side; or if the wall leaves no room
            between the floor and the roof.
    """
    if not straight(node):
        msg = (
            "shell cannot hollow a twisted or tapered extrusion: its inset profile would be"
            " swept straight, not turned or narrowed with it, so the wall would not be even"
        )
        raise ValueError(msg)
    _refused("an extrusion", opened, ("top", "bottom"))
    length = abs(node.distance)
    low = -PAST if "bottom" in opened else wall
    high = length + PAST if "top" in opened else length - wall
    if high - low <= TOL:
        msg = f"a {wall} mm floor and roof leave nothing of a {length} mm extrusion to hollow"
        raise ValueError(msg)
    run = node.profile.plane.normal * math.copysign(1.0, node.distance)
    lifted = move(_inset(node.profile, wall), run * low)
    return Solid(replace(node, profile=lifted, distance=math.copysign(high - low, node.distance)))


def _inset(profile: Face, wall: float) -> Face:
    """``profile`` shrunk by ``wall`` and its holes grown by as much - :func:`offset`'s
    ``ValueError`` when that eats a curve."""
    return offset(profile, -wall)


# ---- a revolve -------------------------------------------------------------------------


def _revolved_cavity(node: Revolve, wall: float, opened: frozenset[str]) -> Solid:
    """The same turn of the profile with every edge moved in by ``wall``, except an edge on
    the axis, which stays there, and an edge whose face is open, which moves out by
    ``PAST``.

    Raises:
        ValueError: if the profile holds a hole or a curve, if ``opened`` names a face this
            revolve does not have, or if the inset folds the profile through itself.
    """
    profile = node.profile
    if profile.inner:
        msg = "shell turns a revolve's profile inset, and a profile with a hole in it is not one"
        raise ValueError(msg)
    if any(not isinstance(e.curve, Line) for e in profile.outer.edges):
        msg = "shell insets a revolve's profile edge by edge, and only a straight edge so far"
        raise ValueError(msg)
    whole = node.angle >= math.tau - TOL
    sides = tuple(f.label for f in faces_of(Solid(node)))[: len(profile.outer.edges)]
    _refused("this revolve", opened, (*sides, *(() if whole else ("start", "end"))))
    if not whole and not {"start", "end"} <= opened:
        msg = "a partial revolve is shelled open at its start and end; walling them is not done"
        raise ValueError(msg)
    moves = tuple(
        0.0 if _on_axis(e, node.axis) else PAST if side in opened else -wall
        for e, side in zip(profile.outer.edges, sides, strict=True)
    )
    inset = _moved_edges(profile, moves, sides)
    if whole:
        return Solid(replace(node, profile=inset))
    beyond = min(PAST / _reach(profile, node.axis), (math.tau - node.angle) / 2)
    wider = Solid(replace(node, profile=inset, angle=node.angle + 2 * beyond))
    return rotate(wider, -beyond, about=node.axis)


def _on_axis(e: Edge, axis: Axis) -> bool:
    """Whether a straight edge lies along ``axis``, sweeping nothing."""
    return all(_off_axis(p, axis) <= TOL for p in (curve_start(e.curve), curve_end(e.curve)))


def _off_axis(p: Point, axis: Axis) -> float:
    """How far ``p`` stands from the line of ``axis``."""
    run = axis.direction * (1.0 / abs(axis.direction))
    v = p - axis.origin
    return abs(v - run * (v @ run))


def _reach(profile: Face, axis: Axis) -> float:
    """The furthest the profile stands from its axis."""
    return max(_off_axis(curve_start(e.curve), axis) for e in profile.outer.edges)


def _moved_edges(profile: Face, moves: tuple[float, ...], sides: tuple[Label, ...]) -> Face:
    """``profile``'s straight outline with edge ``i`` moved ``moves[i]`` outward, each corner
    where its two neighbours now meet, and each edge keeping the name its face had - so the
    cavity's faces are named after the outer faces they follow.

    Two neighbours that ran on in one line and moved by different amounts are joined by a
    short step, named after the edge it follows. An outline the move folds through itself -
    a wall too thick for it - is :func:`~bench.topology.wire`'s ``ValueError``.
    """
    on = profile.plane
    ends = tuple(_flat(curve_start(e.curve), on) for e in profile.outer.edges)
    count = len(ends)
    turn = 1.0 if _area(ends) > 0.0 else -1.0
    lines = tuple(_shifted(ends[i], ends[(i + 1) % count], moves[i] * turn) for i in range(count))
    own = tuple(side.removeprefix("side-") for side in sides)
    corners: list[_Flat] = []
    names: list[str] = []
    for i in range(count):
        before, after = lines[i - 1], lines[i]
        met = _meet(before, after)
        if met is None:
            corners += [before[1], after[0]]
            names += [f"{own[i - 1]}-step", own[i]]
        else:
            corners.append(met)
            names.append(own[i])
    edges = tuple(
        Edge(
            Line(Point(*corners[k], 0.0), Point(*corners[(k + 1) % len(corners)], 0.0)),
            _label(names[k]),
        )
        for k in range(len(corners))
    )
    return face(wire(edges), on=on, label=profile.label)


_Flat = tuple[float, float]


def _flat(p: Point, on: Plane) -> _Flat:
    v = p - on.origin
    return (v @ on.x_dir, v @ on.y_dir)


def _area(points: tuple[_Flat, ...]) -> float:
    """Twice the signed area ``points`` enclose, positive counter-clockwise."""
    return sum(
        points[k][0] * points[(k + 1) % len(points)][1]
        - points[(k + 1) % len(points)][0] * points[k][1]
        for k in range(len(points))
    )


def _shifted(a: _Flat, b: _Flat, by: float) -> tuple[_Flat, _Flat]:
    """The segment ``a`` to ``b`` moved ``by`` to the right of travel - outward, for a
    counter-clockwise outline."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    nx, ny = dy / length * by, -dx / length * by
    return (a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny)


def _meet(one: tuple[_Flat, _Flat], other: tuple[_Flat, _Flat]) -> _Flat | None:
    """Where the endless lines through two segments cross, or ``None`` when they run
    parallel - on together in one line, if they came from neighbouring edges."""
    (x0, y0), (x1, y1) = one
    (u0, v0), (u1, v1) = other
    rx, ry, sx, sy = x1 - x0, y1 - y0, u1 - u0, v1 - v0
    den = rx * sy - ry * sx
    if abs(den) < TOL * math.hypot(rx, ry) * math.hypot(sx, sy):
        return None if math.hypot(u0 - x1, v0 - y1) > TOL else (x1, y1)
    t = ((u0 - x0) * sy - (v0 - y0) * sx) / den
    return (x0 + rx * t, y0 + ry * t)


# ---- a sweep ---------------------------------------------------------------------------


def _swept_cavity(node: Swept, wall: float, opened: frozenset[str]) -> Solid:
    """The profile inset by ``wall`` carried along the same path - run on ``PAST`` beyond an
    open end, and stopped ``wall`` short of a closed one, which is why a closed end has to run
    straight for more than the wall (:func:`_shortened`): an end wall cut square across a bend
    would be thinner on its inside than ``wall``."""
    _refused("a sweep", opened, ("start", "end"))
    edges = list(node.path.edges)
    setting_off = node.profile.plane.normal
    arriving = sweep_stations(node)[-1] @ setting_off
    inset = offset(node.profile, -wall)
    first, last = curve_start(edges[0].curve), curve_end(edges[-1].curve)
    if "start" in opened:
        edges.insert(0, Edge(Line(first - setting_off * PAST, first)))
        inset = move(inset, setting_off * -PAST)
    else:
        edges[0] = Edge(_shortened(edges[0].curve, wall, "start"))
        inset = move(inset, setting_off * wall)
    if "end" in opened:
        edges.append(Edge(Line(last, last + arriving * PAST)))
    else:
        edges[-1] = Edge(_shortened(edges[-1].curve, wall, "end"))
    return Solid(Swept(inset, Wire(tuple(edges))))


def _shortened(leg: Curve, wall: float, end: str) -> Line:
    """The straight leg at one end of a path, ``wall`` shorter at that end.

    Raises:
        ValueError: if the leg is a bend, or no longer than the wall.
    """
    if not isinstance(leg, Line) or abs(leg.end - leg.start) <= wall + TOL:
        msg = (
            f"a sweep is walled at its {end} only where the path runs straight for more than"
            f" the {wall} mm wall; open it, or begin the path with a Straight"
        )
        raise ValueError(msg)
    run = unit(leg.end - leg.start)
    if end == "start":
        return Line(leg.start + run * wall, leg.end)
    return Line(leg.start, leg.end - run * wall)


# ---- a loft ------------------------------------------------------------------------------


def _lofted_cavity(parts: tuple[Solid, ...], wall: float, opened: frozenset[str]) -> Solid:
    """The hull of the two profiles each inset by ``wall`` in its own plane; past an open
    end, that end's inset profile swept on by ``PAST``; short of a closed one, cut level
    ``wall`` inside it.

    Raises:
        ValueError: if the hull is not of exactly two profiles, if ``opened`` names anything
            but ``bottom`` and ``top``, or if an end is closed and the profiles do not lie
            in parallel planes.
    """
    ends = tuple(_profile_of(one) for one in parts)
    if len(ends) != 2 or None in ends:
        msg = "shell hollows a loft of two profiles, and this hull is some other shape"
        raise ValueError(msg)
    _refused("a loft", opened, ("bottom", "top"))
    bottom, top = (f for f in ends if f is not None)
    rise = (top.plane.origin - bottom.plane.origin) @ bottom.plane.normal
    up = bottom.plane.normal * math.copysign(1.0, rise)
    low, high = _inset(bottom, wall), _inset(top, wall)
    cavity = hull(low, high)
    if "bottom" in opened:
        down = -PAST * math.copysign(1.0, up @ bottom.plane.normal)
        cavity = union(cavity, extrude(low, down, label="past-bottom"))
    if "top" in opened:
        rising = PAST * math.copysign(1.0, up @ top.plane.normal)
        cavity = union(cavity, extrude(high, rising, label="past-top"))
    if {"bottom", "top"} <= opened:
        return cavity
    if abs(abs(top.plane.normal @ bottom.plane.normal) - 1.0) > TOL:
        msg = "a loft is walled at an end only when its two profiles lie in parallel planes"
        raise ValueError(msg)
    floor = wall if "bottom" not in opened else -2 * PAST
    roof = abs(rise) - wall if "top" not in opened else abs(rise) + 2 * PAST
    if roof - floor <= TOL:
        msg = f"a {wall} mm floor and roof leave nothing of a {abs(rise)} mm loft to hollow"
        raise ValueError(msg)
    loft = Solid(Hull(parts))
    return Solid(Intersection(cavity, _slab(loft, bottom.plane, up, floor, roof)))


def _profile_of(part: Solid) -> Face | None:
    """The profile a hull's part is, when it is a profile - an extrusion of no height."""
    match part.node:
        case Extrude(profile, distance) if abs(distance) <= TOL:
            return profile
        case _:
            return None


def _slab(body: Solid, on: Plane, up: Vector, floor: float, roof: float) -> Solid:
    """Everything between ``floor`` and ``roof`` millimetres up ``up`` from ``on``, as a
    block wider than ``body`` - its ``bottom`` the cavity's floor and its ``top`` the
    cavity's roof, which is what names a loft's closed ends like an extrusion's.

    ``body`` is the loft as its own recipe stands, before any move above it: the cavity is
    built there and moved with the body afterwards, so the block has to be sized there too.
    """
    box = bounds(body)
    span = math.dist((box.x0, box.y0, box.z0), (box.x1, box.y1, box.z1)) + 2 * PAST
    middle = Point((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2, (box.z0 + box.z1) / 2)
    level = plane(on.origin, up, on.x_dir)
    x, y = _flat(middle, level)
    square = rect(2 * span, 2 * span, Point(x - span, y - span))
    return extrude(fill(square, on=raised(level, floor)), roof - floor)
