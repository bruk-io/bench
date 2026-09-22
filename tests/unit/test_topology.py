"""Unit: :mod:`bench.topology` alone - what `wire`, `face` and `polygon` accept, what the
curves measure, what a move does to a labelled face, and what the tree a solid holds can
say about its own faces before anything builds them."""

import math
from typing import cast

import pytest

from bench import (
    CHORD,
    ORIGIN,
    XY,
    Arc,
    Axis,
    Bounds,
    Circle,
    Edge,
    Face,
    FaceRole,
    Label,
    Line,
    Mesh,
    Plane,
    Point,
    Ring,
    Solid,
    Vector,
    Wire,
    bounds,
    chord_step,
    circle,
    curve_end,
    curve_length,
    curve_start,
    face,
    faces_of,
    foot_chamfer,
    holed,
    identity,
    imported,
    label,
    lifted,
    move,
    near,
    plane,
    polygon,
    profile_frame,
    profile_rings,
    rect,
    rounded_rect,
    to_local,
    translation,
    wire,
)
from bench.topology import (
    Difference,
    Extrude,
    Hull,
    Intersection,
    Revolve,
    Union,
    moved,
    node_children,
)

pytestmark = pytest.mark.unit


# ---- curves ------------------------------------------------------------------------


def test_a_line_runs_from_its_start_to_its_end() -> None:
    c = Line(Point(1, 2), Point(4, 6))
    assert curve_start(c) == Point(1, 2)
    assert curve_end(c) == Point(4, 6)
    assert curve_length(c) == pytest.approx(5.0)


def test_an_arc_starts_and_ends_where_its_angles_say() -> None:
    c = Arc(Point(10, 10), 5.0, 0.0, math.pi / 2, XY)
    assert near(curve_start(c), Point(15, 10))
    assert near(curve_end(c), Point(10, 15))
    assert curve_length(c) == pytest.approx(5 * math.pi / 2)


def test_a_circle_ends_where_it_started_and_is_as_long_as_its_circumference() -> None:
    c = Circle(Point(2, 3), 4.0, XY)
    assert near(curve_start(c), Point(6, 3))
    assert curve_end(c) == curve_start(c)
    assert curve_length(c) == pytest.approx(8 * math.pi)


# ---- constructors ------------------------------------------------------------------


def test_a_wire_needs_an_edge() -> None:
    with pytest.raises(ValueError, match="at least one edge"):
        wire(())


def test_wire_rejects_gaps_and_face_rejects_open_wires() -> None:
    a = Edge(Line(Point(0, 0), Point(10, 0)))
    b = Edge(Line(Point(11, 0), Point(10, 10)))
    with pytest.raises(ValueError):
        wire((a, b))
    open_wire = wire((a, Edge(Line(Point(10, 0), Point(10, 10)))))
    with pytest.raises(ValueError):
        face(open_wire)


def test_moved_keeps_labels() -> None:
    f = face(rect(10, 10, label=Label("outline")), label=Label("front"))
    g = moved(f, translation(Vector(0, 0, 5)))
    assert g.label == Label("front")
    first = g.outer.edges[0].curve
    assert isinstance(first, Line)
    assert near(first.start, Point(0, 0, 5))


def test_polygon_needs_three_distinct_points() -> None:
    with pytest.raises(ValueError, match="at least three points"):
        polygon((Point(0, 0), Point(1, 1)))


def test_polygon_rejects_points_that_land_on_each_other() -> None:
    with pytest.raises(ValueError, match="coincide"):
        polygon((Point(0, 0), Point(10, 0), Point(10, 0), Point(10, 10)))
    # the wrap-around pair counts as consecutive too
    with pytest.raises(ValueError, match="coincide"):
        polygon((Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 0)))


# ---- labels ------------------------------------------------------------------------


def test_a_label_is_one_segment_of_a_ref() -> None:
    assert label("front") == Label("front")
    assert label(Label("side-left")) == Label("side-left")


def test_a_label_cannot_be_empty_or_hold_a_separator() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        label("")
    with pytest.raises(ValueError, match="joins labels into a ref"):
        label("drawer/front")


