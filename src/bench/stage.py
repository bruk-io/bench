"""Stage: where a scene's bodies stand in the 3D view, and the floor drawn under them.

A part's body is built in the part's own coordinates, so left where they were made the bodies
of an assembly would pile up on the origin. The stage lays them out the way a maker lays parts
on a bench: in rows along X in the order the script showed them, :data:`GAP` apart, front edges
on the row's line and standing on ``z = 0``, a row wrapping before it runs too long. It then
hands back the box they fill.

That is :func:`layout`, and it is the right thing to do to a scene of unrelated bodies and
the wrong thing to do to a mechanism: an assembly whose parts the script has already posed
relative to each other is placed by :func:`as_given` instead, which moves nothing. Neither
draws a floor: an assembly has no bed.

A printer's bed is the other place a body stands. :func:`on_bed` puts each printed part,
already laid down the way it prints, side by side on the plate of a :class:`~bench.model.Volume`
with its corner at the origin - and on the next plate along when that one is full - and
:func:`floor` and :func:`edges` are each plate's grid and build volume, drawn there and nowhere
else.

Plain arithmetic on meshes, done here rather than in the viewer, so that what a scene carries
is ready to draw: every triangle's corners already placed and already its own, and every
triangle's name already an index into a short table.
"""

import math
from collections.abc import Sequence
from typing import NamedTuple

from .kernel import Mesh
from .model import Ref, Volume
from .topology import SEP

GAP = 10.0
"""Millimetres between two bodies, across a row and between rows."""

_ROW_WRAP = 600.0
"""Millimetres: a row wraps once the next body would take it past this."""

_FLOOR_STEP = 10.0
"""The bed grid's cells, in millimetres."""

_PLATE_GAP = 40.0
"""Millimetres between one plate and the next, when the parts take more than one."""

Offset = tuple[float, float, float]


class Box(NamedTuple):
    """An axis-aligned box: ``x0, y0, z0`` its low corner and ``x1, y1, z1`` its high one."""

    x0: float
    y0: float
    z0: float
    x1: float
    y1: float
    z1: float


EMPTY = Box(-50.0, -50.0, 0.0, 50.0, 50.0, 50.0)
"""The stage of a scene with no body on it: a small room to look into rather than nothing."""


