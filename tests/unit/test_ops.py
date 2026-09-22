import math
import re

import pytest

from bench import (
    ORIGIN,
    XY,
    Arc,
    Axis,
    Circle,
    Curve,
    Edge,
    Label,
    Line,
    Plane,
    Point,
    Printed,
    Ref,
    Solid,
    Top,
    Turn,
    Vector,
    Wire,
    X,
    Y,
    Z,
    area,
    bbox,
    boss,
    bounds,
    bridge_steps,
    centroid,
    chamfer,
    circle,
    contains,
    cuboid,
    curve_start,
    cut,
    cylinder,
    edge,
    edges,
    extrude,
    faces_of,
    fill,
    foot_chamfer,
    grid,
    hull,
    is_ccw,
    is_closed,
    line,
    loft,
    mirror,
    move,
    name,
    near,
    offset,
    pattern,
    perimeter,
    plane,
    plane_of,
    pocket,
    polygon,
    printable_top,
    profile_rings,
    raised,
    rect,
    refs,
    revolve,
    rotate,
    rounded_rect,
    slot,
    teardrop,
    text_width,
    to_world,
    union,
    wire,
)
from bench.library.print import ASA, PLA
from bench.topology import Extrude

pytestmark = pytest.mark.unit


def _line(e: Edge) -> Line:
    """The straight curve of an edge that is meant to have one."""
    assert isinstance(e.curve, Line)
    return e.curve


def _starts(w: Wire) -> tuple[tuple[float, float], ...]:
    out: list[tuple[float, float]] = []
    for e in w.edges:
        c = e.curve
        assert isinstance(c, Line)
        out.append((round(c.start.x, 9), round(c.start.y, 9)))
    return tuple(out)


# ---- constructors ------------------------------------------------------------------


def test_rect_is_counter_clockwise_and_closed() -> None:
    r = rect(10, 4, Point(1, 2), Label("outline"))
    assert is_closed(r) and is_ccw(r)
    assert r.label == Label("outline")
    assert bbox(r) == (1, 2, 11, 6)
    assert perimeter(r) == 28


def test_line_is_an_open_wire_of_one_straight_edge() -> None:
    ln = line(Point(1, 1), Point(9, 1), Label("reference"))
    assert len(ln.edges) == 1
    assert not is_closed(ln)
    assert ln.label == Label("reference")
    only_edge = ln.edges[0]
    assert isinstance(only_edge.curve, Line)
    assert (only_edge.curve.start, only_edge.curve.end) == (Point(1, 1), Point(9, 1))
    assert perimeter(ln) == 8
    assert line(Point(0, 0), Point(3, 4)).label is None


def test_line_rejects_coincident_ends() -> None:
    with pytest.raises(ValueError):
        line(Point(1, 1), Point(1, 1))


def test_circle_is_one_edge_with_the_area_of_a_circle() -> None:
    c = circle(5, Point(2, 3))
    assert len(c.edges) == 1
    assert isinstance(c.edges[0].curve, Circle)
    assert is_closed(c) and is_ccw(c)
    assert area(fill(c)) == pytest.approx(math.pi * 25)
    assert perimeter(c) == pytest.approx(2 * math.pi * 5)
    assert bbox(c) == pytest.approx((-3, -2, 7, 8))


def test_circle_needs_a_positive_radius() -> None:
    with pytest.raises(ValueError):
        circle(0)


def test_slot_is_a_stadium_of_two_lines_and_two_arcs() -> None:
    s = slot(20, 10)
    kinds = tuple(type(e.curve).__name__ for e in s.edges)
    assert kinds == ("Line", "Arc", "Line", "Arc")
    assert is_closed(s) and is_ccw(s)
    assert bbox(s) == pytest.approx((0, 0, 20, 10))
    assert area(fill(s)) == pytest.approx(10 * 10 + math.pi * 25)
    assert perimeter(s) == pytest.approx(2 * 10 + math.pi * 10)


def test_slot_must_be_longer_than_it_is_high() -> None:
    with pytest.raises(ValueError):
        slot(10, 10)
    with pytest.raises(ValueError):
        slot(10, 0)


def test_rounded_rect_trades_corners_for_arcs() -> None:
    rr = rounded_rect(20, 10, 2)
    assert len(rr.edges) == 8
    assert is_closed(rr) and is_ccw(rr)
    assert bbox(rr) == pytest.approx((0, 0, 20, 10))
    assert area(fill(rr)) == pytest.approx(200 - (4 - math.pi) * 4)
    assert tuple(centroid(fill(rr))) == pytest.approx((10, 5, 0))


def test_rounded_rect_with_no_radius_is_a_rect_and_too_much_radius_raises() -> None:
    assert rounded_rect(10, 4, 0) == rect(10, 4)
    with pytest.raises(ValueError):
        rounded_rect(10, 4, 3)
    with pytest.raises(ValueError):
        rounded_rect(10, 4, -1)


# ---- face builders -----------------------------------------------------------------


def test_fill_and_cut_build_a_face_with_labelled_holes() -> None:
    f = fill(rect(20, 20, label=Label("outline")), label=Label("front"))
    assert f.label == Label("front") and f.inner == ()
    holed = cut(f, rect(10, 10, Point(5, 5)), label=Label("window"))
    assert holed.label == Label("front")
    assert holed.inner[0].label == Label("window")
    assert area(holed) == 300
    assert area(f) == 400


def test_cut_rejects_an_open_hole() -> None:
    open_wire = wire((Edge(Line(Point(0, 0), Point(1, 0))),))
    with pytest.raises(ValueError):
        cut(fill(rect(10, 10)), open_wire, label=Label("hole"))


# ---- offset ------------------------------------------------------------------------


def test_offset_grows_a_counter_clockwise_wire_and_shrinks_it_the_other_way() -> None:
    r = rect(10, 10)
    assert bbox(offset(r, 1)) == pytest.approx((-1, -1, 11, 11))
    assert bbox(offset(r, -1)) == pytest.approx((1, 1, 9, 9))
    assert area(fill(offset(r, 1))) == pytest.approx(144)


