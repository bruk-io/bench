"""Gridfinity bins, printed: the object the whole ecosystem is built on.

A :class:`Spec` says how many units the bin is, how tall, how it is divided and what it
carries; :func:`derive` turns that into millimetres, :func:`validate` names the first
parameter that will not print, and :func:`bin_` returns a :class:`~bench.model.Build` with
one printed part in it. The laser-cut cabinet next door is :mod:`bench.library.gridfinity`;
this is the thing that goes in its drawers.

**The constants are the standard's own** (`gridfinity-rebuilt-openscad`, `src/core/standard.scad`):
:data:`GRID` 42, :data:`BASE_TOP` 41.5 - so a bin is half a millimetre under its grid, a
quarter of a millimetre a side - and :data:`BASE_PROFILE`, the four-point section of the
foot: out 0.8 and up 0.8, straight up 1.8, then out 2.15 and up 2.15, 4.75 mm in all.

**The stacking lip is that same profile plus a fit.** A bin's top is a baseplate pocket for
the bin above, and a baseplate pocket is the base with clearance round it, so the lip's void
here is :data:`BASE_PROFILE` widened by ``clearance(spec.fit, spec.material)`` a side - and,
because every flank of it is at 45 degrees, shortened by the same amount. The standard's own
lip is 2.6 wide by 4.4 tall, which is this rule at 0.35 mm; ``Fit.CLEARANCE`` in PLA is
0.30, so a bin from here stacks a twentieth of a millimetre tighter than the standard and
still takes one either way. One number, in the fit table, rather than a second table to keep
in step with the first.

**Height means four different things** and makers use all four, so it is a union:
:class:`Units` of 7 mm excluding the lip, :class:`Internal` millimetres of usable depth,
:class:`External` millimetres excluding the lip and :class:`ExternalWithLip` including it.
:func:`derive` matches over them and ends in ``assert_never``, so a fifth meaning cannot be
added without every reader being written for it.

Not here: the baseplate. It is the other half of the module and it is its own step.
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import NamedTuple, assert_never

from ..fasteners import M3, MAGNET_6X2, Fit, Magnet, Screw, bore
from ..features import bridge_steps
from ..geometry import TOL, XY, Axis, Point, X, Y, Z, plane, raised
from ..model import Build, Material, Placed, Printed, Ref, assembly, part
from ..ops import fill, rect, rounded_rect
from ..solids import Turn, cut, cylinder, extrude, grid, hull, name, pattern, union
from ..topology import Arc, Edge, Face, Line, Solid, wire
from .print import PLA, clearance

GRID = 42.0
"""One Gridfinity unit across and deep, in millimetres."""

BASE_TOP = 41.5
"""How wide the top of a bin's base is per unit: half a millimetre under :data:`GRID`, which
is the quarter of a millimetre a side that lets a bin drop into a baseplate."""

Z_UNIT = 7.0
"""One Gridfinity height unit."""

BASE_PROFILE = ((0.0, 0.0), (0.8, 0.8), (0.8, 2.6), (2.95, 4.75))
"""The section of a bin's foot, as ``(out, up)`` pairs from its narrowest bottom corner: a
45 degree chamfer of 0.8, 1.8 mm of upright wall, and a 45 degree chamfer of 2.15. The
standard's own table, and the shape a baseplate pocket and a stacking lip are both cut to."""

BASE_HEIGHT = 4.75
"""How tall the foot is - the last height in :data:`BASE_PROFILE`, named because everything
above it is measured from it."""

CORNER_R = 3.75
"""The corner radius at the top of the base, where the footprint is widest. Every slice
below it is rounded by that radius less how far in the slice stands."""

MAGNET_AT = 13.0
"""How far from a unit's centre each magnet or screw sits, in both directions."""

_REACH = BASE_PROFILE[-1][0]
"""How far the foot grows from its narrowest corner to its widest: 2.95 mm."""

