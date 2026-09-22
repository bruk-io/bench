"""Features: the hole a fastener asks for, and the geometry that makes one printable.

:func:`hole` is one verb over the ``Face | Solid`` union - a shape cut clean through a
flat part, a bore drilled into a body - sized from a :class:`~bench.fasteners.Screw` at a
:class:`~bench.fasteners.Fit`, from an insert's own bore, from a plain diameter or from a
drawn profile, with the head's recess and the material's compensation read off the same
tables.

It sits above :mod:`bench.solids` because it is built out of it: a bore is an extrusion cut
away, a countersink a loft of two circles, a bridged top a union of stepped squares. That
is also why the printable-hole geometry is here and not in the print domain -
:class:`Top`, :func:`teardrop`, :func:`d_bore`, :func:`bridge_steps`, :func:`printable_top`
and :func:`foot_chamfer` are shapes, public because a lid, a hinge and a bin need them
without cutting a hole to get them, and :mod:`bench.library.print` imports them back.

What a printer can and cannot do is read off a :class:`~bench.model.Printed` - the material
and the way up - and never guessed: a bore with nothing to read from asks for one by name
rather than choosing a top for itself.
"""

import math
from enum import StrEnum
from typing import assert_never, cast

from .fasteners import COUNTERSINK, Fit, Insert, Screw, bore
from .geometry import ORIGIN, TOL, XY, Plane, Point, Vector, raised, translation, unit
from .model import Printed
from .ops import _at_angle, circle, fill, offset, rect
from .solids import cut, extrude, loft, name, union
from .topology import (
    Arc,
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
    Shape,
    Solid,
    Union,
    Wire,
    moved,
    wire,
)
from .topology import bounds as _bounds

# ---- printable profiles ------------------------------------------------------------


def teardrop(d: float, at: Point = ORIGIN, *, up: Vector, label: str | Label | None = None) -> Wire:
    """A round hole with a pointed top: the profile a bore gets when it lies on its side.

    The upper arc of the circle is replaced by two straight lines tangent to it at the
    points a quarter turn either side of ``up``, meeting at an apex ``r * sqrt(2)`` along
    ``up`` from the centre. Every surface the shape sweeps is then at most 45 degrees from
    the build direction - the tangent at the last point of arc that survives is already at
    45, and the lines that replace the rest hold it - so a printer bridges none of it.

    ``up`` is the build direction *as the sketch is drawn*, so it is read in the plane the
    wire will be filled on and only its in-plane part is used. Counter-clockwise, like every
    other outline here.

    Raises:
        ValueError: if ``d`` is not positive, or ``up`` has no direction in the plane the
            wire is drawn on - a bore pointing straight up the build direction has no
            unsupported top and wants :func:`bench.ops.circle`.
    """
    if d <= TOL:
        msg = "a teardrop needs a positive diameter"
        raise ValueError(msg)
    flat = Vector(up.x, up.y, 0.0)
    if abs(flat) < TOL:
        msg = "a teardrop needs a build direction across its own plane to point along"
        raise ValueError(msg)
    r = d / 2
    along = unit(flat)
    towards = math.atan2(along.y, along.x)
    quarter = math.pi / 2
    apex = at + along * (r * math.sqrt(2.0))
    start = _at_angle(at, r, XY, towards + quarter / 2)
    end = _at_angle(at, r, XY, towards + 7 * quarter / 2)
    edges = (
        Edge(Arc(at, r, towards + quarter / 2, towards + 7 * quarter / 2, XY)),
        Edge(Line(end, apex)),
        Edge(Line(apex, start)),
    )
    return wire(edges, label)