def extent(mesh: Mesh) -> Box | None:
    """The box every corner of every triangle of ``mesh`` lies in, or ``None`` for a mesh with
    no triangles."""
    if not mesh.triangles:
        return None
    vertices = mesh.vertices
    xs = [vertices[3 * one] for one in mesh.triangles]
    ys = [vertices[3 * one + 1] for one in mesh.triangles]
    zs = [vertices[3 * one + 2] for one in mesh.triangles]
    return Box(min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def layout(bodies: Sequence[Mesh | None]) -> tuple[tuple[Offset | None, ...], Box]:
    """Where each body goes - the offset that moves it onto the stage, or ``None`` for a part
    with nothing to stand there - and the box everything on the stage fills.

    Bodies go left to right with their front edges on the row's line. A row wraps once the
    next body would take it past :data:`_ROW_WRAP`, and the next row starts :data:`GAP`
    behind the deepest body of the one before. A part with no body, or a body with no
    triangles, takes no place, so nothing leaves a gap where it would have been.
    """
    offsets: list[Offset | None] = []
    placed: list[Box] = []
    across = 0.0
    front = 0.0
    deepest = 0.0
    for body in bodies:
        own = None if body is None else extent(body)
        if own is None:
            offsets.append(None)
            continue
        width = own.x1 - own.x0
        if across > 0.0 and across + width > _ROW_WRAP:
            front += deepest + GAP
            across = 0.0
            deepest = 0.0
        offset = (across - own.x0, front - own.y0, -own.z0)
        offsets.append(offset)
        placed.append(
            Box(
                own.x0 + offset[0],
                own.y0 + offset[1],
                own.z0 + offset[2],
                own.x1 + offset[0],
                own.y1 + offset[1],
                own.z1 + offset[2],
            )
        )
        across += width + GAP
        deepest = max(deepest, own.y1 - own.y0)
    if not placed:
        return tuple(offsets), EMPTY
    return tuple(offsets), Box(
        min(one.x0 for one in placed),
        min(one.y0 for one in placed),
        min(one.z0 for one in placed),
        max(one.x1 for one in placed),
        max(one.y1 for one in placed),
        max(one.z1 for one in placed),
    )


def as_given(bodies: Sequence[Mesh | None]) -> tuple[tuple[Offset | None, ...], Box]:
    """Where each body goes when nobody is to move it: nowhere, and the box they already
    fill between them.

    :func:`layout`'s answer for a posed assembly - one whose parts the script has already
    placed relative to each other. Every offset is zero, so a body is drawn at its own
    coordinates, and the stage is the union of what those coordinates come to rather than
    the rows a packing would have made. A part with no body still takes no place, exactly as
    in :func:`layout`, and a stage with nothing on it is :data:`EMPTY` the same way.

    Nothing is grounded and nothing is centred: a mechanism modelled about its own axis
    straddles ``z = 0`` rather than standing on it, which is what "as given" means. Moving it
    onto the floor would be a layout by another name, and would put the parts somewhere their
    own numbers - and the clearances measured between them - do not describe.
    """
    offsets: list[Offset | None] = []
    placed: list[Box] = []
    for body in bodies:
        own = None if body is None else extent(body)
        if own is None:
            offsets.append(None)
            continue
        offsets.append((0.0, 0.0, 0.0))
        placed.append(own)
    if not placed:
        return tuple(offsets), EMPTY
    return tuple(offsets), Box(
        min(one.x0 for one in placed),
        min(one.y0 for one in placed),
        min(one.z0 for one in placed),
        max(one.x1 for one in placed),
        max(one.y1 for one in placed),
        max(one.z1 for one in placed),
    )


def widened(box: Box | None, meshes: Sequence[Mesh]) -> Box:
    """``box`` grown to hold every one of ``meshes`` where it already stands - a body shown for
    context, which nothing lays out - or :data:`EMPTY` when neither holds anything.

    ``None`` is a stage no part stands on, rather than :data:`EMPTY`'s small room, so a scene
    of context alone is framed round the context and not round a box nobody drew.
    """
    boxes = [one for one in (extent(mesh) for mesh in meshes) if one is not None]
    if box is not None:
        boxes.append(box)
    if not boxes:
        return EMPTY
    return Box(
        min(one.x0 for one in boxes),
        min(one.y0 for one in boxes),
        min(one.z0 for one in boxes),
        max(one.x1 for one in boxes),
        max(one.y1 for one in boxes),
        max(one.z1 for one in boxes),
    )


class Plated(NamedTuple):
    """Printed parts laid on a printer's plates: where each one goes, the ``x`` of each plate's
    corner, and the box every plate and everything on them fill."""

    offsets: tuple[Offset | None, ...]
    plates: tuple[float, ...]
    box: Box


def on_bed(bodies: Sequence[Box | None], volume: Volume) -> Plated:
    """Where each body goes on the plates of a printer building in ``volume`` - the offset that
    moves it there, or ``None`` for a part with nothing to lay - the plates it took, and the box
    they fill.

    ``bodies`` are the boxes the parts fill already laid down the way they print - lowest
    point on ``z = 0`` - so only X and Y are decided here. The first plate's corner is the
    origin and it runs to ``volume.w`` along X and ``volume.d`` along Y. Parts go left to right
    :data:`GAP` in from its edges and apart, a row wrapping before the next part would cross
    the plate's far side, the next row :data:`GAP` behind the deepest of the one before - and
    a row that would run off the back of a plate that already holds something starts the next
    plate instead, :data:`_PLATE_GAP` to the right, the way a slicer's second plate would be
    printed after the first. A part wider or deeper than a plate is laid on one of its own all
    the same and runs off it - the box, and the next plate along, make room for it - because
    what does not fit is what the view is there to show, and :func:`bench.checks.fits` is what
    says so.
    """
    offsets: list[Offset | None] = []
    plates: list[float] = [0.0]
    placed: list[Box] = []
    across = front = GAP
    deepest = reach = 0.0
    held = False
    for own in bodies:
        if own is None:
            offsets.append(None)
            continue
        width, depth = own.x1 - own.x0, own.y1 - own.y0
        if across > GAP and across + width > volume.w - GAP:
            front += deepest + GAP
            across = GAP
            deepest = 0.0
        if held and front + depth > volume.d - GAP:
            plates.append(max(plates[-1] + volume.w, reach) + _PLATE_GAP)
            across = front = GAP
            deepest = 0.0
            held = False
        offset = (plates[-1] + across - own.x0, front - own.y0, -own.z0)
        offsets.append(offset)
        laid = Box(
            own.x0 + offset[0],
            own.y0 + offset[1],
            own.z0 + offset[2],
            own.x1 + offset[0],
            own.y1 + offset[1],
            own.z1 + offset[2],
        )
        placed.append(laid)
        reach = max(reach, laid.x1)
        across += width + GAP
        deepest = max(deepest, depth)
        held = True
    placed.extend(Box(x, 0.0, 0.0, x + volume.w, volume.d, volume.h) for x in plates)
    return Plated(
        tuple(offsets),
        tuple(plates),
        Box(
            min(one.x0 for one in placed),
            min(one.y0 for one in placed),
            min(one.z0 for one in placed),
            max(one.x1 for one in placed),
            max(one.y1 for one in placed),
            max(one.z1 for one in placed),
        ),
    )


def floor(volume: Volume, plates: Sequence[float] = (0.0,)) -> list[float]:
    """The grid on each plate of a printer building in ``volume``, its corner at each ``x`` of
    ``plates``, as line segments on ``z = 0``: six numbers each, both ends. A line every
    :data:`_FLOOR_STEP` across and along from a plate's corner, and one on each far edge,
    where the plate stops whether or not a whole cell does."""
    out: list[float] = []
    for x in plates:
        for at in _steps(volume.w):
            out.extend((x + at, 0.0, 0.0, x + at, volume.d, 0.0))
        for at in _steps(volume.d):
            out.extend((x, at, 0.0, x + volume.w, at, 0.0))
    return out


def edges(volume: Volume, plates: Sequence[float] = (0.0,)) -> list[float]:
    """The twelve edges of the build volume over each plate of ``plates``, as line segments:
    six numbers each, both ends."""
    w, d, h = volume
    out: list[float] = []
    for x in plates:
        corners = ((x, 0.0), (x + w, 0.0), (x + w, d), (x, d))
        for (x0, y0), (x1, y1) in zip(corners, corners[1:] + corners[:1], strict=True):
            out.extend((x0, y0, 0.0, x1, y1, 0.0))
            out.extend((x0, y0, h, x1, y1, h))
        for cx, cy in corners:
            out.extend((cx, cy, 0.0, cx, cy, h))
    return out


def _steps(length: float) -> list[float]:
    """``0``, every :data:`_FLOOR_STEP` short of ``length``, and ``length`` itself."""
    count = math.ceil(length / _FLOOR_STEP - 1e-9)
    return [min(k * _FLOOR_STEP, length) for k in range(count)] + [length]


def positions(mesh: Mesh, offset: Offset) -> list[float]:
    """``mesh``'s triangles one at a time, each corner moved by ``offset``: nine numbers per
    triangle, so a triangle's number is its position in the list divided by nine."""
    dx, dy, dz = offset
    vertices = mesh.vertices
    out: list[float] = []
    extend = out.extend
    for one in mesh.triangles:
        extend((vertices[3 * one] + dx, vertices[3 * one + 1] + dy, vertices[3 * one + 2] + dz))
    return out


def shifted(points: Sequence[float], offset: Offset) -> list[float]:
    """Points written ``x, y, z, x, y, z, …``, each moved by ``offset`` - an engraving's
    segments or a line of lettering's corners, put where the stage put the plate under them."""
    dx, dy, dz = offset
    moves = (dx, dy, dz)
    return [value + moves[k % 3] for k, value in enumerate(points)]


def ref_table(refs: Sequence[Ref | None], prefix: str) -> tuple[list[str], list[int]]:
    """Every name in ``refs`` once each and under ``prefix``, and each entry's place in that
    table counted from one - ``0`` for an entry that names nothing.

    A mesh names a handful of faces over hundreds of triangles, so a table and an index say
    in a few numbers what a name per triangle says in thousands of characters; an engraving's
    segments are counted the same way.
    """
    table: list[str] = []
    places: dict[str, int] = {}
    index: list[int] = []
    for ref in refs:
        if ref is None:
            index.append(0)
            continue
        name = f"{prefix}{SEP}{ref}"
        place = places.get(name)
        if place is None:
            table.append(name)
            place = places[name] = len(table)
        index.append(place)
    return table, index