def test_offset_of_a_clockwise_wire_moves_the_other_way() -> None:
    cw = polygon((Point(0, 0), Point(0, 10), Point(10, 10), Point(10, 0)))
    assert not is_ccw(cw)
    assert bbox(offset(cw, 1)) == pytest.approx((1, 1, 9, 9))


def test_offset_mitres_concave_corners() -> None:
    u = polygon(
        (
            Point(0, 0),
            Point(10, 0),
            Point(10, 10),
            Point(7, 10),
            Point(7, 4),
            Point(3, 4),
            Point(3, 10),
            Point(0, 10),
        )
    )
    grown = offset(u, 1)
    assert _starts(grown) == (
        (-1, -1),
        (11, -1),
        (11, 11),
        (6, 11),
        (6, 5),
        (4, 5),
        (4, 11),
        (-1, 11),
    )
    assert area(fill(grown)) == pytest.approx(132)


def test_offset_changes_arc_radii_and_keeps_tangency() -> None:
    rr = rounded_rect(20, 10, 2)
    grown = offset(rr, 1)
    assert bbox(grown) == pytest.approx((-1, -1, 21, 11))
    assert area(fill(grown)) == pytest.approx(22 * 12 - (4 - math.pi) * 9)
    radii = tuple(e.curve.radius for e in grown.edges if isinstance(e.curve, Arc))
    assert radii == pytest.approx((3, 3, 3, 3))


def test_offset_of_a_circle_only_wire_changes_the_radius() -> None:
    c = offset(circle(5, Point(2, 3)), 1)
    only = c.edges[0].curve
    assert isinstance(only, Circle)
    assert only.radius == pytest.approx(6)
    assert only.centre == Point(2, 3)


def test_offset_of_a_face_grows_the_outline_and_shrinks_the_holes() -> None:
    f = cut(
        fill(rect(20, 20), label=Label("front")), rect(10, 10, Point(5, 5)), label=Label("hole")
    )
    kerfed = offset(f, 1)
    assert kerfed.label == Label("front")
    assert bbox(kerfed.outer) == pytest.approx((-1, -1, 21, 21))
    assert bbox(kerfed.inner[0]) == pytest.approx((6, 6, 14, 14))
    assert kerfed.inner[0].label == Label("hole")
    assert area(kerfed) == pytest.approx(22 * 22 - 64)


def test_offset_shrinks_a_round_hole_whichever_way_its_wire_runs() -> None:
    f = cut(fill(rect(20, 20), label=Label("front")), circle(3, Point(10, 10)), label=Label("hole"))
    kerfed = offset(f, 0.5)
    assert bbox(kerfed.inner[0]) == pytest.approx((7.5, 7.5, 12.5, 12.5))
    assert area(kerfed) == pytest.approx(21 * 21 - math.pi * 2.5**2)


def test_offset_that_eats_an_arc_raises() -> None:
    with pytest.raises(ValueError, match="collapses"):
        offset(circle(2), -2)
    with pytest.raises(ValueError, match="collapses"):
        offset(rounded_rect(20, 10, 2), -2)


def test_offset_refuses_a_wire_that_does_not_lie_flat_in_xy() -> None:
    standing = polygon((Point(0, 0, 0), Point(10, 0, 0), Point(10, 0, 10), Point(0, 0, 10)))
    with pytest.raises(ValueError, match="parallel to XY"):
        offset(standing, 1.0)
    tilted = wire(
        (
            Edge(Arc(ORIGIN, 5, 0.0, math.pi, plane(ORIGIN, Vector(0, 1, 0), Vector(1, 0, 0)))),
            Edge(Line(Point(-5, 0, 0), Point(5, 0, 0))),
        )
    )
    with pytest.raises(ValueError, match="parallel to XY"):
        offset(tilted, 1.0)
    # a flat wire lifted off the XY plane is still parallel to it, so it offsets
    assert bbox(offset(move(rect(10, 10), Vector(0, 0, 7)), 1)) == pytest.approx((-1, -1, 11, 11))


def test_offset_of_a_face_on_another_plane_works_in_that_plane() -> None:
    """A bare wire has to lie in XY because nothing says which plane it is on. A face does
    say, so it is offset in its own plane - here one standing up in XZ, which grows in X
    and Z and not at all in Y."""
    standing = fill(
        polygon((Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10))),
        on=plane(ORIGIN, Vector(0, -1, 0), Vector(1, 0, 0)),
    )
    grown = offset(standing, 1.0)
    assert bbox(grown) == pytest.approx((-1, 0, 11, 0))
    assert area(grown) == pytest.approx(144.0)
    assert {round(p.y, 9) for e in grown.outer.edges for p in (_line(e).start, _line(e).end)} == {
        0.0
    }
    assert {round(p.z, 9) for e in grown.outer.edges for p in (_line(e).start, _line(e).end)} == {
        -1.0,
        11.0,
    }


def test_offset_retrims_an_arc_that_does_not_meet_its_neighbour_tangentially() -> None:
    pie = wire(
        (
            Edge(Line(ORIGIN, Point(10, 0))),
            Edge(Arc(ORIGIN, 10, 0.0, math.pi / 2, XY)),
            Edge(Line(Point(0, 10), ORIGIN)),
        )
    )
    assert is_ccw(pie)
    assert area(fill(pie)) == pytest.approx(math.pi * 100 / 4)
    grown = offset(pie, 1)
    assert tuple(type(e.curve).__name__ for e in grown.edges) == ("Line", "Arc", "Line")
    arc = grown.edges[1].curve
    assert isinstance(arc, Arc)
    assert arc.radius == pytest.approx(11)
    assert arc.start_angle < 0 < math.pi / 2 < arc.end_angle
    assert bbox(grown) == pytest.approx((-1, -1, 11, 11))
    assert is_closed(grown)


