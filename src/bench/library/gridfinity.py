"""Gridfinity: a laser-cut drawer cabinet sized in Gridfinity units.

A :class:`Spec` says how many Gridfinity units a drawer holds and how thick the stock
is; :func:`derive` turns that into millimetres and :func:`cabinet` into the panels.
Everything is built from :mod:`bench.ops`, :mod:`bench.solids` and :mod:`bench.joints`, so
the cabinet is the same finger-jointed open box as a drawer - turned on its back, with its
open top facing the room.

The fit rules, in one place: a drawer's inside is ``42 x units`` plus a clearance so a
baseplate drops in; its height is ``7 x height_u`` plus the bin lip, a clearance above
the bins and the baseplate it stands on. A drawer's pitch in the carcass is the runner
it sits on, its own height and the gap above it. Runners are strips with tabs that pass
through slots in the cabinet sides; the right side is the left one flipped over, so its
slots are the left one's mirrored.

A :func:`cabinet` returns a :class:`~bench.model.Build`: one :class:`~bench.model.Part` per
*distinct* panel in an assembly, a table saying how many of each to cut, and the OpenSCAD
text for the printed baseplate among its files. Identical panels - a drawer's two sides, the
cabinet's top and bottom - appear once and are counted, which is what a cut list wants and
what keeps every ref unique.
"""

from dataclasses import dataclass, replace
from typing import NamedTuple

from ..geometry import XY, Point
from ..joints import Interval, flat_intervals, jagged_edge, open_box
from ..model import Build, Part, Placed, Process, Ref, Stock, Text, assembly, part
from ..ops import fill, rect, slot, text_width
from ..solids import cut
from ..topology import SEP, Face, Label, wire

GRID = 42.0
"""The Gridfinity grid: one unit across and deep."""

Z_UNIT = 7.0
"""One Gridfinity height unit."""

LIP = 4.4
"""How far a bin's stacking lip stands above its nominal height."""

BASEPLATE_T = 4.65
"""How tall a light baseplate is, and how much drawer height it eats."""

_MATERIAL = "ply"
_TAB = 16.0
"""How long one runner tab is, measured along the runner."""

_TAB_INSET = 6.0
"""How far the end tabs sit in from the runner's ends."""

_TAB_ROOM = 40.0
"""Spare length a runner must have before it earns a third tab in the middle."""

_CORNER_R = 4.0
"""The corner radius of a baseplate's footprint and of a pocket's mouth."""


# ---- the parameters ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Spec:
    """What the cabinet is: Gridfinity units, how many drawers, the stock and the fits.

    ``labels`` is what gets engraved on each drawer front, one per drawer; left empty the
    drawers are numbered ``1`` upwards. ``columns`` is how many of this cabinet to cut,
    so it multiplies every quantity and changes no dimension.
    """

    units_x: int = 4
    units_y: int = 2
    height_u: int = 3
    drawers: int = 6
    columns: int = 1
    drawer_t: float = 3.0
    carcass_t: float = 6.0
    kerf: float = 0.25
    finger: float = 12.0
    baseplate: bool = True
    baseplate_clearance: float = 1.0
    bin_clearance: float = 3.0
    side_clearance: float = 0.75
    drawer_gap: float = 1.5
    runner_reach: float = 8.0
    runner_setback: float = 2.0
    pull_w: float = 30.0
    pull_h: float = 9.0
    pull_margin: float = 5.0
    labels: tuple[str, ...] = ()
    label_size: float = 5.0


@dataclass(frozen=True, slots=True)
class Dims:
    """Every length the panels are cut to, in millimetres.

    ``interior_*`` is the room inside a drawer, ``drawer_*`` the drawer outside, ``cab_*``
    the carcass outside, and ``pitch`` the rise from one drawer to the next. ``runner_w``
    counts the tabs: a runner blank is ``runner_len`` by ``runner_w``.
    """

    interior_w: float
    interior_d: float
    interior_h: float
    drawer_w: float
    drawer_d: float
    drawer_h: float
    pitch: float
    cab_w: float
    cab_d: float
    cab_h: float
    runner_len: float
    runner_w: float


