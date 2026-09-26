"""Functional: a profile swept along a path, through the public vocabulary.

Nothing here asks a modeller. What the tree answers on its own is asserted - where a path's
legs end and which way they leave, what a sweep's faces are called and where ``start`` and
``end`` stand, how far it reaches, what is refused - and so is the mesh bench lays for a sweep
itself (:func:`bench.meshing.swept`), which is closed, wound outwards and the volume Pappus
says, before any modeller sees it. What the shipped modeller makes of it is
``tests/adapter/test_sweep_measured.py``'s.
"""

import math
from collections import Counter
from collections.abc import Callable

import pytest

from bench import (
    ORIGIN,
    XY,
    Bend,
    Face,
    Point,
    Printed,
    Solid,
    Straight,
    Vector,
    X,
    Y,
    Z,
    bounds,
    circle,
    face,
    fill,
    near,
    part,
    path,
    plane_of,
    polygon,
    raised,
    rect,
    refs,
    shell,
    sweep,
)
from bench.library.print import PLA
from bench.meshing import swept
from bench.shell import PAST
from bench.topology import CHORD, Difference, Line, Swept, Wire, curve_end, flat_ring

pytestmark = pytest.mark.functional

R = 60.0
"""The bend radius every path here turns at."""


def _elbow() -> Wire:
    """Up 20, a quarter turn towards X, on 20: ending at (80, 0, 80) heading +X."""
    return path(ORIGIN, Z, Straight(20.0), Bend(R, math.pi / 2, X), Straight(20.0))


def _offset() -> Wire:
    """Up 10, an eighth turn towards X and an eighth back, on 10: an S-bend that leaves the
    way it came in, stepped over by ``2 R (1 - cos 45)``."""
    eighth = math.pi / 4
    return path(ORIGIN, Z, Straight(10.0), Bend(R, eighth, X), Bend(R, eighth, -X), Straight(10.0))


def _round(r: float = 20.0) -> Face:
    return fill(circle(r))


# ---- the path ------------------------------------------------------------------------------


def test_a_bend_turns_the_path_round_its_radius_towards_the_side_asked() -> None:
    route = _elbow()
    assert len(route.edges) == 3
    assert near(curve_end(route.edges[1].curve), Point(R, 0.0, 20.0 + R))
    assert near(curve_end(route.edges[2].curve), Point(R + 20.0, 0.0, 20.0 + R))


def test_an_s_bend_leaves_the_way_it_came_in_stepped_over() -> None:
    end = curve_end(_offset().edges[-1].curve)
    over = 2 * R * (1 - math.cos(math.pi / 4))
    assert end.x == pytest.approx(over)
    assert end.z == pytest.approx(20.0 + 2 * R * math.sin(math.pi / 4))
    last = _offset().edges[-1].curve
    assert isinstance(last, Line)
    assert near(last.end - last.start, Vector(0.0, 0.0, 10.0))


def test_only_the_part_of_toward_square_to_the_heading_counts() -> None:
    """Bending towards ``X + Z`` from a path heading up Z is bending towards X."""
    one = path(ORIGIN, Z, Bend(R, math.pi / 2, X))
    other = path(ORIGIN, Z, Bend(R, math.pi / 2, Vector(1.0, 0.0, 1.0)))
    assert near(curve_end(one.edges[0].curve), curve_end(other.edges[0].curve))


@pytest.mark.parametrize(
    ("legs", "says"),
    [
        ((), "at least one leg"),
        ((Straight(0.0),), "some length"),
        ((Bend(0.0, 1.0, X),), "radius"),
        ((Bend(10.0, 0.0, X),), "radius"),
        ((Bend(10.0, math.tau, X),), "radius"),
        ((Bend(10.0, 1.0, Z),), "no side"),
    ],
)
def test_a_path_that_is_no_route_is_refused(legs: tuple[Straight | Bend, ...], says: str) -> None:
    with pytest.raises(ValueError, match=says):
        path(ORIGIN, Z, *legs)


# ---- the body's names and where they stand -------------------------------------------------


