"""Ducts: the sizes of real hoses and ducts, and the printed fittings that join them.

What the wall vent's manifold (``projects/vent``) built by hand, as calls: a :class:`Size`
for each hose and duct a print has to match, and the fittings between them - a
:func:`spigot`, a :func:`socket`, a :func:`coupler`, a :func:`reducer`, an :func:`elbow`, a
:func:`branch` and a :func:`square_to_round`. Each is a path and a wall rather than a pair of
bodies subtracted wherever one body can be: a straight fitting is an outline turned about its
axis and hollowed with :func:`~bench.shell.shell`, an elbow the wall's own ring carried round
a :func:`~bench.sweep.path`. The branch and the square-to-round are two and three pieces, and
say why they are cut instead.

**Nothing here is two bodies that only touch.** A modeller keeps two solids that meet face to
face as two - measured on the one the app ships, a spigot hollowed and set on a hollowed loft
kept its own underside inside the part as a ceiling leaning 90 degrees - and the overhang and
wall checks read that face as part of the print. So where pieces join they overlap, and a
hollow is one body cut once or a ring swept whole.

**Where a size is measured.** A hose is sold by its inside, a dust port by its outside, and a
fit goes wrong by exactly the wall between the two if the wrong one is assumed - so a
:class:`Size` says which :class:`Side` its nominal is, and each of the table's numbers cites
where it comes from or says plainly that it is an estimate to be measured.

**The gap goes on one part.** :func:`~bench.library.print.clearance` says a fit's gap is taken
off one of the two parts and not both, and a size says which: a spigot is the male side of a
joint and a socket the female. A size measured on its *inside* - a hose, a duct's plain end -
is female already, so the spigot that slides into it is drawn under by the gap and the socket
that stands in for it is drawn at the nominal. A size measured on its *outside* - a
fitting's port - is male already, so its socket is drawn over by the gap and its spigot at the
nominal. Either way ``spigot(s)`` slides into ``socket(s)`` at the fit, and each takes the
real thing it stands in for as well. So ``socket(HOSE_4)`` is a hose end - what slides into
a hose slides into it - and not a socket a hose slides into: a hose's outside is wound wire
and plastic and is not in the table. The gap is the concave one, because every joint here
has a bore on one side of it; no printed-hole compensation is added on top, because a socket
is not a hole :func:`~bench.features.hole` cut and compensating a mating diameter twice is
task-74's bug.

**How each fitting prints.** Every fitting is drawn the way it prints, standing on its start
on the bed at the origin and rising up ``+Z`` - :data:`UPRIGHT` - so a part made of one is
``Printed(material)`` as it comes. Every change of diameter is a cone leaning the material's
``max_overhang`` off the vertical, so it holds itself up whichever way it narrows. Every
wall is ``wall`` measured square to itself except a square-to-round's, which is ``wall``
level with its openings the way :func:`~bench.shell.shell` measures a loft's, so it is
thinner along its leaning sides by the cosine of their lean - and is refused where that
would be under the material's ``min_wall``. A turn past what the plastic holds up is drawn
all the same, and ``check_overhangs`` flags it where it leans too far: it prints best as two
fittings and a :func:`coupler`.
"""

import math
from dataclasses import dataclass
from enum import StrEnum

from ..fasteners import Fit
from ..geometry import ORIGIN, TOL, XY, Axis, Point, X, Y, Z, plane, raised
from ..model import Material, Orient
from ..ops import circle, fill, rounded_rect
from ..shell import PAST, shell
from ..solids import cut, cylinder, extrude, hull, revolve, union
from ..sweep import Bend, Straight, path, sweep
from ..topology import Edge, Line, Solid, Wire, face, wire
from ..topology import label as _label
from .print import PLA, clearance

IN = 25.4
"""Millimetres in an inch: every size in the table is sold in inches."""

WALL = 2.0
"""The wall every fitting is drawn with unless asked for another, in millimetres."""