def test_every_constructor_takes_a_plain_string_and_checks_it() -> None:
    assert rect(10, 10, label="outline").label == Label("outline")
    assert polygon((Point(0, 0), Point(1, 0), Point(1, 1)), "tri").label == Label("tri")
    assert face(rect(10, 10), label="front").label == Label("front")
    with pytest.raises(ValueError, match="joins labels into a ref"):
        rect(10, 10, label="a/b")
    with pytest.raises(ValueError, match="joins labels into a ref"):
        face(rect(10, 10), label="a/b")


# ---- self-intersection -------------------------------------------------------------


def test_a_bowtie_outline_is_refused_and_says_which_edges_cross() -> None:
    with pytest.raises(ValueError, match=r"crosses itself between edge 1 and edge 3"):
        polygon((Point(0, 0), Point(10, 0), Point(0, 10), Point(10, 10)))


def test_a_concave_finger_outline_is_not_a_crossing() -> None:
    """Every notch of a finger joint doubles back on itself without ever crossing, and the
    corners where a run meets a notch only touch."""
    fingered = polygon(
        (
            Point(0, 0),
            Point(10, 0),
            Point(10, 3),
            Point(20, 3),
            Point(20, 0),
            Point(30, 0),
            Point(30, 12),
            Point(20, 12),
            Point(20, 9),
            Point(10, 9),
            Point(10, 12),
            Point(0, 12),
        )
    )
    assert len(fingered.edges) == 12


def test_a_wire_that_only_touches_itself_at_an_end_is_allowed() -> None:
    """An offset mitre can walk a corner right onto another edge's end; that is touching,
    not crossing, and kerf compensation relies on it going through."""
    touching = wire(
        (
            Edge(Line(Point(0, 0), Point(10, 0))),
            Edge(Line(Point(10, 0), Point(5, 5))),
            Edge(Line(Point(5, 5), Point(5, 0))),  # lands on the first edge, end to body
            Edge(Line(Point(5, 0), Point(0, 0))),
        )
    )
    assert len(touching.edges) == 4


def test_a_wire_with_an_arc_in_it_goes_through_unchecked() -> None:
    crossing_with_a_curve = wire(
        (
            Edge(Line(ORIGIN, Point(10, 0))),
            Edge(Arc(Point(10, 5), 5.0, -math.pi / 2, math.pi / 2, XY)),
            Edge(Line(Point(10, 10), Point(0, 10))),
            Edge(Line(Point(0, 10), Point(10, 5))),  # cuts straight across the others
            Edge(Line(Point(10, 5), ORIGIN)),
        )
    )
    assert len(crossing_with_a_curve.edges) == 5


# ---- the tree a solid holds ------------------------------------------------------------


def _named_square(*, holes: tuple[Wire, ...] = (), on: Plane = XY) -> Face:
    """A 10 mm square whose four edges carry the names a finger joint gives them - which is
    exactly the collision the ``side-`` prefix exists for."""
    corners = (ORIGIN, Point(10, 0), Point(10, 10), Point(0, 10))
    names = ("bottom", "right", "top", "left")
    edges = tuple(
        Edge(Line(a, b), label(n))
        for a, b, n in zip(corners, (*corners[1:], corners[0]), names, strict=True)
    )
    return face(wire(edges), holes=holes, on=on)


def _plain_square(side: float = 10.0, at: Point = ORIGIN) -> Face:
    return face(
        polygon(
            (
                at,
                at + Vector(side, 0),
                at + Vector(side, side),
                at + Vector(0, side),
            )
        )
    )


def test_an_extrusion_names_a_top_a_bottom_a_side_per_edge_and_a_face_per_hole() -> None:
    profile = _named_square(
        holes=(
            polygon((Point(2, 2), Point(3, 2), Point(3, 3), Point(2, 3)), Label("vent")),
            polygon((Point(6, 6), Point(7, 6), Point(7, 7), Point(6, 7))),
        )
    )
    faces = faces_of(Solid(Extrude(profile, 4.0), Label("panel")))
    assert tuple(f.label for f in faces) == (
        Label("top"),
        Label("bottom"),
        Label("side-bottom"),
        Label("side-right"),
        Label("side-top"),
        Label("side-left"),
        Label("vent"),
        Label("hole-1"),
    )
    assert tuple(f.role for f in faces[:2]) == (FaceRole.TOP, FaceRole.BOTTOM)
    assert {f.role for f in faces[2:]} == {FaceRole.SIDE}