def test_a_sweep_names_its_start_its_end_and_a_side_per_profile_edge() -> None:
    duct = part("duct", sweep(fill(rect(40, 30, Point(-20, -15))), _elbow()), Printed(PLA))
    assert {"start", "end", "side-0", "side-1", "side-2", "side-3"} <= {str(r) for r in refs(duct)}


def test_a_profile_with_a_hole_names_the_holes_wall_too() -> None:
    pipe = sweep(face(circle(20), holes=(circle(17),)), _elbow())
    assert "hole-0" in {str(r) for r in refs(part("pipe", pipe, Printed(PLA)))}


def test_the_start_is_the_profiles_plane_turned_over() -> None:
    start = plane_of(sweep(_round(), _elbow()), "start")
    assert near(start.origin, ORIGIN)
    assert near(start.normal, -Z)


def test_the_end_is_the_profiles_frame_carried_round_the_bend() -> None:
    """The profile's origin rides the path to its end, its normal turns the quarter turn to
    point on along the path, and its X - which pointed along X, square to the bend's axis -
    turns with it and points down: so a sketch on ``end`` is in the profile's own numbers."""
    end = plane_of(sweep(_round(), _elbow()), "end")
    assert near(end.origin, Point(R + 20.0, 0.0, 20.0 + R))
    assert near(end.normal, X)
    assert near(end.x_dir, -Z)
    assert near(end.y_dir, Y)


def test_an_s_bends_end_faces_the_way_its_start_set_off() -> None:
    end = plane_of(sweep(_round(), _offset()), "end")
    assert near(end.normal, Z)
    assert near(end.x_dir, X)


def test_a_sweeps_bounds_reach_the_outside_of_the_bend() -> None:
    """A 20 mm circle round the elbow: from -20 across X to the far end, and up to where the
    outgoing straight's top edge runs, 20 above the path - never short of the body."""
    box = bounds(sweep(_round(), _elbow()))
    assert box.x0 <= -20.0 and box.x0 >= -20.0 - 2 * CHORD
    assert box.z1 >= 20.0 + R + 20.0 and box.z1 <= 20.0 + R + 20.0 + 2 * CHORD
    assert box.x1 >= R + 20.0


# ---- what is refused -----------------------------------------------------------------------


def test_a_path_that_turns_a_corner_is_refused() -> None:
    cornered = Wire(
        (
            path(ORIGIN, Z, Straight(10.0)).edges[0],
            path(Point(0, 0, 10), X, Straight(10.0)).edges[0],
        )
    )
    with pytest.raises(ValueError, match="corner"):
        sweep(_round(5.0), cornered)


def test_a_profile_not_square_on_the_paths_start_is_refused() -> None:
    with pytest.raises(ValueError, match="square"):
        sweep(fill(circle(5.0), on=raised(XY, 3.0)), _elbow())
    with pytest.raises(ValueError, match="square"):
        sweep(_round(5.0), path(ORIGIN, X, Straight(10.0)))


def test_a_bend_tighter_than_the_profile_is_deep_is_refused() -> None:
    with pytest.raises(ValueError, match="tighter"):
        sweep(_round(20.0), path(ORIGIN, Z, Bend(15.0, math.pi / 2, X)))


def test_the_profile_is_checked_against_a_bend_where_the_bend_starts() -> None:
    """The L reaches 15 towards +X and 5 towards -X: bent towards -X at 10 it clears, bent
    towards +X at 10 it does not."""
    ell = fill(polygon((Point(-5, -5), Point(15, -5), Point(15, 5), Point(-5, 5))))
    sweep(ell, path(ORIGIN, Z, Straight(5.0), Bend(10.0, math.pi / 2, -X)))
    with pytest.raises(ValueError, match="tighter"):
        sweep(ell, path(ORIGIN, Z, Straight(5.0), Bend(10.0, math.pi / 2, X)))


# ---- shelled ---------------------------------------------------------------------------------


def _cavity(shelled: Solid) -> Swept:
    assert isinstance(shelled.node, Difference)
    node = shelled.node.tool.node
    assert isinstance(node, Swept)
    return node