SPIGOT_LENGTH = 1.5 * IN
"""How far a spigot runs: the vent's own ports, and room for a hose clamp."""

SOCKET_DEPTH = 0.75 * IN
"""How deep a socket runs to its stop: the vent's own manifold socket."""

UPRIGHT = Orient()
"""The way every fitting here prints: standing on its start, rising up ``+Z``."""


class Side(StrEnum):
    """Which side of a hose or a duct its nominal size measures."""

    INSIDE = "inside"
    OUTSIDE = "outside"


@dataclass(frozen=True, slots=True)
class Size:
    """One size a print has to match: what it is, which :class:`Side` of it ``diameter``
    measures, in millimetres, and where the number comes from - a page that says it, or,
    where ``estimate`` is set, what it was guessed from and that it wants measuring."""

    name: str
    side: Side
    diameter: float
    source: str
    estimate: bool = False


# ---- the table -------------------------------------------------------------------------

HOSE_4 = Size(
    "4 in dust hose",
    Side.INSIDE,
    4.0 * IN,
    "https://www.rockler.com/dust-right-reg-4-anti-static-dust-hose - 'a 4'' inside diameter'",
)
"""Woodworking dust-collection hose, sold by its inside: it slips over a :data:`PORT_4`."""

PORT_4 = Size(
    "4 in dust port",
    Side.OUTSIDE,
    4.0 * IN,
    "https://www.rockler.com/4-universal-dust-port - 'Small Opening OD: 4\"'; and"
    " https://www.rockler.com/learn/measuring-dust-ports-and-dust-hoses - 'the outside"
    " diameter of the tool port needs to match the inside diameter of the dust hose'",
)
"""A 4 inch dust-collection fitting's port - a blast gate's, a wye's, a tool's - sold by its
outside, which is the hose's inside."""

HOSE_2_5 = Size(
    "2.5 in dust hose",
    Side.INSIDE,
    2.5 * IN,
    "https://www.rockler.com/dust-right-reg-2-1-2-anti-static-dust-hose -"
    " 'a 2-1/2'' inside diameter'",
)
"""The smaller dust-collection hose, sold by its inside like :data:`HOSE_4`."""

PORT_2_5 = Size(
    "2.5 in dust port",
    Side.OUTSIDE,
    2.5 * IN,
    "estimate: Rockler's rule that a port's outside matches its hose's inside"
    " (https://www.rockler.com/learn/measuring-dust-ports-and-dust-hoses) applied to"
    " HOSE_2_5; no 2-1/2 inch port's own figure found - measure one",
    estimate=True,
)
"""A 2-1/2 inch dust port - estimated from the rule, not read off a port."""

VAC_1_25 = Size(
    "1.25 in shop vacuum",
    Side.OUTSIDE,
    1.25 * IN,
    "estimate: Shop-Vac and RIDGID publish the nominal only, not which side it is; taken as"
    " the outside of the wand end an accessory slides onto - measure both",
    estimate=True,
)
"""A small wet-dry vacuum's hose end - the nominal only, and a guess at which side."""

VAC_2_5 = Size(
    "2.5 in shop vacuum",
    Side.OUTSIDE,
    2.5 * IN,
    "estimate: https://www.shopvac.com/collections/2-1-2-diameter-accessories says only"
    " 'fit hoses that are 2-1/2\" in diameter'; taken as the outside of the wand end an"
    " accessory slides onto - measure both",
    estimate=True,
)
"""A shop vacuum's big hose end - the nominal only, and a guess at which side."""

DUCT_4 = Size(
    "4 in round duct",
    Side.INSIDE,
    4.0 * IN,
    "estimate: HVAC practice sizes round duct by its inside, its plain end taking the next"
    " piece's crimped end; no manufacturer's or SMACNA's own text read - measure one",
    estimate=True,
)
"""Round sheet-metal duct, as its plain (uncrimped) end - the side taken on practice's word."""

