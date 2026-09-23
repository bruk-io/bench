import io
import math
import struct
import xml.etree.ElementTree as ET
import zipfile

import pytest

from bench import (
    ORIGIN,
    XY,
    Arc,
    Axis,
    Edge,
    Label,
    Line,
    Mesh,
    Point,
    Process,
    Ref,
    SvgPath,
    Vector,
    X,
    Y,
    Z,
    as_printed,
    circle,
    cut,
    face_paths,
    fill,
    mirror,
    move,
    part,
    part_paths,
    part_svg,
    part_texts,
    rect,
    rounded_rect,
    stl,
    three_mf,
    wire,
)
from bench.export import _MODEL_NS
from tests.support import PLY, panel

pytestmark = pytest.mark.unit


def _commands(d: str) -> tuple[str, ...]:
    return tuple(token for token in d.split() if token.isalpha())


def _arcs(d: str) -> tuple[tuple[str, ...], ...]:
    token = d.split()
    return tuple(
        tuple(token[i : i + 8])
        for i, head in enumerate(token)
        if head == "A" and i + 7 < len(token)
    )


# ---- face paths ----------------------------------------------------------------------


def test_face_paths_names_one_path_per_wire() -> None:
    f = cut(
        fill(rect(10, 6, label=Label("outline")), label=Label("front")),
        circle(1),
        label=Label("hole"),
    )
    paths = face_paths(f, Ref("drawer-3"))
    assert tuple(p.kind for p in paths) == ("outer", "hole")
    assert tuple(p.ref for p in paths) == (
        Ref("drawer-3/front/outline"),
        Ref("drawer-3/front/hole"),
    )


def test_an_unlabelled_outline_answers_to_its_face() -> None:
    f = fill(rect(10, 6), label=Label("front"))
    assert face_paths(f, "")[0].ref == Ref("front")
    assert face_paths(f, Ref("drawer-3"))[0].ref == Ref("drawer-3/front")
    assert face_paths(fill(rect(10, 6)), "")[0].ref is None


def test_an_unlabelled_face_is_transparent_like_the_model_says() -> None:
    f = fill(rect(10, 6, label=Label("outline")))
    assert face_paths(f, Ref("drawer-3"))[0].ref == Ref("drawer-3/outline")
    assert face_paths(f, "")[0].ref == Ref("outline")


def test_a_rectangle_is_four_lines_closed_with_z() -> None:
    path = face_paths(fill(rect(10, 6, Point(1, 2))), "")[0]
    assert path.d == "M 1 2 L 11 2 L 11 8 L 1 8 L 1 2 Z"
    assert _commands(path.d) == ("M", "L", "L", "L", "L", "Z")


# ---- arcs ----------------------------------------------------------------------------


def test_a_circle_is_two_half_arcs_that_sweep_counter_clockwise() -> None:
    path = face_paths(fill(circle(5, Point(10, 10))), "")[0]
    arcs = _arcs(path.d)
    assert len(arcs) == 2
    assert path.d == "M 15 10 A 5 5 0 0 1 5 10 A 5 5 0 0 1 15 10 Z"
    assert all(a[5] == "1" for a in arcs)


def test_arc_sweep_flags_follow_the_way_the_wire_runs() -> None:
    rr = rounded_rect(20, 10, 2)
    assert all(a[5] == "1" for a in _arcs(face_paths(fill(rr), "")[0].d))
    # a mirrored outline still runs counter-clockwise, so the flags do not change
    flipped = mirror(rr, Axis(ORIGIN, Vector(0, 1)))
    assert all(a[5] == "1" for a in _arcs(face_paths(fill(flipped), "")[0].d))
    # ... but an arc recorded from a high angle to a low one sweeps the other way
    clockwise = wire(
        (
            Edge(Arc(ORIGIN, 5, math.pi, 0.0, XY)),
            Edge(Line(Point(5, 0), Point(-5, 0))),
        )
    )
    assert tuple(a[5] for a in _arcs(face_paths(fill(clockwise), "")[0].d)) == ("0",)


