from itertools import combinations

import pytest

from bench import (
    BBox,
    Bed,
    Label,
    Part,
    Placement,
    Point,
    Process,
    Sheet,
    Stock,
    Text,
    bbox,
    circle,
    cuboid,
    cut,
    fill,
    nest,
    part,
    part_paths,
    part_texts,
    rect,
    rotate,
    rounded_rect,
    sheet_name,
)

pytestmark = pytest.mark.functional

PLY = Stock(3.0, "birch ply", kerf=0.25)
THICK = Stock(6.0, "birch ply", kerf=0.4)


def _panel(label: str, w: float, h: float, stock: Stock = PLY) -> Part:
    return part(
        Label(label),
        fill(rect(w, h, label=Label("outline")), label=Label("face")),
        stock,
        Process.LASER,
    )


def _overlap(a: BBox, b: BBox) -> bool:
    return a.x0 < b.x1 - 1e-9 and b.x0 < a.x1 - 1e-9 and a.y0 < b.y1 - 1e-9 and b.y0 < a.y1 - 1e-9


def _every_placement(sheets: tuple[Sheet, ...]) -> tuple[Placement, ...]:
    return tuple(placed for sheet in sheets for placed in sheet.parts)


# ---- the invariants ------------------------------------------------------------------


def test_every_box_stays_inside_the_margins_and_clear_of_every_other() -> None:
    parts = (
        (_panel("wide", 180, 40), 4),
        (_panel("tall", 40, 170), 3),
        (_panel("square", 90, 90), 5),
        (_panel("sliver", 6, 120), 7),
        (_panel("thick-wide", 200, 60, THICK), 6),
        _panel("odd", 33, 77),
    )
    sheets, warnings = nest(parts, Bed(300.0, 200.0, margin=5.0, gap=2.0))
    assert warnings == ()
    assert sum(len(s.parts) for s in sheets) == 4 + 3 + 5 + 7 + 6 + 1
    for sheet in sheets:
        for placed in sheet.parts:
            box = placed.box
            assert box.x0 >= 5.0 - 1e-9
            assert box.y0 >= 5.0 - 1e-9
            assert box.x1 <= sheet.w - 5.0 + 1e-9
            assert box.y1 <= sheet.h - 5.0 + 1e-9
        for a, b in combinations(sheet.parts, 2):
            assert not _overlap(a.box, b.box), f"{a.part.label} overlaps {b.part.label}"


def _coordinates(d: str) -> tuple[tuple[float, float], ...]:
    """Every point a path lands on, arc bulges aside."""
    token = d.split()
    out: list[tuple[float, float]] = []
    i = 0
    while i < len(token):
        match token[i]:
            case "M" | "L":
                out.append((float(token[i + 1]), float(token[i + 2])))
                i += 3
            case "A":
                out.append((float(token[i + 6]), float(token[i + 7])))
                i += 8
            case _:
                i += 1
    return tuple(out)


def test_the_geometry_a_placement_carries_lies_inside_the_box_it_reports() -> None:
    holed = part(
        Label("holed"),
        cut(
            fill(rect(120, 60, label=Label("outline")), label=Label("face")),
            circle(8, Point(20, 30)),
            label=Label("bore"),
        ),
        PLY,
        Process.LASER,
    )
    curvy = part(
        Label("curvy"), fill(rounded_rect(240, 40, 8), label=Label("face")), PLY, Process.LASER
    )
    sheets, warnings = nest(
        ((holed, 3), (curvy, 2), (_panel("tall", 40, 150), 2)), Bed(300.0, 200.0)
    )
    assert warnings == ()
    for placed in _every_placement(sheets):
        box = placed.box
        points = tuple(
            point for path in part_paths(placed.placed) for point in _coordinates(path.d)
        ) + tuple((t.x, t.y) for t in part_texts(placed.placed))
        assert points
        for x, y in points:
            assert box.x0 - 1e-9 <= x <= box.x1 + 1e-9, f"{placed.part.label} x {x} outside {box}"
            assert box.y0 - 1e-9 <= y <= box.y1 + 1e-9, f"{placed.part.label} y {y} outside {box}"


def test_a_gap_is_kept_between_neighbours_on_a_shelf() -> None:
    sheets, _ = nest(((_panel("p", 50, 50), 3),), Bed(300.0, 200.0, margin=4.0, gap=7.0))
    boxes = tuple(placed.box for placed in sheets[0].parts)
    assert tuple(b.x0 for b in boxes) == pytest.approx((4.0, 61.25, 118.5))
    assert all(b.y0 == pytest.approx(4.0) for b in boxes)