def bridge_steps(
    bore_d: float, outer_d: float, layers: int, layer_h: float, *, at: Point = ORIGIN
) -> tuple[Wire, ...]:
    """The stepped cutout that gives a slicer something straight to bridge a ceiling on.

    A ceiling over a round hole is an arch with nothing to start from. The fix, which is
    gridfinity-rebuilt's ``make_hole_printable``, is to cut a few layers of *square* above
    it: each step is ``bore_d`` across and ``outer_d`` long, turned a quarter turn from the
    one before it, so every layer spans between two pieces of material that are already
    there and the hole below keeps its diameter.

    The wires come back drawn flat at ``at``, innermost first. Step ``i`` is ``layer_h``
    thick and stands ``i * layer_h`` deeper than the first: the caller fills each on a plane
    raised by that much, because a wire that carried its own height would be lifted twice -
    once by its points and once by the plane it is drawn on.

    Raises:
        ValueError: if ``bore_d`` is not positive, ``outer_d`` is narrower than it, there is
            less than one layer, or ``layer_h`` is not positive.
    """
    if bore_d <= TOL:
        msg = "a bridged top needs a positive bore"
        raise ValueError(msg)
    if outer_d < bore_d - TOL:
        msg = "a bridged top steps from the bore out to something wider, not in"
        raise ValueError(msg)
    if layers < 1:
        msg = "a bridged top needs at least one layer"
        raise ValueError(msg)
    if layer_h <= TOL:
        msg = "a bridged top needs a positive layer height"
        raise ValueError(msg)
    out: list[Wire] = []
    for i in range(layers):
        w, h = (bore_d, outer_d) if i % 2 == 0 else (outer_d, bore_d)
        out.append(rect(w, h, Point(at.x - w / 2, at.y - h / 2, at.z)))
    return tuple(out)


# ---- holes -------------------------------------------------------------------------


class Top(StrEnum):
    """How the top of a bore is made, so that a printer can build it.

    ``ROUND`` is the circle itself, ``TEARDROP`` replaces its unsupported arc with two
    45 degree lines, ``BRIDGE`` keeps the circle round and cuts a stepped square above it
    for the slicer to span, and ``AUTO`` picks between them - see :func:`printable_top`.
    A :class:`str` as well as an enum, because it reads as the word itself wherever it is
    written down.
    """

    AUTO = "auto"
    ROUND = "round"
    TEARDROP = "teardrop"
    BRIDGE = "bridge"


LEANING = math.radians(30.0)
"""How far a bore may lean off the build direction before its ceiling is an unsupported
arc, in radians. Under thirty degrees a hole is a stack of circles and needs nothing."""

SHORT_SPAN = 4.0
"""The bore diameter, in millimetres, below which a leaning hole still needs nothing: the
unsupported arc is short enough that a printer walks across it."""

_OVERSHOOT = 0.01
"""How far, in millimetres, a cutting tool starts outside the material it cuts. Two
surfaces in exactly the same plane are the one thing a mesh kernel is entitled to be
undecided about; a hundredth of a millimetre of air is not a dimension anybody holds."""

_BRIDGE_LAYERS = 3
"""How many layers of stepped square a bridged top is cut in - gridfinity-rebuilt's own
count, and enough that the layer above the last one is printing onto solid plastic."""


def printable_top(
    top: Top,
    *,
    axis: Vector,
    diameter: float,
    printed: Printed | None,
    round_matters: bool = False,
) -> Top:
    """Which top a bore of ``diameter`` along ``axis`` actually gets.

    Anything but :data:`Top.AUTO` is the caller's decision and comes straight back. ``AUTO``
    is the review's rule, in one place: let theta be the angle between the hole's axis and
    the build direction. Under :data:`LEANING` the bore is a stack of circles and stays
    ``ROUND``; at or over it the ceiling is unsupported, and the remedy is chosen by
    diameter - up to :data:`SHORT_SPAN` the span is short enough to walk across, up to the
    material's ``bridge_max`` a bridged top is available to whoever needs the hole to stay
    round, and beyond that only a teardrop will do.

    Raises:
        ValueError: if ``top`` is ``AUTO`` and there is no print orientation to read, which
            is the one question this rule cannot answer by guessing.
    """
    if top is not Top.AUTO:
        return top
    if printed is None:
        msg = "this part has no print orientation, so top=Top.AUTO cannot tell which way is up"
        raise ValueError(msg)
    if _lean(axis, printed.orient.up) < LEANING:
        return Top.ROUND
    if diameter <= SHORT_SPAN:
        return Top.ROUND
    if round_matters and diameter <= printed.material.bridge_max:
        return Top.BRIDGE
    return Top.TEARDROP


