"""Functional: a mesh, surveyed and then reported, reads as the script that would make it.

The survey and the report are two modules with a record between them; this is the check that
the record carries enough for the report to say something a maker can type. The meshes are
built in the test by arithmetic, so no modeller is anywhere near - the property the pair
exists to have - and the report is checked against the shape the mesh was built as.
"""

import math

import pytest

from bench import ORIGIN, Mesh, Point, report, survey

pytestmark = pytest.mark.functional


def _box(w: float, d: float, h: float, at: Point = ORIGIN) -> Mesh:
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
    faces = (
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
    return Mesh(
        tuple(v + o for corner in corners for v, o in zip(corner, at, strict=True)),
        tuple(index for face in faces for index in face),
        (None,) * len(faces),
    )


def _ring(radius: float, sides: int, z: float, at: Point) -> list[tuple[float, float, float]]:
    return [
        (
            at.x + radius * math.cos(2.0 * math.pi * k / sides),
            at.y + radius * math.sin(2.0 * math.pi * k / sides),
            at.z + z,
        )
        for k in range(sides)
    ]


def _prism(radius: float, sides: int, h: float, at: Point) -> Mesh:
    below = _ring(radius, sides, 0.0, at)
    above = _ring(radius, sides, h, at)
    faces: list[tuple[int, int, int]] = []
    for k in range(sides):
        j = (k + 1) % sides
        faces.append((k, j, sides + j))
        faces.append((k, sides + j, sides + k))
    for k in range(1, sides - 1):
        faces.append((0, k + 1, k))
        faces.append((sides, sides + k, sides + k + 1))
    return Mesh(
        tuple(v for corner in (*below, *above) for v in corner),
        tuple(i for face in faces for i in face),
        (None,) * len(faces),
    )


def _tube(outer: float, inner: float, sides: int, h: float) -> Mesh:
    o0, o1 = _ring(outer, sides, 0.0, ORIGIN), _ring(outer, sides, h, ORIGIN)
    i0, i1 = _ring(inner, sides, 0.0, ORIGIN), _ring(inner, sides, h, ORIGIN)
    corners = (*o0, *o1, *i0, *i1)
    faces: list[tuple[int, int, int]] = []
    for k in range(sides):
        j = (k + 1) % sides
        faces.append((k, j, sides + j))
        faces.append((k, sides + j, sides + k))
        a, b, c, d = 2 * sides + k, 2 * sides + j, 3 * sides + j, 3 * sides + k
        faces.append((a, c, b))
        faces.append((a, d, c))
        faces.append((sides + k, sides + j, 3 * sides + j))
        faces.append((sides + k, 3 * sides + j, 3 * sides + k))
        faces.append((k, 2 * sides + j, j))
        faces.append((k, 2 * sides + k, 2 * sides + j))
    return Mesh(
        tuple(v for corner in corners for v in corner),
        tuple(i for face in faces for i in face),
        (None,) * len(faces),
    )


def _joined(*meshes: Mesh) -> Mesh:
    vertices: tuple[float, ...] = ()
    triangles: tuple[int, ...] = ()
    for m in meshes:
        shift = len(vertices) // 3
        vertices += m.vertices
        triangles += tuple(i + shift for i in m.triangles)
    return Mesh(vertices, triangles, (None,) * (len(triangles) // 3))


def test_a_box_reads_as_the_cuboid_it_is() -> None:
    text = report(survey(_box(30.0, 20.0, 10.0)))

    assert "candidate: cuboid(30.000, 20.000, 10.000, at=Point(0.000, 0.000, 0.000))" in text
    assert "candidate: one straight extrude() runs through these heights" in text
    assert text.count("candidate: an outline drawn on raised(XY, ") == 2, "a top and a bottom"
    assert text.count("candidate: a straight side of an extrude()") == 4
    assert "candidate: a wall of 10.000 mm" in text
    assert "ROUNDS standing alone\n  none" in text


def test_a_tube_reads_as_a_cylinder_with_a_bore_and_a_wall() -> None:
    text = report(survey(_tube(10.0, 6.0, 36, 8.0)))

    assert "cylinder: diameter 20.000 mm (radius 10.000), axis +Z, 8.000 mm long" in text
    assert "candidate: cylinder(10.000, 8.000, at=Point(0.000, 0.000, 0.000))" in text
    assert "bore: diameter 12.000 mm (radius 6.000), axis +Z, 8.000 mm long" in text
    assert "candidate: hole(body, ..., diameter=12.000, depth=8.000)" in text
    assert "candidate: a wall of 4.000 mm" in text
    assert "in the 4.000 mm band" in text, "the thinnest reading is the wall, not a sliver"


def test_bosses_in_a_row_read_as_a_pattern_of_one_cylinder() -> None:
    plate = _joined(
        _box(60.0, 40.0, 3.0),
        *(_prism(2.0, 24, 4.0, Point(x, 20.0, 3.0)) for x in (10.0, 30.0, 50.0)),
    )
    text = report(survey(plate))

    assert "3 in a row, 20.000 mm apart along +X, the first one:" in text
    assert "candidate: cylinder(2.000, 4.000, at=Point(10.000, 20.000, 3.000))" in text
    assert "candidate: pattern(one, 3, Vector(20.000, 0.000, 0.000)), with one as above" in text
    assert "ROUNDS standing alone\n  none" in text, "the bosses repeat and stand alone nowhere"


def _arc_wall(radius: float, sides: int, h: float, first: int, count: int) -> Mesh:
    """One stretch of a prism's wall with vertices of its own: a piece a seam left."""
    below = _ring(radius, sides, 0.0, ORIGIN)
    above = _ring(radius, sides, h, ORIGIN)
    ring = count + 1
    picked = [(first + k) % sides for k in range(ring)]
    corners = [*(below[k] for k in picked), *(above[k] for k in picked)]
    faces: list[tuple[int, int, int]] = []
    for k in range(count):
        faces.append((k, k + 1, ring + k + 1))
        faces.append((k, ring + k + 1, ring + k))
    return Mesh(
        tuple(v for corner in corners for v in corner),
        tuple(i for face in faces for i in face),
        (None,) * len(faces),
    )


def test_a_grip_in_pieces_reads_as_one_cylinder_not_four_partial_rounds() -> None:
    grip = _joined(*(_arc_wall(9.0, 36, 120.0, 9 * k, 9) for k in range(4)))
    text = report(survey(grip))

    assert "cylinder: diameter 18.000 mm (radius 9.000), axis +Z, 120.000 mm long" in text
    assert "candidate: cylinder(9.000, 120.000, at=Point(0.000, 0.000, 0.000))" in text
    rounds = text.partition("ROUNDS standing alone")[2].partition("REPEATS")[0]
    assert "partial round" not in rounds


def test_a_stepped_body_reports_no_runs_of_no_area_at_its_default_heights() -> None:
    """The step's ring of vertices at z = 5 is where h/2 falls; the survey moves off it."""
    stepped = _joined(_box(30.0, 20.0, 5.0), _box(20.0, 20.0, 5.0, Point(0.0, 0.0, 5.0)))
    text = report(survey(stepped))

    assert "at z = 5.020: 1 outline" in text
    assert "enclosing no area" not in text
    assert "cuts nothing" not in text
    assert "OPEN" not in text


def _bend(r: float, big: float, arc: int, steps: int) -> Mesh:
    """A quarter-round of radius ``r`` swept a quarter turn round a circle of radius ``big``
    about Z - the round-over on a plate's edge where the edge turns a corner - with ``arc``
    facets across the round and ``steps`` along the path. Each step is a stretch of a torus,
    which the survey fits as the near-cylinder it is, so the round-over comes back in pieces."""
    corners: list[tuple[float, float, float]] = []
    for k in range(steps + 1):
        phi = (math.pi / 2.0) * k / steps
        for j in range(arc + 1):
            theta = (math.pi / 2.0) * j / arc
            reach = big + r * math.cos(theta)
            corners.append((reach * math.cos(phi), reach * math.sin(phi), r * math.sin(theta)))
    faces: list[tuple[int, int, int]] = []
    ring = arc + 1
    for k in range(steps):
        for j in range(arc):
            a = k * ring + j
            faces.append((a, a + ring, a + 1))
            faces.append((a + 1, a + ring, a + ring + 1))
    return Mesh(
        tuple(v for corner in corners for v in corner),
        tuple(i for face in faces for i in face),
        (None,) * len(faces),
    )


def _frustum(below: float, above: float, h: float, sides: int) -> Mesh:
    """A cone cut off square: what a countersink is, with a cap on each end."""
    low = _ring(below, sides, 0.0, ORIGIN)
    high = _ring(above, sides, h, ORIGIN)
    faces: list[tuple[int, int, int]] = []
    for k in range(sides):
        j = (k + 1) % sides
        faces.append((k, j, sides + j))
        faces.append((k, sides + j, sides + k))
    for k in range(1, sides - 1):
        faces.append((0, k + 1, k))
        faces.append((sides, sides + k, sides + k + 1))
    return Mesh(
        tuple(v for corner in (*low, *high) for v in corner),
        tuple(i for face in faces for i in face),
        (None,) * len(faces),
    )


def test_a_round_over_that_turns_a_corner_reads_as_one_round_over_in_pieces() -> None:
    """Eight steps round the bend are eight partial rounds to the survey - the same radius,
    each touching the next, axes 11 degrees on - and one entry in the report."""
    text = report(survey(_bend(1.0, 8.0, 6, 8)))
    rounds = text.partition("ROUNDS standing alone")[2].partition("REPEATS")[0]

    assert "round-over in 8 pieces: radius 0.998 to 0.998 mm, convex, material inside it" in rounds
    assert "each piece touching the next and turned from it" in rounds
    assert rounds.count("partial round:") == 1, "the largest piece, in full, once"
    assert "and 7 more pieces" in rounds


def test_a_frustum_reads_as_one_cone_in_a_run_of_flats_with_two_caps() -> None:
    text = report(survey(_frustum(5.0, 3.0, 2.0, 24)))
    flats = text.partition("FLATS standing alone")[2].partition("ROUNDS")[0]

    assert "24 flats in a run, 2.9 to 2.9 mm2 each and each touching the next" in flats
    assert "the facets of a cone about +Z" in flats
    assert "candidate: a cone about +Z - the countersink or the chamfer of a hole()" in flats
    assert flats.count("candidate: an outline drawn on raised(XY, ") == 2, "the two caps"
    assert flats.count("degrees off horizontal") == 1, "the largest facet only"


def test_the_same_mesh_surveyed_twice_reports_the_same_text() -> None:
    mesh = _joined(_box(60.0, 40.0, 3.0), _prism(2.0, 24, 4.0, Point(10.0, 20.0, 3.0)))

    assert report(survey(mesh)) == report(survey(mesh))
