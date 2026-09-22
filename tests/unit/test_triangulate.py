"""Unit: a flat region with holes comes back as triangles that fill it exactly.

What "exactly" means is checked the same way for every shape: the triangles' areas add up to
the outline's area less the holes', every triangle turns counter-clockwise, and no triangle
sits in a hole - which together leave no gap, no overlap and nothing outside.
"""

import math

import pytest

from bench.triangulate import Point, Triangle, signed_area, triangles

pytestmark = pytest.mark.unit


def _square(x: float, y: float, size: float) -> list[Point]:
    return [(x, y), (x + size, y), (x + size, y + size), (x, y + size)]


def _circle(cx: float, cy: float, r: float, steps: int = 64) -> list[Point]:
    return [
        (cx + r * math.cos(math.tau * k / steps), cy + r * math.sin(math.tau * k / steps))
        for k in range(steps)
    ]


def _comb(width: float, height: float, tooth: float, depth: float) -> list[Point]:
    """A panel whose bottom edge is a row of finger joints, and whose top edge is cut into
    many points in a line - the two things a real panel's outline is full of."""
    out: list[Point] = []
    x = 0.0
    up = False
    while x < width - 1e-9:
        y = depth if up else 0.0
        out += [(x, y), (min(x + tooth, width), y)]
        x += tooth
        up = not up
    out += [(width, height)]
    out += [(width - width * k / 20, height) for k in range(1, 20)]
    out += [(0.0, height)]
    return out


def _check(outer: list[Point], holes: list[list[Point]] = []) -> list[Triangle]:  # ruff: ignore[mutable-argument-default]
    found = triangles(outer, holes)
    points = [point for ring in (outer, *holes) for point in ring]
    area = abs(signed_area(outer)) - sum(abs(signed_area(hole)) for hole in holes)
    covered = 0.0
    for a, b, c in found:
        turn = signed_area([points[a], points[b], points[c]])
        assert turn > 0.0, "every triangle turns counter-clockwise"
        covered += turn
        centre = (
            (points[a][0] + points[b][0] + points[c][0]) / 3,
            (points[a][1] + points[b][1] + points[c][1]) / 3,
        )
        assert not any(_contains(hole, centre) for hole in holes), "no triangle sits in a hole"
    assert covered == pytest.approx(area, rel=1e-9, abs=1e-9)
    return found


def _contains(ring: list[Point], p: Point) -> bool:
    inside = False
    for k in range(len(ring)):
        (x0, y0), (x1, y1) = ring[k - 1], ring[k]
        if (y0 > p[1]) != (y1 > p[1]) and p[0] < x0 + (p[1] - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def test_a_square_is_two_triangles() -> None:
    assert len(_check(_square(0, 0, 10))) == 2


def test_a_ring_run_clockwise_is_the_same_region() -> None:
    assert len(_check(list(reversed(_square(0, 0, 10))))) == 2


def test_an_l_shape_fills_without_crossing_its_inside_corner() -> None:
    _check([(0, 0), (20, 0), (20, 10), (10, 10), (10, 20), (0, 20)])


def test_a_round_hole_is_left_open() -> None:
    _check(_square(0, 0, 100), [_circle(50, 50, 20)])


def test_two_holes_are_both_left_open() -> None:
    _check(_square(0, 0, 100), [_circle(25, 50, 10), _square(60, 40, 20)])


def test_a_hole_close_to_the_edge_is_still_bridged() -> None:
    _check(_square(0, 0, 100), [_square(98.5, 40, 1.0)])


def test_a_hole_run_counter_clockwise_is_still_a_hole() -> None:
    _check(_square(0, 0, 100), [list(reversed(_square(30, 30, 20)))])


def test_a_finger_jointed_panel_with_points_in_a_line_fills_exactly() -> None:
    _check(_comb(200.0, 80.0, 12.0, 3.0), [_circle(100, 40, 8)])


def test_holes_level_with_each_other_bridge_past_each_other() -> None:
    _check(_square(0, 0, 100), [_square(20, 40, 10), _square(45, 40, 10), _square(70, 40, 10)])


def test_nothing_to_fill_is_no_triangles() -> None:
    assert triangles([]) == []
    assert triangles([(0, 0), (1, 1)]) == []
    assert triangles([(0, 0), (1, 0), (2, 0)]) == [], "points in a line enclose nothing"


def test_a_hole_of_no_area_cuts_nothing() -> None:
    _check(_square(0, 0, 10), [])
    assert len(triangles(_square(0, 0, 10), [[(5, 5), (6, 5), (7, 5)]])) == 2


def test_a_repeated_closing_point_is_not_a_corner() -> None:
    ring = [*_square(0, 0, 10), (0.0, 0.0)]
    assert len(triangles(ring)) == 2