def _lean(axis: Vector, up: Vector) -> float:
    """The angle between a bore's axis and the build direction, folded into a quarter turn:
    an axis is a line rather than an arrow, so drilling up and drilling down lean the same
    amount."""
    return math.acos(min(1.0, abs(unit(axis) @ unit(up))))


def hole[T: Shape](
    subject: T,
    at: Point,
    *,
    on: Plane = XY,
    screw: Screw | None = None,
    diameter: float | None = None,
    insert: Insert | None = None,
    profile: Wire | None = None,
    fit: Fit = Fit.CLEARANCE,
    depth: float | None = None,
    countersink: bool = False,
    counterbore: bool = False,
    angle: float = COUNTERSINK,
    top: Top = Top.AUTO,
    printed: Printed | None = None,
    label: str | Label,
) -> T:
    """``subject`` with a hole in it at ``at``, and the same kind of shape back.

    One verb over the whole ladder, like :func:`bench.solids.cut`: in a
    :class:`~bench.topology.Face` it is a shape cut out of a flat part, and in a
    :class:`~bench.topology.Solid` it is a bore drilled into ``on`` - the plane the hole is
    drawn on, its normal pointing out of the material. ``at`` is read in that plane's own
    frame, the way every sketch is.

    **Exactly one of ``screw``, ``insert``, ``diameter`` and ``profile``** says how wide it
    is, or what shape it is: a screw at a :class:`~bench.fasteners.Fit`, an insert's own
    bore, a plain number for a round hole that is not a fastener at all, or a
    :class:`~bench.topology.Wire` for one that is not round - a keyed shaft's D, say (see
    :func:`d_bore`). A profile is drawn once, centred on the origin the way :func:`circle`
    is when it is given no ``at`` of its own, and ``hole`` moves it to ``at`` itself, the
    same as it centres a plain circle there.

    A profile is read in ``on``'s own frame, like every sketch here - but unlike a circle, a
    profile with a top and a bottom can come out mirrored if the body it is cut into was
    itself built on a plane whose normal points the other way: a plane's second in-plane
    axis is ``cross(normal, x_dir)``, so two planes sharing an ``x_dir`` but opposite
    ``normal`` map a wire's own "up" to opposite world directions. A caller composing a bore
    with a body built on a different frame draws the profile - or turns it, since
    :func:`~bench.solids.rotate` keeps a wire's own winding - to land right side up in
    ``on``'s frame, the same way it would pick the right ``up`` for a hand-built shape.

    The material's ``hole_compensation`` is added to whichever it is when ``printed`` is
    given, because a printed hole comes out undersize and the table is the metal figure - a
    round hole grows by it on its diameter, a profile grows by half of it on every edge
    (:func:`bench.ops.offset`), which is the same amount on the side that matters and keeps
    a caller from applying it by hand.

    ``depth`` is measured from ``on`` into the material and defaults to through, which is
    sized off the body's own bounds. ``countersink`` and ``counterbore`` cut the head's own
    recess from the screw's table - a cone at ``angle`` (90 degrees, the ISO one and the one
    a printer can hold) or a flat-bottomed bore - and need a screw to read it from, so a
    profiled bore, which never has a screw, cannot ask for either.
    ``top`` is the horizontal-hole rule, :func:`printable_top`: with ``printed`` in hand a
    leaning bore gets a teardrop, or a bridged top when it is counterbored and must stay
    round. A body is a thing to be printed, so ``Top.AUTO`` on one asks for ``printed`` and
    refuses to guess without it - ``top=Top.ROUND`` is how a bore says it does not care. A
    face is flat and has no top to make printable, so it never asks. A profile has no round
    top to make printable another way either - a caller draws one that is already safe to
    print lying on its side, the way :func:`d_bore` leans on nothing rounder than its own
    arc - so ``top`` stays at its default with a profile, or the refusal below fires.

    The tool is labelled, so the bore's own faces answer to ``<label>/side-0``, a head to
    ``<label>/head`` and each bridging step to ``<label>/bridge-1``. Everything else a hole
    can be asked for and cannot do - a bore's options on a flat face, a head with no screw
    to size it, a teardrop with no orientation to point along, a printable top on a profile -
    is refused by name where it is worked out.

    Raises:
        ValueError: if none or more than one of ``screw``, ``insert``, ``diameter`` and
            ``profile`` is given, since each says how wide or what shape the hole is and
            they cannot all be right; or if ``profile`` is given alongside ``countersink``,
            ``counterbore`` or a ``top`` other than the default, none of which a profiled
            bore can do.
    """
    given = tuple(one for one in (screw, diameter, insert, profile) if one is not None)
    if len(given) != 1:
        msg = (
            "a hole is a screw at a fit, an insert, a plain diameter, or a profile - give"
            f" exactly one of screw=, insert=, diameter= and profile=, not {len(given)}"
        )
        raise ValueError(msg)
    if profile is not None:
        if countersink or counterbore:
            msg = (
                "a countersink or a counterbore is a screw's own head; a profile has no"
                " screw to size one from"
            )
            raise ValueError(msg)
        if top not in (Top.AUTO, Top.ROUND):
            msg = (
                "a profile has no round top to make printable another way; draw one already"
                " safe to print, not top="
            )
            raise ValueError(msg)
        match subject:
            case Face():
                return cast("T", _face_profile_hole(subject, at, profile, label, depth, printed))
            case Solid():
                tool = _profile_bore(subject, at, on, profile, depth, printed)
                return cast("T", cut(subject, tool, label=label))
            case _:
                assert_never(subject)
    wide = _hole_diameter(screw, diameter, insert, fit, printed)
    match subject:
        case Face():
            return cast("T", _face_hole(subject, at, wide, label, depth, countersink, counterbore))
        case Solid():
            tool = _bore(
                subject, at, on, wide, screw, depth, countersink, counterbore, angle, top, printed
            )
            return cast("T", cut(subject, tool, label=label))
        case _:
            assert_never(subject)