DUCT_6 = Size(
    "6 in round duct",
    Side.INSIDE,
    6.0 * IN,
    "estimate: as DUCT_4",
    estimate=True,
)
"""The 6 inch round duct, taken the same way as :data:`DUCT_4`."""

SIZES = frozendict(
    {
        "hose-4": HOSE_4,
        "port-4": PORT_4,
        "hose-2.5": HOSE_2_5,
        "port-2.5": PORT_2_5,
        "vac-1.25": VAC_1_25,
        "vac-2.5": VAC_2_5,
        "duct-4": DUCT_4,
        "duct-6": DUCT_6,
    }
)
"""Every size in the table by a short name, so a script's panel can offer them."""


# ---- the two sides of a joint ------------------------------------------------------------


def spigot_diameter(size: Size, *, fit: Fit = Fit.SLIDE, material: Material = PLA) -> float:
    """The outside of a spigot that slides into ``size`` - or into ``socket(size)`` - at
    ``fit``: under the nominal by the gap both sides where the size is an inside, the
    nominal itself where it is an outside."""
    match size.side:
        case Side.INSIDE:
            return size.diameter - 2 * clearance(fit, material, concave=True)
        case Side.OUTSIDE:
            return size.diameter


def socket_diameter(size: Size, *, fit: Fit = Fit.SLIDE, material: Material = PLA) -> float:
    """The bore of a socket that ``size`` - or ``spigot(size)`` - slides into at ``fit``:
    over the nominal by the gap both sides where the size is an outside, the nominal itself
    where it is an inside."""
    match size.side:
        case Side.INSIDE:
            return size.diameter
        case Side.OUTSIDE:
            return size.diameter + 2 * clearance(fit, material, concave=True)


# ---- the straight fittings ------------------------------------------------------------------


def spigot(
    size: Size,
    *,
    length: float = SPIGOT_LENGTH,
    wall: float = WALL,
    fit: Fit = Fit.SLIDE,
    material: Material = PLA,
) -> Solid:
    """A plain tube ``length`` long that slides into ``size`` at ``fit``: its outside is
    :func:`spigot_diameter` and its bore that less the wall.

    Raises:
        ValueError: if ``wall`` is under the material's minimum or eats the bore, or
            ``length`` is not positive.
    """
    run = _Run(spigot_diameter(size, fit=fit, material=material) / 2, length, "spigot")
    refused = _refusal(wall, material, run.radius - wall, length=length)
    if refused is not None:
        raise ValueError(refused)
    return _turned((run,), wall, material)


def socket(
    size: Size,
    *,
    depth: float = SOCKET_DEPTH,
    wall: float = WALL,
    fit: Fit = Fit.SLIDE,
    material: Material = PLA,
) -> Solid:
    """A collar ``size`` slides ``depth`` into at ``fit``, and the cone that stops it - which
    narrows it back to the size's own spigot tube, so the socket's far end is a spigot's
    wall, ready to be joined to whatever it is the end of.

    Its bore is :func:`socket_diameter`, for ``depth`` measured inside to where the stop
    begins. It prints standing on its mouth: the stop above leans the material's
    ``max_overhang`` and no more.

    Raises:
        ValueError: if ``wall`` is under the material's minimum, or ``depth`` is not
            positive.
    """
    lean = material.max_overhang
    runs = (
        _Run(_socket_outside(size, wall, fit, material), _socket_run(depth, wall, lean), "socket"),
        _Run(spigot_diameter(size, fit=fit, material=material) / 2, wall, "pipe"),
    )
    refused = _refusal(wall, material, runs[-1].radius - wall, depth=depth)
    if refused is not None:
        raise ValueError(refused)
    return _turned(runs, wall, material)


