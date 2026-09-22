import math
from xml.etree import ElementTree

import pytest

from bench import (
    XY,
    Arc,
    Bed,
    Edge,
    Face,
    Label,
    Part,
    Point,
    Process,
    Sheet,
    Stock,
    Text,
    area,
    circle,
    cut,
    face_paths,
    fill,
    nest,
    part,
    part_paths,
    part_svg,
    rect,
    rounded_rect,
    sheet_dxf,
    sheet_svg,
    wire,
)
from tests.support import PLY, panel

pytestmark = pytest.mark.functional


# ---- svg -----------------------------------------------------------------------------


def test_xml_is_escaped_in_titles_refs_and_text() -> None:
    sheets, warnings = nest(
        (
            part(
                Label('a"b'),
                fill(rect(10, 10, label=Label("<outline>")), label=Label("front")),
                PLY,
                Process.LASER,
                engravings=(Text("x < y & 'z'", Point(1, 1), 3.0),),
            ),
        ),
        Bed(200.0, 100.0),
    )
    assert warnings == ()
    svg = sheet_svg(sheets[0], 'the <"best"> sheet')
    assert "<title>the &lt;&quot;best&quot;&gt; sheet</title>" in svg
    assert 'data-ref="a&quot;b/front/&lt;outline&gt;"' in svg
    assert ">x &lt; y &amp; &apos;z&apos;</text>" in svg


def test_sheet_svg_is_the_size_of_the_sheet_and_holds_every_part() -> None:
    sheets, warnings = nest(((panel(), 3),), Bed(300.0, 200.0))
    assert warnings == ()
    svg = sheet_svg(sheets[0], "sheet-3mm-01")
    assert 'width="300mm" height="200mm" viewBox="0 0 300 200"' in svg
    assert '<g transform="translate(0 200) scale(1 -1)">' in svg
    assert svg.count('data-kind="outer"') == 3
    assert svg.count('data-kind="hole"') == 3
    assert svg.count('data-kind="engrave"') == 6  # three scored rectangles, three numbers


def test_the_svg_a_sheet_writes_is_well_formed_xml() -> None:
    sheets, _ = nest(((panel(), 2),), Bed(300.0, 200.0))
    root = ElementTree.fromstring(sheet_svg(sheets[0], "sheet & co"))
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    groups = root.findall("{http://www.w3.org/2000/svg}g/{http://www.w3.org/2000/svg}g")
    assert [g.get("id") for g in groups] == ["cut", "engrave"]
    ElementTree.fromstring(part_svg(panel()))


# ---- dxf -----------------------------------------------------------------------------


def _pairs(dxf: str) -> tuple[tuple[str, str], ...]:
    lines = dxf.split("\n")[:-1]
    assert len(lines) % 2 == 0
    return tuple((lines[i], lines[i + 1]) for i in range(0, len(lines), 2))


