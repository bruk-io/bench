"""Nest: kerf compensation and shelf packing onto sheets.

Every part is first grown by half its stock's kerf - outlines out, holes in, engravings
left where they are - and moved so its extent starts at the origin. The blanks are then
sorted tallest first and laid left to right in shelves: a row as tall as its first part,
then the next row above it. A part is turned a quarter turn when it will not fit upright -
too wide for what is left of the shelf, or too tall for what is left of the sheet - and
only when turning it will not make that shelf taller.

One sheet series per stock thickness, thinnest first, because a sheet is one thickness of
material. A part too big for the bed in either direction is reported as a warning and
never quietly dropped.

A nest is sheets, so a printed part is not one of its parts at all: it is passed over in
silence rather than warned about, because a body in a scene of bodies is not a mistake and
a warning is for something that went wrong. A part cut from *sheet* stock that is not a
planar face still is a mistake, and still says so.
"""

import math
from dataclasses import dataclass, replace
from typing import NamedTuple, assert_never

from .geometry import ORIGIN, TOL, Axis, Vector, Z, rotation, translation
from .model import Part, Printed, Stock, moved_part
from .ops import BBox, bbox, offset
from .topology import Face, Solid

PartSpec = Part | tuple[Part, int]


class Bed(NamedTuple):
    """The stock a nest lays parts on: a sheet ``w`` by ``h``, how far in from its edge
    everything stays (``margin``) and how far apart neighbours are kept (``gap``), in
    millimetres."""

    w: float
    h: float
    margin: float = 3.0
    gap: float = 3.0


@dataclass(frozen=True, slots=True)
class Placement:
    """One part on one sheet.

    ``part`` is the part as the script made it; ``placed`` is the same part
    kerf-compensated and translated into sheet coordinates, so it is what gets cut - hand
    it to :func:`bench.export.part_paths` or :func:`bench.export.part_texts`. ``at`` is
    that translation, applied after the blank's extent was moved to the origin and, when
    ``rotated``, turned a quarter turn counter-clockwise. ``box`` is the blank's extent
    where it now lies.
    """

    part: Part
    placed: Part
    at: Vector
    rotated: bool
    box: BBox


@dataclass(frozen=True, slots=True)
class Sheet:
    """One piece of stock ``w`` by ``h`` with everything nested on it."""

    thickness: float
    w: float
    h: float
    parts: tuple[Placement, ...]


def sheet_name(sheet: Sheet, index: int) -> str:
    """``sheet-3mm-01``: the stock thickness and the sheet's place in its series.

    ``index`` counts from zero, as a sheet's position in its thickness series does; the
    name counts from one, as a person does.
    """
    return f"sheet-{_mm(sheet.thickness)}mm-{index + 1:02d}"


def nest(parts: tuple[PartSpec, ...], bed: Bed) -> tuple[tuple[Sheet, ...], tuple[str, ...]]:
    """``parts`` nested onto sheets of ``bed``, and what went wrong.

    A part on its own counts as one; pair it with a number for more. Every placement
    stays ``bed.margin`` in from the sheet's edge and ``bed.gap`` clear of its neighbours,
    and sheets come back grouped by stock thickness, thinnest series first.
    """
    warnings: list[str] = []
    blanks: list[_Blank] = []
    for spec in parts:
        part, quantity = _quantity(spec)
        sheet = _sheet_stock(part)
        if sheet is None:
            continue
        shape = _planar(part)
        if shape is None:
            warnings.append(f"part {part.label!r} is not a planar face, so it cannot be nested")
            continue
        blanks += [_blank(part, shape, sheet)] * quantity

    room_w, room_h = bed.w - 2 * bed.margin, bed.h - 2 * bed.margin
    fitting: list[_Blank] = []
    for b in blanks:
        if _fits(b.w, b.h, room_w, room_h) or _fits(b.h, b.w, room_w, room_h):
            fitting.append(b)
        else:
            warnings.append(
                f"part {b.part.label!r} is {_mm(b.w)} by {_mm(b.h)} mm with kerf and does not"
                f" fit a {_mm(bed.w)} by {_mm(bed.h)} mm sheet inside a"
                f" {_mm(bed.margin)} mm margin"
            )

    series: dict[float, list[_Blank]] = {}
    for b in fitting:
        series.setdefault(b.thickness, []).append(b)
    sheets: list[Sheet] = []
    for thickness in sorted(series):
        tallest_first = sorted(series[thickness], key=lambda b: (-b.h, -b.w, str(b.part.label)))
        packed, unplaced = _pack(thickness, tuple(tallest_first), bed)
        sheets += packed
        warnings += [
            f"part {b.part.label!r} is {_mm(b.w)} by {_mm(b.h)} mm with kerf and found no room"
            f" on a {_mm(bed.w)} by {_mm(bed.h)} mm sheet"
            for b in unplaced
        ]
    return tuple(sheets), tuple(warnings)


# ---- blanks ---------------------------------------------------------------------------


class _Blank(NamedTuple):
    """A part ready to place: ``ready`` is kerf-compensated with its extent at the
    origin, so ``w`` and ``h`` are exactly its box there. ``thickness`` is the sheet's,
    which is what groups the series."""

    part: Part
    ready: Part
    w: float
    h: float
    thickness: float