def test_offset_keeps_edge_labels_and_a_zero_offset_is_the_shape_itself() -> None:
    labelled = wire(
        (
            Edge(Line(Point(0, 0), Point(10, 0)), Label("bottom")),
            Edge(Line(Point(10, 0), Point(10, 10)), Label("right")),
            Edge(Line(Point(10, 10), Point(0, 10)), Label("top")),
            Edge(Line(Point(0, 10), Point(0, 0)), Label("left")),
        )
    )
    grown = offset(labelled, 2)
    assert tuple(e.label for e in grown.edges) == tuple(e.label for e in labelled.edges)
    assert offset(labelled, 0) == labelled


# ---- other modifiers ---------------------------------------------------------------


def test_move_and_rotate() -> None:
    assert bbox(move(rect(10, 2), Vector(5, 5))) == pytest.approx((5, 5, 15, 7))
    turned = rotate(fill(rect(10, 2), label=Label("f")), math.pi / 2)
    assert bbox(turned) == pytest.approx((-2, 0, 0, 10))
    assert turned.label == Label("f") and is_ccw(turned.outer)


def test_mirror_reflects_and_keeps_outlines_counter_clockwise() -> None:
    f = cut(
        fill(rect(20, 10), label=Label("side-left")), circle(2, Point(3, 5)), label=Label("hole")
    )
    flipped = mirror(f, Axis(Point(10, 0), Vector(0, 1)))
    assert bbox(flipped) == pytest.approx((0, 0, 20, 10))
    assert bbox(flipped.inner[0]) == pytest.approx((15, 3, 19, 7))
    assert area(flipped) == pytest.approx(area(f))
    assert is_ccw(flipped.outer) and is_ccw(flipped.inner[0])
    assert contains(flipped, Point(3, 5)) and not contains(flipped, Point(17, 5))


def test_mirror_of_an_arc_wire_is_the_mirror_image() -> None:
    rr = rounded_rect(20, 10, 2, Point(5, 0))
    flipped = mirror(rr, Axis(ORIGIN, Vector(0, 1)))
    assert bbox(flipped) == pytest.approx((-25, 0, -5, 10))
    assert is_ccw(flipped)
    assert area(fill(flipped)) == pytest.approx(area(fill(rr)))


def test_pattern_numbers_the_copies() -> None:
    holes = pattern(circle(1, Point(2, 2), Label("hole")), 3, Vector(5, 0))
    assert tuple(h.label for h in holes) == (Label("hole-1"), Label("hole-2"), Label("hole-3"))
    assert tuple(bbox(h).x0 for h in holes) == pytest.approx((1, 6, 11))
    assert pattern(circle(1), 1, Vector(5, 0))[0].label is None


def test_pattern_needs_a_copy() -> None:
    with pytest.raises(ValueError):
        pattern(rect(1, 1), 0, Vector(1, 0))


def test_name_renames_a_node_and_leaves_the_one_it_was_given_alone() -> None:
    f = fill(rect(10, 10), label=Label("front"))
    assert name(f, Label("back")).label == Label("back")
    assert name(f, "back") == name(f, Label("back"))
    assert f.label == Label("front")
    with pytest.raises(ValueError, match="joins labels into a ref"):
        name(f, "front/back")


def test_chamfer_cuts_the_corner_at_the_end_of_an_edge() -> None:
    r = wire(
        (
            Edge(Line(Point(0, 0), Point(10, 0)), Label("bottom")),
            Edge(Line(Point(10, 0), Point(10, 10)), Label("right")),
            Edge(Line(Point(10, 10), Point(0, 10)), Label("top")),
            Edge(Line(Point(0, 10), Point(0, 0)), Label("left")),
        ),
        Label("outline"),
    )
    cut_corner = chamfer(r, Label("bottom"), 2)
    assert len(cut_corner.edges) == 5
    assert is_closed(cut_corner) and is_ccw(cut_corner)
    assert cut_corner.label == Label("outline")
    assert area(fill(cut_corner)) == pytest.approx(98)
    assert _starts(cut_corner) == ((0, 0), (8, 0), (10, 2), (10, 10), (0, 10))
    assert chamfer(r, -1, 2) == chamfer(r, 3, 2)
    assert is_closed(chamfer(r, 3, 2))


def test_chamfer_rejects_a_bad_corner() -> None:
    r = rect(10, 10)
    with pytest.raises(ValueError):
        chamfer(r, 0, 0)
    with pytest.raises(ValueError):
        chamfer(r, 0, 20)
    with pytest.raises(LookupError):
        chamfer(r, Label("nope"), 2)
    with pytest.raises(LookupError):
        chamfer(r, 9, 2)
    with pytest.raises(ValueError):
        chamfer(circle(5), 0, 1)


# ---- selectors ---------------------------------------------------------------------


def test_edges_filters_by_direction_point_and_label() -> None:
    f = cut(fill(rect(10, 10, label=Label("outline"))), circle(2, Point(5, 5)), label=Label("hole"))
    assert len(edges(f)) == 5
    assert len(edges(f, direction=Vector(1, 0))) == 2
    assert len(edges(f, direction=Vector(0, 1))) == 2
    bottom = edge(f, near_point=Point(5, 0))
    assert isinstance(bottom.curve, Line)
    assert bottom.curve.start == Point(0, 0)
    assert len(edges(f, near_point=Point(7, 5))) == 1
    assert edges(f, label=Label("nope")) == ()


def test_edge_wants_exactly_one() -> None:
    f = fill(rect(10, 10))
    with pytest.raises(LookupError):
        edge(f, near_point=Point(50, 50))
    with pytest.raises(LookupError):
        edge(f, direction=Vector(1, 0))
    assert edge(f, near_point=Point(0, 0), direction=Vector(1, 0)).curve == Line(
        Point(0, 0), Point(10, 0)
    )


# ---- queries ----------------------------------------------------------------------