def coupler(
    start: Size,
    end: Size | None = None,
    *,
    depth: float = SOCKET_DEPTH,
    wall: float = WALL,
    fit: Fit = Fit.SLIDE,
    material: Material = PLA,
) -> Solid:
    """Two sockets back to back - ``start`` below, ``end`` above, the same size when ``end``
    is not given - joining two spigots, each at ``fit`` and each stopped at ``depth``.

    The waist between them is the narrower size's spigot tube, so both stops are the gap and
    a wall wide.

    Raises:
        ValueError: if ``wall`` is under the material's minimum, or ``depth`` is not
            positive.
    """
    other = start if end is None else end
    lean = material.max_overhang
    waist = min(spigot_diameter(one, fit=fit, material=material) for one in (start, other)) / 2
    runs = (
        _Run(_socket_outside(start, wall, fit, material), _socket_run(depth, wall, lean), "inlet"),
        _Run(waist, wall, "waist"),
        _Run(_socket_outside(other, wall, fit, material), _socket_run(depth, wall, lean), "outlet"),
    )
    refused = _refusal(wall, material, waist - wall, depth=depth)
    if refused is not None:
        raise ValueError(refused)
    return _turned(runs, wall, material)


def reducer(
    start: Size,
    end: Size,
    *,
    length: float = SPIGOT_LENGTH,
    wall: float = WALL,
    fit: Fit = Fit.SLIDE,
    material: Material = PLA,
) -> Solid:
    """A spigot for ``start`` below and one for ``end`` above, each ``length`` long, joined
    by a cone leaning the material's ``max_overhang`` - so it prints standing on either
    end, whichever is the wider.

    Raises:
        ValueError: if ``wall`` is under the material's minimum or eats the smaller bore, or
            ``length`` is not positive.
    """
    runs = (
        _Run(spigot_diameter(start, fit=fit, material=material) / 2, length, "inlet"),
        _Run(spigot_diameter(end, fit=fit, material=material) / 2, length, "outlet"),
    )
    refused = _refusal(wall, material, min(one.radius for one in runs) - wall, length=length)
    if refused is not None:
        raise ValueError(refused)
    return _turned(runs, wall, material)


# ---- the elbow ---------------------------------------------------------------------------


def elbow(
    size: Size,
    angle: float,
    *,
    radius: float | None = None,
    length: float = SPIGOT_LENGTH,
    wall: float = WALL,
    fit: Fit = Fit.SLIDE,
    material: Material = PLA,
) -> Solid:
    """A spigot tube for ``size`` turned ``angle`` radians towards ``+X`` round a bend of
    ``radius`` - one and a half of its own diameters when not given - with ``length`` of
    straight spigot at each end.

    The wall itself carried along a :func:`~bench.sweep.path`: a ring ``wall`` wide swept
    from the start to the end, so the elbow's faces are the sweep's own - ``start``, ``end``,
    ``side-0`` outside and ``bore`` inside - and ``end`` is a flat face a part can be mated
    onto.

    **Any turn is drawn; not every turn prints unsupported.** It prints standing on its
    start, and there the inside of the bend leans as far off the vertical as the elbow
    turns. Up to the material's ``max_overhang`` - 45 degrees in PLA - that holds itself up;
    past it ``check_overhangs`` says so, the way it says so of any part. A turn beyond that
    angle is best made as two elbows joined by a :func:`coupler` - two of 45 degrees for a
    90 - each of which prints clean; one elbow of the whole turn prints with support.

    Raises:
        ValueError: if ``wall`` is under the material's minimum or leaves no bore, or if
            ``length`` is not positive - and, from :func:`~bench.sweep.path` and
            :func:`~bench.sweep.sweep`, if ``angle`` turns nothing or a whole turn, or the
            bend is tighter than the tube is wide.
    """
    outside = spigot_diameter(size, fit=fit, material=material)
    refused = _refusal(wall, material, outside / 2 - wall, length=length)
    if refused is not None:
        raise ValueError(refused)
    bend = 1.5 * outside if radius is None else radius
    route = path(ORIGIN, Z, Straight(length), Bend(bend, angle, X), Straight(length))
    ring = face(circle(outside / 2), holes=(circle(outside / 2 - wall, label="bore"),))
    return sweep(ring, route)


