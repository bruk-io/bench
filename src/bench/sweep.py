"""Sweep: a profile carried along a path of lines and arcs - a duct's bend, an S-bend, an offset.

:func:`sweep` makes the body and :func:`path` the route, written the way a duct is described:
so far straight on, then round so far at such a radius towards such a side. The profile is
drawn where the path starts, square to it, and carried without twisting - moved along a line,
turned about an arc's own axis round a bend - so ``end`` is the profile's own frame carried
to the end of the path, and a spigot, a flange or another part mates onto it in the numbers
the profile was drawn in.

**How it is built, and why that way.** The modeller has no sweep. Two ways of making one out
of what it does have were measured before this was written, by ``tools/sweep_routes.py`` on
the modeller the app ships (Pyodide under Node), with the profile at the same stations and
every curve cut by the same chord rule for both: a 40 by 30 rounded rectangle, a 40 mm
circle, the same circle as a 3 mm-walled pipe, and an L 30 by 30 with 10 mm legs, each along
a 90 degree bend and an S-bend of 60 mm radius, against the volume Pappus gives. The 90
degree bend (the S-bend reads the same, to a few percent):

====================  =================  ===============  ============  =====================
profile               volume vs Pappus   triangles        ms (median)   faces named
                      hulls / mesh       hulls / mesh     hulls / mesh  hulls / mesh
====================  =================  ===============  ============  =====================
rounded rectangle     -0.13% / -0.13%    2396 / 1452      56.6 / 6.8    none / start, end, 8
circle                -0.38% / -0.38%    4138 / 2336      92.4 / 9.6    none / start, end, 1
pipe (hole)           -0.21% / -0.21%    13044 / 4472     229 / 19.4    the bore / start, end,
                                                                        side, hole
L (concave)           +37.4% / -0.06%    278 / 308        8.4 / 2.9     none / start, end, 6
====================  =================  ===============  ============  =====================

* **A chain of hulls** - one round each pair of neighbouring slices, unioned - is as exact as
  the mesh for a convex profile (the shortfall both share is the chords), and wrong for any
  other: a hull fills the L's notch. A hole has to be a second chain cut out of the first.
  It names no face, because a hull keeps none, so a bend's end cannot be mated. The hulls
  only touch, and the union keeps the slices between them inside the body: for the circle,
  1802 of its 4138 triangles lie on the 24 inner slices, the other 2336 are the mesh's own
  count, and the surface comes back in 105 pieces joined at no vertex (``V - E + F`` of 148
  to 410 where one solid is 2). And it asks the modeller for a hull and a union per station,
  3 to 12 times the time.
* **A mesh built here** - a ring of the profile at each station, neighbouring rings joined,
  the ends capped on the same vertices - handed over once as an import: any profile, holes
  and concave corners included, one closed surface, 40 to 65 percent fewer triangles for the
  round and rounded ones (the L a tenth more), and every triangle carries the face it was
  laid for.

The second is what :class:`~bench.topology.Swept` is built as (:func:`bench.meshing.swept`):
``start``, ``end`` and a ``side-`` per profile edge are named and pickable, and
:func:`bench.shell.shell` hollows a sweep by sweeping the inset profile along the same path.

**What is refused**, because it would not be a solid: a path that turns a corner instead of
bending round one, a profile not standing square on the path's start, and a bend tighter than
the profile is deep on its inside, which would fold the inside of the bend through itself.
"""

import math
from typing import NamedTuple, assert_never

from .geometry import TOL, Axis, Plane, Point, Vector, cross, identity, plane, rotation, unit
from .topology import (
    Arc,
    Circle,
    Curve,
    Edge,
    Face,
    Label,
    Line,
    Solid,
    Swept,
    Wire,
    curve_start,
    flat_ring,
    sweep_stations,
    wire,
)
from .topology import label as _label


class Straight(NamedTuple):
    """A leg of a :func:`path` running ``length`` millimetres straight on."""

    length: float


class Bend(NamedTuple):
    """A leg of a :func:`path` turning ``angle`` radians round a ``radius`` millimetre bend,
    towards ``toward`` - a direction, of which only the part square to the way the path is
    heading counts, so ``toward=X`` bends towards X from wherever the path points."""

    radius: float
    angle: float
    toward: Vector