def _on(centre: Point, r: float, on: Plane, theta: float) -> Point:
    return centre + on.x_dir * (r * math.cos(theta)) + on.y_dir * (r * math.sin(theta))


def _walk(c: Curve, steps: int) -> tuple[Point, ...]:
    """One curve as many points along it, so an extent can be measured by brute force."""
    if isinstance(c, Line):
        return (c.start, c.end)
    if isinstance(c, Arc):
        span = c.end_angle - c.start_angle
        return tuple(
            _on(c.centre, c.radius, c.plane, c.start_angle + span * k / steps)
            for k in range(steps + 1)
        )
    return tuple(
        _on(c.centre, c.radius, c.plane, 2 * math.pi * k / steps) for k in range(steps + 1)
    )


def _dense(w: Wire, steps: int = 20_000) -> tuple[float, float, float, float]:
    points = tuple(p for e in w.edges for p in _walk(e.curve, steps))
    xs = tuple(p.x for p in points)
    ys = tuple(p.y for p in points)
    return (min(xs), min(ys), max(xs), max(ys))


def test_bbox_of_a_turned_circle_is_measured_against_the_world_axes() -> None:
    """A circle is as wide as its diameter whichever way its frame is turned; sampling the
    frame's own quarter turns instead makes the box too small everywhere but on the axes."""
    for turn in (0.0, 0.3, 0.7854, math.pi / 4, 1.0):
        spun = rotate(circle(7), turn)
        assert bbox(spun).w == pytest.approx(14.0, abs=1e-9), turn
        assert bbox(spun).h == pytest.approx(14.0, abs=1e-9), turn
        assert tuple(bbox(spun)) == pytest.approx((-7, -7, 7, 7), abs=1e-9)


def test_bbox_of_an_arc_wire_in_a_skew_frame_matches_a_dense_walk() -> None:
    skew = Axis(ORIGIN, Vector(math.cos(math.radians(20)), math.sin(math.radians(20))))
    flipped = mirror(slot(40, 10, Point(3, 2)), skew)
    assert tuple(bbox(flipped)) == pytest.approx(_dense(flipped), abs=1e-6)
    spun = rotate(rounded_rect(30, 12, 4), 0.7)
    assert tuple(bbox(spun)) == pytest.approx(_dense(spun), abs=1e-6)
    part_turn = rotate(slot(40, 10), 0.3)
    assert tuple(bbox(part_turn)) == pytest.approx(_dense(part_turn), abs=1e-6)


def test_bbox_follows_an_arc_past_its_ends() -> None:
    half = wire((Edge(Arc(ORIGIN, 5, 0.0, math.pi, XY)), Edge(Line(Point(-5, 0), Point(5, 0)))))
    assert bbox(half) == pytest.approx((-5, 0, 5, 5))
    assert bbox(fill(half)) == pytest.approx((-5, 0, 5, 5))
    assert bbox(BBOX_FACE) == pytest.approx((0, 0, 20, 20))


BBOX_FACE = cut(fill(rect(20, 20)), rect(5, 5, Point(3, 3)), label=Label("hole"))


def test_area_takes_out_the_holes_and_perimeter_walks_the_wire() -> None:
    assert area(BBOX_FACE) == 400 - 25
    assert perimeter(BBOX_FACE.outer) == 80
    assert perimeter(BBOX_FACE.inner[0]) == 20


def test_centroid_balances_a_face() -> None:
    ell = polygon(
        (Point(0, 0), Point(10, 0), Point(10, 5), Point(5, 5), Point(5, 10), Point(0, 10))
    )
    assert tuple(centroid(fill(ell))) == pytest.approx((25 / 6, 25 / 6, 0))
    assert tuple(centroid(fill(circle(4, Point(7, 9))))) == pytest.approx((7, 9, 0))
    offcentre = cut(fill(rect(20, 10)), rect(4, 4, Point(1, 3)), label=Label("hole"))
    assert centroid(offcentre).x == pytest.approx((200 * 10 - 16 * 3) / (200 - 16))


def test_centroid_of_a_face_with_no_area_raises() -> None:
    flat = wire(
        (Edge(Line(ORIGIN, Point(10, 0))), Edge(Line(Point(10, 0), ORIGIN))),
    )
    with pytest.raises(ValueError):
        centroid(fill(flat))


def test_is_ccw_sees_which_way_round_a_wire_goes() -> None:
    assert is_ccw(rect(10, 10))
    assert not is_ccw(polygon((Point(0, 0), Point(0, 10), Point(10, 10))))
    assert is_ccw(circle(3))


def test_a_solid_moves_mirrors_and_shadows_its_bounds_onto_xy() -> None:
    box = cuboid(10, 12, 4, label=Label("body"))
    assert bounds(box) == pytest.approx((0, 0, 0, 10, 12, 4))
    assert bbox(box) == pytest.approx((0, 0, 10, 12))
    assert bbox(move(box, Vector(1, 1))) == pytest.approx((1, 1, 11, 13))
    flipped = mirror(box, Axis(ORIGIN, Vector(0, 1)))
    assert bbox(flipped) == pytest.approx((-10, 0, 0, 12))
    assert flipped.label == Label("body")
    assert tuple(f.label for f in faces_of(flipped)) == tuple(f.label for f in faces_of(box))


def test_a_solid_is_bounded_in_z_as_well_as_across_the_bed() -> None:
    stood = rotate(cuboid(10, 12, 4), math.pi / 2, about=Axis(ORIGIN, X))
    assert bounds(stood) == pytest.approx((0, -4, 0, 10, 0, 12))
    assert bbox(stood) == pytest.approx((0, -4, 10, 0))


def test_contains_respects_holes() -> None:
    f = cut(fill(rect(20, 20)), circle(5, Point(10, 10)), label=Label("hole"))
    assert contains(f, Point(1, 1))
    assert not contains(f, Point(10, 10))
    assert not contains(f, Point(-1, 10))
    assert contains(f, Point(10, 16))


