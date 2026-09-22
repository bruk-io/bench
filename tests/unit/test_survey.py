"""Survey: reading a mesh back in, and measuring what it turns out to be.

A ``Mesh`` is a plain record of flat buffers, so every case here builds one by hand and no
solid modeller appears anywhere - which is the property the module exists to have. The bodies
are boxes, prisms and tubes with their corners placed by arithmetic, so every number the survey
answers with has a number here it can be checked against.
"""

import math

import pytest

from bench import ORIGIN, Mesh, Point, Step, Vector, stl
from bench.facets import thinnest
from bench.survey import Extent, Flat, Round, flat_faces, mesh_from_stl, section_loops, survey

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


def _ring(radius: float, sides: int, z: float, at: Point) -> list[tuple[float, float, float]]:
    """``sides`` corners on a circle of ``radius`` about ``at``, at height ``z`` above it -
    on the circle exactly, the way a tessellated arc puts them."""
    return [
        (
            at.x + radius * math.cos(2.0 * math.pi * k / sides),
            at.y + radius * math.sin(2.0 * math.pi * k / sides),
            at.z + z,
        )
        for k in range(sides)
    ]


def _prism(
    radius: float,
    sides: int,
    h: float,
    at: Point = ORIGIN,
    *,
    caps: bool = True,
    inward: bool = False,
) -> Mesh:
    """A regular prism standing on ``at``: its sides, and its two caps unless ``caps`` is
    off. Wound outward, or inward for the wall of a bore."""
    below = _ring(radius, sides, 0.0, at)
    above = _ring(radius, sides, h, at)
    faces: list[tuple[int, int, int]] = []
    for k in range(sides):
        j = (k + 1) % sides
        faces.append((k, j, sides + j))
        faces.append((k, sides + j, sides + k))
    if caps:
        for k in range(1, sides - 1):
            faces.append((0, k + 1, k))
            faces.append((sides, sides + k, sides + k + 1))
    if inward:
        faces = [(a, c, b) for a, b, c in faces]
    return Mesh(
        tuple(v for corner in (*below, *above) for v in corner),
        tuple(i for face in faces for i in face),
        (None,) * len(faces),
    )


def _tube(outer: float, inner: float, sides: int, h: float) -> Mesh:
    """A tube on the origin: an outer wall facing out, an inner wall facing in, and the two
    annular caps between them. Closed, so every wall has a thickness."""
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


def _arc_wall(
    radius: float,
    sides: int,
    h: float,
    first: int,
    count: int,
    at: Point = ORIGIN,
    *,
    inward: bool = False,
) -> Mesh:
    """Facets ``first`` to ``first + count`` of a ``sides``-gon prism's wall, with vertices of
    its own - so two of these joined share no edge, which is the seam a tessellation leaves
    where it breaks one surface into pieces."""
    below = _ring(radius, sides, 0.0, at)
    above = _ring(radius, sides, h, at)
    ring = count + 1
    picked = [(first + k) % sides for k in range(ring)]
    corners = [*(below[k] for k in picked), *(above[k] for k in picked)]
    faces: list[tuple[int, int, int]] = []
    for k in range(count):
        j = k + 1
        faces.append((k, j, ring + j))
        faces.append((k, ring + j, ring + k))
    if inward:
        faces = [(a, c, b) for a, b, c in faces]
    return Mesh(
        tuple(v for corner in corners for v in corner),
        tuple(i for face in faces for i in face),
        (None,) * len(faces),
    )


def _joined(*meshes: Mesh) -> Mesh:
    vertices: tuple[float, ...] = ()
    triangles: tuple[int, ...] = ()
    refs: tuple[None, ...] = ()
    for m in meshes:
        shift = len(vertices) // 3
        vertices += m.vertices
        triangles += tuple(i + shift for i in m.triangles)
        refs += (None,) * len(m.refs)
    return Mesh(vertices, triangles, refs)