# ---- the branch --------------------------------------------------------------------------


def branch(
    run: Size,
    tap: Size | None = None,
    *,
    angle: float = math.radians(45.0),
    length: float = SPIGOT_LENGTH,
    wall: float = WALL,
    fit: Fit = Fit.SLIDE,
    material: Material = PLA,
) -> Solid:
    """A wye: a straight ``run`` with a ``tap`` - the same size when not given - leaving it
    towards ``+X`` the way the air does, up the run and round a bend of ``angle`` radians,
    every port a spigot ``length`` long.

    Two paths: the run straight up, and the tap setting off up the run's own axis from the
    top of the inlet spigot and bending out of it. Each is a rod, and the two rods unioned
    have both bores cut out of them together - ``run``, ``tap`` and ``bore`` in the tree, the
    run's ends ``run/bottom`` and ``run/top`` and the tap's ``tap/end``. Not hollowed with
    :func:`~bench.shell.shell`: two paths crossing are a union, which shell has no one recipe
    to make again.

    The tap sets off *along* the run rather than across it for the printer's sake. A tap
    drilled straight into a run of its own size meets the run's bore at two points where
    the two bores are tangent, and the end of the tool that cut it is left there as a
    sliver leaning ``90 - angle`` degrees - past what ASA holds up. Setting off up the run,
    the tap's bore begins as a floor instead, which leans nothing.

    It prints standing on the run's start, where the tap's bend leans as far as it turns:
    up to the material's ``max_overhang`` it holds itself up, and past it
    ``check_overhangs`` says so, as it would of any part.

    Raises:
        ValueError: if ``angle`` does not leave the run somewhere between straight on and
            square across it, if the tap is wider than the run, if ``wall`` is under the
            material's minimum or leaves no bore, or ``length`` is not positive.
    """
    big = spigot_diameter(run, fit=fit, material=material) / 2
    small = spigot_diameter(run if tap is None else tap, fit=fit, material=material) / 2
    refused = _refusal(wall, material, small - wall, length=length)
    if refused is not None:
        raise ValueError(refused)
    if not TOL < angle <= math.pi / 2 + TOL:
        msg = (
            f"a branch's tap leaves its run between 0 and 90 degrees, not {math.degrees(angle):.1f}"
        )
        raise ValueError(msg)
    if small > big + TOL:
        msg = f"a branch's tap ({2 * small:.1f} mm) is no wider than its run ({2 * big:.1f} mm)"
        raise ValueError(msg)
    sin, cos = math.sin(angle), math.cos(angle)
    bend = 3.0 * small
    out, up = bend * (1.0 - cos), bend * sin  # where the bend ends, from where it began
    # Along the tap's straight leg, how far until its near side is clear of the run's
    # outside: the tap's spigot starts there, and the run's outlet spigot above its far side.
    clear = max(0.0, (big + small * cos - out) / sin)
    top = length + up + clear * cos + small * sin + length
    rods = union(
        cylinder(big, top, label="run"),
        sweep(
            fill(circle(small), on=raised(XY, length)),
            _tapped(length, bend, angle, clear + length),
            label="tap",
        ),
    )
    bores = union(
        cylinder(big - wall, top + 2 * PAST, at=Point(0.0, 0.0, -PAST), label="run"),
        sweep(
            fill(circle(small - wall), on=raised(XY, length)),
            _tapped(length, bend, angle, clear + length + PAST),
            label="tap",
        ),
    )
    return cut(rods, bores, label="bore")


def _tapped(start: float, bend: float, angle: float, leg: float) -> Wire:
    """A tap's path: up the run's axis from ``start``, round ``bend`` towards ``+X`` by
    ``angle``, and ``leg`` on."""
    return path(Point(0.0, 0.0, start), Z, Bend(bend, angle, X), Straight(leg))