@pytest.mark.parametrize("r", [10.0, 500.0])
def test_contains_flattens_a_boundary_as_finely_as_its_radius_needs(r: float) -> None:
    """A fixed angular step puts the chords of a big circle millimetres inside it, so a
    point a thousandth of the radius in reads as outside. The step follows the radius."""
    disc = fill(circle(r))
    # no angle is spared, so whichever one falls between two chord ends is tried too
    for k in range(720):
        theta = 2 * math.pi * k / 720
        inside = Point(0.999 * r * math.cos(theta), 0.999 * r * math.sin(theta))
        outside = Point(1.001 * r * math.cos(theta), 1.001 * r * math.sin(theta))
        assert contains(disc, inside), theta
        assert not contains(disc, outside), theta


# ---- text ---------------------------------------------------------------------------


def test_text_width_scales_with_characters_and_cap_height() -> None:
    assert text_width("hi", 10.0) == pytest.approx(2 * 0.6 * 10.0)
    assert text_width("", 10.0) == pytest.approx(0.0)
    assert text_width("abc", 5.0) == pytest.approx(3 * text_width("a", 5.0))
    assert text_width("ab", 20.0) == pytest.approx(2 * text_width("ab", 10.0))


# ---- bodies ----------------------------------------------------------------------------


def _labels(solid: Solid) -> tuple[str, ...]:
    return tuple(str(f.label) for f in faces_of(solid))


def test_a_cuboid_is_a_labelled_rectangle_swept_so_its_sides_are_named() -> None:
    box = cuboid(20, 10, 4, label="body")
    assert box.label == Label("body")
    assert _labels(box) == ("top", "bottom", "side-front", "side-right", "side-back", "side-left")
    assert bounds(box) == pytest.approx((0, 0, 0, 20, 10, 4))


def test_a_cylinder_is_one_round_edge_swept_and_stands_where_it_is_put() -> None:
    post = cylinder(3, 8, at=Point(5, 5, 2))
    assert _labels(post) == ("top", "bottom", "side-0")
    assert bounds(post) == pytest.approx((2, 2, 2, 8, 8, 10))


def test_an_extrusion_needs_a_distance_and_a_pocket_a_depth() -> None:
    with pytest.raises(ValueError, match="distance to sweep"):
        extrude(fill(rect(10, 10)), 0.0)
    with pytest.raises(ValueError, match="positive depth"):
        pocket(cuboid(10, 10, 10), fill(rect(2, 2)), 0.0, label="p")
    with pytest.raises(ValueError, match="positive height"):
        boss(cuboid(10, 10, 10), fill(rect(2, 2)), 0.0, label="b")


def test_a_revolve_refuses_an_axis_out_of_the_profiles_plane_and_a_turn_past_a_whole_one() -> None:
    profile = fill(rect(4, 10, Point(2, 0)))
    with pytest.raises(ValueError, match="lie in the profile"):
        revolve(profile, Axis(Point(0, 0, 5), Vector(0, 1, 0)))
    with pytest.raises(ValueError, match="whole turn"):
        revolve(profile, Axis(ORIGIN, Vector(0, 1, 0)), angle=7.0)
    turned = revolve(profile, Axis(ORIGIN, Vector(0, 1, 0)), label="knob")
    assert _labels(turned) == ("side-0", "side-1", "side-2", "side-3")


def test_the_label_of_a_cut_goes_on_the_tool_and_a_union_leaves_both_named() -> None:
    plate = extrude(fill(rect(40, 30)), 5.0, label="plate")
    holed = cut(plate, cylinder(2, 5.0), label="bore")
    assert holed.label is None
    assert refs(holed) == (
        Ref("plate"),
        Ref("plate/top"),
        Ref("plate/bottom"),
        Ref("plate/side-0"),
        Ref("plate/side-1"),
        Ref("plate/side-2"),
        Ref("plate/side-3"),
        Ref("bore"),
        Ref("bore/top"),
        Ref("bore/bottom"),
        Ref("bore/side-0"),
    )
    both = union(
        extrude(fill(rect(4, 4)), 2.0, label="a"), cuboid(2, 2, 2, label="b"), label="pair"
    )
    assert both.label == Label("pair")
    assert faces_of(both) == ()
    assert Ref("a/top") in refs(both) and Ref("b/top") in refs(both)


def test_a_pocket_floor_is_the_tools_own_bottom_and_a_boss_crown_its_top() -> None:
    plate = extrude(fill(rect(40, 30)), 5.0)
    sunk = pocket(
        plate, fill(rect(10, 10, Point(5, 5)), on=plane_of(plate, "top")), 2.0, label="pocket"
    )
    floor = plane_of(sunk, "pocket/bottom")
    assert near(floor.origin, Point(0, 0, 3))
    assert near(floor.normal, Vector(0, 0, -1))
    assert near(plane_of(sunk, "pocket/top").origin, Point(0, 0, 5))
    stood = boss(
        plate, fill(circle(3, Point(20, 15)), on=plane_of(plate, "top")), 4.0, label="boss"
    )
    assert near(plane_of(stood, "boss/top").origin, Point(0, 0, 9))
    assert bounds(stood) == pytest.approx((0, 0, 0, 40, 30, 9))


def test_a_named_face_is_read_in_the_profiles_own_coordinates() -> None:
    """The whole point of ``plane_of``: a sketch laid on ``top`` is drawn with the numbers
    the profile was drawn with, so ``Point(5, 5)`` means the same place on both."""
    plate = extrude(fill(rect(40, 30)), 5.0, label="plate")
    top = plane_of(plate, "top")
    assert near(to_world(top) @ Point(5, 5), Point(5, 5, 5))
    assert near(top.normal, Vector(0, 0, 1))
    # the same face by its full path, which is what the editor inserts
    assert plane_of(plate, "plate/top") == top
    under = plane_of(plate, "bottom")
    assert near(under.normal, Vector(0, 0, -1))
    assert near(under.x_dir, top.x_dir)
    assert near(under.y_dir, -top.y_dir)


