"""Unit: :mod:`bench.stage`, where a scene's bodies stand and the floor under them.

Every mesh here is written by hand, so every offset, box and grid below is arithmetic done in
the reader's head rather than read off the code.
"""

import pytest

from bench.kernel import Mesh
from bench.model import Ref
from bench.stage import (
    EMPTY,
    GAP,
    Box,
    as_given,
    extent,
    grid,
    layout,
    positions,
    ref_table,
    shifted,
)

pytestmark = pytest.mark.unit


def _slab(x0: float, y0: float, z0: float, x1: float, y1: float, z1: float) -> Mesh:
    """Two triangles spanning a box corner to corner - enough for an extent to read."""
    return Mesh(
        (x0, y0, z0, x1, y0, z0, x1, y1, z1, x0, y1, z1),
        (0, 1, 2, 0, 2, 3),
        (Ref("top"), None),
    )


def test_the_extent_of_a_mesh_is_the_box_its_triangles_fill() -> None:
    assert extent(_slab(1, 2, 3, 4, 6, 8)) == Box(1, 2, 3, 4, 6, 8)


def test_a_mesh_with_no_triangles_has_no_extent() -> None:
    assert extent(Mesh((1.0, 2.0, 3.0), (), ())) is None


def test_the_first_body_starts_the_row_front_edge_on_the_line_and_on_the_floor() -> None:
    offsets, _ = layout([_slab(5, 10, -2, 25, 30, 4)])
    assert offsets == ((-5, -10, 2),)


def test_the_next_body_stands_a_gap_after_the_last_ones_width() -> None:
    offsets, box = layout([_slab(0, 0, 0, 20, 10, 5), _slab(100, 0, 0, 110, 4, 8)])
    second = offsets[1]
    assert second is not None
    assert second[0] == 20 + GAP - 100
    assert box == Box(0, 0, 0, 20 + GAP + 10, 10, 8)


def test_a_row_wraps_behind_the_deepest_body_before_it_runs_too_long() -> None:
    """Two 400 mm bodies do not fit in one 600 mm row, so the second starts a row of its own,
    a gap behind the deeper of the first row's bodies."""
    offsets, box = layout(
        [_slab(0, 0, 0, 400, 40, 3), _slab(0, 0, 0, 100, 70, 3), _slab(0, 0, 0, 400, 20, 3)]
    )
    assert offsets == ((0, 0, 0), (400 + GAP, 0, 0), (0, 70 + GAP, 0))
    assert box == Box(0, 0, 0, 400 + GAP + 100, 70 + GAP + 20, 3)


def test_a_part_with_nothing_to_show_takes_no_place_in_the_row() -> None:
    offsets, box = layout([None, Mesh((), (), ()), _slab(0, 0, 0, 10, 10, 10)])
    assert offsets[:2] == (None, None)
    assert offsets[2] == (0, 0, 0)
    assert box.x0 == 0


def test_a_stage_with_no_bodies_is_the_empty_room() -> None:
    assert layout([None]) == ((None,), EMPTY)


# ---- as given: the posed assembly's placement -------------------------------------------


def test_as_given_moves_nothing_and_the_stage_is_what_the_bodies_already_fill() -> None:
    """The two slabs would be packed into a row by ``layout`` - the second shoved back to
    ``x = 30``. Posed, they stay where they are, overlap in x and all, because where they are
    is the answer the script already worked out."""
    bodies = [_slab(5, 10, -2, 25, 30, 4), _slab(20, 0, 0, 40, 8, 6)]
    assert as_given(bodies) == (((0, 0, 0), (0, 0, 0)), Box(5, 0, -2, 40, 30, 6))


def test_as_given_leaves_a_posed_body_where_it_straddles_the_floor() -> None:
    """``layout`` stands every body on ``z = 0``; this one is modelled about its own axis and
    is left below it. Grounding it would be a layout by another name."""
    _, box = as_given([_slab(-5, -5, -5, 5, 5, 5)])
    assert box.z0 == -5


def test_a_posed_part_with_nothing_to_show_takes_no_place_either() -> None:
    offsets, box = as_given([None, Mesh((), (), ()), _slab(1, 2, 3, 4, 6, 8)])
    assert offsets == (None, None, (0, 0, 0))
    assert box == Box(1, 2, 3, 4, 6, 8)


def test_a_posed_stage_with_no_bodies_is_the_same_empty_room() -> None:
    assert as_given([None]) == ((None,), EMPTY)


def test_the_grid_is_a_quarter_wider_than_the_work_in_whole_cells() -> None:
    floor = grid(Box(0, -5, 0, 33, 5, 8))
    assert floor.size == 50  # 33 * 1.25 = 41.25, up to the next 10
    assert floor.divisions == 5
    assert (floor.centre_x, floor.centre_y) == (16.5, 0)


def test_a_tiny_part_still_stands_on_a_floor() -> None:
    assert grid(Box(0, 0, 0, 1, 1, 1)).size == 20


def test_positions_are_one_triangle_at_a_time_and_moved() -> None:
    mesh = Mesh((0, 0, 0, 1, 0, 0, 0, 1, 0), (0, 1, 2, 2, 1, 0), (None, None))
    assert positions(mesh, (10, 0, 1)) == [
        10, 0, 1, 11, 0, 1, 10, 1, 1,
        10, 1, 1, 11, 0, 1, 10, 0, 1,
    ]  # fmt: skip


def test_points_in_threes_are_each_moved_by_the_offset() -> None:
    assert shifted([0, 0, 0, 1, 2, 3], (10, 20, 30)) == [10, 20, 30, 11, 22, 33]


def test_a_ref_table_names_each_face_once_and_counts_from_one() -> None:
    table, index = ref_table((Ref("top"), None, Ref("side-1"), Ref("top")), "plate")
    assert table == ["plate/top", "plate/side-1"]
    assert index == [1, 0, 2, 1]