def test_an_arc_past_a_half_turn_is_written_as_two_halves() -> None:
    """No single ``A`` may turn more than a half turn, so nothing ever needs the large-arc
    flag and an arc whose ends coincide can never be written as one dropped command."""
    three_quarters = wire(
        (
            Edge(Arc(ORIGIN, 5, 0.0, 3 * math.pi / 2, XY)),
            Edge(Line(Point(0, -5), ORIGIN)),
            Edge(Line(ORIGIN, Point(5, 0))),
        )
    )
    arcs = _arcs(face_paths(fill(three_quarters), "")[0].d)
    assert len(arcs) == 2
    assert all(a[4] == "0" for a in arcs)
    # the halves meet at three eighths of a turn, where the arc is at 45 degrees
    assert (float(arcs[0][6]), float(arcs[0][7])) == pytest.approx(
        (5 * math.cos(3 * math.pi / 4), 5 * math.sin(3 * math.pi / 4)), abs=1e-4
    )
    assert (float(arcs[1][6]), float(arcs[1][7])) == pytest.approx((0.0, -5.0))
    quarter = _arcs(face_paths(fill(rounded_rect(20, 10, 2)), "")[0].d)
    assert len(quarter) == 4
    assert all(a[4] == "0" for a in quarter)


def test_an_arc_further_than_a_whole_turn_is_refused() -> None:
    over = wire((Edge(Arc(ORIGIN, 5, 0.0, 2 * math.pi + 0.5, XY)),), Label("over"))
    spiral = part(Label("p"), fill(rect(20, 20)), PLY, Process.LASER, engravings=(over,))
    with pytest.raises(ValueError, match="whole turn"):
        part_paths(spiral)


# ---- part paths and texts ------------------------------------------------------------


def test_part_paths_add_engraved_wires_and_keep_text_apart() -> None:
    paths = part_paths(panel())
    assert tuple(p.kind for p in paths) == ("outer", "hole", "engrave")
    assert tuple(p.ref for p in paths) == (
        Ref("drawer-3/front/outline"),
        Ref("drawer-3/front/vent"),
        Ref("drawer-3/score"),
    )
    texts = part_texts(panel())
    assert len(texts) == 1
    assert (texts[0].ref, texts[0].text, texts[0].x, texts[0].y, texts[0].size) == (
        Ref("drawer-3/number"),
        "3 & up",
        5.0,
        20.0,
        6.0,
    )


def test_an_open_engraved_wire_is_not_closed_with_z() -> None:
    scratch = wire((Edge(Line(Point(1, 1), Point(9, 1))),), Label("scratch"))
    p = part(Label("p"), fill(rect(10, 10)), PLY, Process.LASER, engravings=(scratch,))
    assert part_paths(p)[-1].d == "M 1 1 L 9 1"


# ---- svg -----------------------------------------------------------------------------


def test_part_svg_is_a_page_in_mm_with_the_origin_at_the_bottom_left() -> None:
    svg = part_svg(panel())
    assert svg.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<svg ')
    assert 'width="60mm" height="40mm" viewBox="0 0 60 40"' in svg
    assert '<g transform="translate(0 40) scale(1 -1)">' in svg
    assert '<g id="cut" stroke="#ff0000" stroke-width="0.1" fill="none">' in svg
    assert '<g id="engrave" stroke="#0000ff" stroke-width="0.1" fill="none">' in svg
    assert svg.rstrip().endswith("</svg>")


def test_part_svg_moves_a_part_that_is_not_at_the_origin_to_it() -> None:
    away = part(
        Label("p"),
        fill(move(rect(20, 10), Vector(100, 50)), label=Label("front")),
        PLY,
        Process.LASER,
    )
    svg = part_svg(away)
    assert 'width="20mm" height="10mm" viewBox="0 0 20 10"' in svg
    assert 'd="M 0 0 L 20 0 L 20 10 L 0 10 L 0 0 Z"' in svg


def test_every_path_carries_its_kind_and_its_ref_when_it_has_one() -> None:
    svg = part_svg(panel())
    assert '<path data-ref="drawer-3/front/outline" data-kind="outer"' in svg
    assert '<path data-ref="drawer-3/front/vent" data-kind="hole"' in svg
    assert '<path data-ref="drawer-3/score" data-kind="engrave"' in svg
    anonymous = part_svg(part(Label("p"), fill(rect(5, 5)), PLY, Process.LASER))
    assert 'data-ref="p" data-kind="outer"' in anonymous


def test_lettering_is_flipped_back_upright_and_escaped() -> None:
    svg = part_svg(panel())
    assert 'transform="translate(5 20) scale(1 -1)"' in svg
    assert 'font-size="6"' in svg
    assert ">3 &amp; up</text>" in svg