def test_a_side_of_an_extrusion_is_read_along_the_edge_and_up_the_sweep() -> None:
    box = cuboid(20, 10, 4)
    front = plane_of(box, "side-front")
    assert near(front.normal, Vector(0, -1, 0))
    assert near(to_world(front) @ Point(3, 1), Point(3, 0, 1))


def test_plane_of_says_which_faces_it_cannot_answer_for() -> None:
    knob = revolve(fill(rect(4, 10, Point(2, 0))), Axis(ORIGIN, Vector(0, 1, 0)), label="knob")
    with pytest.raises(ValueError, match="no single plane"):
        plane_of(knob, "side-0")
    with pytest.raises(LookupError, match="no face named"):
        plane_of(knob, "top")
    # A square pocket's wall is four faces under one name and no turn either: nothing to
    # take a tangent at, and it says so rather than guessing one of the four.
    slotted = extrude(cut(fill(rect(20, 20)), rect(4, 4, Point(8, 8)), label="slot"), 4.0)
    with pytest.raises(ValueError, match="no single plane"):
        plane_of(slotted, "slot")


def test_a_loft_is_a_hull_and_names_nothing_under_itself() -> None:
    taper = loft(fill(rect(20, 20)), fill(rect(10, 10, Point(5, 5, 6))), label="taper")
    assert faces_of(taper) == ()
    assert refs(taper) == ()
    assert bounds(taper) == pytest.approx((0, 0, 0, 20, 20, 6))


def test_pattern_and_rotate_work_on_a_body_unchanged() -> None:
    posts = pattern(cylinder(2, 6, label="post"), 3, Vector(10, 0))
    assert tuple(str(p.label) for p in posts) == ("post-1", "post-2", "post-3")
    assert bounds(posts[2]) == pytest.approx((18, -2, 0, 22, 2, 6))
    assert _labels(posts[2]) == ("top", "bottom", "side-0")


def test_mirror_takes_a_plane_as_well_as_an_axis() -> None:
    box = cuboid(10, 10, 4, at=Point(5, 0, 0))
    across_axis = mirror(box, Axis(ORIGIN, Vector(0, 1)))
    assert bounds(across_axis) == pytest.approx((-15, 0, 0, -5, 10, 4))
    across_plane = mirror(box, plane(Point(0, 0, 2), Vector(0, 0, 1)))
    assert bounds(across_plane) == pytest.approx((5, 0, 0, 15, 10, 4))


def test_a_sketch_is_drawn_in_the_numbers_of_the_plane_it_is_put_on() -> None:
    """The fix every maker script needs: a profile filled ``on`` a face lands on that face
    at the profile's own numbers, not at the world's. Before it, ``on=`` recorded a plane
    and moved nothing, so a ten by six rectangle stayed on the floor."""
    plate = extrude(fill(rect(60, 40)), 5.0, label="plate")
    top = plane_of(plate, "top")
    drawn = fill(rect(10, 6), on=top)
    corners = tuple(curve_start(e.curve) for e in drawn.outer.edges)
    assert near(corners[0], Point(0, 0, 5))
    assert near(corners[2], Point(10, 6, 5))
    assert bounds(drawn) == pytest.approx((0, 0, 5, 10, 6, 5))


def test_drawing_on_xy_is_what_it_always_was() -> None:
    """Every flat script in the package goes through the same code path now, and must come
    out byte for byte what it did: ``XY``'s lift is the identity."""
    flat = rect(10, 6, Point(2, 3))
    assert fill(flat).outer is flat
    assert fill(flat, on=XY).outer is flat
    assert fill(flat, on=raised(XY, 0.0)).outer is flat


def test_a_raised_plane_is_the_same_frame_higher_up() -> None:
    up = raised(XY, 7.0)
    assert near(up.origin, Point(0, 0, 7))
    assert up.normal == XY.normal and up.x_dir == XY.x_dir
    assert near(to_world(up) @ Point(4, 5), Point(4, 5, 7))
    assert near(raised(raised(XY, 7.0), -7.0).origin, ORIGIN)
    sideways = plane(Point(1, 0, 0), Vector(1, 0, 0))
    assert near(raised(sideways, 2.0).origin, Point(3, 0, 0))


def test_a_hole_cut_in_a_face_is_placed_in_the_faces_own_frame() -> None:
    """``cut``'s face arm reads its tool the way ``fill`` reads an outline, so a vent is
    placed in the numbers the panel was drawn in whichever plane it stands on."""
    on = plane(Point(0, 0, 5), Vector(0, 0, 1), Vector(1, 0, 0))
    panel = fill(rect(30, 20), on=on, label="panel")
    vented = cut(panel, circle(3, Point(10, 10)), label="vent")
    assert vented.label == Label("panel")
    hole = vented.inner[0]
    assert hole.label == Label("vent")
    bore = hole.edges[0].curve
    assert isinstance(bore, Circle)
    assert near(bore.centre, Point(10, 10, 5))


def test_a_cuboid_and_a_cylinder_are_put_where_they_are_asked_for_and_not_twice() -> None:
    """``at`` names one place. The height goes into the plane the sketch is drawn on and the
    sketch keeps only its X and Y, or the lift would apply it a second time."""
    assert bounds(cuboid(4, 6, 2, at=Point(1, 2, 3))) == pytest.approx((1, 2, 3, 5, 8, 5))
    round_one = bounds(cylinder(2, 5, at=Point(10, 0, 4)))
    assert round_one == pytest.approx((8, -2, 4, 12, 2, 9))


# ---- printable holes -------------------------------------------------------------------


def _chords(w: Wire) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    """``w`` flattened by the package's own chord rule, as the straight steps it becomes.

    A teardrop is an arc and two lines, and what a printer sees is the chords the arc is cut
    into - so the claim "nothing steeper than 45 degrees" has to be measured on those and
    not on the ideal curve.
    """
    node = extrude(fill(w), 1.0).node
    assert isinstance(node, Extrude)
    ring = profile_rings(node)[0]
    points = ring.points
    return tuple(zip(points, (*points[1:], points[0]), strict=True))


