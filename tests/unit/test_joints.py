from collections.abc import Callable

import pytest

from bench import (
    Box,
    Face,
    Interval,
    Label,
    Line,
    Partition,
    Point,
    area,
    bbox,
    female_intervals,
    flat_intervals,
    is_ccw,
    is_closed,
    jagged_edge,
    male_intervals,
    open_box,
    partition,
)

pytestmark = pytest.mark.unit

W, D, H, T, FINGER = 120.0, 80.0, 60.0, 3.0, 12.0


# ---- partitions --------------------------------------------------------------------


def test_partition_is_odd_and_near_the_target() -> None:
    p = partition(120, 12, 6)
    assert p.count == 11 and p.count % 2 == 1
    assert p.step == pytest.approx(120 / 11)
    assert partition(60, 12, 6) == Partition(60, 5)
    assert partition(74, 12, 6).count == 7


def test_partition_never_goes_below_three_segments_or_the_minimum_finger() -> None:
    assert partition(10, 100, 3).count == 3
    long_fingers = partition(100, 3, 9)
    assert long_fingers.count == 11
    assert long_fingers.step >= 9


def test_partition_rejects_an_edge_too_short_to_joint() -> None:
    with pytest.raises(ValueError):
        partition(10, 5, 4)
    with pytest.raises(ValueError):
        partition(0, 5, 1)
    with pytest.raises(ValueError):
        partition(10, 5, 0)


def test_partition_needs_a_finger_length_to_aim_at() -> None:
    with pytest.raises(ValueError, match="positive length, target"):
        partition(100, 0, 5)
    with pytest.raises(ValueError, match="positive length, target"):
        partition(100, -12, 5)


def test_female_intervals_are_the_odd_segments() -> None:
    p = partition(30, 10, 3)
    assert female_intervals(p) == (Interval(10, 20),)
    assert female_intervals(Partition(50, 5)) == (Interval(10, 20), Interval(30, 40))
    assert female_intervals(p)[0].length == pytest.approx(p.step)


def test_male_intervals_shift_the_parent_segments_into_the_panel() -> None:
    p = Partition(50, 5)
    assert male_intervals(p, 0.0, 50) == (Interval(10, 20), Interval(30, 40))
    assert male_intervals(p, 3.0, 44) == (Interval(7, 17), Interval(27, 37))


def test_male_intervals_refuse_a_tab_at_a_corner() -> None:
    p = Partition(50, 5)
    with pytest.raises(ValueError):
        male_intervals(p, 10.0, 30)
    with pytest.raises(ValueError):
        male_intervals(p, -10.0, 50)
    with pytest.raises(ValueError):
        male_intervals(p, 0.0, 0)


def test_flat_intervals_leave_an_edge_alone() -> None:
    assert flat_intervals() == ()


# ---- jagged edges ------------------------------------------------------------------


def test_jagged_edge_steps_off_the_line_and_comes_back() -> None:
    run = jagged_edge(Point(0, 0), Point(30, 0), (Interval(10, 20),), 3.0, Label("bottom"))
    assert tuple(e.label for e in run) == (
        Label("bottom"),
        Label("bottom-1"),
        Label("bottom-2"),
        Label("bottom-3"),
        Label("bottom-4"),
    )
    corners = []
    for e in run:
        assert isinstance(e.curve, Line)
        corners.append((e.curve.start.x, e.curve.start.y))
    assert corners == [(0, 0), (10, 0), (10, 3), (20, 3), (20, 0)]
    last = run[-1].curve
    assert isinstance(last, Line)
    assert last.end == Point(30, 0)


def test_jagged_edge_with_no_intervals_is_one_straight_edge() -> None:
    run = jagged_edge(Point(0, 0), Point(10, 0), flat_intervals(), 3.0, Label("top"))
    assert len(run) == 1
    assert run[0].curve == Line(Point(0, 0), Point(10, 0))
    assert run[0].label == Label("top")
    assert jagged_edge(Point(0, 0), Point(10, 0), (), 3.0)[0].label is None