_BRIDGE_LAYERS = 3
"""How many layers of stepped square a magnet pocket's ceiling is bridged with -
gridfinity-rebuilt's own count."""

_OVER = 0.01
"""How far, in millimetres, a cutting tool starts outside the material it cuts."""


# ---- what a height means --------------------------------------------------------------


class Units(NamedTuple):
    """A height in 7 mm Gridfinity units, excluding the stacking lip - what a bin is
    usually called by (``2x1x3``). The field is ``units`` rather than ``count`` because a
    :class:`~typing.NamedTuple` is a tuple, and a tuple already has a ``count``."""

    units: int


class Internal(NamedTuple):
    """A height as the usable depth inside the bin, in millimetres - what a maker measures
    when the thing to be stored is the thing that matters."""

    mm: float


class External(NamedTuple):
    """A height as the bin's own, in millimetres, excluding the stacking lip."""

    mm: float


class ExternalWithLip(NamedTuple):
    """A height as the bin's own, in millimetres, lip included - what a drawer's headroom
    is measured against."""

    mm: float


Height = Units | Internal | External | ExternalWithLip
"""The four things "how tall" means. Consumers ``match`` and end in ``assert_never``."""

_THREE_UNITS = Units(3)
"""The commonest bin there is, as a value rather than a call in a default."""


class Tab(StrEnum):
    """Where the label tab sits over a compartment, if it sits anywhere."""

    NONE = "none"
    LEFT = "left"
    CENTRE = "centre"
    RIGHT = "right"
    FULL = "full"


# ---- the parameters ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Spec:
    """What the bin is.

    ``divisions`` is how many compartments across and deep; ``scoop`` is a weight from 0 to
    1 rather than a flag, so a shallow bin can have a shallow ramp; ``tab_angle`` is the
    slope of the label tab's underside, where the standard's 36 degrees leaves a 54 degree
    overhang and 45 is the steepest a printer holds up by itself, which is why it is the
    default here. ``fit`` is how loosely this bin sits in the bin below it.
    """

    units_x: int = 2
    units_y: int = 1
    height: Height = _THREE_UNITS
    lip: bool = True
    wall: float = 1.2
    floor: float = 1.2
    divisions: tuple[int, int] = (1, 1)
    scoop: float = 0.0
    label_tab: Tab = Tab.NONE
    tab_width: float | None = None
    tab_depth: float = 15.85
    tab_angle: float = math.radians(45.0)
    magnets: bool = False
    screws: bool = False
    magnet: Magnet = MAGNET_6X2
    screw: Screw = M3
    fit: Fit = Fit.CLEARANCE
    material: Material = PLA


@dataclass(frozen=True, slots=True)
class Dims:
    """Every millimetre the bin is built from.

    ``height`` is the body, lip excluded, and ``total`` includes it. ``floor_z`` is the top
    of the floor, which is where every compartment starts. ``stack`` is the clearance the
    lip's void is grown by, and ``top_inset`` how far the material at the very top of the
    wall stands in from the outside - more than ``wall`` wherever there is a lip, which is
    what the 45 degree flare under the mouth of each compartment makes up.
    """

    outer_w: float
    outer_d: float
    height: float
    total: float
    floor_z: float
    compartment_w: float
    compartment_d: float
    scoop_r: float
    stack: float
    top_inset: float


def derive(spec: Spec) -> Dims:
    """The millimetres ``spec`` implies - the arithmetic only. :func:`validate` has the
    opinions."""
    outer_w = BASE_TOP + (spec.units_x - 1) * GRID
    outer_d = BASE_TOP + (spec.units_y - 1) * GRID
    floor_z = BASE_HEIGHT + spec.floor
    stack = clearance(spec.fit, spec.material)
    lip_h = BASE_HEIGHT - stack if spec.lip else 0.0
    height = _body_height(spec.height, floor_z, lip_h)
    top_inset = max(spec.wall, _REACH - stack) if spec.lip else spec.wall
    across, deep = spec.divisions
    compartment_w = (outer_w - 2 * spec.wall - (across - 1) * spec.wall) / across
    compartment_d = (outer_d - 2 * spec.wall - (deep - 1) * spec.wall) / deep
    return Dims(
        outer_w=outer_w,
        outer_d=outer_d,
        height=height,
        total=height + lip_h,
        floor_z=floor_z,
        compartment_w=compartment_w,
        compartment_d=compartment_d,
        scoop_r=spec.scoop * min(height - floor_z, compartment_d / 2),
        stack=stack,
        top_inset=top_inset,
    )


