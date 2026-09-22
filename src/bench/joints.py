"""Joints: finger-joint edge profiles for boxes cut from sheet stock.

An edge joint is a *partition*: an odd number of equal segments along a parent
length. Even-indexed segments are material on the female panel, odd-indexed ones are
where the male panel's tabs land. An odd count means a partition starts and ends with
material, so the corner block of every box edge belongs to exactly one panel, and a
tab never reaches a panel corner - :func:`male_intervals` refuses to make one that
would.

A female edge has notches of depth ``t`` cut into its nominal rectangle; a male edge
has tabs of depth ``t`` grown out of it. The male panel is usually inset - a box
bottom sits between the walls - so its tabs are the parent's odd segments shifted
into the panel's own coordinates by an ``offset``.
"""

from dataclasses import dataclass
from itertools import pairwise
from typing import NamedTuple

from .geometry import TOL, XY, Point, distance, perpendicular
from .topology import Edge, Face, Label, Line, face, wire
from .topology import label as _label


class Interval(NamedTuple):
    """A stretch of one edge, measured from its start."""

    start: float
    end: float

    @property
    def length(self) -> float:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class Partition:
    """``count`` equal segments along ``length``; ``count`` is odd and at least three."""

    length: float
    count: int

    @property
    def step(self) -> float:
        return self.length / self.count


def partition(length: float, target: float, min_finger: float) -> Partition:
    """An odd partition of ``length`` into segments as close to ``target`` as it can
    get without any of them falling below ``min_finger``.

    Raises:
        ValueError: if any argument is not positive, or ``length`` cannot hold three
            segments of ``min_finger``.
    """
    if length <= 0 or target <= 0 or min_finger <= 0:
        msg = "a partition needs a positive length, target and minimum finger"
        raise ValueError(msg)
    if length < 3 * min_finger - TOL:
        msg = f"an edge of {length} is too short for three fingers of {min_finger}"
        raise ValueError(msg)
    count = max(3, round(length / target))
    if count % 2 == 0:
        below, above = max(3, count - 1), count + 1
        count = below if abs(length / below - target) <= abs(length / above - target) else above
    while count > 3 and length / count < min_finger:
        count -= 2
    return Partition(length, count)


def female_intervals(p: Partition) -> tuple[Interval, ...]:
    """Where the female panel is notched: the odd segments of the partition."""
    return tuple(Interval(i * p.step, (i + 1) * p.step) for i in range(1, p.count, 2))


def male_intervals(p: Partition, offset: float, own_length: float) -> tuple[Interval, ...]:
    """Where the male panel grows tabs, in its own coordinates: the parent's odd
    segments shifted back by ``offset``.

    Raises:
        ValueError: if ``own_length`` is not positive, or a tab would touch either end
            of the panel's edge, which would hand a corner to two panels at once.
    """
    if own_length <= 0:
        msg = "a male edge needs a positive length"
        raise ValueError(msg)
    out: list[Interval] = []
    for a, b in female_intervals(p):
        tab = Interval(a - offset, b - offset)
        if tab.start < TOL or tab.end > own_length - TOL:
            msg = f"a tab at {tab} reaches the corner of an edge {own_length} long"
            raise ValueError(msg)
        out.append(tab)
    return tuple(out)


def flat_intervals() -> tuple[Interval, ...]:
    """No intervals at all: the edge stays straight. Lets a panel with a plain edge go
    through :func:`jagged_edge` like every other one."""
    return ()


def jagged_edge(
    start: Point,
    end: Point,
    intervals: tuple[Interval, ...],
    depth: float,
    label: str | Label | None = None,
) -> tuple[Edge, ...]:
    """The edges of one logical side of a panel: the straight run from ``start`` to
    ``end``, stepping ``depth`` off the line over each of ``intervals``.

    ``depth`` is measured to the left of travel, so on a counter-clockwise outline a
    female notch is positive and a male tab negative. The first edge carries ``label``
    and the rest carry ``label-1``, ``label-2`` ... so every edge of the finished wire
    still has a ref of its own.

    Raises:
        ValueError: if ``start`` and ``end`` coincide, or the intervals are not
            ordered, disjoint and inside the edge.
    """
    named = None if label is None else _label(label)
    span = end - start
    length = abs(span)
    if length < TOL:
        msg = "an edge needs two distinct ends"
        raise ValueError(msg)
    along = span / length
    sideways = perpendicular(along) * depth
    done = 0.0
    for a, b in intervals:
        if a < -TOL or b > length + TOL or b - a < TOL or a < done - TOL:
            msg = f"interval ({a}, {b}) is not inside an edge {length} long, after {done}"
            raise ValueError(msg)
        done = b
    corners = [start]
    for a, b in intervals:
        at_a, at_b = start + along * a, start + along * b
        corners += [at_a, at_a + sideways, at_b + sideways, at_b]
    corners.append(end)
    out: list[Edge] = []
    for p, q in pairwise(corners):
        if distance(p, q) > TOL:
            out.append(Edge(Line(p, q), _step_label(named, len(out))))
    return tuple(out)