def _hole_diameter(
    screw: Screw | None,
    diameter: float | None,
    insert: Insert | None,
    fit: Fit,
    printed: Printed | None,
) -> float:
    """How wide the hole is cut: the table's figure, plus what the plastic takes back.

    Exactly one of the three ways of saying it has already been settled by :func:`hole`.

    Raises:
        ValueError: if what was given is not a positive diameter.
    """
    if screw is not None:
        wide = bore(screw, fit)
    elif insert is not None:
        wide = insert.bore
    else:
        wide = diameter if diameter is not None else 0.0
    if wide <= TOL:
        msg = "a hole needs a positive diameter"
        raise ValueError(msg)
    return wide + (0.0 if printed is None else printed.material.hole_compensation)


def _placed_profile(profile: Wire, at: Point, printed: Printed | None) -> Wire:
    """``profile``, drawn once at the origin, grown by half the material's printed
    compensation on every edge and moved to ``at`` - the profile equivalent of adding
    ``hole_compensation`` to a plain diameter, worked out once so neither ``_face_profile_hole``
    nor ``_profile_bore`` has to repeat it."""
    comp = 0.0 if printed is None else printed.material.hole_compensation / 2
    grown = offset(profile, comp) if comp > TOL else profile
    return moved(grown, translation(Vector(at.x, at.y, 0.0)))