def _body_height(height: Height, floor_z: float, lip_h: float) -> float:
    """The bin's own height, lip excluded, whichever of the four ways it was given."""
    match height:
        case Units(units):
            return Z_UNIT * units
        case Internal(mm):
            return mm + floor_z
        case External(mm):
            return mm
        case ExternalWithLip(mm):
            return mm - lip_h
        case _:
            assert_never(height)


# ---- validation ----------------------------------------------------------------------


def validate(spec: Spec) -> None:
    """Nothing at all, when ``spec`` describes a bin that can be printed.

    Raises:
        ValueError: naming the first parameter that does not work.
    """
    for parameter in ("units_x", "units_y"):
        units = getattr(spec, parameter)
        if units < 1:
            msg = f"{parameter} must be at least one unit, not {units}"
            raise ValueError(msg)
    for parameter in ("wall", "floor", "tab_depth"):
        size = getattr(spec, parameter)
        if size <= 0.0:
            msg = f"{parameter} must be positive, not {size}"
            raise ValueError(msg)
    if spec.wall < spec.material.min_wall:
        msg = (
            f"wall of {spec.wall} is under the {spec.material.min_wall} mm"
            f" {spec.material.name} prints"
        )
        raise ValueError(msg)
    if not 0.0 <= spec.scoop <= 1.0:
        msg = f"scoop is a weight from 0 to 1, not {spec.scoop}"
        raise ValueError(msg)
    if not TOL < spec.tab_angle < math.pi / 2 - TOL:
        msg = f"tab_angle is a slope between flat and upright, not {spec.tab_angle} radians"
        raise ValueError(msg)
    if min(spec.divisions) < 1:
        msg = f"divisions needs at least one compartment each way, not {spec.divisions}"
        raise ValueError(msg)
    dims = derive(spec)
    room = dims.height - dims.floor_z
    flare = dims.top_inset - spec.wall
    if room <= flare + TOL:
        msg = (
            f"height leaves {room:.2f} mm inside a bin whose base and floor take"
            f" {dims.floor_z:.2f} mm, and the flare under its own mouth takes {flare:.2f} mm"
            f" of that"
        )
        raise ValueError(msg)
    if min(dims.compartment_w, dims.compartment_d) <= 2 * dims.top_inset:
        msg = (
            f"divisions of {spec.divisions} leaves a"
            f" {min(dims.compartment_w, dims.compartment_d):.2f} mm compartment, which its own"
            f" walls close up"
        )
        raise ValueError(msg)
    if spec.tab_width is not None and not 0.0 < spec.tab_width <= dims.compartment_w:
        msg = (
            f"tab_width of {spec.tab_width} does not fit a {dims.compartment_w:.2f} mm compartment"
        )
        raise ValueError(msg)
    if spec.magnets and BASE_HEIGHT - spec.magnet.h < _BRIDGE_LAYERS * spec.material.layer:
        msg = (
            f"magnets of {spec.magnet.h} mm leave no room under the {BASE_HEIGHT} mm base for"
            f" the layers that bridge the pocket"
        )
        raise ValueError(msg)


# ---- the bin -------------------------------------------------------------------------