def path(start: Point, heading: Vector, *legs: Straight | Bend) -> Wire:
    """The route from ``start``, setting off along ``heading``, leg after leg, as a wire of
    lines and arcs that meet end to end and run on smoothly into each other.

    A :class:`Bend` is a quarter-turn elbow or a half of an S-bend: ``Bend(60, pi / 4, X)``
    then ``Bend(60, pi / 4, -X)`` steps the path sideways and sets it off the way it came.

    Raises:
        ValueError: if there is no leg, if a straight has no length, if a bend has no radius
            or turns nothing or all the way round, or if ``toward`` points along the path and
            so names no side to bend towards.
    """
    if not legs:
        msg = "a path needs at least one leg"
        raise ValueError(msg)
    here, going = start, unit(heading)
    edges: list[Edge] = []
    for leg in legs:
        match leg:
            case Straight(length):
                if length <= TOL:
                    msg = f"a straight leg runs on some length, not {length}"
                    raise ValueError(msg)
                ahead = here + going * length
                edges.append(Edge(Line(here, ahead)))
                here = ahead
            case Bend(radius, angle, toward):
                if radius <= TOL or not TOL < angle < math.tau - TOL:
                    msg = f"a bend has a radius and turns less than a whole turn, not {leg}"
                    raise ValueError(msg)
                side = toward - going * (toward @ going)
                if abs(side) <= TOL:
                    msg = f"{toward} points along the path, so it names no side to bend towards"
                    raise ValueError(msg)
                side = unit(side)
                centre = here + side * radius
                on = plane(centre, cross(going, side), -side)
                edges.append(Edge(Arc(centre, radius, 0.0, angle, on)))
                turned = rotation(Axis(centre, on.normal), angle)
                here, going = turned @ here, turned @ going
            case _:
                assert_never(leg)
    return wire(tuple(edges))


def sweep(profile: Face, along: Wire, *, label: str | Label | None = None) -> Solid:
    """The body ``profile`` sweeps out carried along ``along``, a path of lines and arcs.

    The profile is read where it is: it must stand on the path's start, square to it, its
    normal the way the path sets off - which is what drawing it ``on=`` a plane at the start
    of a :func:`path` gives. Its faces are ``start`` on the profile's own plane, ``end`` where
    the path stops - the profile's frame carried there, so a part mated onto it is placed in
    the numbers the profile was drawn in - and a ``side-`` per outer edge and one per hole
    wire, which follow the bends and have no single plane.

    Raises:
        ValueError: if the path holds a whole circle or turns a corner rather than running on
            smoothly, if the profile does not stand square on the path's start, or if a bend
            is tighter than the profile reaches in towards its centre.
    """
    for e in along.edges:
        if isinstance(e.curve, Circle):
            msg = "a path runs from one end to another, and a whole circle has no ends"
            raise ValueError(msg)
    curves = tuple(e.curve for e in along.edges)
    for i in range(1, len(curves)):
        if abs(_heading(curves[i - 1], end=True) - _heading(curves[i], end=False)) > 1e-6:
            msg = f"the path turns a corner between leg {i - 1} and leg {i}; round it with a bend"
            raise ValueError(msg)
    setting_off = _heading(curves[0], end=False)
    first = curve_start(curves[0])
    on = profile.plane
    if abs((first - on.origin) @ on.normal) > TOL or abs(setting_off - on.normal) > 1e-6:
        msg = "a profile is swept from where it stands: draw it square on the path's start"
        raise ValueError(msg)
    node = Swept(profile, along)
    _clear_of_every_bend(node)
    return Solid(node, None if label is None else _label(label))


def _heading(c: Curve, *, end: bool) -> Vector:
    """Which way a path's curve runs at its start, or at its end."""
    match c:
        case Line(start, stop):
            return unit(stop - start)
        case Arc(_, _, a0, a1, on):
            return _round_heading(on, a1 if end else a0, 1.0 if a1 >= a0 else -1.0)
        case Circle(_, _, on):
            return _round_heading(on, 0.0, 1.0)
        case _:
            assert_never(c)


def _round_heading(on: Plane, theta: float, sense: float) -> Vector:
    """Which way a curve round ``on``'s normal runs at ``theta``, walked ``sense`` about it."""
    return (on.x_dir * -math.sin(theta) + on.y_dir * math.cos(theta)) * sense


def _clear_of_every_bend(node: Swept) -> None:
    """Refuse a bend the profile reaches past the centre of - where the inside of the bend
    would sweep back through itself.

    Raises:
        ValueError: if any point of the profile, carried to where a bend starts, stands on
            the far side of that bend's axis from the path.
    """
    on = node.profile.plane
    ring = flat_ring(node.profile.outer, on, (0,) * len(node.profile.outer.edges))
    corners = tuple(on.origin + on.x_dir * u + on.y_dir * v for u, v in ring.points)
    edges = node.path.edges
    for i, e in enumerate(edges):
        if not isinstance(e.curve, Arc):
            continue
        here = sweep_stations(Swept(node.profile, Wire(edges[:i])))[-1] if i else identity()
        out = unit(curve_start(e.curve) - e.curve.centre)
        if min(((here @ p) - e.curve.centre) @ out for p in corners) <= TOL:
            msg = (
                f"bend {i} is tighter than the profile is deep: its inside would fold through"
                " itself; give it a bigger radius"
            )
            raise ValueError(msg)