def test_an_unlabelled_edge_earns_its_index_and_a_round_one_has_no_plane() -> None:
    profile = face(wire((Edge(Circle(ORIGIN, 5.0, XY)),)))
    (_, _, side) = faces_of(Solid(Extrude(profile, 3.0)))
    assert side.label == Label("side-0")
    assert side.plane is None


def test_a_round_side_carries_the_axis_it_turns_about_instead_of_a_plane() -> None:
    """No single plane, but a plane at every point of it: the axis, the radius and where
    zero points are what :func:`bench.solids.plane_of` builds one out of."""
    profile = face(wire((Edge(Circle(Point(2, 3), 5.0, XY)),)))
    (_, _, side) = faces_of(Solid(Extrude(profile, 3.0)))
    assert side.curved is not None
    assert near(side.curved.axis.origin, Point(2, 3, 0))
    assert near(side.curved.axis.direction, Vector(0, 0, 1))
    assert near(side.curved.zero, Vector(1, 0, 0))
    assert side.curved.radius == pytest.approx(5.0)
    assert side.curved.outward, "the material is inside a boss"


def test_a_round_hole_is_curved_the_other_way_round_and_a_square_one_is_not_curved() -> None:
    bored = face(_plain_square().outer, holes=(wire((Edge(Circle(Point(5, 5), 2.0, XY)),)),))
    (_, _, _, _, _, _, hole) = faces_of(Solid(Extrude(bored, 3.0)))
    assert hole.curved is not None and not hole.curved.outward
    squared = face(_plain_square().outer, holes=(_plain_square(4.0, Point(3, 3)).outer,))
    assert faces_of(Solid(Extrude(squared, 3.0)))[-1].curved is None


def test_an_extrusions_ends_sit_at_the_sweep_and_face_out_of_the_material() -> None:
    up = faces_of(Solid(Extrude(_plain_square(), 4.0)))
    top, bottom = up[0], up[1]
    assert top.plane is not None
    assert bottom.plane is not None
    assert near(top.plane.origin, Point(0, 0, 4))
    assert near(top.plane.normal, Vector(0, 0, 1))
    assert near(bottom.plane.origin, ORIGIN)
    assert near(bottom.plane.normal, Vector(0, 0, -1))


def test_a_negative_sweep_puts_top_at_the_distance_and_turns_both_ends_over() -> None:
    """``top`` is the face at ``distance`` whichever way the sweep runs, and both normals
    still point out of the material."""
    down = faces_of(Solid(Extrude(_plain_square(), -4.0)))
    top, bottom = down[0], down[1]
    assert top.plane is not None
    assert bottom.plane is not None
    assert near(top.plane.origin, Point(0, 0, -4))
    assert near(top.plane.normal, Vector(0, 0, -1))
    assert near(bottom.plane.normal, Vector(0, 0, 1))


def test_a_side_is_the_plane_the_edge_sweeps_with_the_edge_as_its_own_x() -> None:
    faces = faces_of(Solid(Extrude(_plain_square(), 4.0)))
    front = faces[2]
    assert front.plane is not None
    assert near(front.plane.origin, ORIGIN)
    assert near(front.plane.normal, Vector(0, -1, 0))
    assert near(front.plane.x_dir, Vector(1, 0, 0))
    assert near(front.plane.y_dir, Vector(0, 0, 1))


def test_a_full_revolve_names_only_its_sides_and_a_partial_one_names_its_ends() -> None:
    profile = _plain_square(at=Point(2, 0, 0))
    axis = Axis(ORIGIN, Vector(0, 1, 0))
    whole = faces_of(Solid(Revolve(profile, axis), Label("knob")))
    assert tuple(f.label for f in whole) == (
        Label("side-0"),
        Label("side-1"),
        Label("side-2"),
        Label("side-3"),
    )
    assert all(f.plane is None for f in whole)
    part_turn = faces_of(Solid(Revolve(profile, axis, math.pi / 2), Label("knob")))
    assert tuple(f.label for f in part_turn[-2:]) == (Label("start"), Label("end"))
    assert tuple(f.role for f in part_turn[-2:]) == (FaceRole.START, FaceRole.END)
    start, end = part_turn[-2], part_turn[-1]
    assert start.plane is not None
    assert end.plane is not None
    # a quarter turn about +Y carries the profile down into -Z, so both ends face away
    # from the material it swept: the start upward, the end back along -X.
    assert near(start.plane.normal, Vector(0, 0, 1))
    assert near(end.plane.normal, Vector(-1, 0, 0))


