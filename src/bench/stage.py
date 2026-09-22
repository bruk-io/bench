"""Stage: where a scene's bodies stand in the 3D view, and the floor drawn under them.

A part's body is built in the part's own coordinates, so left where they were made the bodies
of an assembly would pile up on the origin. The stage lays them out the way a maker lays parts
on a bench: in rows along X in the order the script showed them, :data:`GAP` apart, front edges
on the row's line and standing on ``z = 0``, a row wrapping before it runs too long. It then
sizes the grid drawn under them.

That is :func:`layout`, and it is the right thing to do to a scene of unrelated bodies and
the wrong thing to do to a mechanism: an assembly whose parts the script has already posed
relative to each other is placed by :func:`as_given` instead, which moves nothing.

Plain arithmetic on meshes, done here rather than in the viewer, so that what a scene carries
is ready to draw: every triangle's corners already placed and already its own, and every
triangle's name already an index into a short table.
"""

import math
from collections.abc import Sequence
from typing import NamedTuple

from .kernel import Mesh
from .model import Ref
from .topology import SEP

GAP = 10.0
"""Millimetres between two bodies, across a row and between rows."""

_ROW_WRAP = 600.0
"""Millimetres: a row wraps once the next body would take it past this."""

_GRID_STEP = 10.0
"""The grid's cells, in millimetres."""

_GRID_MARGIN = 1.25
"""How much wider than the work the grid runs."""

_GRID_LEAST = 10.0
"""The narrowest the work is taken to be, so a pin still stands on a floor."""

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


class Grid(NamedTuple):
    """The floor under the work: its width, how many cells across, and where its middle is."""

    size: float
    divisions: int
    centre_x: float
    centre_y: float


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


def grid(box: Box) -> Grid:
    """The floor under ``box``: a quarter wider than the work, in whole cells, centred under
    it."""
    span = max(box.x1 - box.x0, box.y1 - box.y0, _GRID_LEAST)
    size = math.ceil(span * _GRID_MARGIN / _GRID_STEP) * _GRID_STEP
    return Grid(
        size, max(2, round(size / _GRID_STEP)), (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2
    )


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