class Box(NamedTuple):
    """The five panels of an open-topped box, each one a labelled :class:`~bench.topology.Face`.

    The fields are the panels a maker names: ``front`` and ``back`` are the same cut twice,
    and so are ``side_left`` and ``side_right``. The faces' labels keep the hyphen a ref
    wants (``side-left``).
    """

    front: Face
    back: Face
    side_left: Face
    side_right: Face
    bottom: Face


def open_box(*, w: float, d: float, h: float, t: float, finger: float) -> Box:
    """The five panels of an open-topped box ``w`` by ``d`` by ``h`` outside, cut from
    stock ``t`` thick and joined with fingers about ``finger`` long.

    The dimensions are keyword-only: a box has three of them and nothing about the order
    they are written in says which is which.

    Front and back span the full width and are female everywhere; the sides sit
    between them and the bottom sits inside all four walls, so both are male. Each
    panel's outline runs counter-clockwise from its lower left with edges labelled
    ``bottom``, ``right``, ``top`` and ``left`` - plus ``bottom-1``, ``bottom-2`` ...
    for the rest of a jagged run.

    Raises:
        ValueError: if a dimension is not positive, or the walls leave no room for a
            panel between them.
    """
    if min(w, d, h, t, finger) <= 0:
        msg = "a box needs positive dimensions"
        raise ValueError(msg)
    if w <= 2 * t or d <= 2 * t:
        msg = f"walls {t} thick leave nothing between them in a box {w} by {d}"
        raise ValueError(msg)
    across = partition(w, finger, 2 * t)
    deep = partition(d - 2 * t, finger, 2 * t)
    up = partition(h, finger, 2 * t)
    notch_x = female_intervals(across)
    notch_y = female_intervals(deep)
    notch_z = female_intervals(up)
    tab_x = male_intervals(across, t, w - 2 * t)
    tab_y = male_intervals(deep, 0.0, d - 2 * t)
    tab_z = male_intervals(up, 0.0, h)
    flat = _Side(flat_intervals(), 0.0)
    wall = (_Side(notch_x, t), _Side(notch_z, t), flat, _Side(notch_z, t))
    side = (_Side(notch_y, t), _Side(tab_z, -t), flat, _Side(tab_z, -t))
    base = (_Side(tab_x, -t), _Side(tab_y, -t), _Side(tab_x, -t), _Side(tab_y, -t))
    return Box(
        front=_panel(Label("front"), w, h, wall),
        back=_panel(Label("back"), w, h, wall),
        side_left=_panel(Label("side-left"), d - 2 * t, h, side),
        side_right=_panel(Label("side-right"), d - 2 * t, h, side),
        bottom=_panel(Label("bottom"), w - 2 * t, d - 2 * t, base),
    )


class _Side(NamedTuple):
    """One logical edge of a panel: where it steps off the line, and how far."""

    intervals: tuple[Interval, ...]
    depth: float


_SIDE_NAMES = (Label("bottom"), Label("right"), Label("top"), Label("left"))


def _panel(
    label: Label, width: float, height: float, sides: tuple[_Side, _Side, _Side, _Side]
) -> Face:
    """A panel in the XY plane with its lower left at the origin, walked
    counter-clockwise from there."""
    corners = (
        Point(0.0, 0.0),
        Point(width, 0.0),
        Point(width, height),
        Point(0.0, height),
        Point(0.0, 0.0),
    )
    edges = tuple(
        e
        for (a, b), side, name in zip(pairwise(corners), sides, _SIDE_NAMES, strict=True)
        for e in jagged_edge(a, b, side.intervals, side.depth, name)
    )
    return face(wire(edges), on=XY, label=label)


def _step_label(label: Label | None, index: int) -> Label | None:
    if label is None:
        return None
    return label if index == 0 else Label(f"{label}-{index}")