def bin_(spec: Spec) -> Build:
    """The bin ``spec`` describes: one printed part, base first.

    Built bottom up, and every feature named as it enters the tree - ``foot-1``,
    ``lip/void``, ``compartment-2/scoop``, ``magnet-3`` - so a click in the viewer answers
    with something a script can be written against. The wall block is the one anonymous
    body, because the part names it.
    """
    validate(spec)
    dims = derive(spec)
    stock = Printed(spec.material)
    body = _walls(dims)
    for foot in _feet(spec):
        body = union(body, foot)
    if spec.lip:
        body = union(body, _lip(dims))
    corners = _compartment_corners(spec, dims)
    for i, corner in enumerate(corners):
        body = cut(body, _cavity(spec, dims, corner.x, corner.y), label=f"compartment-{i + 1}")
    for i, corner in enumerate(corners):
        if dims.scoop_r > TOL:
            body = union(body, name(_scoop(dims, corner.x, corner.y), f"scoop-{i + 1}"))
        tab = _tab(spec, dims, corner.x, corner.y)
        if tab is not None:
            body = union(body, name(tab, f"tab-{i + 1}"))
    body = _holes(spec, dims, body)
    one = part("bin", body, stock)
    return Build(
        assembly(f"gridfinity-{spec.units_x}x{spec.units_y}", (Placed(one, XY),)),
        frozendict({Ref(one.label): 1}),
    )


# ---- the base ------------------------------------------------------------------------


def _slice_at(size_w: float, size_d: float, inset: float, z: float, at: Point) -> Face:
    """One flat slice of a profile: a rounded rectangle centred on ``at``, ``inset`` in from
    the widest the shape gets, drawn on the plane ``z`` millimetres up."""
    w, d = size_w - 2 * inset, size_d - 2 * inset
    return fill(
        rounded_rect(w, d, max(0.0, CORNER_R - inset), Point(at.x - w / 2, at.y - d / 2)),
        on=raised(XY, z),
    )


def _feet(spec: Spec) -> tuple[Solid, ...]:
    """One foot per grid unit: the hull of the four slices of :data:`BASE_PROFILE`.

    There is no sweep on this kernel, so a chamfered profile is a stack of flat slices with
    a hull round it - which is how every Gridfinity generator has always written it, and
    exact here because every run between two slices is straight.
    """
    middle = Point(BASE_TOP / 2, BASE_TOP / 2, 0.0)
    foot = hull(
        *(_slice_at(BASE_TOP, BASE_TOP, _REACH - out, z, middle) for out, z in BASE_PROFILE),
        label="foot",
    )
    return grid(foot, (spec.units_x, spec.units_y), (X * GRID, Y * GRID))


def _walls(dims: Dims) -> Solid:
    """The block the compartments are cut out of: the whole footprint, from the top of the
    base to the top of the bin. The part's one anonymous body."""
    return extrude(
        fill(rounded_rect(dims.outer_w, dims.outer_d, CORNER_R), on=raised(XY, BASE_HEIGHT)),
        dims.height - BASE_HEIGHT,
    )


def _lip(dims: Dims) -> Solid:
    """The stacking lip: a ring of the full footprint with a baseplate pocket cut out of it.

    The pocket is :data:`BASE_PROFILE` grown by the fit - see this module's own docstring -
    so the bin above drops into it and the two never touch.
    """
    blank = extrude(
        fill(rounded_rect(dims.outer_w, dims.outer_d, CORNER_R), on=raised(XY, dims.height)),
        dims.total - dims.height,
    )
    middle = Point(dims.outer_w / 2, dims.outer_d / 2, 0.0)
    void = hull(
        *(
            _slice_at(dims.outer_w, dims.outer_d, inset, dims.height + z, middle)
            for inset, z in (_grown(_REACH - out, up, dims.stack) for out, up in BASE_PROFILE)
        )
    )
    return name(cut(blank, void, label="void"), "lip")


def _grown(inset: float, z: float, gap: float) -> tuple[float, float]:
    """One step of the base profile as the lip's void: ``gap`` further out, and where that
    would reach past the outside face, ``gap`` further down instead.

    Every flank of the profile is at 45 degrees, so out and down are the same move, which is
    what keeps the grown profile parallel to the one it came from - and what makes the
    void 4.45 mm deep where the foot is 4.75 mm tall.
    """
    return (inset - gap, z) if inset >= gap else (0.0, z - (gap - inset))