def derive(spec: Spec) -> Dims:
    """The lengths ``spec`` implies - the arithmetic only, with no opinion on whether the
    result can be cut; :func:`validate` has the opinions."""
    interior_w = GRID * spec.units_x + spec.baseplate_clearance
    interior_d = GRID * spec.units_y + spec.baseplate_clearance
    floor = BASEPLATE_T if spec.baseplate else 0.0
    interior_h = Z_UNIT * spec.height_u + LIP + spec.bin_clearance + floor
    drawer_w = interior_w + 2 * spec.drawer_t
    drawer_d = interior_d + 2 * spec.drawer_t
    drawer_h = interior_h + spec.drawer_t
    pitch = spec.carcass_t + drawer_h + spec.drawer_gap
    return Dims(
        interior_w=interior_w,
        interior_d=interior_d,
        interior_h=interior_h,
        drawer_w=drawer_w,
        drawer_d=drawer_d,
        drawer_h=drawer_h,
        pitch=pitch,
        cab_w=drawer_w + 2 * spec.side_clearance + 2 * spec.carcass_t,
        cab_d=drawer_d + spec.carcass_t,
        cab_h=2 * spec.carcass_t + spec.drawers * pitch,
        runner_len=drawer_d - spec.runner_setback,
        runner_w=spec.runner_reach + spec.carcass_t,
    )


def _labels(spec: Spec) -> tuple[str, ...]:
    """What goes on each drawer front: the spec's own labels, or ``1`` upwards."""
    if spec.labels:
        return spec.labels
    return tuple(str(i + 1) for i in range(spec.drawers))


# ---- validation ----------------------------------------------------------------------

_COUNTS = ("units_x", "units_y", "height_u", "drawers", "columns")
_SIZES = ("drawer_t", "carcass_t", "finger", "pull_w", "pull_h", "label_size")
_GAPS = (
    "kerf",
    "baseplate_clearance",
    "bin_clearance",
    "side_clearance",
    "drawer_gap",
    "runner_reach",
    "runner_setback",
    "pull_margin",
)


def validate(spec: Spec) -> None:
    """Nothing at all, when ``spec`` describes a cabinet that can be cut.

    Raises:
        ValueError: naming the first parameter that does not work.
    """
    for parameter in _COUNTS:
        count = getattr(spec, parameter)
        if count < 1:
            msg = f"{parameter} must be at least one, not {count}"
            raise ValueError(msg)
    for parameter in _SIZES:
        size = getattr(spec, parameter)
        if size <= 0:
            msg = f"{parameter} must be positive, not {size}"
            raise ValueError(msg)
    for parameter in _GAPS:
        gap = getattr(spec, parameter)
        if gap < 0:
            msg = f"{parameter} cannot be negative, not {gap}"
            raise ValueError(msg)
    if spec.finger < 2 * spec.carcass_t:
        msg = (
            f"finger of {spec.finger} is shorter than the {2 * spec.carcass_t} a joint in"
            f" {spec.carcass_t} mm stock needs"
        )
        raise ValueError(msg)
    dims = derive(spec)
    _jointable(dims.drawer_w, dims.drawer_d, dims.drawer_h, spec.drawer_t, "drawer_t", "drawer")
    _jointable(dims.cab_h, dims.cab_w, dims.cab_d, spec.carcass_t, "carcass_t", "carcass")
    _pull_fits(spec, dims)
    _runner_fits(spec, dims)
    _labels_fit(spec)


def _jointable(w: float, d: float, h: float, t: float, parameter: str, what: str) -> None:
    """Nothing, when every jointed run of a box ``w`` by ``d`` by ``h`` in ``t`` mm stock
    is long enough for three fingers of ``2 * t``.

    Raises:
        ValueError: naming ``parameter`` when one of those runs is too short.
    """
    shortest = min(w, d - 2 * t, h)
    if shortest < 6 * t:
        msg = (
            f"{parameter} of {t} leaves the {what} a {shortest} mm run, too short for three"
            f" fingers of {2 * t}"
        )
        raise ValueError(msg)