def test_svg_path_is_a_frozen_record() -> None:
    p = SvgPath(Ref("a"), "outer", "M 0 0 Z")
    with pytest.raises(AttributeError):
        p.d = "M 1 1 Z"  # type: ignore[misc]


# ---- as_printed ------------------------------------------------------------------------


def _box(low: tuple[float, float, float], high: tuple[float, float, float]) -> Mesh:
    """A mesh of one box, ``low`` to ``high`` - two triangles a face, which is more than
    :func:`as_printed` reads (only the vertices), but keeps the refs on a face worth
    naming."""
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
    refs = (Ref("bottom"), None, Ref("top"), None)
    return Mesh(vertices, triangles, refs)


BOX = _box((0.0, 0.0, 0.0), (4.0, 2.0, 1.0))
"""4 x 2 x 1 mm, its low corner at the world origin - a box lopsided enough in every
dimension that a swapped axis or a missed turn changes its extent, not just its label."""


def test_as_printed_with_up_plus_z_only_drops_it_to_the_bed_and_centres_it() -> None:
    """``up`` already +Z: nothing turns, only z = 0 and the footprint centred."""
    out = as_printed(BOX, Z)
    xs, ys, zs = out.vertices[0::3], out.vertices[1::3], out.vertices[2::3]
    assert min(zs) == pytest.approx(0.0)
    assert max(zs) - min(zs) == pytest.approx(1.0)
    assert max(xs) - min(xs) == pytest.approx(4.0)
    assert max(ys) - min(ys) == pytest.approx(2.0)
    assert (min(xs) + max(xs)) / 2 == pytest.approx(0.0)
    assert (min(ys) + max(ys)) / 2 == pytest.approx(0.0)


def test_as_printed_with_up_minus_z_turns_the_box_over() -> None:
    """A part printed upside down - the enclosure lid's own ``Orient(up=-Z)`` - comes out
    with what was its lowest corner now its highest, and the other way round."""
    out = as_printed(BOX, -Z)
    was_low = out.vertices[0:3]  # vertex 0 was (0, 0, 0), the box's low corner
    was_high = out.vertices[12:15]  # vertex 4 was (0, 0, 1), straight above it
    assert was_low[2] == pytest.approx(1.0)
    assert was_high[2] == pytest.approx(0.0)


def test_as_printed_with_up_sideways_stands_that_axis_up() -> None:
    """``up`` along the box's longest edge (X, 4 mm) makes that edge the height."""
    out = as_printed(BOX, X)
    zs = out.vertices[2::3]
    assert max(zs) - min(zs) == pytest.approx(4.0)


def test_as_printed_reads_nothing_of_where_the_mesh_already_is() -> None:
    """decision-10: an assembly's pose is not part of the maths - only the direction a part
    prints in. The same box moved far from the origin first exports identically."""
    elsewhere = _box((100.0, 100.0, 100.0), (104.0, 102.0, 101.0))
    assert as_printed(elsewhere, Z).vertices == pytest.approx(as_printed(BOX, Z).vertices)


def test_bed_along_settles_the_turn_up_alone_leaves_free() -> None:
    """Aligning ``up`` to +Z is two degrees of freedom; the third - the turn about it - is
    ``bed_along``'s, not guessed the same way twice by accident: two different ``along``s,
    both perpendicular to a sideways ``up``, turn the box out differently."""
    one = as_printed(BOX, X, bed_along=Y)
    other = as_printed(BOX, X, bed_along=Z)
    assert one.vertices != pytest.approx(other.vertices)


def test_as_printed_is_deterministic() -> None:
    """The same mesh and the same ``Orient`` give the same bytes every run - decision-9's
    reproducibility, which a 3MF's fixed zip stamp already promises further down the line."""
    assert as_printed(BOX, X).vertices == pytest.approx(as_printed(BOX, X).vertices)


def test_as_printed_keeps_triangles_and_refs() -> None:
    """Only the vertices move; a triangle answers to the same ref and the same two other
    corners it always did."""
    out = as_printed(BOX, -Z)
    assert out.triangles == BOX.triangles
    assert out.refs == BOX.refs


def test_as_printed_of_an_empty_mesh_moves_nothing() -> None:
    empty = Mesh((), (), ())
    assert as_printed(empty, Z) == empty


# ---- what a printer reads ---------------------------------------------------------------