# ---- what is cut out of it -----------------------------------------------------------


def _compartment_corners(spec: Spec, dims: Dims) -> tuple[Point, ...]:
    """The lower-left corner of every compartment, row by row - the order the labels count
    in, so ``compartment-3`` on a two by two is the left one of the back row."""
    across, deep = spec.divisions
    return tuple(
        Point(
            spec.wall + i * (dims.compartment_w + spec.wall),
            spec.wall + j * (dims.compartment_d + spec.wall),
            0.0,
        )
        for j in range(deep)
        for i in range(across)
    )


def _cavity(spec: Spec, dims: Dims, x: float, y: float) -> Solid:
    """One compartment, from the floor to the top of the bin.

    Under a stacking lip the material at the top of the wall stands further in than the wall
    does, so the mouth of the compartment is flared back to meet it at 45 degrees rather
    than left as a ledge with nothing under it.
    """
    w, d = dims.compartment_w, dims.compartment_d
    taper = dims.top_inset - spec.wall
    if taper <= TOL:
        return extrude(fill(rect(w, d, Point(x, y)), on=raised(XY, dims.floor_z)), dims.height)
    straight = extrude(
        fill(rect(w, d, Point(x, y)), on=raised(XY, dims.floor_z)),
        dims.height - taper - dims.floor_z,
    )
    mouth = hull(
        fill(rect(w, d, Point(x, y)), on=raised(XY, dims.height - taper)),
        fill(
            rect(w - 2 * taper, d - 2 * taper, Point(x + taper, y + taper)),
            on=raised(XY, dims.height),
        ),
    )
    return union(straight, mouth)


def _scoop(dims: Dims, x: float, y: float) -> Solid:
    """The ramp at the front of a compartment, so a thumb can get under what is in it.

    The section is a square with a quarter circle taken out of the corner - a fillet drawn
    as the shape it makes, since there is no fillet verb - swept along the compartment by
    extruding it.
    """
    r = dims.scoop_r
    on = plane(Point(x, y, dims.floor_z), X, Y)  # u runs +Y, v runs +Z, the sweep runs +X
    section = wire(
        (
            Edge(Line(Point(0.0, 0.0, 0.0), Point(r, 0.0, 0.0))),
            Edge(Arc(Point(r, r, 0.0), r, -math.pi / 2, -math.pi, XY)),
            Edge(Line(Point(0.0, r, 0.0), Point(0.0, 0.0, 0.0))),
        )
    )
    return extrude(fill(section, on=on), dims.compartment_w)


def _tab(spec: Spec, dims: Dims, x: float, y: float) -> Solid | None:
    """The label tab over the back of a compartment, or ``None`` where there is none.

    A wedge: flat on top, level with the bin's rim, and sloping back to the wall underneath
    at ``tab_angle``. At 45 degrees that underside is the steepest a printer holds up with
    nothing beneath it.
    """
    if spec.label_tab is Tab.NONE:
        return None
    width = _tab_width(spec, dims)
    drop = spec.tab_depth * math.tan(spec.tab_angle)
    at = _tab_x(spec, dims, x, width)
    on = plane(Point(at, y + dims.compartment_d, dims.height), X, Y)
    section = wire(
        (
            Edge(Line(Point(0.0, 0.0, 0.0), Point(-spec.tab_depth, 0.0, 0.0))),
            Edge(Line(Point(-spec.tab_depth, 0.0, 0.0), Point(0.0, -drop, 0.0))),
            Edge(Line(Point(0.0, -drop, 0.0), Point(0.0, 0.0, 0.0))),
        )
    )
    return extrude(fill(section, on=on), width)