def _pull_fits(spec: Spec, dims: Dims) -> None:
    """Nothing, when the pull and the label both fit on a drawer front.

    Raises:
        ValueError: naming ``pull_w`` when the stadium cannot sit between the side joints,
            or ``pull_h`` and ``pull_margin`` when they leave no band for the label above
            the bottom joint.
    """
    if spec.pull_w <= spec.pull_h:
        msg = f"pull_w of {spec.pull_w} must be longer than pull_h of {spec.pull_h} to be a stadium"
        raise ValueError(msg)
    room = dims.drawer_w - 2 * spec.drawer_t
    if spec.pull_w > room:
        msg = f"pull_w of {spec.pull_w} does not fit the {room} mm of front between the side joints"
        raise ValueError(msg)
    band = dims.drawer_h - spec.pull_margin - spec.pull_h - spec.drawer_t
    if band < spec.label_size:
        msg = (
            f"pull_h of {spec.pull_h} and pull_margin of {spec.pull_margin} leave {band} mm"
            f" between the pull and the bottom joint, less than the label_size of"
            f" {spec.label_size}"
        )
        raise ValueError(msg)


def _runner_fits(spec: Spec, dims: Dims) -> None:
    """Nothing, when a runner is long enough for a tab at each end.

    Raises:
        ValueError: naming ``runner_setback`` when it is not.
    """
    shortest = 2 * (_TAB_INSET + _TAB)
    if dims.runner_len <= shortest:
        msg = (
            f"runner_setback of {spec.runner_setback} leaves a {dims.runner_len} mm runner, too"
            f" short for two tabs in {shortest} mm"
        )
        raise ValueError(msg)


def _labels_fit(spec: Spec) -> None:
    """Nothing, when the engraved labels can each name a drawer front.

    Raises:
        ValueError: naming ``labels`` when there is not one distinct path segment per drawer.
    """
    if not spec.labels:
        return
    if len(spec.labels) != spec.drawers:
        msg = f"labels has {len(spec.labels)} entries for {spec.drawers} drawers"
        raise ValueError(msg)
    if len(set(spec.labels)) != len(spec.labels):
        msg = "labels repeat, so two drawer fronts would answer to one ref"
        raise ValueError(msg)
    for text in spec.labels:
        if not text or SEP in text:
            msg = f"labels entry {text!r} is not one path segment"
            raise ValueError(msg)


# ---- the cabinet ---------------------------------------------------------------------


def cabinet(spec: Spec) -> Build:
    """The cabinet ``spec`` describes: every distinct panel as a part, how many of each,
    and the baseplate to print.

    Drawers are open boxes. The carcass is the same open box turned on its back - so its
    open top is the open front - which is why its width is the cabinet's height: the box's
    front and back stand up as the cabinet's two sides, its sides lie down as the top and
    bottom, and its bottom closes the back.
    """
    validate(spec)
    dims = derive(spec)
    drawer_stock = Stock(spec.drawer_t, _MATERIAL, spec.kerf)
    carcass_stock = Stock(spec.carcass_t, _MATERIAL, spec.kerf)
    entries = (
        *_drawer_parts(spec, dims, drawer_stock),
        *_carcass_parts(spec, dims, carcass_stock),
    )
    root = assembly(Label("cabinet"), tuple(Placed(p, XY) for p, _ in entries))
    scad = baseplate_scad(spec.units_x, spec.units_y) if spec.baseplate else ""
    files = {"baseplate.scad": scad} if scad else {}
    return Build(root, frozendict({Ref(p.label): n for p, n in entries}), frozendict(files))


def _drawer_parts(spec: Spec, dims: Dims, stock: Stock) -> tuple[tuple[Part, int], ...]:
    """One part per distinct drawer panel. Every front is its own part because its label
    is engraved on it; the backs, sides and bottoms are all the same panel counted up."""
    box = open_box(
        w=dims.drawer_w, d=dims.drawer_d, h=dims.drawer_h, t=spec.drawer_t, finger=spec.finger
    )
    each = spec.drawers * spec.columns
    fronts = tuple(
        (_front_part(spec, dims, box.front, stock, text), spec.columns) for text in _labels(spec)
    )
    return (
        *fronts,
        (part(Label("drawer-back"), _plain(box.back), stock, Process.LASER), each),
        (part(Label("drawer-side"), _plain(box.side_left), stock, Process.LASER), 2 * each),
        (part(Label("drawer-bottom"), _plain(box.bottom), stock, Process.LASER), each),
    )


