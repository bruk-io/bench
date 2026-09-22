"""Unit: :mod:`bench.placement` alone - reading a `[reference]` table into a plane, and the
rigid move that plane describes.

The systainer foot from decision-4 is the running example: a box that starts at
(606.795, -116.868, 0.000) and stands 6.8 mm tall, already right way up. Every test here reads
against that document, not against a re-derived design.
"""

import pytest

from bench import Mesh, Plane, Point, X, Y, Z, placed, placement
from bench.placement import named_origins

pytestmark = pytest.mark.unit


def _box(low: tuple[float, float, float], high: tuple[float, float, float]) -> Mesh:
    """A mesh of one box, ``low`` to ``high`` - two triangles per face is not needed, since
    only the vertices' own extent and count matter to :mod:`bench.placement`."""
    lx, ly, lz = low
    hx, hy, hz = high
    corners = [
        (lx, ly, lz),
        (hx, ly, lz),
        (hx, hy, lz),
        (lx, hy, lz),
        (lx, ly, hz),
        (hx, ly, hz),
        (hx, hy, hz),
        (lx, hy, hz),
    ]
    vertices = tuple(v for corner in corners for v in corner)
    triangles = (0, 1, 2, 0, 2, 3, 4, 5, 6, 4, 6, 7)
    refs = (None, None, None, None)
    return Mesh(vertices, triangles, refs)


FOOT = _box((606.795, -116.868, 0.0), (651.795, -78.868, 6.8))


# ---- placement(): origin ---------------------------------------------------------------


def test_origin_low_is_the_box_s_low_corner() -> None:
    frame = placement({"origin": "low", "up": "+Z", "along": "+X"}, FOOT)
    assert frame.origin == Point(606.795, -116.868, 0.0)


def test_origin_high_is_the_box_s_high_corner() -> None:
    frame = placement({"origin": "high", "up": "+Z", "along": "+X"}, FOOT)
    assert frame.origin == Point(651.795, -78.868, 6.8)


def test_origin_centre_is_the_middle_of_the_box() -> None:
    frame = placement({"origin": "centre", "up": "+Z", "along": "+X"}, FOOT)
    assert frame.origin == Point(629.295, -97.868, 3.4)


def test_origin_as_a_triple_is_read_in_the_mesh_s_own_coordinates() -> None:
    frame = placement({"origin": [606.795, -116.868, 0.0], "up": "+Z", "along": "+X"}, FOOT)
    assert frame.origin == Point(606.795, -116.868, 0.0)


# ---- placement(): up and along, as signed axes and as triples -------------------------


def test_up_and_along_as_signed_axes() -> None:
    frame = placement({"origin": "low", "up": "+Z", "along": "+X"}, FOOT)
    assert frame.normal == Z
    assert frame.x_dir == X


def test_up_and_along_as_triples_read_the_same_as_the_axes_they_match() -> None:
    named = placement({"origin": "low", "up": "+Z", "along": "+X"}, FOOT)
    triples = placement({"origin": "low", "up": [0.0, 0.0, 1.0], "along": [1.0, 0.0, 0.0]}, FOOT)
    assert triples.normal == named.normal
    assert triples.x_dir == named.x_dir


def test_an_export_lying_on_its_side_is_up_minus_y() -> None:
    frame = placement({"origin": "low", "up": "-Y", "along": "+X"}, FOOT)
    assert frame.normal == -Y


def test_along_only_roughly_along_the_edge_is_projected_perpendicular_to_up() -> None:
    """`along` need not be exactly perpendicular to `up`; :func:`bench.geometry.plane` projects
    it, and what comes out the other side is what the plane actually uses."""
    frame = placement({"origin": "low", "up": "+Z", "along": [1.0, 0.0, 0.3]}, FOOT)
    assert frame.x_dir @ frame.normal == pytest.approx(0.0, abs=1e-9)
    assert frame.x_dir.x > 0


# ---- placement(): refusals --------------------------------------------------------------


@pytest.mark.parametrize("key", ["origin", "up", "along"])
def test_a_missing_key_is_refused_by_name(key: str) -> None:
    table = {"origin": "low", "up": "+Z", "along": "+X"}
    del table[key]
    with pytest.raises(ValueError, match=key):
        placement(table, FOOT)


def test_an_origin_that_is_neither_a_word_nor_a_triple_is_refused() -> None:
    with pytest.raises(ValueError, match="origin"):
        placement({"origin": "diagonal", "up": "+Z", "along": "+X"}, FOOT)