def _face_profile_hole(
    subject: Face,
    at: Point,
    profile: Wire,
    label: str | Label,
    depth: float | None,
    printed: Printed | None,
) -> Face:
    """A profiled hole cut clean through a flat part - the same refusal `_face_hole` makes
    for anything only a bore has.

    Raises:
        ValueError: if ``depth`` was asked for. A cutter has one depth, the stock's, and a
            profile is round or not by the caller's own drawing, so nothing else a bore
            offers is even askable here.
    """
    if depth is not None:
        msg = "depth describes a bore; a face is cut straight through, at the stock's own thickness"
        raise ValueError(msg)
    return cut(subject, _placed_profile(profile, at, printed), label=label)


def _profile_bore(
    subject: Solid,
    at: Point,
    on: Plane,
    profile: Wire,
    depth: float | None,
    printed: Printed | None,
) -> Solid:
    """The body taken out of a solid to leave a profiled bore: ``profile``, grown by the
    printed compensation and swept from ``on`` through the part.

    Unlike a round bore, :func:`printable_top` has no rule for growing an arbitrary shape a
    self-supporting top - that is the caller's to solve at the point the profile is drawn
    (see :func:`d_bore`), so this sweeps it straight through and nothing more.
    """
    reach = (_through(subject, on) if depth is None else depth) + _OVERSHOOT
    mouth = raised(on, _OVERSHOOT)
    return extrude(fill(_placed_profile(profile, at, printed), on=mouth), -reach)


def d_bore(r: float, flat: float, at: Point = ORIGIN, *, label: str | Label | None = None) -> Wire:
    """A capital D: a circle of radius ``r`` cut flat ``flat`` below its centre.

    The profile a keyed shaft turns in rather than slides in. Drawn once, centred at the
    origin the way :func:`bench.ops.circle` is when it is given no ``at`` of its own, and
    passed to :func:`hole` as ``profile=``, which moves it to its own ``at`` and grows it by
    the printed compensation itself - the same way it grows a round bore's diameter - so the
    flat moves out exactly as far as the arc does without the caller adding either fit or
    compensation to this call directly.

    A function beside :func:`teardrop`, not a method on some catalog of profiles: every
    other shape this module hands a caller pre-built - :func:`teardrop`, :func:`bridge_steps`,
    :func:`foot_chamfer` - is a plain function returning a :class:`~bench.topology.Wire` or
    tuple of them, and a D-bore is the same kind of thing for the same reason. A hex socket
    or a T-slot would join it here the same way, as their own functions, if and when one is
    built - see task-30's notes for what was scoped out for now.

    Raises:
        ValueError: if ``r`` is not positive, or ``flat`` does not cut between the centre and
            the rim - at the centre there is no D left, and past the rim there is no circle.
    """
    if r <= TOL:
        msg = "a D-bore needs a positive radius"
        raise ValueError(msg)
    if not TOL < flat < r - TOL:
        msg = "a D-bore's flat has to cut between the centre and the rim"
        raise ValueError(msg)
    a = math.asin(flat / r)
    x, y, _ = at
    start = Point(x + r * math.cos(a), y - flat, 0.0)
    end = Point(x - r * math.cos(a), y - flat, 0.0)
    return wire((Edge(Arc(at, r, -a, math.pi + a, XY)), Edge(Line(end, start))), label)