def _front_part(spec: Spec, dims: Dims, blank: Face, stock: Stock, text: str) -> Part:
    """One drawer front: the box's front panel with a stadium pull cut below its top edge
    and the drawer's label engraved between the pull and the bottom joint."""
    pull_y = dims.drawer_h - spec.pull_margin - spec.pull_h
    pull = slot(spec.pull_w, spec.pull_h, Point((dims.drawer_w - spec.pull_w) / 2, pull_y))
    face = cut(_plain(blank), pull, label=Label("pull"))
    width = text_width(text, spec.label_size)
    baseline = (spec.drawer_t + pull_y - spec.label_size) / 2
    engraving = Text(
        text, Point((dims.drawer_w - width) / 2, baseline), spec.label_size, Label("label")
    )
    return part(Label(f"drawer-front-{text}"), face, stock, Process.LASER, engravings=(engraving,))


def _carcass_parts(spec: Spec, dims: Dims, stock: Stock) -> tuple[tuple[Part, int], ...]:
    """One part per distinct carcass panel, plus the runners the drawers ride on."""
    # The carcass is a box lying on its back, so the box's width runs up the cabinet: see
    # :func:`cabinet`. Its front stands up as a side, its left side lies down as a shelf,
    # and its bottom closes the back - the twins of those two are the same cut again.
    box = open_box(w=dims.cab_h, d=dims.cab_w, h=dims.cab_d, t=spec.carcass_t, finger=spec.finger)
    wall, shelf, rear = box.front, box.side_left, box.bottom
    return (
        (
            part(
                Label("cabinet-side-left"),
                _slotted(spec, dims, wall, mirrored=False),
                stock,
                Process.LASER,
            ),
            spec.columns,
        ),
        (
            part(
                Label("cabinet-side-right"),
                _slotted(spec, dims, wall, mirrored=True),
                stock,
                Process.LASER,
            ),
            spec.columns,
        ),
        (part(Label("cabinet-top-bottom"), _plain(shelf), stock, Process.LASER), 2 * spec.columns),
        (part(Label("cabinet-back"), _plain(rear), stock, Process.LASER), spec.columns),
        (
            part(Label("runner"), _runner(spec, dims), stock, Process.LASER),
            2 * spec.drawers * spec.columns,
        ),
    )


def _slotted(spec: Spec, dims: Dims, blank: Face, *, mirrored: bool) -> Face:
    """A cabinet side with a through-slot for every runner tab.

    The panel's own x runs up the cabinet, so runner ``i`` is slotted at
    ``carcass_t + i * pitch`` from the bottom; its own y runs from the back of the
    cabinet to the open front, so a slot sits where the runner's tab does. ``mirrored``
    flips every slot across the panel's middle, which is the right-hand side: the same
    physical panel, turned over.
    """
    tabs = _runner_tabs(dims.runner_len)
    face = _plain(blank)
    for i in range(spec.drawers):
        along = spec.carcass_t + i * dims.pitch
        x = dims.cab_h - along - spec.carcass_t if mirrored else along
        for j, tab in enumerate(tabs):
            opening = rect(spec.carcass_t, tab.length, Point(x, spec.carcass_t + tab.start))
            face = cut(face, opening, label=_slot_label(i, j))
    return face


def _slot_label(runner: int, opening: int) -> Label:
    """``slot-2``, then ``slot-2-1``, ``slot-2-2`` for the rest of that runner's
    openings - the way a jagged edge names the rest of its run."""
    base = f"slot-{runner}"
    return Label(base if opening == 0 else f"{base}-{opening}")


def _runner_tabs(length: float) -> tuple[Interval, ...]:
    """Where a runner grows tabs along its length: one in from each end, and a third in
    the middle once the runner is long enough to sag without it."""
    first = Interval(_TAB_INSET, _TAB_INSET + _TAB)
    last = Interval(length - _TAB_INSET - _TAB, length - _TAB_INSET)
    if length <= 2 * _TAB_INSET + 3 * _TAB + _TAB_ROOM:
        return (first, last)
    middle = Interval(length / 2 - _TAB / 2, length / 2 + _TAB / 2)
    return (first, middle, last)