# ---- kerf -----------------------------------------------------------------------------


def test_each_blank_grows_by_half_the_kerf_all_round() -> None:
    sheets, _ = nest((_panel("p", 100, 50),), Bed(300.0, 200.0, margin=3.0))
    box = sheets[0].parts[0].box
    assert (box.w, box.h) == pytest.approx((100.25, 50.25))
    assert (box.x0, box.y0) == pytest.approx((3.0, 3.0))


def test_engravings_are_not_kerf_compensated_only_carried_along() -> None:
    scored = part(
        Label("p"),
        fill(rect(100, 50, label=Label("outline")), label=Label("face")),
        Stock(3.0, "ply", kerf=0.4),
        Process.LASER,
        engravings=(rect(40, 2, Point(10, 15), Label("score")), Text("3", Point(2, 2), 5.0)),
    )
    sheets, _ = nest((scored,), Bed(300.0, 200.0, margin=3.0))
    placed = sheets[0].parts[0]
    assert (placed.box.w, placed.box.h) == pytest.approx((100.4, 50.4))
    # the outline moved out 0.2 and the whole blank then moved to (3, 3), so the
    # engraving is 0.2 + 3 from where it was and is still 40 by 2
    engrave = next(p for p in part_paths(placed.placed) if p.kind == "engrave")
    assert engrave.d == "M 13.2 18.2 L 53.2 18.2 L 53.2 20.2 L 13.2 20.2 L 13.2 18.2 Z"
    lettering = part_texts(placed.placed)
    assert (lettering[0].x, lettering[0].y) == pytest.approx((5.2, 5.2))


def test_a_part_with_no_kerf_is_placed_exactly() -> None:
    sheets, _ = nest((_panel("p", 100, 50, Stock(3.0, "ply")),), Bed(300.0, 200.0, margin=3.0))
    assert sheets[0].parts[0].box == pytest.approx(BBox(3.0, 3.0, 103.0, 53.0))


# ---- quantities and thicknesses -------------------------------------------------------


def test_a_bare_part_means_one_and_a_pair_means_as_many_as_it_says() -> None:
    sheets, warnings = nest((_panel("a", 40, 40), (_panel("b", 40, 40), 3)), Bed(300.0, 200.0))
    assert warnings == ()
    labels = [placed.part.label for placed in _every_placement(sheets)]
    assert labels.count(Label("a")) == 1
    assert labels.count(Label("b")) == 3


def test_one_sheet_series_per_thickness_thinnest_first() -> None:
    parts = (
        (_panel("thick", 150, 150, THICK), 4),
        (_panel("thin", 150, 150, PLY), 4),
        (_panel("mid", 150, 150, Stock(4.0, "ply", kerf=0.2)), 1),
    )
    sheets, warnings = nest(parts, Bed(320.0, 320.0))
    assert warnings == ()
    assert tuple(s.thickness for s in sheets) == (3.0, 4.0, 6.0)
    for sheet in sheets:
        for placed in sheet.parts:
            # a nested part is cut from a sheet by construction; `Printed` never gets here
            assert isinstance(placed.part.stock, Stock)
            assert placed.part.stock.thickness == sheet.thickness


def test_parts_spill_onto_more_sheets_of_the_same_thickness() -> None:
    sheets, warnings = nest(((_panel("p", 140, 140), 5),), Bed(300.0, 300.0))
    assert warnings == ()
    assert len(sheets) == 2
    assert tuple(len(s.parts) for s in sheets) == (4, 1)
    assert {s.thickness for s in sheets} == {3.0}
    assert all((s.w, s.h) == (300.0, 300.0) for s in sheets)


def test_parts_come_back_tallest_first() -> None:
    sheets, _ = nest(
        (_panel("short", 40, 20), _panel("tall", 40, 120), _panel("middling", 40, 60)),
        Bed(300.0, 200.0),
    )
    assert tuple(p.part.label for p in sheets[0].parts) == (
        Label("tall"),
        Label("middling"),
        Label("short"),
    )


# ---- rotation -------------------------------------------------------------------------


def test_a_part_too_wide_for_the_bed_is_turned_a_quarter_turn() -> None:
    sheets, warnings = nest((_panel("long", 250, 30),), Bed(100.0, 300.0))
    assert warnings == ()
    placed = sheets[0].parts[0]
    assert placed.rotated
    assert (placed.box.w, placed.box.h) == pytest.approx((30.25, 250.25))