def _polyline_vertices(dxf: str, layer: str) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Every POLYLINE on one layer, as its vertex coordinates."""
    out: list[tuple[tuple[float, float], ...]] = []
    current: list[tuple[float, float]] | None = None
    on_layer = False
    entity = ""
    x: float | None = None
    for code, value in _pairs(dxf):
        if code == "0":
            entity = value
            if value == "POLYLINE":
                current, on_layer = [], False
            elif value == "SEQEND":
                if current is not None and on_layer:
                    out.append(tuple(current))
                current = None
            x = None
        elif code == "8" and entity == "POLYLINE":
            on_layer = value == layer
        elif code == "10" and entity == "VERTEX":
            x = float(value)
        elif code == "20" and entity == "VERTEX" and x is not None and current is not None:
            current.append((x, float(value)))
            x = None
    return tuple(out)


def _flat(ring: tuple[tuple[float, float], ...]) -> tuple[float, ...]:
    """A ring as one run of numbers, which is what ``approx`` can compare."""
    return tuple(value for point in ring for value in point)


def _sheet_of(p: Part) -> Sheet:
    sheets, warnings = nest((p,), Bed(300.0, 200.0))
    assert warnings == ()
    return sheets[0]


def test_dxf_is_r12_with_a_cut_and_an_engrave_layer() -> None:
    dxf = sheet_dxf(_sheet_of(panel()))
    pairs = _pairs(dxf)
    assert pairs[0] == ("0", "SECTION")
    assert ("1", "AC1009") in pairs
    assert ("2", "CUT") in pairs
    assert ("2", "ENGRAVE") in pairs
    assert pairs[-1] == ("0", "EOF")
    assert ("0", "POLYLINE") in pairs
    assert ("0", "VERTEX") in pairs
    assert ("0", "SEQEND") in pairs
    assert ("0", "TEXT") in pairs
    assert ("1", "3 & up") in pairs  # DXF is not XML; text goes in raw


def test_dxf_puts_cuts_and_engravings_on_their_own_layers() -> None:
    dxf = sheet_dxf(_sheet_of(panel()))
    cuts = _polyline_vertices(dxf, "CUT")
    engraves = _polyline_vertices(dxf, "ENGRAVE")
    assert len(cuts) == 2  # outline and vent
    assert len(engraves) == 1  # the scored rectangle
    assert len(engraves[0]) == 4  # a closed ring says so with a flag, not a repeated corner


def test_dxf_flattens_an_arc_to_within_a_twentieth_of_a_millimetre() -> None:
    bored = cut(
        fill(rect(60, 60, label=Label("outline")), label=Label("front")),
        circle(20, Point(30, 30)),
        label=Label("bore"),
    )
    disc = part(Label("disc"), bored, Stock(3.0, "ply", kerf=0.0), Process.LASER)
    ring = _polyline_vertices(sheet_dxf(_sheet_of(disc)), "CUT")[1]
    centre = (3.0 + 30.0, 3.0 + 30.0)  # the margin, then the hole in the panel
    radii = tuple(math.hypot(x - centre[0], y - centre[1]) for x, y in ring)
    assert radii == pytest.approx((20.0,) * len(ring), abs=1e-3)
    sagitta = max(
        20.0 - math.hypot((a[0] + b[0]) / 2 - centre[0], (a[1] + b[1]) / 2 - centre[1])
        for a, b in zip(ring, (*ring[1:], ring[0]), strict=True)
    )
    assert 0.0 < sagitta <= 0.05 + 1e-6
    assert len(ring) >= 16


def test_dxf_closes_a_cut_ring_and_keeps_it_where_the_svg_put_it() -> None:
    dxf = sheet_dxf(_sheet_of(panel()))
    assert ("70", "1") in _pairs(dxf)
    outline = _polyline_vertices(dxf, "CUT")[0]
    # panel() is 60 x 40 mm on PLY's 0.25 mm kerf, grown by half that (0.125 mm) on every
    # side before nesting: 60.25 x 40.25, then Bed's default 3 mm margin from the corner
    assert _flat(outline) == pytest.approx((3, 3, 63.25, 3, 63.25, 43.25, 3, 43.25))


def test_flattened_arcs_bulge_the_way_the_sweep_flags_say() -> None:
    """Reading ``d`` back the way SVG defines it and measuring what it encloses is the
    end-to-end check on the sweep and large-arc flags: get one wrong and the arc lands on
    the other side of its chord, which the area notices."""
    outline = rounded_rect(20, 10, 2)
    rounded = part(
        Label("r"), fill(outline, label=Label("face")), Stock(3.0, "ply", kerf=0.0), Process.LASER
    )
    ring = _polyline_vertices(sheet_dxf(_sheet_of(rounded)), "CUT")[0]
    true_area = area(fill(outline))
    # chords cut the corner arcs off inside the true curve, so a little is always lost
    assert _ring_area(ring) == pytest.approx(true_area, rel=5e-3)
    assert _ring_area(ring) < true_area

    bore = circle(20, Point(30, 30))
    disc = part(
        Label("disc"),
        cut(
            fill(rect(60, 60, label=Label("outline")), label=Label("front")),
            bore,
            label=Label("bore"),
        ),
        Stock(3.0, "ply", kerf=0.0),
        Process.LASER,
    )
    hole = _polyline_vertices(sheet_dxf(_sheet_of(disc)), "CUT")[1]
    assert _ring_area(hole) == pytest.approx(area(fill(bore)), rel=1e-2)


def _ring_area(ring: tuple[tuple[float, float], ...]) -> float:
    pairs = zip(ring, (*ring[1:], ring[0]), strict=True)
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairs)) / 2


def _arc_ends(d: str) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    """Where each ``A`` command starts and where it ends, walking the path as SVG does."""
    token = d.split()
    out: list[tuple[tuple[float, float], tuple[float, float]]] = []
    here = (0.0, 0.0)
    i = 0
    while i < len(token):
        match token[i]:
            case "M" | "L":
                here = (float(token[i + 1]), float(token[i + 2]))
                i += 3
            case "A":
                end = (float(token[i + 6]), float(token[i + 7]))
                out.append((here, end))
                here = end
                i += 8
            case _:
                i += 1
    return tuple(out)


def _full_turn_bore() -> Part:
    """A hole written as one ``Arc`` that sweeps the whole way round, rather than as the
    ``Circle`` that :func:`circle` would give."""
    bore = wire((Edge(Arc(Point(30, 30), 20.0, 0.0, 2 * math.pi, XY)),), Label("bore"))
    return part(
        Label("disc"),
        cut(
            fill(rect(60, 60, label=Label("outline")), label=Label("front")),
            bore,
            label=Label("bore"),
        ),
        Stock(3.0, "ply", kerf=0.0),
        Process.LASER,
    )


def test_a_full_turn_arc_is_cut_as_two_half_arcs_rather_than_nothing() -> None:
    """One ``A`` whose ends coincide is dropped by the SVG spec, so a whole-turn arc
    written as a single command is a hole the model has and the cut file does not."""
    hole = next(p for p in part_paths(_full_turn_bore()) if p.kind == "hole")
    assert hole.d.count("A ") == 2
    for start, end in _arc_ends(hole.d):
        assert math.dist(start, end) > 1e-6, hole.d
    # two half turns is exactly what a Circle of the same size writes, so they agree
    same = cut(
        fill(rect(60, 60, label=Label("outline")), label=Label("front")),
        circle(20, Point(30, 30)),
        label=Label("bore"),
    )
    assert hole.d == face_paths(same, "")[1].d


def test_a_full_turn_arc_reads_back_out_of_dxf_like_a_circle_does() -> None:
    turned = _polyline_vertices(sheet_dxf(_sheet_of(_full_turn_bore())), "CUT")[1]
    as_circle = part(
        Label("disc"),
        cut(
            fill(rect(60, 60, label=Label("outline")), label=Label("front")),
            circle(20, Point(30, 30)),
            label=Label("bore"),
        ),
        Stock(3.0, "ply", kerf=0.0),
        Process.LASER,
    )
    assert len(turned) == len(_polyline_vertices(sheet_dxf(_sheet_of(as_circle)), "CUT")[1])
    # chords cut inside the true curve, so the flattened ring is always a little smaller
    assert _ring_area(turned) == pytest.approx(math.pi * 400, rel=1e-2)
    assert _ring_area(turned) < math.pi * 400


def test_a_full_turn_arc_keeps_its_area_through_the_svg_a_sheet_writes() -> None:
    panel = _full_turn_bore()
    svg = sheet_svg(_sheet_of(panel), "sheet-3mm-01")
    root = ElementTree.fromstring(svg)
    rings = tuple(
        _rings_of(element.get("d") or "")
        for element in root.iter("{http://www.w3.org/2000/svg}path")
    )
    assert len(rings) == 2
    read_back = _ring_area(rings[0]) - _ring_area(rings[1])
    shape = panel.shape
    assert isinstance(shape, Face)
    assert read_back == pytest.approx(area(shape), rel=1e-3)


def _rings_of(d: str) -> tuple[tuple[float, float], ...]:
    """One subpath of ``d`` as points, every ``A`` walked as the SVG spec reads it."""
    token = d.split()
    out: list[tuple[float, float]] = []
    i = 0
    while i < len(token):
        match token[i]:
            case "M" | "L":
                out.append((float(token[i + 1]), float(token[i + 2])))
                i += 3
            case "A":
                out += _svg_arc(
                    out[-1],
                    (float(token[i + 6]), float(token[i + 7])),
                    float(token[i + 1]),
                    large=token[i + 4] == "1",
                    sweep=token[i + 5] == "1",
                )
                i += 8
            case _:
                i += 1
    return tuple(out)


def _svg_arc(
    start: tuple[float, float],
    end: tuple[float, float],
    r: float,
    *,
    large: bool,
    sweep: bool,
) -> tuple[tuple[float, float], ...]:
    """An SVG elliptical-arc command with equal radii, stepped out at a degree a time."""
    (x0, y0), (x1, y1) = start, end
    dx, dy = x1 - x0, y1 - y0
    span = math.hypot(dx, dy)
    assert span > 1e-9, "an A whose ends coincide draws nothing at all"
    lift = math.sqrt(max(0.0, r * r - span * span / 4))
    side = 1.0 if large != sweep else -1.0
    cx = (x0 + x1) / 2 + side * lift * -dy / span
    cy = (y0 + y1) / 2 + side * lift * dx / span
    a0 = math.atan2(y0 - cy, x0 - cx)
    a1 = math.atan2(y1 - cy, x1 - cx)
    if sweep and a1 <= a0:
        a1 += 2 * math.pi
    if not sweep and a1 >= a0:
        a1 -= 2 * math.pi
    steps = max(1, math.ceil(abs(a1 - a0) / math.radians(1.0)))
    angles = tuple(a0 + (a1 - a0) * k / steps for k in range(1, steps + 1))
    return tuple((cx + r * math.cos(a), cy + r * math.sin(a)) for a in angles)


def test_a_path_with_no_arcs_round_trips_its_corners() -> None:
    p = part(Label("p"), fill(rect(10, 4), label=Label("front")), Stock(3.0, "ply"), Process.LASER)
    ring = _polyline_vertices(sheet_dxf(_sheet_of(p)), "CUT")[0]
    # this Stock has no kerf, so the 10 x 4 mm rectangle nests unchanged behind Bed's
    # default 3 mm margin: (3, 3) to (3 + 10, 3 + 4)
    assert _flat(ring) == pytest.approx((3, 3, 13, 3, 13, 7, 3, 7))