def _face_hole(
    subject: Face,
    at: Point,
    wide: float,
    label: str | Label,
    depth: float | None,
    countersink: bool,
    counterbore: bool,
) -> Face:
    """A round hole cut clean through a flat part - what a laser does and all it does.

    Raises:
        ValueError: if anything only a bore has was asked for. A cutter has one depth, the
            stock's, and no way to sink a head into it; silently ignoring the keyword would
            hand back a part that does not hold the screw it was drawn for.
    """
    asked = tuple(
        name
        for name, given in (
            ("depth", depth is not None),
            ("countersink", countersink),
            ("counterbore", counterbore),
        )
        if given
    )
    if asked:
        msg = (
            f"{', '.join(asked)} describes a bore; a face is cut straight through, at the"
            " stock's own thickness"
        )
        raise ValueError(msg)
    return cut(subject, circle(wide / 2, at), label=label)


def _bore(
    subject: Solid,
    at: Point,
    on: Plane,
    wide: float,
    screw: Screw | None,
    depth: float | None,
    countersink: bool,
    counterbore: bool,
    angle: float,
    top: Top,
    printed: Printed | None,
) -> Solid:
    """The body taken out of a solid to leave the hole: the bore, the head's recess, and
    whatever a bridged top needs above it.

    Raises:
        ValueError: if a head was asked for without a screw to size it, or both at once.
    """
    if countersink and counterbore:
        msg = "a head is sunk or it is buried - countersink or counterbore, not both"
        raise ValueError(msg)
    if (countersink or counterbore) and screw is None:
        msg = "a countersink or a counterbore is the screw's own head; give screw="
        raise ValueError(msg)
    chosen = printable_top(
        top, axis=on.normal, diameter=wide, printed=printed, round_matters=counterbore
    )
    reach = (_through(subject, on) if depth is None else depth) + _OVERSHOOT
    mouth = raised(on, _OVERSHOOT)
    tool = extrude(fill(_bore_profile(wide, at, chosen, on, printed), on=mouth), -reach)
    if counterbore and screw is not None:
        tool = union(tool, _counterbored(screw, at, mouth, label="head"))
        if chosen is Top.BRIDGE:
            for i, step in enumerate(_bridge(screw, wide, at, on, printed)):
                tool = union(tool, name(step, f"bridge-{i + 1}"))
    if countersink and screw is not None:
        tool = union(tool, _countersunk(screw, wide, at, on, angle, label="head"))
    return tool


def _bore_profile(wide: float, at: Point, chosen: Top, on: Plane, printed: Printed | None) -> Wire:
    """The cross-section the bore is swept from: a circle, or a teardrop pointed the way
    the part is printed.

    Raises:
        ValueError: if a teardrop or a bridged top was asked for with nothing to build it
            from - a teardrop needs an orientation to point along, and a bridged top needs a
            counterbore to step out to, which :func:`_bore` only offers it when there is one.
    """
    match chosen:
        case Top.ROUND | Top.AUTO:
            return circle(wide / 2, at)
        case Top.TEARDROP:
            if printed is None:
                msg = "a teardrop needs a print orientation to point along; give printed="
                raise ValueError(msg)
            up = printed.orient.up
            return teardrop(wide, at, up=Vector(up @ on.x_dir, up @ on.y_dir, 0.0))
        case Top.BRIDGE:
            return circle(wide / 2, at)
        case _:
            assert_never(chosen)


def _through(subject: Solid, on: Plane) -> float:
    """How deep a hole drilled from ``on`` has to be to come out the other side: the
    furthest the body's own bound reaches under that plane, which is conservative wherever
    :func:`~bench.topology.bounds` is and so never leaves a hole short."""
    box = _bounds(subject)
    corners = tuple(
        Point(x, y, z) for x in (box.x0, box.x1) for y in (box.y0, box.y1) for z in (box.z0, box.z1)
    )
    return max(0.0, max((c - on.origin) @ -on.normal for c in corners)) + _OVERSHOOT


def _counterbored(screw: Screw, at: Point, mouth: Plane, *, label: str) -> Solid:
    """The flat-bottomed bore a socket cap sinks into, from the screw's own table."""
    deep = screw.counterbore_depth + _OVERSHOOT
    return extrude(fill(circle(screw.counterbore_d / 2, at), on=mouth), -deep, label=label)