def test_a_boolean_names_nothing_of_its_own_and_hands_back_its_operands() -> None:
    base = Solid(Extrude(_plain_square(), 4.0))
    tool = Solid(Extrude(_plain_square(2.0), 1.0), Label("pocket"))
    for node in (
        Union(base, tool),
        Difference(base, tool),
        Intersection(base, tool),
    ):
        assert faces_of(Solid(node)) == ()
        assert node_children(node, identity()) == (base, tool)


def test_a_hull_names_nothing_under_it_at_all() -> None:
    """Identity does not survive a hull: the kernel builds one from a point cloud, so the
    parts that went in are unreachable as refs and the body answers to its own label only."""
    parts = (Solid(Extrude(_plain_square(), 1.0), Label("small")),)
    assert node_children(Hull(parts), identity()) == ()
    assert faces_of(Solid(Hull(parts), Label("taper"))) == ()


def test_a_move_renames_nothing_and_carries_the_planes_with_it() -> None:
    flat = Solid(Extrude(_plain_square(), 4.0), Label("panel"))
    lifted = moved(flat, translation(Vector(0, 0, 10)))
    assert lifted.label == Label("panel")
    assert tuple(f.label for f in faces_of(lifted)) == tuple(f.label for f in faces_of(flat))
    top = faces_of(lifted)[0]
    assert top.plane is not None
    assert near(top.plane.origin, Point(0, 0, 14))


def test_a_move_over_a_boolean_reaches_the_faces_under_it() -> None:
    tool = Solid(Extrude(_plain_square(2.0), 1.0), Label("pocket"))
    body = moved(
        Solid(Difference(Solid(Extrude(_plain_square(), 4.0)), tool)), translation(Vector(0, 0, 10))
    )
    found = node_children(body.node, identity())
    assert tuple(one.label for one in found) == (None, Label("pocket"))
    floor = faces_of(cast("Solid", found[1]))[1]
    assert floor.plane is not None
    assert near(floor.plane.origin, Point(0, 0, 10))


# ---- bounds ----------------------------------------------------------------------------


def test_bounds_of_an_extrusion_covers_the_sweep() -> None:
    assert bounds(Solid(Extrude(_plain_square(), 4.0))) == pytest.approx((0, 0, 0, 10, 10, 4))
    assert bounds(_plain_square()) == pytest.approx((0, 0, 0, 10, 10, 0))


def test_bounds_of_a_union_covers_both_and_a_move_carries_it() -> None:
    here = Solid(Extrude(_plain_square(), 4.0))
    there = moved(Solid(Extrude(_plain_square(), 2.0)), translation(Vector(20, 0, 0)))
    assert bounds(Solid(Union(here, there))) == pytest.approx((0, 0, 0, 30, 10, 4))


def test_bounds_is_conservative_under_a_cut_and_an_intersection() -> None:
    """A tool that bites the whole body away still leaves the base's bound: whether it
    really bit is the kernel's answer, and a bound that is too big never passes a part that
    will not fit."""
    base = Solid(Extrude(_plain_square(), 4.0))
    tool = Solid(Extrude(_plain_square(100.0), 40.0), Label("everything"))
    assert bounds(Solid(Difference(base, tool))) == pytest.approx((0, 0, 0, 10, 10, 4))
    assert bounds(Solid(Intersection(base, tool))) == pytest.approx((0, 0, 0, 10, 10, 4))
    assert bounds(Solid(Intersection(tool, base))) == pytest.approx((0, 0, 0, 100, 100, 40))


def test_bounds_of_a_partial_revolve_is_the_whole_turn_it_is_part_of() -> None:
    quarter = Solid(
        Revolve(_plain_square(at=Point(2, 0, 0)), Axis(ORIGIN, Vector(0, 1, 0)), math.pi / 2)
    )
    assert bounds(quarter) == pytest.approx((-12, 0, -12, 12, 10, 12))


def test_a_hull_of_nothing_has_no_bound() -> None:
    with pytest.raises(ValueError):
        bounds(Solid(Hull(())))


# ---- a sketch drawn on a plane ----------------------------------------------------------


def _tilted() -> Plane:
    """A plane that is neither ``XY`` nor parallel to it: origin off the world origin, and
    turned so that a lift changes every coordinate rather than only one."""
    return plane(Point(3, 4, 5), Vector(1, 1, 1), Vector(1, -1, 0))