# ---- reading an STL --------------------------------------------------------------------


def test_a_mesh_bench_wrote_reads_back_the_same_size() -> None:
    made = _box(30.0, 20.0, 10.0)
    read = mesh_from_stl(stl(made))

    assert len(read.triangles) // 3 == len(made.triangles) // 3
    assert _bounds(read) == _bounds(made)


def test_an_imported_mesh_invents_no_names() -> None:
    read = mesh_from_stl(stl(_box(4.0, 4.0, 4.0)))

    assert set(read.refs) == {None}
    assert len(read.refs) == len(read.triangles) // 3


def test_coincident_corners_become_one_vertex() -> None:
    """A box has eight corners however many triangles share them."""
    read = mesh_from_stl(stl(_box(5.0, 5.0, 5.0)))

    assert len(read.vertices) // 3 == 8


def test_an_ascii_stl_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="ASCII"):
        mesh_from_stl(b"solid box\n facet normal 0 0 1\n endsolid box\n")


def test_a_truncated_stl_says_how_much_is_missing() -> None:
    whole = stl(_box(2.0, 2.0, 2.0))

    with pytest.raises(ValueError, match="bytes"):
        mesh_from_stl(whole[:-20])


# ---- extent and sections ---------------------------------------------------------------


def test_a_survey_measures_the_box_it_was_given() -> None:
    found = survey(_box(30.0, 20.0, 10.0))

    assert found.triangles == 12
    assert found.extent == Extent(
        Point(0.0, 0.0, 0.0),
        Point(30.0, 20.0, 10.0),
        Point(30.0, 20.0, 10.0) - Point(0.0, 0.0, 0.0),
    )


def test_a_straight_wall_sections_the_same_all_the_way_up() -> None:
    """The measurement that catches a taper: every section of a box is the same box."""
    found = survey(_box(30.0, 20.0, 10.0))

    assert len(found.sections) == 5
    for section in found.sections:
        (outline,) = section.outlines
        assert outline.closed
        assert outline.low == Point(0.0, 0.0, 0.0)
        assert outline.high == Point(30.0, 20.0, 0.0)
        assert outline.area == pytest.approx(600.0)


def test_a_section_asked_for_by_height_is_the_one_answered() -> None:
    found = survey(_box(10.0, 10.0, 10.0), at=(2.5, 7.5))

    assert tuple(section.z for section in found.sections) == (2.5, 7.5)


def test_a_height_outside_the_body_cuts_nothing() -> None:
    found = survey(_box(10.0, 10.0, 10.0), at=(50.0,))

    (section,) = found.sections
    assert section.outlines == ()


def test_a_hollow_body_sections_into_two_outlines() -> None:
    """An outer wall and an inner one, which is what tells a tube from a post."""
    both = _joined(_box(20.0, 20.0, 10.0), _box(10.0, 10.0, 10.0, Point(5.0, 5.0), inward=True))

    (section,) = survey(both, at=(5.0,)).sections
    assert len(section.outlines) == 2
    assert sorted(round(one.area) for one in section.outlines) == [100, 400]


def _stepped() -> Mesh:
    """A 30 x 20 x 5 box with a 20 x 20 x 5 box on top: vertex layers at 0, 5 and 10, and
    the middle of five default heights lands on the one at 5."""
    return _joined(_box(30.0, 20.0, 5.0), _box(20.0, 20.0, 5.0, Point(0.0, 0.0, 5.0)))


def test_a_default_height_on_a_layer_of_vertices_is_moved_off_it() -> None:
    """A plane exactly through the step's ring of vertices touches every wall triangle and
    crosses none, and cuts nothing at all; two hundredths above it cuts the upper box."""
    found = survey(_stepped())

    heights = [s.z for s in found.sections]
    assert heights == pytest.approx([10 / 6, 20 / 6, 5.02, 40 / 6, 50 / 6])
    (middle,) = [s for s in found.sections if abs(s.z - 5.02) < 1e-9]
    (outline,) = middle.outlines
    assert outline.closed
    assert outline.area == pytest.approx(400.0), "the upper box, cut through"