def test_an_up_that_is_not_a_direction_is_refused() -> None:
    with pytest.raises(ValueError, match="up"):
        placement({"origin": "low", "up": "sideways", "along": "+X"}, FOOT)


def test_an_along_parallel_to_up_is_refused() -> None:
    with pytest.raises(ValueError, match="parallel"):
        placement({"origin": "low", "up": "+Z", "along": "+Z"}, FOOT)


def test_a_zero_vector_up_is_refused() -> None:
    with pytest.raises(ValueError, match="up"):
        placement({"origin": "low", "up": [0.0, 0.0, 0.0], "along": "+X"}, FOOT)


# ---- placed(): the rigid move -----------------------------------------------------------


def test_placed_puts_the_named_origin_at_the_world_origin() -> None:
    frame = placement({"origin": "low", "up": "+Z", "along": "+X"}, FOOT)
    body = placed(FOOT, frame)

    assert body.vertices[0:3] == pytest.approx((0.0, 0.0, 0.0))


def test_placed_keeps_the_box_s_size() -> None:
    """A rigid move changes where the box is, never how big it is."""
    frame = placement({"origin": "low", "up": "+Z", "along": "+X"}, FOOT)
    body = placed(FOOT, frame)

    xs = body.vertices[0::3]
    ys = body.vertices[1::3]
    zs = body.vertices[2::3]
    assert max(xs) - min(xs) == pytest.approx(45.0)
    assert max(ys) - min(ys) == pytest.approx(38.0)
    assert max(zs) - min(zs) == pytest.approx(6.8)


def test_placed_leaves_triangles_and_refs_untouched() -> None:
    frame = placement({"origin": "low", "up": "+Z", "along": "+X"}, FOOT)
    body = placed(FOOT, frame)

    assert body.triangles == FOOT.triangles
    assert body.refs == FOOT.refs


def test_placed_at_the_world_frame_moves_nothing() -> None:
    identity = Plane(Point(0.0, 0.0, 0.0), Z, X)
    body = placed(FOOT, identity)

    assert body.vertices == FOOT.vertices


def test_a_rotated_placement_turns_what_was_up_into_what_leans() -> None:
    """Placing by a face that is not axis-aligned is exactly what decision-4 warns costs
    something - here it is only pinned as a fact about the move, not judged."""
    frame = placement({"origin": "low", "up": "+X", "along": "+Y"}, FOOT)
    body = placed(FOOT, frame)

    # the low corner still lands on the origin, whichever axis became "up"
    assert body.vertices[0:3] == pytest.approx((0.0, 0.0, 0.0))
    # but the box's long axis (45 mm in X) now reads along what was the normal, Z
    zs = body.vertices[2::3]
    assert max(zs) - min(zs) == pytest.approx(45.0)


# ---- named_origins(): the points a pick may resolve to a word ---------------------------


def test_named_origins_are_the_words_in_the_order_a_reference_table_reads_them() -> None:
    assert tuple(name for name, _ in named_origins(FOOT)) == ("low", "high", "centre")


def test_named_origins_are_exactly_what_placement_resolves_those_words_to() -> None:
    """The invariant decision-7's pick rests on: a pick that writes `"low"` because the point
    it measured was this point must mean, later, the point `placement()` reads `"low"` as. One
    box, both readers, and no second definition of the box anywhere."""
    for name, point in named_origins(FOOT):
        assert placement({"origin": name, "up": "+Z", "along": "+X"}, FOOT).origin == point


def test_named_origins_of_an_empty_mesh_are_all_the_origin() -> None:
    """The same answer :func:`placement` already gives for a mesh with no vertices - a body
    with no corners has nothing else to name."""
    assert named_origins(Mesh((), (), ())) == (
        ("low", Point(0.0, 0.0, 0.0)),
        ("high", Point(0.0, 0.0, 0.0)),
        ("centre", Point(0.0, 0.0, 0.0)),
    )


def test_placement_and_placed_are_exported_for_a_script_to_use_by_hand() -> None:
    """decision-4's own worked example: usable at once from a script, no file and no UI."""
    from bench import plane, survey

    reference = FOOT
    result = survey(placed(reference, plane(Point(606.795, -116.868, 0.0), Z, X)))
    assert result.extent.low == Point(0.0, 0.0, 0.0)