def test_a_wire_lifted_onto_xy_is_the_wire_itself() -> None:
    """``XY``'s frame is the world's, so its lift is the identity - and not merely an equal
    value: the very object comes back, which is what keeps every flat drawing in the package
    exactly what it was before there were other planes to draw on."""
    flat = rect(10, 6)
    assert lifted(flat, XY) is flat
    assert face(flat).outer is flat


def test_a_wire_is_read_in_the_planes_frame_and_lifted_into_the_world() -> None:
    """What ``on=`` means: the profile's own ten by six, put where the plane is."""
    on = _tilted()
    raised_ring = lifted(rect(10, 6), on)
    corners = tuple(curve_start(e.curve) for e in raised_ring.edges)
    assert near(corners[0], on.origin)
    assert near(corners[1], on.origin + on.x_dir * 10)
    assert near(corners[2], on.origin + on.x_dir * 10 + on.y_dir * 6)
    assert near(corners[3], on.origin + on.y_dir * 6)


def test_lifting_a_wire_and_reading_it_back_gives_the_numbers_it_was_drawn_with() -> None:
    """The round trip: a wire lifted onto a plane and mapped back into that plane's own
    coordinates is where it started, so nothing is lost on the way up."""
    on = _tilted()
    drawn = rounded_rect(20, 12, 3, Point(-2, 1))
    there = lifted(drawn, on)
    back = tuple(curve_start(e.curve) for e in moved(there, to_local(on)).edges)
    for was, now in zip(tuple(curve_start(e.curve) for e in drawn.edges), back, strict=True):
        assert near(was, now)


def test_a_face_lifts_its_holes_with_its_outline() -> None:
    on = _tilted()
    plate = face(rect(20, 20), holes=(circle(2, Point(10, 10)),), on=on)
    hole = plate.inner[0].edges[0].curve
    assert isinstance(hole, Circle)
    assert near(hole.centre, on.origin + on.x_dir * 10 + on.y_dir * 10)
    assert near(hole.plane.normal, on.normal)


def test_a_hole_added_later_is_read_in_the_faces_own_frame() -> None:
    """:func:`holed` is the second arm of ``cut`` written where the checks live: the face
    keeps its plane, its outline and its label, and only the new wire is lifted."""
    on = _tilted()
    plate = face(rect(20, 20), on=on, label="plate")
    more = holed(plate, circle(2, Point(5, 5)))
    assert more.plane == plate.plane
    assert more.outer is plate.outer
    assert more.label == Label("plate")
    added = more.inner[0].edges[0].curve
    assert isinstance(added, Circle)
    assert near(added.centre, on.origin + on.x_dir * 5 + on.y_dir * 5)
    with pytest.raises(ValueError, match="hole in a face must be closed"):
        holed(plate, wire((Edge(Line(ORIGIN, Point(1, 0))),)))


# ---- the rings a kernel builds a swept body from -----------------------------------------


def _rounded(ring: Ring) -> tuple[tuple[float, float], ...]:
    """A ring's points to the nearest nanometre, so a lift and its inverse read as the whole
    numbers they were drawn with."""
    return tuple((round(u, 9) + 0.0, round(v, 9) + 0.0) for u, v in ring.points)


def test_an_extrusions_rings_are_the_profile_in_its_own_frame_with_the_faces_they_sweep() -> None:
    """``profile_rings`` is what a kernel extrudes and what it tags with: the outer wire
    first, holes after it, and each step carrying the index of the face it sweeps - ``2``
    onwards for an extrusion, because ``top`` and ``bottom`` come first."""
    on = _tilted()
    node = Extrude(face(rect(10, 6), holes=(rect(2, 2, Point(4, 2)),), on=on), 3.0)
    outer, hole = profile_rings(node)
    assert _rounded(outer) == ((0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0))
    assert outer.faces == (2, 3, 4, 5)
    assert _rounded(hole) == ((4.0, 2.0), (6.0, 2.0), (6.0, 4.0), (4.0, 4.0))
    assert hole.faces == (6, 6, 6, 6)
    assert profile_frame(node) is on