def test_the_foot_at_its_own_single_precision_numbers_cuts_no_zero_area_runs() -> None:
    """The systainer foot's z values as its STL holds them: a floor a few nanometres up, a
    plateau at 3.4 and a lid at 6.8, each the double a float32 reads back as. h/2 lands two
    nanometres off the plateau, near enough to leave slivers shorter than the tolerance that
    joins a section up - thirty-six runs of no area, before the height was moved."""
    floor, plateau, lid = 4.632568550988481e-09, 3.4000000953674316, 6.800000190734863
    mesh = _joined(
        _box(45.0, 38.0, plateau - floor, Point(0.0, 0.0, floor)),
        _box(41.0, 33.0, lid - plateau, Point(0.0, 0.0, plateau)),
    )
    found = survey(mesh)

    assert abs(floor + (lid - floor) / 2.0 - plateau) < 1e-8, "the case the foot presents"
    heights = [s.z for s in found.sections]
    assert heights[2] == pytest.approx(plateau + 0.02)
    for section in found.sections:
        assert all(o.closed and o.area > 1.0 for o in section.outlines), section


def test_a_height_the_caller_asks_for_is_taken_as_asked_wherever_it_lands() -> None:
    found = survey(_stepped(), at=(5.0, 2.5))

    assert [s.z for s in found.sections] == [5.0, 2.5]


def test_the_same_mesh_surveys_at_the_same_heights_however_it_arrived() -> None:
    lower, upper = _box(30.0, 20.0, 5.0), _box(20.0, 20.0, 5.0, Point(0.0, 0.0, 5.0))

    one = [s.z for s in survey(_joined(lower, upper)).sections]
    other = [s.z for s in survey(_joined(upper, lower)).sections]
    assert one == other == [s.z for s in survey(_joined(lower, upper)).sections]


def test_a_mesh_with_a_gap_still_sections_open() -> None:
    """A box with one side missing: every plane through it leaves an outline whose ends do
    not meet, and the moved heights do not close it."""
    whole = _box(10.0, 10.0, 10.0)
    torn = Mesh(whole.vertices, whole.triangles[: 6 * 3] + whole.triangles[8 * 3 :], (None,) * 10)

    found = survey(torn)
    assert len(found.sections) == 5
    for section in found.sections:
        assert any(not o.closed for o in section.outlines), section


def test_an_empty_mesh_measures_nothing_rather_than_failing() -> None:
    found = survey(Mesh((), (), ()))

    assert found.triangles == 0
    assert found.extent.size == Point(0.0, 0.0, 0.0) - Point(0.0, 0.0, 0.0)
    assert found.sections == ()
    assert found.walls is None
    assert (found.flats, found.rounds, found.repeats) == ((), (), ())


# ---- walls -----------------------------------------------------------------------------


def test_walls_report_the_thinnest_place_and_the_distribution_by_area() -> None:
    """A 30 by 20 by 10 box is 10 mm thick under its two big faces, 20 under the next pair
    and 30 under the smallest: three bands, most surface first."""
    walls = survey(_box(30.0, 20.0, 10.0)).walls

    assert walls is not None
    assert walls.thinnest == pytest.approx(10.0)
    assert walls.at.z in (0.0, 10.0), "measured from the top or the bottom"
    assert [(b.thickness, round(b.area)) for b in walls.bands] == [
        (10.0, 1200),
        (20.0, 600),
        (30.0, 400),
    ]


def test_a_hollow_body_reports_the_wall_between_its_skins_not_the_body() -> None:
    hollow = _joined(
        _box(20.0, 20.0, 20.0), _box(10.0, 10.0, 10.0, Point(5.0, 5.0, 5.0), inward=True)
    )
    walls = survey(hollow).walls

    assert walls is not None
    assert walls.thinnest == pytest.approx(5.0)
    (band,) = walls.bands
    assert band.thickness == pytest.approx(5.0)
    assert band.area == pytest.approx(6 * 400.0 + 6 * 100.0), "both skins measured it"