def test_a_part_is_turned_to_finish_a_shelf_it_would_not_otherwise_fit() -> None:
    # the shelf starts 120 tall with 84.75 left across it; the 100 by 30 part does not
    # fit that upright, and turned it is 30 by 100, still short enough for the shelf
    sheets, warnings = nest(
        (_panel("first", 200, 120), _panel("second", 100, 30)),
        Bed(300.0, 200.0, margin=5.0, gap=5.0),
    )
    assert warnings == ()
    first, second = sheets[0].parts
    assert not first.rotated
    assert second.rotated
    assert second.box.y0 == pytest.approx(first.box.y0)
    assert (second.box.w, second.box.h) == pytest.approx((30.25, 100.25))


def test_a_turn_that_would_make_the_shelf_taller_starts_a_new_shelf_instead() -> None:
    # 25 mm is left across a 20 mm shelf; the 30 by 15 part needs 30 upright and turning
    # it would stand 30 mm tall, so the shelf stays as it is and the part waits
    plain = Stock(3.0, "ply")
    sheets, warnings = nest(
        (_panel("first", 60, 20, plain), _panel("second", 30, 15, plain)),
        Bed(100.0, 200.0, margin=5.0, gap=5.0),
    )
    assert warnings == ()
    first, second = sheets[0].parts
    assert not second.rotated
    assert second.box.y0 == pytest.approx(first.box.y1 + 5.0)
    assert second.box.x0 == pytest.approx(5.0)


def test_rotation_turns_the_geometry_with_the_box() -> None:
    holed = part(
        Label("p"),
        fill(rect(250, 30, label=Label("outline")), label=Label("face")),
        Stock(3.0, "ply"),
        Process.LASER,
        engravings=(Text("x", Point(10, 5), 4.0, Label("mark")),),
    )
    sheets, _ = nest((holed,), Bed(100.0, 300.0, margin=0.0))
    placed = sheets[0].parts[0]
    assert placed.rotated
    # a quarter turn counter-clockwise sends (10, 5) to (-5, 10), then back in by 30
    turned = part_texts(placed.placed)[0]
    assert (turned.x, turned.y) == pytest.approx((25.0, 10.0))
    assert placed.box == pytest.approx(BBox(0.0, 0.0, 30.0, 250.0))


# ---- warnings -------------------------------------------------------------------------


def test_a_part_too_big_either_way_round_is_warned_about_not_dropped() -> None:
    sheets, warnings = nest(
        ((_panel("huge", 400, 400), 2), _panel("fine", 50, 50)), Bed(300.0, 200.0, margin=3.0)
    )
    assert len(warnings) == 2
    assert all("huge" in w and "does not fit" in w for w in warnings)
    assert tuple(p.part.label for p in _every_placement(sheets)) == (Label("fine"),)


def test_a_part_that_only_fits_turned_is_not_warned_about() -> None:
    sheets, warnings = nest((_panel("long", 280, 60),), Bed(100.0, 300.0))
    assert warnings == ()
    assert sheets[0].parts[0].rotated


def test_a_part_too_tall_upright_is_turned_rather_than_dropped() -> None:
    """300 across by 200 up: a 100 by 250 panel fits across but stands 50 mm too tall, and
    turned it is 250 by 100, which fits. Trying the turn only when the part is too *wide*
    loses it with nothing said."""
    sheets, warnings = nest((_panel("tall", 100, 250),), Bed(300.0, 200.0, margin=3.0))
    assert warnings == ()
    placed = sheets[0].parts[0]
    assert placed.rotated
    assert (placed.box.w, placed.box.h) == pytest.approx((250.25, 100.25))
    assert (placed.box.x0, placed.box.y0) == pytest.approx((3.0, 3.0))


def test_a_part_too_tall_upright_still_lands_beside_a_wide_neighbour() -> None:
    """Mixed in with a part that shares its shelf, nothing vanishes: every blank asked for
    comes back on a sheet."""
    parts = ((_panel("tall", 100, 250), 2), (_panel("wide", 180, 40), 3), _panel("small", 20, 20))
    sheets, warnings = nest(parts, Bed(300.0, 200.0, margin=3.0, gap=2.0))
    assert warnings == ()
    placed = _every_placement(sheets)
    assert len(placed) == 2 + 3 + 1
    assert [p.part.label for p in placed].count(Label("tall")) == 2
    assert all(p.rotated for p in placed if p.part.label == Label("tall"))
    for sheet in sheets:
        for a, b in combinations(sheet.parts, 2):
            assert not _overlap(a.box, b.box), f"{a.part.label} overlaps {b.part.label}"