def test_a_round_edge_is_cut_into_chords_that_stay_within_the_one_tolerance() -> None:
    """One chord rule for the whole package, driven by the radius: every step's midpoint is
    within :data:`~bench.topology.CHORD` of the true circle, and no finer than it needs to
    be."""
    radius = 8.0
    (ring,) = profile_rings(Extrude(face(circle(radius)), 1.0))
    assert len(ring.points) == math.ceil(math.tau / chord_step(radius))
    assert set(ring.faces) == {2}
    for (x0, y0), (x1, y1) in zip(ring.points, (*ring.points[1:], ring.points[0]), strict=True):
        middle = math.hypot((x0 + x1) / 2, (y0 + y1) / 2)
        assert 0.0 < radius - middle <= CHORD


def test_a_revolves_rings_measure_out_from_the_axis_and_along_it() -> None:
    """A kernel turns a cross-section about its own vertical, so the profile is handed over
    as ``(r, h)`` and ``profile_frame`` says where to put the result: normal along the axis,
    X pointing at the profile."""
    profile = face(rect(5, 3, Point(5, 2)))
    node = Revolve(profile, Axis(ORIGIN, Vector(1, 0, 0)), math.pi)
    (ring,) = profile_rings(node)
    assert sorted(_rounded(ring)) == [(2.0, 5.0), (2.0, 10.0), (5.0, 5.0), (5.0, 10.0)]
    assert ring.faces == (0, 1, 2, 3)
    frame = profile_frame(node)
    assert near(frame.normal, Vector(1, 0, 0))
    assert near(frame.x_dir, Vector(0, 1, 0))


def test_a_revolve_finds_the_side_of_the_axis_its_profile_is_on() -> None:
    """Only the positive half of a cross-section is turned, so which half that is has to be
    settled before anything is built - the profile below the axis comes back with the same
    radii as the one above it."""
    above = Revolve(face(rect(4, 2, Point(0, 3))), Axis(ORIGIN, Vector(1, 0, 0)), math.tau)
    below = Revolve(face(rect(4, 2, Point(0, -5))), Axis(ORIGIN, Vector(1, 0, 0)), math.tau)
    assert sorted({round(v, 9) for _, v in profile_rings(above)[0].points}) == [0.0, 4.0]
    assert sorted({round(u, 9) for u, _ in profile_rings(above)[0].points}) == [3.0, 5.0]
    assert sorted({round(u, 9) for u, _ in profile_rings(below)[0].points}) == [3.0, 5.0]
    assert near(profile_frame(above).x_dir, -profile_frame(below).x_dir)


# ---- a mesh somebody else made ----------------------------------------------------------


def _cube_mesh() -> Mesh:
    """A 10 mm cube as a bare mesh, the way a host hands a dropped STL over."""
    corners = (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (0.0, 10.0, 0.0),
        (0.0, 0.0, 10.0),
        (10.0, 0.0, 10.0),
        (10.0, 10.0, 10.0),
        (0.0, 10.0, 10.0),
    )
    faces = ((0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7))
    return Mesh(
        tuple(value for corner in corners for value in corner),
        tuple(corner for face_ in faces for corner in face_),
        (None,) * len(faces),
    )


def test_an_import_bounds_itself_exactly_from_its_own_vertices() -> None:
    """The one node whose extent needs no kernel and is not a conservative guess: an
    import's vertices *are* its boundary, so the bound read off them is the body's own."""
    assert bounds(imported(_cube_mesh())) == pytest.approx(Bounds(0, 0, 0, 10, 10, 10))


def test_an_import_carries_its_move_into_the_bound_it_answers_with() -> None:
    """A move is recorded rather than done, so the points come back through the transform
    above them - the same rule every other node's extent is read under."""
    moved_ = move(imported(_cube_mesh()), Vector(100, -50, 7))
    assert bounds(moved_) == pytest.approx(Bounds(100, -50, 7, 110, -40, 17))


def test_an_import_names_nothing_under_itself() -> None:
    """A file somebody else wrote has no names in it to keep, so the whole body answers to
    the label it was given and there is nothing beneath it - the rule a hull is already
    under, for the same reason."""
    assert faces_of(imported(_cube_mesh(), label="dropped")) == ()
    assert imported(_cube_mesh(), label="dropped").label == Label("dropped")


def test_an_import_has_no_extruded_root_to_chamfer_a_foot_on() -> None:
    """An import is not a sweep and never had a footprint, so the verbs that need one refuse
    it by name rather than guessing at a profile it does not have."""
    with pytest.raises(ValueError, match="extruded from a profile"):
        foot_chamfer(imported(_cube_mesh()), 0.5)