def test_the_wall_a_survey_reports_is_the_wall_the_shared_measurement_finds() -> None:
    """Criterion #4 by construction: ``survey`` and ``checks.wall`` both call
    :func:`bench.facets.thinnest`. Checked here against the function itself; the functional
    layer checks it against ``wall`` through a kernel."""
    mesh = _tube(10.0, 6.0, 36, 8.0)
    walls = survey(mesh).walls
    found = thinnest(mesh)

    assert walls is not None and found is not None
    assert walls.thinnest == found[0]


# ---- flats -----------------------------------------------------------------------------


def test_a_box_has_six_flats_with_the_numbers_that_place_and_size_them() -> None:
    flats = survey(_box(30.0, 20.0, 10.0)).flats

    assert len(flats) == 6
    assert [round(f.area) for f in flats] == [600, 600, 300, 300, 200, 200], "biggest first"
    (top,) = [f for f in flats if f.normal.z > 0.5]
    assert top == Flat(
        normal=Vector(0.0, 0.0, 1.0),
        centre=Point(15.0, 10.0, 10.0),
        low=Point(0.0, 0.0, 10.0),
        high=Point(30.0, 20.0, 10.0),
        area=600.0,
        facets=2,
    )
    assert {(round(f.normal.x), round(f.normal.y), round(f.normal.z)) for f in flats} == {
        (0, 0, 1),
        (0, 0, -1),
        (1, 0, 0),
        (-1, 0, 0),
        (0, 1, 0),
        (0, -1, 0),
    }


def test_a_hexagonal_prism_is_eight_flats_and_no_round() -> None:
    """Sixty degrees between faces is a corner, not a curve: a hexagon is what a maker draws
    when they mean a hexagon."""
    found = survey(_prism(5.0, 6, 10.0))

    assert found.rounds == ()
    assert len(found.flats) == 8
    assert sum(1 for f in found.flats if abs(f.normal.z) > 0.5) == 2


def test_a_flat_smaller_than_a_square_millimetre_is_not_reported() -> None:
    found = survey(_box(0.5, 0.5, 0.5))

    assert found.flats == ()


# ---- flat_faces --------------------------------------------------------------------------


def test_flat_faces_finds_the_same_flats_survey_does_with_their_own_triangles() -> None:
    faces = flat_faces(_box(30.0, 20.0, 10.0))

    assert len(faces) == 6
    assert [round(flat.area) for flat, _ in faces] == [600, 600, 300, 300, 200, 200]
    for flat, region in faces:
        assert len(region) == flat.facets


