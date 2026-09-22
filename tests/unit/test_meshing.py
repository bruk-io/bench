"""Unit: :mod:`bench.meshing`, the decisions about names that need no modeller.

Every function here takes flat numbers and gives flat numbers, so every check is a triangle
written by hand and the face index, ref or matrix it must come back with. The rings are the
real ones :func:`~bench.topology.profile_rings` makes of a real primitive, so a side triangle
is placed on a wall this module found rather than one this file guessed.
"""

import math
from array import array

import pytest

from bench import Ref, Vector, cuboid, name
from bench.geometry import Transform, identity, translation
from bench.meshing import (
    column_major,
    extruded_faces,
    face_refs,
    mesh,
    placed,
    revolved_faces,
    section,
    segments,
    triangle_refs,
    walls,
)
from bench.topology import Extrude, Ring, profile_rings

pytestmark = pytest.mark.unit


def _plate() -> Extrude:
    node = name(cuboid(20, 10, 4), "plate").node
    assert isinstance(node, Extrude)
    return node


def _triangle(*corners: tuple[float, float, float]) -> tuple[array[float], array[int]]:
    """One triangle as a modeller hands it over: a vertex buffer of stride three, and
    indices."""
    return array("f", (value for corner in corners for value in corner)), array("I", (0, 1, 2))


def test_a_triangle_facing_up_is_the_top_and_one_facing_down_the_bottom() -> None:
    rings = profile_rings(_plate())
    up = _triangle((0, 0, 4), (1, 0, 4), (0, 1, 4))
    down = _triangle((0, 0, 0), (0, 1, 0), (1, 0, 0))
    assert list(extruded_faces(*up[:1], 3, up[1], 4.0, rings)) == [0]
    assert list(extruded_faces(*down[:1], 3, down[1], 4.0, rings)) == [1]


def test_an_extrusion_swept_the_other_way_swaps_its_caps() -> None:
    """``top`` is the face at ``distance``, so sweeping down makes the upward cap the bottom."""
    rings = profile_rings(_plate())
    vertices, indices = _triangle((0, 0, 0), (1, 0, 0), (0, 1, 0))
    assert list(extruded_faces(vertices, 3, indices, -4.0, rings)) == [1]


def test_a_side_triangle_is_the_face_of_the_wall_under_it() -> None:
    rings = profile_rings(_plate())
    ends, owners = walls(rings)
    for w in range(len(owners)):
        u0, v0, u1, v1 = ends[4 * w : 4 * w + 4]
        vertices, indices = _triangle((u0, v0, 0), (u1, v1, 0), (u0, v0, 4))
        assert list(extruded_faces(vertices, 3, indices, 4.0, rings)) == [owners[w]]


def test_a_mesh_with_more_than_positions_per_vertex_is_read_at_its_stride() -> None:
    rings = profile_rings(_plate())
    vertices = array("f", (0, 0, 4, 9, 1, 0, 4, 9, 0, 1, 4, 9))
    assert list(extruded_faces(vertices, 4, array("I", (0, 1, 2)), 4.0, rings)) == [0]


_KNOB = (Ring(((2.0, 0.0), (6.0, 0.0), (6.0, 10.0), (2.0, 10.0)), (0, 1, 2, 3)),)
"""A rectangle standing clear of the axis, in a revolve's ``(r, h)``, one face per step."""


def test_a_partial_turn_names_its_start_and_end_caps_by_position() -> None:
    turn = 2.0
    caps = 6
    start = _triangle((2, 0, 0), (6, 0, 0), (6, 0, 10))
    far = (math.cos(turn), math.sin(turn))
    end = _triangle(
        (2 * far[0], 2 * far[1], 0), (6 * far[0], 6 * far[1], 0), (6 * far[0], 6 * far[1], 10)
    )
    assert list(revolved_faces(start[0], 3, start[1], turn, _KNOB, caps)) == [caps - 2]
    assert list(revolved_faces(end[0], 3, end[1], turn, _KNOB, caps)) == [caps - 1]


def test_a_whole_turn_has_no_caps_and_its_side_is_the_step_under_it() -> None:
    """The outer wall, ``r = 6``, is the second step of the ring."""
    side = _triangle((6, 0, 2), (0, 6, 2), (0, 6, 8))
    assert list(revolved_faces(side[0], 3, side[1], math.tau, _KNOB, 4)) == [1]


def test_the_rings_cross_as_one_flat_run_and_a_count_per_ring() -> None:
    rings = (Ring(((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)), (0, 0, 0)), Ring(((5.0, 5.0),), (1,)))
    flat, lengths = section(rings)
    assert list(flat) == [0, 0, 1, 0, 0, 1, 5, 5]
    assert list(lengths) == [3, 1]


def test_a_turn_is_never_fewer_than_three_facets() -> None:
    assert segments((Ring(((0.0, 0.0),), (0,)),)) == 3


def test_a_translation_is_column_major_with_its_offset_last() -> None:
    columns = column_major(translation(Vector(1, 2, 3)))
    assert list(columns) == [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 1, 2, 3, 1]


def test_a_rotation_reads_down_its_columns() -> None:
    """A quarter turn about Z sends X to Y: the first column is ``(0, 1, 0)``."""
    quarter = Transform(((0.0, -1.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0)))
    assert list(column_major(quarter)[:4]) == [0, 1, 0, 0]


def test_vertices_are_placed_by_the_transform_at_their_stride() -> None:
    vertices = array("f", (1, 2, 3, 99))
    assert list(placed(vertices, 4, translation(Vector(10, 0, 0)))) == [11, 2, 3]
    assert list(placed(vertices, 4, identity())) == [1, 2, 3]


def test_a_triangle_answers_to_the_pair_of_its_run_and_its_face() -> None:
    tags = {(7, 0): Ref("plate/top"), (7, 1): Ref("plate/bottom"), (9, 0): None}
    refs = triangle_refs(array("I", (0, 6, 9)), array("I", (7, 9)), array("I", (1, 0, 0)), tags)
    assert refs == [Ref("plate/bottom"), Ref("plate/top"), None]


def test_a_pair_that_names_nothing_is_none() -> None:
    assert triangle_refs(array("I", (0, 3)), array("I", (4,)), array("I", (2,)), {}) == [None]


def test_an_extrusions_faces_are_named_top_and_bottom_first_under_the_prefix() -> None:
    refs = face_refs(_plate(), "plate")
    assert refs[:2] == (Ref("plate/top"), Ref("plate/bottom"))
    assert all(str(ref).startswith("plate/") for ref in refs)


def test_a_mesh_keeps_only_positions_whatever_the_stride() -> None:
    built = mesh(array("f", (1, 2, 3, 9, 4, 5, 6, 9)), 4, array("I", (0, 1, 0)), [None])
    assert built.vertices == (1, 2, 3, 4, 5, 6)
    assert built.triangles == (0, 1, 0)
    assert built.refs == (None,)