def _steepest(w: Wire) -> float:
    """The worst angle, in degrees, between the build direction (``+Y`` here) and any chord
    of ``w`` that is over the centre - the part a printer has to hold up in mid air. What is
    under the centre rests on the layer below and is nobody's problem."""
    worst = 0.0
    for (u0, v0), (u1, v1) in _chords(w):
        if (v0 + v1) / 2 <= 0.0:
            continue
        worst = max(worst, math.degrees(math.atan2(abs(u1 - u0), abs(v1 - v0))))
    return worst


def test_a_teardrop_has_no_edge_steeper_than_forty_five_degrees_and_a_circle_does() -> None:
    """The whole reason the shape exists, measured rather than asserted - and measured
    against the circle it replaces, so the test is known to be able to fail."""
    assert _steepest(teardrop(8.0, up=Y)) <= 45.0 + 1e-9
    assert _steepest(circle(4.0)) > 80.0


def test_a_teardrops_apex_stands_root_two_radii_above_its_centre() -> None:
    """Where two tangents drawn at 45 degrees meet, which is what makes them 45 degrees."""
    at = Point(5.0, 7.0)
    drop = teardrop(6.0, at, up=Y)
    assert bbox(drop).y1 == pytest.approx(at.y + 3.0 * math.sqrt(2.0))
    assert bbox(drop).x0 == pytest.approx(at.x - 3.0)
    assert bbox(drop).x1 == pytest.approx(at.x + 3.0)


def test_a_teardrop_points_wherever_up_is_and_is_still_an_outline() -> None:
    """``up`` is read in the plane the wire is drawn on, so a bore lying on its side in any
    direction gets a shape pointed the right way - and it is closed and counter-clockwise
    like every other outline, because it is filled the same way."""
    sideways = teardrop(6.0, up=X)
    assert is_closed(sideways) and is_ccw(sideways)
    assert bbox(sideways).x1 == pytest.approx(3.0 * math.sqrt(2.0))
    assert bbox(sideways).y1 == pytest.approx(3.0)
    assert _steepest(rotate(sideways, math.pi / 2)) <= 45.0 + 1e-9


def test_a_teardrop_refuses_what_it_cannot_point() -> None:
    with pytest.raises(ValueError, match="positive diameter"):
        teardrop(0.0, up=Y)
    with pytest.raises(ValueError, match="build direction across its own plane"):
        teardrop(6.0, up=Z)


def test_bridge_steps_alternate_a_quarter_turn_from_the_bore_out_to_the_opening() -> None:
    """gridfinity-rebuilt's trick: every layer spans between material that is already there,
    and the hole under it keeps its diameter."""
    steps = bridge_steps(6.5, 10.0, 3, 0.2, at=Point(4.0, 4.0))
    assert len(steps) == 3
    boxes = [bbox(step) for step in steps]
    assert [(round(b.w, 3), round(b.h, 3)) for b in boxes] == [
        (6.5, 10.0),
        (10.0, 6.5),
        (6.5, 10.0),
    ]
    for box in boxes:
        assert (box.x0 + box.x1) / 2 == pytest.approx(4.0)
        assert (box.y0 + box.y1) / 2 == pytest.approx(4.0)


def test_bridge_steps_refuse_a_stack_that_would_bridge_nothing() -> None:
    with pytest.raises(ValueError, match="positive bore"):
        bridge_steps(0.0, 10.0, 3, 0.2)
    with pytest.raises(ValueError, match="out to something wider"):
        bridge_steps(10.0, 6.0, 3, 0.2)
    with pytest.raises(ValueError, match="at least one layer"):
        bridge_steps(6.0, 10.0, 0, 0.2)
    with pytest.raises(ValueError, match="positive layer height"):
        bridge_steps(6.0, 10.0, 3, 0.0)


def test_the_horizontal_hole_rule_reads_the_angle_then_the_diameter() -> None:
    """The review's rule, arm by arm: under thirty degrees off the build direction nothing
    is needed; over it, a short span still needs nothing, a wide one gets a teardrop, and a
    bridged top is available in between to a hole that has to stay round."""
    pla = Printed(PLA)
    upright = printable_top(Top.AUTO, axis=Z, diameter=20.0, printed=pla)
    assert upright is Top.ROUND
    assert printable_top(Top.AUTO, axis=-Z, diameter=20.0, printed=pla) is Top.ROUND
    assert printable_top(Top.AUTO, axis=X, diameter=3.0, printed=pla) is Top.ROUND
    assert printable_top(Top.AUTO, axis=X, diameter=6.0, printed=pla) is Top.TEARDROP
    assert (
        printable_top(Top.AUTO, axis=X, diameter=6.0, printed=pla, round_matters=True) is Top.BRIDGE
    )
    # past the material's own longest bridge, only a teardrop will do
    assert (
        printable_top(Top.AUTO, axis=X, diameter=12.0, printed=pla, round_matters=True)
        is Top.TEARDROP
    )
    assert (
        printable_top(Top.AUTO, axis=X, diameter=8.0, printed=Printed(ASA), round_matters=True)
        is Top.TEARDROP
    )


def test_the_horizontal_hole_rule_leaves_a_told_top_alone() -> None:
    """Only ``AUTO`` is a rule; the other three are the caller's decision, and are not
    second-guessed even where the rule would have chosen differently."""
    for told in (Top.ROUND, Top.TEARDROP, Top.BRIDGE):
        assert printable_top(told, axis=X, diameter=20.0, printed=None) is told


def test_auto_on_a_part_with_no_orientation_says_so() -> None:
    """The error the review asked for, word for word: a part that never said which way it
    prints cannot be asked which way is up."""
    with pytest.raises(
        ValueError,
        match=re.escape(
            "this part has no print orientation, so top=Top.AUTO cannot tell which way is up"
        ),
    ):
        printable_top(Top.AUTO, axis=X, diameter=6.0, printed=None)