def _countersunk(
    screw: Screw, wide: float, at: Point, on: Plane, angle: float, *, label: str
) -> Solid:
    """The cone a flat head sinks into: the screw's countersink diameter at the surface,
    narrowing at ``angle`` until it meets the bore.

    A hull of two circles, which is exactly a frustum and is the one shape this kernel can
    taper without naming anything it cannot keep.

    Raises:
        ValueError: if ``angle`` is not a cone - nothing at all, or a whole half turn, in
            which case the countersink is a flat pocket and wants a counterbore instead.
    """
    if not TOL < angle < math.pi - TOL:
        msg = "a countersink is a cone between nothing and flat"
        raise ValueError(msg)
    flare = math.tan(angle / 2)
    deep = max(TOL, (screw.countersink_d - wide) / 2 / flare)
    return loft(
        fill(circle(wide / 2, at), on=raised(on, -deep)),
        fill(circle(screw.countersink_d / 2 + _OVERSHOOT * flare, at), on=raised(on, _OVERSHOOT)),
        label=label,
    )


def _bridge(
    screw: Screw, wide: float, at: Point, on: Plane, printed: Printed | None
) -> tuple[Solid, ...]:
    """The stepped square cut under a counterbore's floor, so the slicer bridges it.

    Raises:
        ValueError: if there is no material to read a layer height from.
    """
    if printed is None:
        msg = "a bridged top is cut in layers; give printed= so there is a layer height"
        raise ValueError(msg)
    layer = printed.material.layer
    floor = screw.counterbore_depth
    return tuple(
        extrude(fill(step, on=raised(on, -(floor + i * layer))), -layer)
        for i, step in enumerate(
            bridge_steps(wide, screw.counterbore_d, _BRIDGE_LAYERS, layer, at=at)
        )
    )


def foot_chamfer(solid: Solid, d: float) -> Solid:
    """``solid`` with a 45 degree chamfer ``d`` tall taken off the face it stands on.

    The elephant's foot: the first layers of a print spread sideways under the weight of
    what follows, so the footprint comes out a fraction over. The fix is not a number
    sprinkled through the sketch but one chamfer at the bottom, and this is it - the wedge
    between the footprint and the footprint inset by ``d`` is cut away, under the label
    ``foot``.

    It is the bottom of an *extrusion* that can be chamfered, because that is the body whose
    footprint the tree knows; the taper itself is a hull of the two profiles, so it is exact
    for a convex footprint and leaves a re-entrant corner under-cut.

    Raises:
        ValueError: if ``d`` is not positive, or ``solid`` is not an extrusion (under any
            number of moves), which is the only body with a footprint to inset.
    """
    if d <= TOL:
        msg = "a foot chamfer needs a positive size"
        raise ValueError(msg)
    found = _extruded_root(solid.node)
    if found is None:
        msg = "a foot chamfer needs a body extruded from a profile, whose footprint is known"
        raise ValueError(msg)
    profile, distance = found
    n = profile.plane.normal
    bottom = min(0.0, distance)
    low = moved(profile, translation(n * bottom))
    high = moved(profile, translation(n * (bottom + d)))
    wedge = cut(extrude(low, d), loft(offset(low, -d), high), label="taper")
    return cut(solid, wedge, label="foot")


def _extruded_root(node: Node) -> tuple[Face, float] | None:
    """The profile and distance of the extrusion a body is, seen through any moves, or
    ``None`` for a body built some other way. A move carries the profile with it, so the
    face that comes back is where the body actually stands."""
    match node:
        case Extrude(profile, distance):
            return (profile, distance)
        case Moved(inner, t):
            found = _extruded_root(inner)
            if found is None:
                return None
            profile, distance = found
            return (moved(profile, t), distance)
        case Revolve() | Union() | Difference() | Intersection() | Hull() | Imported():
            return None
        case _:
            assert_never(node)