def test_a_part_that_fits_no_way_round_still_warns_and_nothing_else_is_lost() -> None:
    parts = (_panel("tall", 100, 250), _panel("enormous", 400, 400), _panel("fine", 50, 50))
    sheets, warnings = nest(parts, Bed(300.0, 200.0, margin=3.0))
    assert len(warnings) == 1
    assert "enormous" in warnings[0] and "does not fit" in warnings[0]
    assert {str(p.part.label) for p in _every_placement(sheets)} == {"tall", "fine"}


def test_two_round_parts_turned_off_axis_keep_their_distance() -> None:
    """A disc is as wide as its diameter whichever way its arc's frame is turned. Measure
    it from the frame instead and the blanks are cut too small, so the discs themselves
    overlap on the sheet even though their boxes do not."""
    disc = part(
        Label("disc"),
        fill(rotate(circle(25), 0.4), label=Label("face")),
        Stock(3.0, "ply"),
        Process.LASER,
    )
    sheets, warnings = nest(((disc, 2),), Bed(300.0, 200.0, margin=3.0, gap=1.0))
    assert warnings == ()
    a, b = sheets[0].parts
    assert (a.box.w, a.box.h) == pytest.approx((50.0, 50.0))
    assert _centre(b) - _centre(a) >= 51.0 - 1e-9


def _centre(placed: Placement) -> float:
    """Where a placement sits across the sheet; both discs share a shelf, so X is enough."""
    return (placed.box.x0 + placed.box.x1) / 2


def test_a_margin_that_swallows_the_sheet_warns_for_everything_and_nests_nothing() -> None:
    sheets, warnings = nest((_panel("p", 10, 10),), Bed(100.0, 100.0, margin=60.0))
    assert sheets == ()
    assert len(warnings) == 1


def test_a_solid_part_is_warned_about_rather_than_nested() -> None:
    lump = part(
        Label("lump"),
        cuboid(10, 10, 10, label=Label("body")),
        PLY,
        Process.LASER,
    )
    sheets, warnings = nest((lump, _panel("flat", 20, 20)), Bed(300.0, 200.0))
    assert len(warnings) == 1
    assert "lump" in warnings[0]
    assert tuple(p.part.label for p in _every_placement(sheets)) == (Label("flat"),)


# ---- names and records ----------------------------------------------------------------


def test_a_bed_is_a_sheet_and_the_two_clearances_round_everything_on_it() -> None:
    assert Bed(300.0, 200.0) == (300.0, 200.0, 3.0, 3.0)
    sheets, _ = nest((_panel("p", 50, 50), _panel("q", 50, 50)), Bed(300.0, 200.0))
    first, second = sheets[0].parts
    assert (first.box.x0, first.box.y0) == pytest.approx((3.0, 3.0))
    assert second.box.x0 - first.box.x1 == pytest.approx(3.0)


def test_sheet_name_reads_thickness_and_place_in_the_series() -> None:
    sheet = Sheet(3.0, 300.0, 200.0, ())
    assert sheet_name(sheet, 0) == "sheet-3mm-01"
    assert sheet_name(sheet, 2) == "sheet-3mm-03"
    assert sheet_name(Sheet(6.0, 1.0, 1.0, ()), 0) == "sheet-6mm-01"
    assert sheet_name(Sheet(3.2, 1.0, 1.0, ()), 11) == "sheet-3.2mm-12"


def test_a_placement_keeps_the_part_the_script_made_and_the_one_that_gets_cut() -> None:
    panel = _panel("p", 40, 40)
    sheets, _ = nest((panel,), Bed(300.0, 200.0))
    placed = sheets[0].parts[0]
    assert placed.part is panel
    assert placed.placed.label == panel.label
    # the part that gets cut is kerf-compensated and already in sheet coordinates
    assert tuple(bbox(placed.placed.shape)) == pytest.approx(tuple(placed.box))
    assert bbox(panel.shape).x1 == pytest.approx(40.0)
    assert (placed.at.x, placed.at.y) == pytest.approx((placed.box.x0, placed.box.y0))
    assert isinstance(placed, Placement)
    with pytest.raises(AttributeError):
        placed.rotated = True  # type: ignore[misc]


def test_nesting_nothing_gives_nothing() -> None:
    assert nest((), Bed(300.0, 200.0)) == ((), ())