def _blank(part: Part, shape: Face, stock: Stock) -> _Blank:
    kerfed = offset(shape, stock.kerf / 2)
    box = bbox(kerfed)
    at_origin = moved_part(replace(part, shape=kerfed), translation(Vector(-box.x0, -box.y0)))
    return _Blank(part, at_origin, box.w, box.h, stock.thickness)


def _turned(b: _Blank) -> _Blank:
    """``b`` a quarter turn counter-clockwise, its extent back at the origin."""
    spun = moved_part(b.ready, rotation(Axis(ORIGIN, Z), math.pi / 2))
    box = bbox(spun.shape)
    ready = moved_part(spun, translation(Vector(-box.x0, -box.y0)))
    return _Blank(b.part, ready, b.h, b.w, b.thickness)


def _sheet_stock(part: Part) -> Stock | None:
    """The sheet ``part`` is cut from, or ``None`` when it is printed.

    A nest is sheets: a printed part has no thickness to group by and no kerf to grow by,
    and there is no honest way to lay a filament on a laser bed. It is left out without a
    word - a body among bodies is not a mistake, and a plate layout is its own step that
    does not exist yet.
    """
    match part.stock:
        case Stock() as sheet:
            return sheet
        case Printed():
            return None
        case _:
            assert_never(part.stock)


def _planar(part: Part) -> Face | None:
    match part.shape:
        case Face() as shape:
            return shape
        case Solid():
            return None
        case _:
            assert_never(part.shape)


def _quantity(spec: PartSpec) -> tuple[Part, int]:
    match spec:
        case Part():
            return (spec, 1)
        case (part, count):
            return (part, count)
        case _:
            assert_never(spec)


# ---- packing --------------------------------------------------------------------------


class _Spot(NamedTuple):
    """Which way round a blank goes where it was offered."""

    blank: _Blank
    rotated: bool


def _pack(
    thickness: float, blanks: tuple[_Blank, ...], bed: Bed
) -> tuple[tuple[Sheet, ...], tuple[_Blank, ...]]:
    """Shelves filled left to right, bottom to top, on as many sheets as it takes, and
    whatever found no room at all.

    Every blank here already fits an empty sheet one way round or the other, so each one
    lands on the shelf it is offered, the next shelf up, or a new sheet - one pass, no part
    seen twice. A blank that still finds nowhere to go comes back in the second tuple for
    :func:`nest` to warn about; it is never quietly skipped.
    """
    right, top = bed.w - bed.margin, bed.h - bed.margin
    sheets: list[Sheet] = []
    placed: list[Placement] = []
    homeless: list[_Blank] = []
    x, shelf_y, shelf_h = bed.margin, bed.margin, 0.0
    for b in blanks:
        spot = _choose(b, x, shelf_y, shelf_h, right, top)
        if spot is None:
            above = shelf_y + shelf_h + bed.gap if shelf_h > TOL else shelf_y
            spot = _choose(b, bed.margin, above, 0.0, right, top)
            if spot is not None:
                x, shelf_y, shelf_h = bed.margin, above, 0.0
        if spot is None:
            if placed:
                sheets.append(Sheet(thickness, bed.w, bed.h, tuple(placed)))
                placed = []
            x, shelf_y, shelf_h = bed.margin, bed.margin, 0.0
            spot = _choose(b, x, shelf_y, shelf_h, right, top)
        if spot is None:
            homeless.append(b)
            continue
        placed.append(_placement(spot, Vector(x, shelf_y)))
        x += spot.blank.w + bed.gap
        shelf_h = max(shelf_h, spot.blank.h)
    if placed:
        sheets.append(Sheet(thickness, bed.w, bed.h, tuple(placed)))
    return tuple(sheets), tuple(homeless)


def _choose(
    b: _Blank, x: float, shelf_y: float, shelf_h: float, right: float, top: float
) -> _Spot | None:
    """How ``b`` sits with its lower left at ``x``, ``shelf_y``, or ``None`` if it does
    not belong on this shelf.

    Upright wins whenever it fits, across and up. A quarter turn is considered whenever
    upright fails either way - too wide for what is left of the shelf, or too tall for
    what is left of the sheet - and is only taken when it leaves the shelf no taller than
    it already is; an empty shelf has no height to grow.
    """
    if x + b.w <= right + TOL and shelf_y + b.h <= top + TOL:
        return _Spot(b, rotated=False)
    turned = _turned(b)
    if shelf_h > TOL and turned.h > shelf_h + TOL:
        return None
    if x + turned.w <= right + TOL and shelf_y + turned.h <= top + TOL:
        return _Spot(turned, rotated=True)
    return None


def _placement(spot: _Spot, at: Vector) -> Placement:
    b = spot.blank
    return Placement(
        part=b.part,
        placed=moved_part(b.ready, translation(at)),
        at=at,
        rotated=spot.rotated,
        box=BBox(at.x, at.y, at.x + b.w, at.y + b.h),
    )


def _fits(w: float, h: float, room_w: float, room_h: float) -> bool:
    return w <= room_w + TOL and h <= room_h + TOL


# ---- small helpers -------------------------------------------------------------------


def _mm(value: float) -> str:
    text = f"{value:.3f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text