def test_a_foot_chamfer_names_the_wedge_it_takes_off_and_leaves_everything_else() -> None:
    """The elephant's foot, cut once at the bottom rather than sprinkled through the sketch.
    The body keeps every ref it had; the wedge arrives under ``foot``."""
    plate = cuboid(40, 30, 6)
    stood = foot_chamfer(plate, 0.5)
    found = refs(stood)
    assert found[:2] == (Ref("top"), Ref("bottom"))
    assert Ref("foot") in found and Ref("foot/taper") in found
    assert len(set(found)) == len(found)
    # a cut never grows a body, and bounds stay the base's under a difference
    assert bounds(stood) == pytest.approx(bounds(plate))


def test_a_foot_chamfer_refuses_a_body_with_no_footprint() -> None:
    with pytest.raises(ValueError, match="positive size"):
        foot_chamfer(cuboid(10, 10, 10), 0.0)
    joined = union(cuboid(10, 10, 4), cuboid(10, 10, 4, at=Point(0, 0, 4), label="lid"))
    with pytest.raises(ValueError, match="extruded from a profile"):
        foot_chamfer(joined, 0.5)


# ---- hull, grid and a turning pattern --------------------------------------------------


def test_a_hull_wraps_faces_and_bodies_alike_and_names_nothing_under_itself() -> None:
    """The verb the Gridfinity base is written with: flat slices at different heights, and
    the hull between them is the chamfered sweep this kernel cannot sweep."""
    foot = hull(
        fill(rect(35.6, 35.6, Point(2.95, 2.95))),
        fill(rect(41.5, 41.5), on=raised(XY, 4.75)),
        label="foot",
    )
    assert faces_of(foot) == ()
    assert refs(foot) == ()
    assert bounds(foot) == pytest.approx((0.0, 0.0, 0.0, 41.5, 41.5, 4.75))
    # a body may go in beside a face, and one shape is its own hull
    assert bounds(hull(cuboid(10, 10, 10), fill(circle(2), on=raised(XY, 20)))) == pytest.approx(
        (-2.0, -2.0, 0.0, 10.0, 10.0, 20.0)
    )
    with pytest.raises(ValueError, match="at least one shape"):
        hull()


def test_a_loft_is_the_hull_of_two_profiles() -> None:
    bottom, top = fill(rect(20, 20)), fill(rect(10, 10, Point(5, 5)), on=raised(XY, 6))
    assert loft(bottom, top, label="taper") == hull(bottom, top, label="taper")


def test_a_grid_numbers_its_copies_in_one_flat_run() -> None:
    """The reason it is a verb of its own: nesting two patterns would call the second copy
    of the second row ``foot-2-2``, and a ref that reads like a mistake is a mistake."""
    feet = grid(cylinder(2, 4, label="foot"), (3, 2), (X * 42.0, Y * 42.0))
    assert tuple(str(f.label) for f in feet) == tuple(f"foot-{i + 1}" for i in range(6))
    assert bounds(feet[3]) == pytest.approx(bounds(move(feet[0], Y * 42.0)))
    assert bounds(feet[5]) == pytest.approx(bounds(move(feet[0], X * 84.0 + Y * 42.0)))
    with pytest.raises(ValueError, match="at least one copy each way"):
        grid(cylinder(2, 4), (0, 3), (X, Y))


def test_a_pattern_steps_round_an_axis_as_readily_as_along_a_line() -> None:
    """Eight crush ribs round a magnet pocket - the same verb, a turn instead of a move."""
    ribs = pattern(
        cylinder(0.3, 2, at=Point(3.25, 0, 0), label="rib"), 8, Turn(Axis(ORIGIN, Z), math.tau / 8)
    )
    assert tuple(str(r.label) for r in ribs) == tuple(f"rib-{i + 1}" for i in range(8))
    quarter = bounds(ribs[2])
    assert quarter.x0 == pytest.approx(-0.3, abs=1e-9) and quarter.y1 == pytest.approx(3.55)
    assert bounds(ribs[4]).x1 == pytest.approx(-2.95)


# ---- a plane on a round face -----------------------------------------------------------


def test_a_round_side_answers_with_the_plane_tangent_to_it() -> None:
    """The collar's set screw: a cylinder's side has no plane, but it has one at every point
    of it, and the radius comes off the body rather than out of the script."""
    collar = cylinder(8.0, 12.0)
    seat = plane_of(collar, "side-0", around=0.0, along=6.0)
    assert near(seat.origin, Point(8.0, 0.0, 6.0))
    assert near(seat.normal, X)
    assert near(seat.y_dir, Z), "Y runs up the sweep, as it does on a flat side"
    quarter = plane_of(collar, "side-0", around=math.pi / 2, along=0.0)
    assert near(quarter.origin, Point(0.0, 8.0, 0.0))
    assert near(quarter.normal, Y)


def test_a_bore_is_round_from_the_other_side() -> None:
    """Material is to the left of travel, so a hole walked the other way round hands back a
    normal pointing at its own axis - out of the material, like every other face plane."""
    plate = extrude(cut(fill(rect(40, 40)), circle(5, Point(20, 20)), label="bore"), 10.0)
    wall = plane_of(plate, "bore", around=0.0, along=4.0)
    assert near(wall.origin, Point(25.0, 20.0, 4.0))
    assert near(wall.normal, -X)


def test_plane_of_refuses_a_turn_on_a_flat_face_and_a_height_with_no_turn() -> None:
    plate = cuboid(20, 20, 5)
    with pytest.raises(ValueError, match="not round"):
        plane_of(plate, "top", around=1.0)
    with pytest.raises(ValueError, match="give around="):
        plane_of(plate, "top", along=3.0)
    with pytest.raises(ValueError, match="give around="):
        plane_of(cylinder(4, 10), "side-0")