def _runner(spec: Spec, dims: Dims) -> Face:
    """A runner: a strip the drawer slides on, with tabs down one long edge that pass
    through the cabinet side. Its x runs from the back of the cabinet forward, so its
    tabs are at the same distances as the slots that take them."""
    length, reach = dims.runner_len, spec.runner_reach
    flat = flat_intervals()
    at = (Point(0.0, 0.0), Point(length, 0.0), Point(length, reach), Point(0.0, reach))
    edges = (
        *jagged_edge(at[0], at[1], _runner_tabs(length), -spec.carcass_t, Label("bottom")),
        *jagged_edge(at[1], at[2], flat, 0.0, Label("right")),
        *jagged_edge(at[2], at[3], flat, 0.0, Label("top")),
        *jagged_edge(at[3], at[0], flat, 0.0, Label("left")),
    )
    return fill(wire(edges))


def _plain(f: Face) -> Face:
    """``f`` with its label dropped. A part carries the name, so its face is transparent
    and the holes cut in it hang straight off the part's own ref."""
    return replace(f, label=None)


# ---- the printed baseplate -----------------------------------------------------------


class _Slice(NamedTuple):
    """One level of a baseplate pocket: a rounded square of ``size`` across with corners
    of ``radius``, ``z`` above the plate's underside."""

    size: float
    radius: float
    z: float


_POCKET = (
    _Slice(36.3, 1.15, 0.0),
    _Slice(37.7, 1.85, 0.7),
    _Slice(37.7, 1.85, 2.5),
    _Slice(GRID, _CORNER_R, BASEPLATE_T),
)


def baseplate_scad(units_x: int, units_y: int, floor_t: float = 0.0) -> str:
    """OpenSCAD source for a Gridfinity light baseplate ``units_x`` by ``units_y``.

    Each pocket is the hull of four rounded squares, so its wall reads bottom to top as a
    0.7 mm chamfer, 1.8 mm upright and a 2.15 mm chamfer - 4.65 mm in all. With a
    ``floor_t`` of zero the plate is open-bottomed, which is what a drawer with a wooden
    bottom wants; a positive ``floor_t`` adds that much solid material beneath the pockets.

    Raises:
        ValueError: if either unit count is below one, or ``floor_t`` is negative.
    """
    if units_x < 1 or units_y < 1:
        msg = f"a baseplate needs at least one unit each way, not {units_x} by {units_y}"
        raise ValueError(msg)
    if floor_t < 0:
        msg = f"floor_t cannot be negative, not {floor_t}"
        raise ValueError(msg)
    hull = "\n".join(
        f"        _slice({_num(s.size)}, {_num(s.radius)}, {_num(s.z)});" for s in _POCKET
    )
    return f"""\
// Gridfinity light baseplate, {units_x} x {units_y} units of {_num(GRID)} mm.
// Generated by bench. Millimetres throughout.
$fn = 64;

grid = {_num(GRID)};
units_x = {units_x};
units_y = {units_y};
height = {_num(BASEPLATE_T)};
floor_t = {_num(floor_t)};
corner_r = {_num(_CORNER_R)};
eps = 0.01;

module _slice(size, r, z) {{
    translate([0, 0, z - eps / 2])
        linear_extrude(eps)
            offset(r = r)
                square(size - 2 * r, center = true);
}}

module pocket() {{
    hull() {{
{hull}
    }}
}}

module baseplate() {{
    difference() {{
        translate([0, 0, -floor_t])
            linear_extrude(height + floor_t)
                offset(r = corner_r)
                    square([grid * units_x - 2 * corner_r, grid * units_y - 2 * corner_r],
                           center = true);
        for (ix = [0 : units_x - 1])
            for (iy = [0 : units_y - 1])
                translate([(ix + 0.5 - units_x / 2) * grid,
                           (iy + 0.5 - units_y / 2) * grid, 0])
                    pocket();
    }}
}}

baseplate();
"""


def _num(value: float) -> str:
    """A millimetre written for OpenSCAD, as short as it goes."""
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text or "0"