def test_jagged_edge_tabs_go_the_other_way_from_notches() -> None:
    notch = jagged_edge(Point(0, 0), Point(30, 0), (Interval(10, 20),), 3.0)
    tab = jagged_edge(Point(0, 0), Point(30, 0), (Interval(10, 20),), -3.0)
    ys = [e.curve.start.y for e in notch if isinstance(e.curve, Line)]
    zs = [e.curve.start.y for e in tab if isinstance(e.curve, Line)]
    assert max(ys) == 3 and min(ys) == 0
    assert min(zs) == -3 and max(zs) == 0


def test_jagged_edge_rejects_nonsense() -> None:
    with pytest.raises(ValueError):
        jagged_edge(Point(0, 0), Point(0, 0), (), 3.0)
    with pytest.raises(ValueError):
        jagged_edge(Point(0, 0), Point(10, 0), (Interval(5, 15),), 3.0)
    with pytest.raises(ValueError):
        jagged_edge(Point(0, 0), Point(10, 0), (Interval(-1, 2),), 3.0)
    with pytest.raises(ValueError):
        jagged_edge(Point(0, 0), Point(10, 0), (Interval(6, 8), Interval(2, 4)), 3.0)
    with pytest.raises(ValueError):
        jagged_edge(Point(0, 0), Point(10, 0), (Interval(2, 2),), 3.0)


# ---- the box -----------------------------------------------------------------------


def test_open_box_returns_five_labelled_closed_panels() -> None:
    panels = open_box(w=W, d=D, h=H, t=T, finger=FINGER)
    assert tuple(f.label for f in panels) == (
        Label("front"),
        Label("back"),
        Label("side-left"),
        Label("side-right"),
        Label("bottom"),
    )
    for f in panels:
        assert f.inner == ()
        assert is_closed(f.outer) and is_ccw(f.outer)
        assert len(f.outer.edges) > 4


def test_open_box_hands_back_a_box_whose_panels_have_names() -> None:
    """Five faces in a row with two pairs of twins is a thing to get wrong positionally;
    a :class:`Box` says which is which."""
    box = open_box(w=W, d=D, h=H, t=T, finger=FINGER)
    assert isinstance(box, Box)
    assert box.side_left.label == Label("side-left")
    assert box.side_right.label == Label("side-right")
    assert bbox(box.side_left) == bbox(box.side_right)
    assert bbox(box.front) == bbox(box.back)
    assert tuple(box) == (box.front, box.back, box.side_left, box.side_right, box.bottom)


def test_open_box_panels_are_the_size_the_box_needs() -> None:
    front, back, left, right, base = open_box(w=W, d=D, h=H, t=T, finger=FINGER)
    assert bbox(front) == pytest.approx((0, 0, W, H))
    assert bbox(back) == bbox(front)
    assert bbox(left) == pytest.approx((-T, 0, D - T, H))
    assert bbox(right) == bbox(left)
    assert bbox(base) == pytest.approx((-T, -T, W - T, D - T))
    assert area(front) < W * H
    assert area(base) > (W - 2 * T) * (D - 2 * T)


def test_open_box_edges_carry_side_names_and_refs_stay_unique() -> None:
    """Every side is present once each, which is what :func:`~bench.model.part` checks
    when it builds these edges into a real part - so this test needs no part of its own."""
    for f in open_box(w=W, d=D, h=H, t=T, finger=FINGER):
        labels = [e.label for e in f.outer.edges]
        assert labels[0] == Label("bottom")
        for side in ("bottom", "right", "top", "left"):
            assert Label(side) in labels
        assert len(set(labels)) == len(labels)


def test_open_box_rejects_a_box_its_walls_do_not_fit() -> None:
    with pytest.raises(ValueError):
        open_box(w=W, d=D, h=H, t=0, finger=FINGER)
    with pytest.raises(ValueError):
        open_box(w=W, d=-D, h=H, t=T, finger=FINGER)
    with pytest.raises(ValueError):
        open_box(w=5, d=D, h=H, t=T, finger=FINGER)
    with pytest.raises(ValueError):
        open_box(w=W, d=D, h=10, t=T, finger=FINGER)  # too short for three fingers of 2t