# ---- square to round ---------------------------------------------------------------------


def square_to_round(
    width: float,
    deep: float,
    size: Size,
    *,
    corner: float = 2.0,
    collar: float = 10.0,
    length: float = SPIGOT_LENGTH,
    wall: float = WALL,
    fit: Fit = Fit.SLIDE,
    material: Material = PLA,
) -> Solid:
    """A rectangular opening ``width`` by ``deep`` inside, corners rounded to ``corner``, to a
    spigot for ``size`` - a register boot, a hood's throat.

    A ``collar`` of the rectangle straight up off the bed, a loft from it to the round, and
    the spigot ``length`` on up from that - ``collar``, ``transition`` and ``spigot`` in the
    tree, the cavity through all three ``bore``. The loft rises as little as keeps every part
    of it leaning no more than the material's ``max_overhang``, wherever the rectangle is
    wider than the round or narrower. The collar is what it stands on, so the leaning loft
    is never cut off open at the bed with a knife edge for its rim.

    **Why it is a cut and not three shells.** Three bodies hollowed and set end to end meet
    face to face, and a modeller keeps two bodies that only touch as two: measured, the
    spigot's underside stays in the part as a ceiling leaning 90 degrees and the loft's rim
    as a wall 0.17 mm thick. So each piece here runs a wall's length on into the next - the
    loft's both ends straight on, the way the collar and the spigot run - and the outside and
    the cavity are each one body, the cavity cut out once.

    **The loft's wall is ``wall`` level with the openings**, as :func:`~bench.shell.shell`
    measures a loft's, so along a side leaning ``a`` it is ``wall * cos(a)`` through; and
    that is what is held to the material's ``min_wall``.

    Raises:
        ValueError: if ``wall`` leaning the most the loft leans is under the material's
            minimum, if the opening, ``corner`` or ``length`` is not positive, if the
            ``collar`` is no taller than the wall, or the spigot's bore closes up.
    """
    lean = material.max_overhang
    radius = spigot_diameter(size, fit=fit, material=material) / 2
    refused = _refusal(
        wall * math.cos(lean),
        material,
        radius - wall,
        width=width,
        deep=deep,
        corner=corner,
        length=length,
        collar=collar - wall,
    )
    if refused is not None:
        raise ValueError(refused)
    # How far the rectangle's outside reaches past the round's at its corners, and falls
    # short of it across its narrower side: whichever is more sets how far the loft leans.
    reach = math.hypot(width / 2 - corner, deep / 2 - corner) + corner + wall - radius
    short = radius - min(width, deep) / 2 - wall
    top = collar + max(reach, short, wall) / math.tan(lean)
    outside = union(
        union(
            extrude(fill(_opening(width, deep, corner, wall)), collar, label="collar"),
            _lofted(_opening(width, deep, corner, wall), radius, collar, top, wall, "transition"),
        ),
        extrude(fill(circle(radius), on=raised(XY, top)), length, label="spigot"),
    )
    inside = union(
        union(
            extrude(
                fill(_opening(width, deep, corner, 0.0), on=raised(XY, -PAST)),
                collar + PAST,
                label="collar",
            ),
            _lofted(
                _opening(width, deep, corner, 0.0), radius - wall, collar, top, wall, "transition"
            ),
        ),
        extrude(fill(circle(radius - wall), on=raised(XY, top)), length + PAST, label="spigot"),
    )
    return cut(outside, inside, label="bore")


def _opening(width: float, deep: float, corner: float, grown: float) -> Wire:
    """The rectangle ``width`` by ``deep`` about the axis, grown by ``grown`` all round."""
    return rounded_rect(
        width + 2 * grown,
        deep + 2 * grown,
        corner + grown,
        Point(-width / 2 - grown, -deep / 2 - grown),
    )