def _tab_width(spec: Spec, dims: Dims) -> float:
    """How wide the tab is: what was asked for, or the whole compartment."""
    if spec.label_tab is Tab.FULL or spec.tab_width is None:
        return dims.compartment_w
    return spec.tab_width


def _tab_x(spec: Spec, dims: Dims, x: float, width: float) -> float:
    """Where the tab starts along the compartment."""
    match spec.label_tab:
        case Tab.NONE | Tab.FULL | Tab.LEFT:
            return x
        case Tab.CENTRE:
            return x + (dims.compartment_w - width) / 2
        case Tab.RIGHT:
            return x + dims.compartment_w - width
        case _:
            assert_never(spec.label_tab)


# ---- magnets and screws --------------------------------------------------------------


def _holes(spec: Spec, dims: Dims, body: Solid) -> Solid:
    """``body`` with a magnet pocket, a screw hole or both at each corner of each unit.

    A magnet pocket is cut from underneath, so its ceiling is a disc with nothing holding it
    up. The fix is gridfinity-rebuilt's: three layers of square, each turned a quarter turn
    from the last, stepping out from the screw hole to the pocket, for the slicer to bridge
    onto. That is :func:`~bench.features.bridge_steps`, and it is why the pocket and the steps
    are one feature here rather than two.
    """
    if not (spec.magnets or spec.screws):
        return body
    layer = spec.material.layer
    inner = bore(spec.screw, Fit.PRESS) + spec.material.hole_compensation
    for i, at in enumerate(_hole_centres(spec)):
        if spec.magnets:
            pocket = cylinder(spec.magnet.hole / 2, spec.magnet.h + _OVER, at=at + Z * -_OVER)
            body = cut(body, pocket, label=f"magnet-{i + 1}")
            body = union(body, name(_ribs(spec, at), f"ribs-{i + 1}"))
            steps = tuple(
                name(
                    extrude(fill(step, on=raised(XY, spec.magnet.h + j * layer)), layer),
                    f"step-{j + 1}",
                )
                for j, step in enumerate(
                    bridge_steps(inner, spec.magnet.hole, _BRIDGE_LAYERS, layer, at=at)
                )
            )
            body = cut(body, _all(steps), label=f"bridge-{i + 1}")
        if spec.screws:
            reach = dims.floor_z + 2 * _OVER
            body = cut(
                body,
                cylinder(inner / 2, reach, at=at + Z * -_OVER),
                label=f"screw-{i + 1}",
            )
    return body


def _hole_centres(spec: Spec) -> tuple[Point, ...]:
    """Four to a unit, :data:`MAGNET_AT` either way from its centre."""
    out: list[Point] = []
    for j in range(spec.units_y):
        for i in range(spec.units_x):
            centre = Point(BASE_TOP / 2 + i * GRID, BASE_TOP / 2 + j * GRID, 0.0)
            out += [
                Point(centre.x + dx * MAGNET_AT, centre.y + dy * MAGNET_AT, 0.0)
                for dy in (-1.0, 1.0)
                for dx in (-1.0, 1.0)
            ]
    return tuple(out)


def _ribs(spec: Spec, at: Point) -> Solid:
    """The crush ribs that hold a magnet: pillars standing proud of the pocket wall, printed
    a fraction under the magnet's own diameter so they crush as it goes in.

    The one pattern here that turns rather than steps - eight of them round the pocket - and
    what :class:`~bench.solids.Turn` is for.
    """
    magnet = spec.magnet
    thick = magnet.hole - magnet.rib_d
    rib = cylinder(thick / 2, magnet.h, at=Point(at.x + magnet.hole / 2, at.y, 0.0), label="rib")
    return _all(pattern(rib, magnet.ribs, Turn(Axis(at, Z), math.tau / magnet.ribs)))


def _all(bodies: tuple[Solid, ...]) -> Solid:
    """Several bodies as one. Every one of them is labelled, so none of the names collide."""
    made = bodies[0]
    for one in bodies[1:]:
        made = union(made, one)
    return made