# ---- the corner-ownership property -------------------------------------------------


def _ring(f: Face) -> tuple[tuple[float, float], ...]:
    out: list[tuple[float, float]] = []
    for e in f.outer.edges:
        c = e.curve
        assert isinstance(c, Line)
        out.append((c.start.x, c.start.y))
    return tuple(out)


def _inside(ring: tuple[tuple[float, float], ...], x: float, y: float) -> bool:
    """Crossing count against a polygon; the panels are all straight edges."""
    crossings = 0
    for (x0, y0), (x1, y1) in zip(ring, (*ring[1:], ring[0]), strict=True):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            crossings += 1
    return crossings % 2 == 1


def _assembled(
    w: float, d: float, h: float, t: float, finger: float
) -> Callable[[float, float, float], int]:
    """The box put together: how many panels own the material at a world point.

    Each panel is a slab of thickness ``t`` where it stands in the assembly, and its
    cut outline decides what is inside that slab.
    """
    front, back, left, right, base = open_box(w=w, d=d, h=h, t=t, finger=finger)
    rings = {f.label: _ring(f) for f in (front, back, left, right, base)}

    def owners(x: float, y: float, z: float) -> int:
        found = 0
        if 0 <= y <= t and _inside(rings[Label("front")], x, z):
            found += 1
        if d - t <= y <= d and _inside(rings[Label("back")], x, z):
            found += 1
        if 0 <= x <= t and _inside(rings[Label("side-left")], y - t, z):
            found += 1
        if w - t <= x <= w and _inside(rings[Label("side-right")], y - t, z):
            found += 1
        if 0 <= z <= t and _inside(rings[Label("bottom")], x - t, y - t):
            found += 1
        return found

    return owners


def test_every_joint_strip_belongs_to_exactly_one_panel() -> None:
    owners = _assembled(W, D, H, T, FINGER)
    samples = 400
    strips: tuple[tuple[str, Callable[[float], tuple[float, float, float]], float, float], ...] = (
        ("front to side-left", lambda s: (T / 2, T / 2, s), 0.0, H),
        ("front to side-right", lambda s: (W - T / 2, T / 2, s), 0.0, H),
        ("back to side-left", lambda s: (T / 2, D - T / 2, s), 0.0, H),
        ("back to side-right", lambda s: (W - T / 2, D - T / 2, s), 0.0, H),
        ("front to bottom", lambda s: (s, T / 2, T / 2), 0.0, W),
        ("back to bottom", lambda s: (s, D - T / 2, T / 2), 0.0, W),
        ("side-left to bottom", lambda s: (T / 2, s, T / 2), T, D - T),
        ("side-right to bottom", lambda s: (W - T / 2, s, T / 2), T, D - T),
    )
    for what, point, lo, hi in strips:
        for i in range(samples):
            along = lo + (i + 0.5) * (hi - lo) / samples
            x, y, z = point(along)
            assert owners(x, y, z) == 1, f"{what} at {along}: {owners(x, y, z)} panels"


def test_the_box_is_hollow_and_its_walls_are_solid() -> None:
    owners = _assembled(W, D, H, T, FINGER)
    assert owners(W / 2, D / 2, H / 2) == 0
    assert owners(W / 2, D / 2, H) == 0
    assert owners(W / 2, T / 2, H / 2) == 1
    assert owners(W / 2, D / 2, T / 2) == 1
    assert owners(T / 2, D / 2, H / 2) == 1
    assert owners(-1, -1, -1) == 0


def test_corner_ownership_holds_for_other_boxes_too() -> None:
    for w, d, h, t, finger in ((60.0, 60.0, 40.0, 3.0, 10.0), (200.0, 90.0, 50.0, 6.0, 25.0)):
        owners = _assembled(w, d, h, t, finger)
        for i in range(200):
            z = (i + 0.5) * h / 200
            assert owners(t / 2, t / 2, z) == 1
            assert owners(w - t / 2, d - t / 2, z) == 1
        for i in range(200):
            x = (i + 0.5) * w / 200
            assert owners(x, t / 2, t / 2) == 1
            assert owners(x, d - t / 2, t / 2) == 1