def _lofted(
    rectangle: Wire, radius: float, low: float, high: float, run_on: float, name: str
) -> Solid:
    """The loft from ``rectangle`` at ``low`` to a circle of ``radius`` at ``high``, running
    straight on ``run_on`` past each end - one hull, since both ends' straight runs keep it
    convex - so the pieces either side of it overlap it rather than touch it."""
    return hull(
        fill(rectangle, on=raised(XY, low - run_on)),
        fill(rectangle, on=raised(XY, low)),
        fill(circle(radius), on=raised(XY, high)),
        fill(circle(radius), on=raised(XY, high + run_on)),
        label=name,
    )


# ---- turned outlines ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Run:
    """One straight stretch of a turned fitting's outside: its radius, how long it runs, and
    the name its face takes."""

    radius: float
    length: float
    name: str


def _turned(runs: tuple[_Run, ...], wall: float, material: Material) -> Solid:
    """``runs`` stacked up ``+Z`` from the origin with a cone leaning the material's
    ``max_overhang`` between any two of different radius, turned about ``Z`` and hollowed to
    ``wall``, open at both ends.

    Every edge of the outline is named, so every face is: a run's outside is
    ``side-<name>``, a cone's ``side-<below>-<above>``, the two ends ``side-start`` and
    ``side-end``, and the bore under each ``inside/side-...`` of the same. A revolve's faces
    have no one plane, so none of these takes a mate by name: a turned fitting is placed on
    its axis, coaxial with what it joins, the way ``dust_line.py`` slides its coupler on.
    """
    run_of_cone = math.tan(material.max_overhang)
    corners: list[tuple[float, float, str]] = [(0.0, 0.0, "start")]
    z = 0.0
    for i, one in enumerate(runs):
        if i:
            before = runs[i - 1]
            step = abs(one.radius - before.radius)
            if step > TOL:
                corners.append((before.radius, z, f"{before.name}-{one.name}"))
                z += step / run_of_cone
        corners.append((one.radius, z, one.name))
        z += one.length
    corners += [(runs[-1].radius, z, "end"), (0.0, z, "axis")]
    on = plane(ORIGIN, -Y, X)  # drawn in x (out from the axis) and z (up it)
    edges = tuple(
        Edge(
            Line(
                Point(r0, z0),
                Point(corners[(k + 1) % len(corners)][0], corners[(k + 1) % len(corners)][1]),
            ),
            _label(called),
        )
        for k, (r0, z0, called) in enumerate(corners)
    )
    body = revolve(face(wire(edges), on=on), Axis(ORIGIN, Z))
    return shell(body, wall, open=("side-start", "side-end"))


def _socket_outside(size: Size, wall: float, fit: Fit, material: Material) -> float:
    """A socket collar's outside radius: its bore and a wall."""
    return socket_diameter(size, fit=fit, material=material) / 2 + wall


def _socket_run(depth: float, wall: float, lean: float) -> float:
    """How far a socket collar's outside runs for its bore to run ``depth`` to the stop.

    The stop's cone and the collar meet a little further along outside than inside:
    hollowing moves the corner between them ``wall * tan(lean / 2)`` along the axis."""
    return depth + wall * math.tan(lean / 2)


# ---- refusals ---------------------------------------------------------------------------


def _refusal(least: float, material: Material, bore: float, **sizes: float) -> str | None:
    """Why a fitting cannot be drawn, or ``None`` when it can: any of ``sizes`` that is not a
    length, a wall whose thinnest, ``least``, is under what ``material`` prints, or a
    narrowest bore of radius ``bore`` that the wall has closed up."""
    for called, size in sizes.items():
        if size <= TOL:
            return f"{called} must be positive, not {size}"
    if least < material.min_wall - TOL:
        return f"a {least:.2f} mm wall is under the {material.min_wall} mm {material.name} prints"
    if bore <= TOL:
        return "the wall is as wide as the tube, and leaves no bore"
    return None