def _tetrahedron() -> Mesh:
    """A unit corner tetrahedron, wound so every face points out: volume one sixth, four
    triangles, four vertices. Small enough to check by hand, closed enough to measure."""
    return Mesh(
        vertices=(0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
        triangles=(0, 2, 1, 0, 1, 3, 0, 3, 2, 1, 2, 3),
        refs=(Ref("a"), Ref("b"), Ref("c"), None),
    )


def _closed_volume(written: bytes) -> float:
    """What the facets of a binary STL enclose, by the divergence theorem."""
    count = struct.unpack("<I", written[80:84])[0]
    total = 0.0
    for at in range(count):
        start = 84 + 50 * at + 12
        a, b, c = (
            struct.unpack("<3f", written[start + 12 * k : start + 12 * k + 12]) for k in range(3)
        )
        cross = (b[1] * c[2] - b[2] * c[1], b[2] * c[0] - b[0] * c[2], b[0] * c[1] - b[1] * c[0])
        total += sum(a[k] * cross[k] for k in range(3)) / 6
    return total


def test_a_binary_stl_is_header_count_and_fifty_bytes_a_triangle() -> None:
    written = stl(_tetrahedron())
    assert len(written) == 84 + 50 * 4
    assert struct.unpack("<I", written[80:84])[0] == 4
    assert _closed_volume(written) == pytest.approx(1 / 6)


def test_an_stl_writes_the_normal_its_own_winding_implies() -> None:
    """The normal is computed rather than trusted, so it can never disagree with the corners
    written beside it. The first facet here is the one on the floor, facing down."""
    written = stl(_tetrahedron())
    first = struct.unpack("<3f", written[84:96])
    assert first == pytest.approx((0.0, 0.0, -1.0))


def test_an_empty_mesh_is_a_well_formed_stl_of_no_triangles() -> None:
    written = stl(Mesh((), (), ()))
    assert len(written) == 84
    assert struct.unpack("<I", written[80:84])[0] == 0


def test_a_3mf_is_a_zip_of_exactly_the_three_parts_the_format_asks_for() -> None:
    """No ``project_settings.config`` and no ``slice_info.config``: those are one slicer's
    settings for one printer, and nobody asked us how to print the thing."""
    archive = zipfile.ZipFile(io.BytesIO(three_mf((("plate", _tetrahedron()),))))
    assert archive.namelist() == ["[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"]
    assert archive.testzip() is None


def test_a_3mf_model_is_millimetres_one_object_a_part_and_one_item_each() -> None:
    objects = (("plate", _tetrahedron()), ("lid", _tetrahedron()))
    archive = zipfile.ZipFile(io.BytesIO(three_mf(objects)))
    root = ET.fromstring(archive.read("3D/3dmodel.model"))
    assert root.get("unit") == "millimeter"
    written = root.findall(f".//{{{_MODEL_NS}}}object")
    assert [(one.get("id"), one.get("name")) for one in written] == [("1", "plate"), ("2", "lid")]
    items = root.findall(f".//{{{_MODEL_NS}}}item")
    assert [one.get("objectid") for one in items] == ["1", "2"]


def test_no_3mf_triangle_points_past_the_vertices_of_its_own_object() -> None:
    """Indices are per object, as the format wants, so two parts in one package do not have
    to be merged or renumbered against each other."""
    archive = zipfile.ZipFile(io.BytesIO(three_mf((("a", _tetrahedron()), ("b", _tetrahedron())))))
    root = ET.fromstring(archive.read("3D/3dmodel.model"))
    for one in root.findall(f".//{{{_MODEL_NS}}}object"):
        count = len(one.findall(f".//{{{_MODEL_NS}}}vertex"))
        assert count == 4
        for triangle in one.findall(f".//{{{_MODEL_NS}}}triangle"):
            corners = [int(triangle.get(which) or -1) for which in ("v1", "v2", "v3")]
            assert all(0 <= corner < count for corner in corners), corners


def test_a_3mf_is_the_same_bytes_for_the_same_model() -> None:
    """Every entry carries one fixed date, so a file is a function of the model and of
    nothing else - which is what lets a browser cache one and a test compare two."""
    assert three_mf((("plate", _tetrahedron()),)) == three_mf((("plate", _tetrahedron()),))


def test_an_objects_name_is_escaped_rather_than_breaking_the_document() -> None:
    archive = zipfile.ZipFile(io.BytesIO(three_mf((('a "&" <name>', _tetrahedron()),))))
    root = ET.fromstring(archive.read("3D/3dmodel.model"))
    assert root.findall(f".//{{{_MODEL_NS}}}object")[0].get("name") == 'a "&" <name>'