def test_flat_faces_regions_are_disjoint_and_index_real_triangles() -> None:
    mesh = _box(30.0, 20.0, 10.0)
    faces = flat_faces(mesh)

    claimed = [i for _, region in faces for i in region]
    assert len(claimed) == len(set(claimed)), "no triangle grows two flats"
    assert all(0 <= i < len(mesh.triangles) // 3 for i in claimed)


def test_flat_faces_on_a_mesh_with_no_flat_is_empty() -> None:
    assert flat_faces(_box(0.5, 0.5, 0.5)) == ()


# ---- section_loops ----------------------------------------------------------------------


def test_section_loops_is_one_closed_loop_within_the_hexagons_own_radius() -> None:
    """Not exactly six points: `_prism`'s sides are each two triangles, and the diagonal
    between them crosses the section plane too, on the chord rather than the corner - a
    real point the mesh's own triangulation puts there, sitting inside the true radius
    rather than on it. Only a corner reaches the radius exactly."""
    loops = section_loops(_prism(5.0, 6, 10.0), 5.0)

    assert len(loops) == 1
    points, closed = loops[0]
    assert closed
    assert len(points) >= 6
    assert all(p.z == pytest.approx(5.0) for p in points)
    assert all((p.x**2 + p.y**2) ** 0.5 <= 5.0 + 1e-6 for p in points)
    assert max((p.x**2 + p.y**2) ** 0.5 for p in points) == pytest.approx(5.0)


def test_section_loops_of_a_hollow_tube_is_two_loops_one_inside_the_other() -> None:
    loops = section_loops(_tube(10.0, 6.0, 24, 5.0), 2.5)

    assert len(loops) == 2
    radii = sorted(max((p.x**2 + p.y**2) ** 0.5 for p in points) for points, _ in loops)
    assert radii[0] == pytest.approx(6.0, abs=0.05)
    assert radii[1] == pytest.approx(10.0, abs=0.05)


def test_section_loops_at_a_height_outside_the_body_is_empty() -> None:
    assert section_loops(_box(10.0, 10.0, 10.0), 50.0) == ()


def test_section_loops_and_survey_agree_on_how_many_outlines_a_height_has() -> None:
    """The same walk, kept instead of thrown away: what `survey` counts as a `Section`'s own
    outlines is exactly what `section_loops` returns loops for."""
    mesh = _tube(10.0, 6.0, 24, 5.0)
    found = survey(mesh, at=(2.5,))

    assert len(section_loops(mesh, 2.5)) == len(found.sections[0].outlines)


# ---- rounds ----------------------------------------------------------------------------


def test_a_cylinder_is_one_round_with_its_axis_radius_and_length() -> None:
    found = survey(_prism(5.0, 36, 10.0, Point(20.0, 30.0, 0.0)))

    (one,) = found.rounds
    assert one.axis == Vector(0.0, 0.0, 1.0)
    assert one.radius == pytest.approx(5.0, abs=1e-6)
    assert one.length == pytest.approx(10.0)
    assert one.turn == pytest.approx(2.0 * math.pi)
    assert one.concave is False
    assert one.spread < 1e-6
    assert one.centre.x == pytest.approx(20.0) and one.centre.y == pytest.approx(30.0)
    assert one.centre.z == pytest.approx(5.0)
    assert one.facets == 72
    assert len(found.flats) == 2, "the two caps"


def test_a_round_reads_its_radius_off_the_corners_so_the_chords_do_not_shrink_it() -> None:
    """A 36-gon's facets sit 5 cos(5 degrees) = 4.981 mm from the axis; its corners sit at
    5.000. The radius reported is the corners', because that is where the arc is."""
    (one,) = survey(_prism(5.0, 36, 10.0)).rounds

    assert one.radius == pytest.approx(5.0, abs=1e-6)
    assert one.radius != pytest.approx(5.0 * math.cos(math.radians(5.0)), abs=1e-3)


def test_a_tube_is_a_boss_outside_and_a_bore_inside() -> None:
    found = survey(_tube(10.0, 6.0, 36, 8.0))

    assert len(found.rounds) == 2
    outer, inner = found.rounds
    assert (outer.concave, inner.concave) == (False, True)
    assert outer.radius == pytest.approx(10.0, abs=1e-6)
    assert inner.radius == pytest.approx(6.0, abs=1e-6)
    assert outer.turn == inner.turn == pytest.approx(2.0 * math.pi)
    assert len(found.flats) == 2, "the two annular caps"
    walls = found.walls
    assert walls is not None
    assert walls.thinnest == pytest.approx(4.0, abs=0.05), "the wall, not the height"


def test_a_partial_round_says_how_much_of_a_circle_it_covers() -> None:
    """A quarter of a cylinder's wall on its own: nine facets of a 36-gon, a quarter turn."""
    whole = _prism(5.0, 36, 10.0, caps=False)
    quarter = Mesh(whole.vertices, whole.triangles[: 9 * 6], (None,) * 18)

    (one,) = survey(quarter).rounds
    assert one.turn == pytest.approx(math.pi / 2.0, abs=1e-6)
    assert one.radius == pytest.approx(5.0, abs=1e-6)


def test_a_cylinder_the_tessellation_broke_into_pieces_is_one_round() -> None:
    """Four quarter walls of one 36-gon, sharing no edge: four partial rounds of a quarter
    turn each, grown separately, that lie on one cylinder and are put back as it."""
    pieces = _joined(*(_arc_wall(5.0, 36, 10.0, 9 * k, 9) for k in range(4)))
    (whole,) = survey(_prism(5.0, 36, 10.0, caps=False)).rounds

    (one,) = survey(pieces).rounds
    assert one.turn == pytest.approx(2.0 * math.pi)
    assert one.radius == pytest.approx(5.0, abs=1e-6)
    assert one.length == pytest.approx(10.0)
    assert one.concave is False
    assert one.facets == 72
    assert one.area == pytest.approx(whole.area)
    assert one.spread < 1e-6
    assert one.centre.z == pytest.approx(5.0)


def test_two_bores_of_one_size_on_one_axis_with_material_between_stay_two() -> None:
    """A 3 mm bore through the floor of a block and another through its lid: the same
    cylinder, with nothing measured along it between the two."""
    block = _joined(
        _box(20.0, 20.0, 20.0),
        _prism(3.0, 36, 5.0, Point(10.0, 10.0, 0.0), caps=False, inward=True),
        _prism(3.0, 36, 5.0, Point(10.0, 10.0, 15.0), caps=False, inward=True),
    )

    found = survey(block)
    assert len(found.rounds) == 2
    assert all(r.concave and r.radius == pytest.approx(3.0, abs=1e-6) for r in found.rounds)
    assert sorted(r.centre.z for r in found.rounds) == pytest.approx([2.5, 17.5])
    assert all(r.length == pytest.approx(5.0) for r in found.rounds)


def test_two_arcs_of_one_radius_on_parallel_axes_are_two_rounds() -> None:
    """The systainer handle's 83 and 63 degree pieces sit 17 mm from its grip on a parallel
    axis at the same radius; sharing a radius and a direction is not sharing a cylinder."""
    two = _joined(
        _arc_wall(5.0, 36, 10.0, 0, 9),
        _arc_wall(5.0, 36, 10.0, 0, 9, Point(17.0, 0.0, 0.0)),
    )

    assert len(survey(two).rounds) == 2


def test_two_arcs_on_one_cylinder_cover_their_arcs_and_not_the_gap_between() -> None:
    """Sixty degrees either side of a rod, as two flats milled across it leave: one round,
    of the 120 degrees the pieces cover - not the 300 that one piece's widest gap would say."""
    rod = _joined(_arc_wall(5.0, 36, 10.0, 0, 6), _arc_wall(5.0, 36, 10.0, 18, 6))

    (one,) = survey(rod).rounds
    assert one.turn == pytest.approx(2.0 * math.pi / 3.0, abs=1e-6)
    assert one.facets == 24


def test_pieces_that_meet_end_to_end_are_one_round_the_whole_length() -> None:
    """A quarter of a wall over the lower half of a cylinder and the next quarter over the
    upper half: they meet at one ring, and the round is ten long and a half turn."""
    two = _joined(
        _arc_wall(5.0, 36, 5.0, 0, 9),
        _arc_wall(5.0, 36, 5.0, 9, 9, Point(0.0, 0.0, 5.0)),
    )

    (one,) = survey(two).rounds
    assert one.length == pytest.approx(10.0)
    assert one.turn == pytest.approx(math.pi, abs=1e-6)
    assert one.centre.z == pytest.approx(5.0)


def test_a_round_smaller_than_a_square_millimetre_is_not_reported() -> None:
    found = survey(_prism(0.2, 24, 0.5))

    assert found.rounds == ()


def test_a_round_that_barely_turns_is_a_blend_not_a_feature() -> None:
    """Three facets of a 360-gon: a degree of turn, on a radius bigger than the mesh."""
    whole = _prism(50.0, 360, 10.0, caps=False)
    sliver = Mesh(whole.vertices, whole.triangles[: 3 * 6], (None,) * 6)

    assert survey(sliver).rounds == ()


# ---- repeats ---------------------------------------------------------------------------


def _plate_with_bosses(*at: Point) -> Mesh:
    return _joined(
        _box(60.0, 40.0, 3.0),
        *(_prism(2.0, 24, 4.0, Point(p.x, p.y, 3.0), caps=True) for p in at),
    )


def test_three_bosses_in_a_row_are_one_repeat_not_three_rounds() -> None:
    found = survey(_plate_with_bosses(Point(10.0, 20.0), Point(30.0, 20.0), Point(50.0, 20.0)))

    assert found.rounds == ()
    (repeat,) = [r for r in found.repeats if isinstance(r.one, Round)]
    assert isinstance(repeat.one, Round)
    assert repeat.one.radius == pytest.approx(2.0, abs=1e-6)
    assert repeat.one.centre.x == pytest.approx(10.0), "the first of them"
    assert repeat.steps == (Step(Vector(20.0, 0.0, 0.0), 3),) or (
        len(repeat.steps) == 1
        and repeat.steps[0].count == 3
        and repeat.steps[0].along.x == pytest.approx(20.0)
        and repeat.steps[0].along.y == pytest.approx(0.0)
    )
    assert sum(1 for f in found.flats if f.normal.z > 0.5 and f.area < 20.0) == 0, (
        "the three identical crowns repeat too, and left the flats"
    )
    crowns = [r for r in found.repeats if isinstance(r.one, Flat) and r.one.normal.z > 0.5]
    assert len(crowns) == 1 and crowns[0].steps[0].count == 3


def test_two_bosses_are_two_features_not_a_repetition() -> None:
    """Any two things are evenly spaced."""
    found = survey(_plate_with_bosses(Point(10.0, 20.0), Point(50.0, 20.0)))

    assert found.repeats == ()
    assert len(found.rounds) == 2


def test_a_two_by_two_grid_of_bosses_is_one_repeat_with_two_steps() -> None:
    found = survey(
        _plate_with_bosses(
            Point(10.0, 10.0), Point(50.0, 10.0), Point(10.0, 30.0), Point(50.0, 30.0)
        )
    )

    assert found.rounds == ()
    rounds = [r for r in found.repeats if isinstance(r.one, Round)]
    (grid,) = rounds
    assert sorted((round(abs(s.along)), s.count) for s in grid.steps) == [(20, 2), (40, 2)]


def test_bosses_of_different_sizes_do_not_repeat_each_other() -> None:
    found = survey(
        _joined(
            _box(60.0, 40.0, 3.0),
            _prism(2.0, 24, 4.0, Point(10.0, 20.0, 3.0)),
            _prism(3.0, 24, 4.0, Point(30.0, 20.0, 3.0)),
            _prism(2.0, 24, 4.0, Point(50.0, 20.0, 3.0)),
        )
    )

    assert found.repeats == ()
    assert sorted(round(r.radius) for r in found.rounds) == [2, 2, 3]


def test_an_uneven_spacing_is_not_a_repetition() -> None:
    found = survey(_plate_with_bosses(Point(10.0, 20.0), Point(30.0, 20.0), Point(45.0, 20.0)))

    assert found.repeats == ()
    assert len(found.rounds) == 3


# ---- helpers ---------------------------------------------------------------------------


def _bounds(mesh: Mesh) -> tuple[float, ...]:
    """The mesh's own extent, read straight off its buffer."""
    return (
        min(mesh.vertices[0::3]),
        min(mesh.vertices[1::3]),
        min(mesh.vertices[2::3]),
        max(mesh.vertices[0::3]),
        max(mesh.vertices[1::3]),
        max(mesh.vertices[2::3]),
    )