def test_a_shelled_sweep_names_its_inside_after_its_outside() -> None:
    duct = shell(sweep(_round(), _elbow()), 2.0, open=("start", "end"))
    named = {str(r) for r in refs(part("duct", duct, Printed(PLA)))}
    assert {"inside/start", "inside/end", "inside/side-0", "end", "side-0"} <= named


def test_an_open_sweep_is_hollowed_past_both_ends_along_the_same_bend() -> None:
    cavity = _cavity(shell(sweep(_round(), _elbow()), 2.0, open=("start", "end")))
    first, last = cavity.path.edges[0].curve, cavity.path.edges[-1].curve
    assert isinstance(first, Line)
    assert near(first.start, Point(0.0, 0.0, -PAST))
    assert near(curve_end(last), Point(R + 20.0 + PAST, 0.0, 20.0 + R))
    assert len(cavity.path.edges) == len(_elbow().edges) + 2


def test_a_closed_end_stops_a_wall_short() -> None:
    shelled = shell(sweep(_round(), _elbow()), 2.0, open=("end",))
    first = _cavity(shelled).path.edges[0].curve
    assert isinstance(first, Line)
    assert near(first.start, Point(0.0, 0.0, 2.0))
    floor = plane_of(shelled, "inside/start")
    assert near(floor.origin, Point(0.0, 0.0, 2.0))
    assert near(floor.normal, Z)


def test_a_closed_end_on_a_bend_is_refused() -> None:
    with pytest.raises(ValueError, match="straight"):
        shell(sweep(_round(), path(ORIGIN, Z, Bend(R, math.pi / 2, X))), 2.0)


# ---- the mesh bench lays for it --------------------------------------------------------------


def _signed_volume(vertices: tuple[float, ...], triangles: tuple[int, ...]) -> float:
    total = 0.0
    for t in range(len(triangles) // 3):
        a, b, c = (vertices[3 * i : 3 * i + 3] for i in triangles[3 * t : 3 * t + 3])
        total += (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        )
    return total / 6.0


def _ring_area(r: float) -> float:
    points = flat_ring(circle(r), XY, (0,)).points
    return (
        abs(
            sum(
                x0 * y1 - x1 * y0
                for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True)
            )
        )
        / 2
    )


@pytest.mark.parametrize(
    ("route", "length"),
    [(_elbow, 40.0 + R * math.pi / 2), (_offset, 20.0 + 2 * R * math.pi / 4)],
    ids=["elbow", "offset"],
)
def test_the_mesh_is_closed_and_wound_out_and_holds_what_pappus_says(
    route: Callable[[], Wire], length: float
) -> None:
    """Every edge is shared by exactly two triangles and the surface is one sphere's worth
    (``V - E + F = 2``), and its signed volume is positive and the chorded profile's area
    times the length of the path its centre runs - short by what cutting the bend into chords
    takes, which for a step cut to :data:`~bench.topology.CHORD` on a bend's outside is a few
    parts in ten thousand."""
    body = sweep(_round(), route())
    assert isinstance(body.node, Swept)
    vertices, triangles, _ = swept(body.node)
    v, t = tuple(vertices), tuple(triangles)
    corners = [(t[3 * k], t[3 * k + 1], t[3 * k + 2]) for k in range(len(t) // 3)]
    edges = Counter(
        (min(p, q), max(p, q)) for a, b, c in corners for p, q in ((a, b), (b, c), (c, a))
    )
    assert set(edges.values()) == {2}
    assert len(v) // 3 - len(edges) + len(corners) == 2
    pappus = _ring_area(20.0) * length
    assert pappus * (1 - 1e-3) < _signed_volume(v, t) < pappus


def test_every_triangle_is_laid_on_the_face_its_profile_edge_sweeps() -> None:
    """The caps are ``start`` (0) and ``end`` (1), a rectangle's four sides 2 to 5, and each
    face gets triangles."""
    body = sweep(fill(rect(40, 30, Point(-20, -15))), _elbow())
    assert isinstance(body.node, Swept)
    _, triangles, faces = swept(body.node)
    assert len(faces) == len(triangles) // 3
    assert set(faces) == {0, 1, 2, 3, 4, 5}
