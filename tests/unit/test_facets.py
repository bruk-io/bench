"""Unit: :mod:`bench.facets` alone - a mesh as triangles, and the material under each.

Every mesh here is built by hand from flat buffers, so what is asserted is arithmetic: a box's
walls measure the box, a hollow box's walls measure the gap between its skins, and a ray that
leaves an open mesh meets nothing and says so.
"""

import pytest

from bench import ORIGIN, Mesh, Point, Vector
from bench.facets import SKIN, area, centre, normal, thicknesses, thinnest, triangles

pytestmark = pytest.mark.unit


def _box(w: float, d: float, h: float, at: Point = ORIGIN, *, inward: bool = False) -> Mesh:
    """A closed box from ``at``, twelve triangles wound outward - or inward, for the inside
    skin of a hollow body."""
    corners = (
        (0.0, 0.0, 0.0),
        (w, 0.0, 0.0),
        (w, d, 0.0),
        (0.0, d, 0.0),
        (0.0, 0.0, h),
        (w, 0.0, h),
        (w, d, h),
        (0.0, d, h),
    )
    faces: tuple[tuple[int, int, int], ...] = (
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    )
    if inward:
        faces = tuple((a, c, b) for a, b, c in faces)
    return Mesh(
        tuple(v + o for corner in corners for v, o in zip(corner, at, strict=True)),
        tuple(index for face in faces for index in face),
        (None,) * len(faces),
    )


def _joined(a: Mesh, b: Mesh) -> Mesh:
    shift = len(a.vertices) // 3
    return Mesh(
        a.vertices + b.vertices,
        a.triangles + tuple(i + shift for i in b.triangles),
        a.refs + b.refs,
    )


def test_a_box_is_twelve_triangles_with_outward_normals_and_the_right_area() -> None:
    corners = triangles(_box(30.0, 20.0, 10.0))

    assert len(corners) == 12
    assert sum(area(t) for t in corners) == pytest.approx(2 * (600.0 + 300.0 + 200.0))
    normals = [normal(t) for t in corners]
    assert all(n is not None for n in normals)
    outward = {(round(n.x), round(n.y), round(n.z)) for n in normals if n is not None}
    assert outward == {(0, 0, -1), (0, 0, 1), (0, -1, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0)}
    top = [t for t, n in zip(corners, normals, strict=True) if n is not None and n.z > 0.5]
    assert all(centre(t).z == pytest.approx(10.0) for t in top)


def test_a_triangle_with_no_area_has_no_normal() -> None:
    flat = (Point(0.0, 0.0, 0.0), Point(1.0, 1.0, 0.0), Point(2.0, 2.0, 0.0))

    assert normal(flat) is None
    assert area(flat) == pytest.approx(0.0)


def test_a_solid_box_measures_its_own_dimensions_under_every_face() -> None:
    """From the top, straight down, is the height; from a side, straight in, is the width or
    the depth. Every face of a solid box measures the box."""
    box = _box(30.0, 20.0, 10.0)
    corners = triangles(box)

    through = thicknesses(box)
    for t, found in zip(corners, through, strict=True):
        n = normal(t)
        assert n is not None and found is not None
        expected = 30.0 if abs(n.x) > 0.5 else 20.0 if abs(n.y) > 0.5 else 10.0
        assert found == pytest.approx(expected)


def test_the_thinnest_wall_of_a_box_is_its_smallest_dimension_measured_from_a_big_face() -> None:
    box = _box(30.0, 20.0, 10.0)

    found = thinnest(box)
    assert found is not None
    thickness, index = found
    assert thickness == pytest.approx(10.0)
    n = normal(triangles(box)[index])
    assert n is not None and abs(n.z) > 0.5, "measured from the top or the bottom"


def test_a_hollow_box_measures_the_gap_between_its_skins() -> None:
    """A 20 mm box with a 10 mm cavity in the middle: every side wall is 5 mm, and from
    inside the cavity the ray meets the outer skin 5 mm away too."""
    hollow = _joined(
        _box(20.0, 20.0, 20.0), _box(10.0, 10.0, 10.0, Point(5.0, 5.0, 5.0), inward=True)
    )

    through = thicknesses(hollow)
    assert all(found is not None and found == pytest.approx(5.0) for found in through)
    found = thinnest(hollow)
    assert found is not None and found[0] == pytest.approx(5.0)


def test_a_ray_that_meets_nothing_answers_none() -> None:
    """One triangle on its own: its ray goes into the air, and nothing invents a wall."""
    lone = Mesh((0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 10.0, 0.0), (0, 1, 2), (None,))

    assert thicknesses(lone) == (None,)
    assert thinnest(lone) is None


def test_an_empty_mesh_has_no_thinnest_wall() -> None:
    assert thinnest(Mesh((), (), ())) is None
    assert thicknesses(Mesh((), (), ())) == ()


def test_a_surface_facing_the_same_way_is_not_a_wall() -> None:
    """Two parallel sheets both facing up: the ray from the upper one goes down through the
    lower one's back, which faces away, so it is not a surface facing back and does not count.
    Only material with an inside has a thickness."""
    sheet = Mesh((0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 10.0, 0.0), (0, 1, 2), (None,))
    lifted = Mesh((0.0, 0.0, 3.0, 10.0, 0.0, 3.0, 0.0, 10.0, 3.0), (0, 1, 2), (None,))

    assert thicknesses(_joined(sheet, lifted)) == (None, None)


def test_a_hit_closer_than_the_skin_is_the_surface_itself_and_does_not_count() -> None:
    """Two sheets a fraction of the skin apart facing each other are one surface with a seam
    in it, as far as a measuring ray is concerned - the same rule that stops a ray meeting its
    own neighbours at a shared edge."""
    down = Mesh((0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 10.0, 0.0), (0, 2, 1), (None,))
    up = Mesh((0.0, 0.0, SKIN / 2, 10.0, 0.0, SKIN / 2, 0.0, 10.0, SKIN / 2), (0, 1, 2), (None,))

    assert thicknesses(_joined(down, up)) == (None, None)


def test_normals_are_unit_and_the_centre_is_the_mean_corner() -> None:
    t = (Point(0.0, 0.0, 0.0), Point(6.0, 0.0, 0.0), Point(0.0, 3.0, 0.0))

    assert normal(t) == Vector(0.0, 0.0, 1.0)
    assert centre(t) == Point(2.0, 1.0, 0.0)
    assert area(t) == pytest.approx(9.0)
