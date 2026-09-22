"""Unit: :mod:`bench.geometry` alone - points, vectors, transforms and planes."""

import math

import pytest

from bench import (
    Axis,
    Point,
    Transform,
    Vector,
    angle,
    cross,
    distance,
    identity,
    inverse,
    lerp,
    midpoint,
    near,
    perpendicular,
    plane,
    project,
    rotation,
    to_local,
    to_world,
    translation,
    unit,
)

pytestmark = pytest.mark.unit


def test_point_vector_algebra_types() -> None:
    corner = Point(0, 0)
    hole = Point(30, 10)
    move = hole - corner
    assert isinstance(move, Vector)
    assert isinstance(corner + move, Point)
    assert isinstance(hole - move, Point)
    assert corner + move == hole
    assert isinstance(move + move, Vector)
    assert 2 * move == move * 2 == Vector(60, 20)
    assert near(move / 2, Vector(15, 5))


def test_adding_two_points_is_a_type_error() -> None:
    p = Point(1, 2)
    with pytest.raises(TypeError):
        _ = p + p  # type: ignore[operator]


def test_abs_is_length_and_matmul_is_dot() -> None:
    v = Vector(3, 4)
    assert abs(v) == 5
    assert v @ Vector(1, 0) == 3
    assert cross(Vector(1, 0, 0), Vector(0, 1, 0)) == Vector(0, 0, 1)
    assert distance(Point(0, 0), Point(3, 4)) == 5


def test_unit_scales_a_vector_to_length_one_keeping_its_direction() -> None:
    assert near(unit(Vector(3, 4)), Vector(0.6, 0.8))
    assert abs(unit(Vector(10, 0, 0))) == pytest.approx(1.0)
    assert near(unit(Vector(0, 0, -5)), Vector(0, 0, -1))


def test_unit_of_zero_vector_raises() -> None:
    with pytest.raises(ValueError):
        unit(Vector(0, 0, 0))


def test_perpendicular_turns_a_vector_a_quarter_turn_counter_clockwise_in_xy() -> None:
    assert perpendicular(Vector(1, 0)) == Vector(0, 1)
    assert perpendicular(Vector(0, 1)) == Vector(-1, 0)
    assert abs(perpendicular(Vector(3, 4)) @ Vector(3, 4)) < 1e-9  # perpendicular, hence the name
    assert perpendicular(Vector(2, 0, 5)) == Vector(0, 2, 5)  # z rides along unchanged


def test_angle_is_the_unsigned_turn_between_two_directions() -> None:
    assert angle(Vector(1, 0), Vector(5, 0)) == pytest.approx(0.0)
    assert angle(Vector(1, 0), Vector(0, 1)) == pytest.approx(math.pi / 2)
    assert angle(Vector(0, 1), Vector(1, 0)) == pytest.approx(math.pi / 2)  # unsigned
    assert angle(Vector(1, 0), Vector(-3, 0)) == pytest.approx(math.pi)
    assert angle(Vector(1, 1), Vector(0, 1)) == pytest.approx(math.pi / 4)


def test_the_inverse_of_a_transform_that_flattens_space_does_not_exist() -> None:
    flat = Transform(((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0)))
    with pytest.raises(ValueError, match="singular"):
        inverse(flat)
    with pytest.raises(ValueError, match="singular"):
        inverse(Transform(((0.0, 0.0, 0.0, 0.0),) * 3))


def test_lerp_and_midpoint_walk_the_line_between_two_places() -> None:
    a, b = Point(0, 0), Point(10, 20)
    assert lerp(a, b, 0.0) == a
    assert near(lerp(a, b, 1.0), b)
    assert near(lerp(a, b, 0.25), Point(2.5, 5))
    assert near(midpoint(a, b), lerp(a, b, 0.5))
    assert near(midpoint(a, b), Point(5, 10))


def test_project_is_the_component_along_a_direction() -> None:
    assert near(project(Vector(3, 4), Vector(1, 0)), Vector(3, 0))
    assert near(project(Vector(3, 4), Vector(0, 2)), Vector(0, 4))
    # the leftover is perpendicular to what it was projected onto
    onto = Vector(1, 1)
    rest = Vector(3, 4) - project(Vector(3, 4), onto)
    assert abs(rest @ onto) < 1e-9


def test_identity_changes_nothing_and_composes_away() -> None:
    i = identity()
    assert i @ Point(3, 4, 5) == Point(3, 4, 5)
    assert i @ Vector(3, 4, 5) == Vector(3, 4, 5)
    t = translation(Vector(7, 0, 0))
    assert near((i @ t) @ Point(1, 2, 3), t @ Point(1, 2, 3))
    assert near(inverse(i) @ Point(1, 2, 3), Point(1, 2, 3))


def test_transform_moves_points_but_not_vectors() -> None:
    t = translation(Vector(100, 0, 0))
    assert t @ Point(1, 2, 3) == Point(101, 2, 3)
    assert t @ Vector(1, 2, 3) == Vector(1, 2, 3)


def test_rotation_about_offset_axis_and_inverse_round_trip() -> None:
    r = rotation(Axis(Point(10, 0, 0), Vector(0, 0, 1)), math.pi / 2)
    p = r @ Point(20, 0, 0)
    assert near(p, Point(10, 10, 0))
    assert near(inverse(r) @ p, Point(20, 0, 0))
    assert near((r @ inverse(r)) @ Point(5, 6, 7), Point(5, 6, 7))


def test_plane_local_world_round_trip() -> None:
    p = plane(Point(0, 0, 36), Vector(0, -1, 0))  # a drawer front, normal facing -Y
    local = Point(10, 5, 0)
    world = to_world(p) @ local
    assert near(to_local(p) @ world, local)
    # a direction in the plane stays perpendicular to its normal
    assert abs((to_world(p) @ Vector(1, 0, 0)) @ p.normal) < 1e-9


def test_plane_rejects_parallel_x_dir() -> None:
    with pytest.raises(ValueError):
        plane(Point(0, 0), Vector(0, 0, 1), Vector(0, 0, 2))
