"""Report: a survey record rendered as text, from the record alone.

Every survey here is built by hand out of the survey's own records - no mesh, no
:func:`bench.survey.survey` - which is criterion #1 made into a test: the report can only say
what the record holds. The checks are on the wording, because the wording is the job: a
candidate is offered and never concluded, nothing is said that was not measured, and the same
record renders the same text however its lists arrived.
"""

import math
import re

import pytest

from bench import Point, Vector
from bench.report import report
from bench.survey import (
    Band,
    Extent,
    Flat,
    Outline,
    Repeat,
    Round,
    Section,
    Step,
    Survey,
    Walls,
)

pytestmark = pytest.mark.unit

_UP = Vector(0.0, 0.0, 1.0)
_DOWN = Vector(0.0, 0.0, -1.0)


def _flat(normal: Vector, low: Point, high: Point, area: float, facets: int = 2) -> Flat:
    centre = Point((low.x + high.x) / 2, (low.y + high.y) / 2, (low.z + high.z) / 2)
    return Flat(normal=normal, centre=centre, low=low, high=high, area=area, facets=facets)


def _round(
    radius: float,
    centre: Point,
    length: float,
    *,
    concave: bool,
    turn: float = 2.0 * math.pi,
    axis: Vector = _UP,
) -> Round:
    half = axis * (length / 2.0)
    return Round(
        axis=axis,
        centre=centre,
        radius=radius,
        length=length,
        turn=turn,
        concave=concave,
        spread=0.0004,
        low=centre - half - Vector(radius, radius, 0.0),
        high=centre + half + Vector(radius, radius, 0.0),
        area=2.0 * math.pi * radius * length * turn / (2.0 * math.pi),
        facets=48,
    )


def _outline(low: Point, high: Point, area: float, *, closed: bool = True) -> Outline:
    return Outline(low=low, high=high, area=area, closed=closed)


def _plate() -> Survey:
    """A 60 x 40 x 3 plate with a 4 mm bore through it and three 2 mm bosses in a row: the
    record :func:`bench.survey.survey` would give for it, written out by hand."""
    rim = _outline(Point(0.0, 0.0), Point(60.0, 40.0), 2400.0 - math.pi * 4.0)
    bore = _outline(Point(28.0, 8.0), Point(32.0, 12.0), math.pi * 4.0)
    boss = _round(2.0, Point(10.0, 20.0, 5.0), 4.0, concave=False)
    crown = _flat(_UP, Point(8.0, 18.0, 7.0), Point(12.0, 22.0, 7.0), math.pi * 4.0, 22)
    return Survey(
        triangles=336,
        extent=Extent(Point(0.0, 0.0, 0.0), Point(60.0, 40.0, 7.0), Vector(60.0, 40.0, 7.0)),
        sections=(
            Section(z=1.0, outlines=(rim, bore)),
            Section(z=2.0, outlines=(bore, rim)),
        ),
        walls=Walls(
            thinnest=3.0,
            at=Point(40.0, 13.333, 0.0),
            bands=(Band(3.0, 4800.0), Band(40.0, 360.0), Band(60.0, 240.0), Band(4.0, 224.9)),
        ),
        flats=(
            _flat(_DOWN, Point(0.0, 0.0, 0.0), Point(60.0, 40.0, 0.0), 2400.0),
            _flat(_UP, Point(0.0, 0.0, 3.0), Point(60.0, 40.0, 3.0), 2400.0 - math.pi * 4.0),
            _flat(Vector(0.0, -1.0, 0.0), Point(0.0, 0.0, 0.0), Point(60.0, 0.0, 3.0), 180.0),
            _flat(Vector(1.0, 0.0, 0.0), Point(60.0, 0.0, 0.0), Point(60.0, 40.0, 3.0), 120.0),
        ),
        rounds=(_round(2.0, Point(30.0, 10.0, 1.5), 3.0, concave=True),),
        repeats=(
            Repeat(one=boss, steps=(Step(Vector(20.0, 0.0, 0.0), 3),)),
            Repeat(one=crown, steps=(Step(Vector(20.0, 0.0, 0.0), 3),)),
        ),
    )


def _measured(text: str) -> str:
    """The report up to its closing block, which is the only place the words for what was
    *not* measured - fit, nominal - are allowed to appear."""
    body, _, _ = text.partition("NOT MEASURED")
    return body


# ---- the same survey renders the same report -------------------------------------------


def test_rendering_twice_gives_the_same_text() -> None:
    found = _plate()

    assert report(found) == report(found)


def test_the_order_records_arrive_in_does_not_show() -> None:
    """Every list a survey holds, reversed: the report sorts on the numbers, not on arrival."""
    found = _plate()
    shuffled = Survey(
        triangles=found.triangles,
        extent=found.extent,
        sections=tuple(
            Section(z=s.z, outlines=tuple(reversed(s.outlines))) for s in reversed(found.sections)
        ),
        walls=Walls(
            thinnest=found.walls.thinnest,
            at=found.walls.at,
            bands=tuple(reversed(found.walls.bands)),
        )
        if found.walls is not None
        else None,
        flats=tuple(reversed(found.flats)),
        rounds=tuple(reversed(found.rounds)),
        repeats=tuple(
            Repeat(one=r.one, steps=tuple(reversed(r.steps))) for r in reversed(found.repeats)
        ),
    )

    assert report(shuffled) == report(found)


def test_every_number_prints_to_fixed_places() -> None:
    text = report(_plate())

    assert re.search(r"\d\.\d{4,}", text) is None, "a float leaked its full precision"
    assert re.search(r"\d\.\d+e[-+]\d", text) is None, "a float printed in scientific notation"


def test_a_negative_zero_prints_as_zero() -> None:
    found = _plate()
    tilted = Survey(
        triangles=found.triangles,
        extent=Extent(Point(-0.0, 0.0, -0.0000001), found.extent.high, found.extent.size),
        sections=found.sections,
        walls=found.walls,
        flats=found.flats,
        rounds=found.rounds,
        repeats=found.repeats,
    )

    assert "-0.000" not in report(tilted)


# ---- bench's vocabulary, offered as candidates -----------------------------------------


def test_a_bore_is_offered_as_a_hole_of_its_diameter() -> None:
    text = report(_plate())

    assert "bore: diameter 4.000 mm (radius 2.000), axis +Z, 3.000 mm long" in text
    assert "candidate: hole(body, ..., diameter=4.000, depth=3.000)" in text


def test_a_row_is_offered_as_a_pattern_and_a_grid_as_a_grid() -> None:
    text = report(_plate())
    assert "3 in a row, 20.000 mm apart along +X" in text
    assert "candidate: pattern(one, 3, Vector(20.000, 0.000, 0.000))" in text
    assert "candidate: cylinder(2.000, 4.000, at=Point(10.000, 20.000, 3.000))" in text

    found = _plate()
    gridded = Survey(
        triangles=found.triangles,
        extent=found.extent,
        sections=found.sections,
        walls=found.walls,
        flats=found.flats,
        rounds=found.rounds,
        repeats=(
            Repeat(
                one=found.repeats[0].one,
                steps=(Step(Vector(40.0, 0.0, 0.0), 2), Step(Vector(0.0, 20.0, 0.0), 2)),
            ),
        ),
    )
    text = report(gridded)
    # The shorter step is written first, whichever order the survey found them in.
    assert "2 x 2 grid, 20.000 mm apart along +Y and 40.000 mm along +X" in text
    assert (
        "candidate: grid(one, (2, 2), (Vector(0.000, 20.000, 0.000), Vector(40.000, 0.000, 0.000)))"
        in text
    )


def test_a_flat_is_placed_on_the_plane_it_lies_in() -> None:
    text = report(_plate())

    assert "facing +Z (up) at z = 3.000: 60.000 x 40.000 mm from (0.000, 0.000)" in text
    assert "candidate: an outline drawn on raised(XY, 3.000)" in text
    assert "facing -Y at y = 0.000: 60.000 mm along x from x = 0.000, 3.000 mm tall" in text
    assert 'plane_of(body, "side-...")' in text


def test_a_leaning_flat_is_offered_as_a_loft_not_an_extrude() -> None:
    lean = Vector(math.sin(math.radians(30.0)), 0.0, math.cos(math.radians(30.0)))
    found = _plate()
    leaning = Survey(
        triangles=found.triangles,
        extent=found.extent,
        sections=found.sections,
        walls=found.walls,
        flats=(_flat(lean, Point(0.0, 0.0, 0.0), Point(10.0, 40.0, 17.32), 800.0),),
        rounds=(),
        repeats=(),
    )
    text = report(leaning)

    assert "30 degrees off horizontal" in text
    assert "candidate: a face that leans is a loft() between two outlines" in text


def test_a_partial_round_about_z_is_a_corner_and_about_x_a_rod_or_a_fillet() -> None:
    """A partial round lying along an axis that is not vertical could be either a rod that
    has not gone all the way round or a fillet easing a corner - convex, either reading is
    live, so both are offered; task-23 is what stops a concave one from getting the rod half
    of this, tested below."""
    found = _plate()
    quarter_z = _round(3.0, Point(3.0, 3.0, 5.0), 10.0, concave=False, turn=math.pi / 2.0)
    quarter_x = _round(
        3.0,
        Point(30.0, 3.0, 3.0),
        60.0,
        concave=False,
        turn=math.pi / 2.0,
        axis=Vector(1.0, 0.0, 0.0),
    )
    text = report(
        Survey(
            triangles=found.triangles,
            extent=found.extent,
            sections=found.sections,
            walls=found.walls,
            flats=(),
            rounds=(quarter_z, quarter_x),
            repeats=(),
        )
    )

    assert "partial round: radius 3.000 mm over 90 degrees, axis +Z" in text
    assert "candidate: an outside corner of a rounded_rect(..., 3.000) extruded 10.000 mm" in text
    assert "partial round: radius 3.000 mm over 90 degrees, axis +X" in text
    assert (
        "candidate: 90 degrees of a cylinder of diameter 6.000 lying along +X - a rod or a bar "
        "if the surface goes on round, a fillet or an eased edge if it rounds a corner" in text
    ), "the systainer's 18 mm grip is a partial round too, and it is convex, so it is no fillet"


def test_a_concave_partial_round_is_never_offered_as_a_rod() -> None:
    """A concave surface has material outside it, so however far it turns it is not a rod or
    a bar - the failure task-23 exists for. At a quarter turn it is still a plausible inside
    fillet or eased edge, the same reading the axis-along-Z corner wording gives a corner."""
    found = _plate()
    quarter_x = _round(
        3.0,
        Point(30.0, 3.0, 3.0),
        60.0,
        concave=True,
        turn=math.pi / 2.0,
        axis=Vector(1.0, 0.0, 0.0),
    )
    text = report(
        Survey(
            triangles=found.triangles,
            extent=found.extent,
            sections=found.sections,
            walls=found.walls,
            flats=(),
            rounds=(quarter_x,),
            repeats=(),
        )
    )

    assert "partial round: radius 3.000 mm over 90 degrees, axis +X" in text
    assert (
        "candidate: 90 degrees of a concave cylinder of diameter 6.000 lying along +X - a "
        "fillet or an eased edge rounding a corner; material is outside it, so it is never a "
        "rod or a bar" in text
    )
    assert "a rod or a bar if the surface goes on round" not in text


def test_a_concave_partial_round_nearly_full_is_a_bore_opened_into() -> None:
    """The systainer handle's own case: a 4 mm bore, concave, that turns 345 of 360 degrees -
    a bore something (a slot) has opened into, never a rod and, at that much arc, not
    sensibly a fillet or an eased edge either."""
    found = _plate()
    nearly_full = _round(
        2.0,
        Point(30.0, 3.0, 3.0),
        10.0,
        concave=True,
        turn=math.radians(345.0),
        axis=Vector(1.0, 0.0, 0.0),
    )
    text = report(
        Survey(
            triangles=found.triangles,
            extent=found.extent,
            sections=found.sections,
            walls=found.walls,
            flats=(),
            rounds=(nearly_full,),
            repeats=(),
        )
    )

    assert "partial round: radius 2.000 mm over 345 degrees, axis +X" in text
    assert (
        "candidate: 345 degrees of a bore of diameter 4.000 lying along +X, missing 15 "
        "degrees - hole(...) with a slot or a wall opened into it along the missing arc; "
        "material is outside it, so it is never a rod or a bar" in text
    )


def test_a_concave_partial_round_at_half_turn_gets_no_candidate() -> None:
    """Neither a fillet nor a bore opened by something is warranted at 180 degrees - task-23
    criterion #3, and the report says so rather than guessing."""
    found = _plate()
    half = _round(
        2.0,
        Point(30.0, 3.0, 3.0),
        10.0,
        concave=True,
        turn=math.radians(220.0),
        axis=Vector(1.0, 0.0, 0.0),
    )
    text = report(
        Survey(
            triangles=found.triangles,
            extent=found.extent,
            sections=found.sections,
            walls=found.walls,
            flats=(),
            rounds=(half,),
            repeats=(),
        )
    )

    assert "partial round: radius 2.000 mm over 220 degrees, axis +X" in text
    assert (
        "no candidate: 220 degrees of a concave cylinder of diameter 4.000 lying along +X is "
        "too much arc to call a fillet or an eased edge and not little enough missing to be "
        "sure it is a bore something has opened into; the measurement above is all this is" in text
    )


def test_sections_that_match_offer_one_extrude_and_sections_that_differ_refuse_it() -> None:
    straight = report(_plate())
    assert "is the same section to within 0.050 mm; candidate: one straight extrude()" in straight

    found = _plate()
    tapered = Survey(
        triangles=found.triangles,
        extent=found.extent,
        sections=(
            found.sections[0],
            Section(
                z=2.0,
                outlines=(
                    _outline(Point(1.0, 1.0), Point(59.0, 39.0), 2204.0),
                    found.sections[0].outlines[1],
                ),
            ),
        ),
        walls=found.walls,
        flats=found.flats,
        rounds=found.rounds,
        repeats=found.repeats,
    )
    text = report(tapered)
    assert "the sections differ between z = 1.000 and z = 2.000" in text
    assert "not one straight extrude()" in text
    assert "candidate: one straight extrude()" not in text


def test_an_outline_says_how_much_of_its_box_it_fills_and_names_no_shape() -> None:
    """A rounded_rect with small corners fills 99.7% of its box; the report cannot tell it
    from a rect, so it gives the share and the legend and lets the reader decide."""
    text = report(_plate())

    assert "enclosing 2387.4 mm2, filling 99.5% of its box" in text
    assert "a rect fills 100.0%, a circle or an ellipse 78.5%" in text
    assert "as a rect does" not in text


# ---- nothing that was not measured -----------------------------------------------------


def test_a_bore_is_never_a_screw_a_fit_or_a_nominal() -> None:
    body = _measured(report(_plate()))

    for word in ("M4", "clearance", "nominal", "Fit", "fit ", "screw"):
        assert word not in body, f"{word!r} claims an intent the mesh does not hold"
    assert "which screw, fit or nominal asked for either is not in the mesh" in report(_plate())


def test_a_sliver_thinnest_reading_is_called_one_place_not_a_wall() -> None:
    found = _plate()
    assert found.walls is not None
    sliver = Survey(
        triangles=found.triangles,
        extent=found.extent,
        sections=found.sections,
        walls=Walls(
            thinnest=0.012,
            at=Point(12.5, 0.0, 3.0),
            bands=(*found.walls.bands, Band(0.0, 0.3)),
        ),
        flats=found.flats,
        rounds=found.rounds,
        repeats=found.repeats,
    )
    text = report(sliver)

    assert "thinnest single reading: 0.012 mm at (12.500, 0.000, 3.000), from one triangle" in text
    assert "under a square millimetre of surface read within 0.050 mm of it" in text
    assert "so this is one place, as a sliver of the tessellation leaves" in text
    assert "not a wall; the bands above are where the material is" in text
    assert "candidate: a wall of 3.000 mm" in text


def test_a_thin_reading_with_real_surface_behind_it_is_a_thin_place_not_a_sliver() -> None:
    """The systainer base plate: 0.500 mm under 44.8 mm2 - the four 3.8 x 3.8 mm socket
    floors - is a genuine thin floor, well under 1% of the surface. It is neither a sliver
    nor a wall, and the report says exactly that."""
    found = _plate()
    assert found.walls is not None
    floors = Survey(
        triangles=found.triangles,
        extent=found.extent,
        sections=found.sections,
        walls=Walls(
            thinnest=0.5,
            at=Point(269.221, 74.328, 0.5),
            bands=(*found.walls.bands, Band(0.5, 44.8)),
        ),
        flats=found.flats,
        rounds=found.rounds,
        repeats=found.repeats,
    )
    text = report(floors)

    assert "thinnest single reading: 0.500 mm at (269.221, 74.328, 0.500); 44.8 mm2" in text
    assert "a thin place of that area, not one of the walls above" in text
    assert "one place" not in text
    assert "candidate: a wall of 3.000 mm" in text


def test_a_thinnest_reading_the_surface_agrees_with_is_a_wall() -> None:
    text = report(_plate())

    assert (
        "thinnest single reading: 3.000 mm at (40.000, 13.333, 0.000), in the 3.000 mm band" in text
    )
    assert "4800.0 mm2 (85.3%) of the surface measured" in text, "4800 of 5624.9 mm2"
    assert "one place" not in text


def test_band_tail_under_a_percent_each_is_summed_into_one_line() -> None:
    found = _plate()
    assert found.walls is not None
    noisy = Survey(
        triangles=found.triangles,
        extent=found.extent,
        sections=found.sections,
        walls=Walls(
            thinnest=3.0,
            at=found.walls.at,
            bands=(*found.walls.bands, *(Band(8.0 + 0.1 * k, 2.0) for k in range(30))),
        ),
        flats=found.flats,
        rounds=found.rounds,
        repeats=found.repeats,
    )
    text = report(noisy)

    assert "and 30 more bands, 8.000 to 10.900 mm, each under 1.0% of the surface" in text
    assert "8.100 mm under" not in text
    assert "3.000 mm under 4800.0 mm2" in text


def test_an_open_outline_is_flagged_and_its_area_distrusted() -> None:
    found = _plate()
    torn = Survey(
        triangles=found.triangles,
        extent=found.extent,
        sections=(
            Section(
                z=1.0,
                outlines=(_outline(Point(0.0, 0.0), Point(60.0, 40.0), 2100.0, closed=False),),
            ),
        ),
        walls=found.walls,
        flats=found.flats,
        rounds=found.rounds,
        repeats=found.repeats,
    )
    text = report(torn)

    assert (
        "OPEN - its ends did not meet: the plane runs along an edge or a face of the mesh" in text
    )
    assert "or the mesh has a gap; either way the area is not to be trusted" in text
    assert "filling" not in text.partition("WALLS")[0]


def test_runs_enclosing_no_area_are_one_line_and_not_counted_as_outlines() -> None:
    """A height that lands exactly on a plateau - the systainer foot at z = 3.400 - leaves
    dozens of zero-length runs beside the real outlines. They are a fact about the height
    chosen, not the mesh, and are neither listed one by one nor called a gap."""
    found = _plate()
    real = found.sections[0].outlines
    traces = tuple(
        _outline(Point(610.0 + k, -105.0), Point(610.0 + k, -105.0), 0.0, closed=k % 7 != 0)
        for k in range(36)
    )
    plateau = Survey(
        triangles=found.triangles,
        extent=found.extent,
        sections=(Section(z=3.4, outlines=(*traces, *real)), found.sections[1]),
        walls=found.walls,
        flats=found.flats,
        rounds=found.rounds,
        repeats=found.repeats,
    )
    text = report(plateau)

    assert "at z = 3.400: 2 outlines" in text
    assert "and 36 runs enclosing no area: what a plane leaves where it meets the mesh" in text
    assert "survey(mesh, at=...) a little off it would not" in text
    assert "gap" not in text.partition("WALLS")[0]
    assert text.count("OPEN") == 0
    assert "is the same section to within 0.050 mm" in text, "the traces do not break straightness"


def test_what_was_not_found_is_said_to_be_absent_not_left_out() -> None:
    found = _plate()
    bare = Survey(
        triangles=12,
        extent=found.extent,
        sections=(),
        walls=None,
        flats=(),
        rounds=(),
        repeats=(),
    )
    text = report(bare)

    assert "none taken: the body has no height to cut through" in text
    assert "no thickness measured: no ray from any triangle met a surface facing back" in text
    assert "FLATS standing alone\n  none of a square millimetre or more" in text
    assert "ROUNDS standing alone\n  none of a square millimetre or more" in text
    assert "REPEATS\n  none: no three identical surfaces" in text
    for verb in ("hole(", "cylinder(", "pattern(", "grid(", "raised(", "a wall of"):
        assert verb not in text, f"{verb!r} offered with nothing measured to fit it"


def test_an_empty_survey_says_there_was_nothing_to_measure() -> None:
    text = report(
        Survey(
            triangles=0,
            extent=Extent(Point(0.0, 0.0, 0.0), Point(0.0, 0.0, 0.0), Vector(0.0, 0.0, 0.0)),
            sections=(),
            walls=None,
            flats=(),
            rounds=(),
            repeats=(),
        )
    )

    assert text.startswith("SURVEY of 0 triangles\n  nothing to measure")
    assert "cuboid(" not in text
    assert "account for" not in text


def test_the_surfaces_listed_are_counted_against_the_triangles() -> None:
    text = report(_plate())

    listed = 2 + 2 + 2 + 2 + 48 + 48 + 22
    assert f"account for {listed} of 336 triangles" in text
    assert "a repeat counted once" in text
    assert "each repeat is one surface" in text


# ---- flats that are not faces ----------------------------------------------------------


def test_single_triangles_and_strips_are_summed_and_offered_no_candidate() -> None:
    """On the systainer handle 507 of 592 flats are one triangle each - facets of a bent
    bar the round test could not take - and every one read as a face with a loft() beside
    it. One triangle is flat whatever it belongs to; a strip is the facet along an edge."""
    lean = Vector(math.sin(math.radians(30.0)), 0.0, math.cos(math.radians(30.0)))
    found = _plate()
    triangles = tuple(
        Flat(
            normal=lean,
            centre=Point(10.0 + k, 5.0, 2.0),
            low=Point(9.0 + k, 4.0, 1.0),
            high=Point(11.0 + k, 6.0, 3.0),
            area=2.0,
            facets=1,
        )
        for k in range(5)
    )
    strip = _flat(lean, Point(0.0, 0.0, 6.7), Point(31.0, 0.1, 6.8), 3.5, 28)
    face = _flat(lean, Point(0.0, 0.0, 0.0), Point(10.0, 40.0, 17.32), 800.0)
    text = report(
        Survey(
            triangles=found.triangles,
            extent=found.extent,
            sections=found.sections,
            walls=found.walls,
            flats=(*triangles, strip, face),
            rounds=(),
            repeats=(),
        )
    )
    flats_block = text.partition("FLATS standing alone")[2].partition("ROUNDS")[0]

    assert flats_block.count("candidate: a face that leans is a loft()") == 1, "the real face only"
    assert (
        "and 6 more flats not offered as faces - 5 of one triangle each and 1 strip under "
        "0.500 mm wide, 13.5 mm2 in all, the largest 3.5 mm2 at (15.500, 0.050, 6.750)"
    ) in text
    assert "one triangle is flat whatever surface it belongs to" in text
    assert "1 facet" not in flats_block, "no single triangle is listed on its own"


def test_a_repeat_of_single_triangles_keeps_its_spacing_but_gets_no_candidate_face() -> None:
    """The base plate's foot sockets repeat eleven one-triangle facets on the same 2 x 2
    grid as the sockets: the repetition is measured and stays, the face is not offered."""
    found = _plate()
    facet = Flat(
        normal=Vector(0.609, 0.793, 0.002),
        centre=Point(267.471, 72.477, 2.562),
        low=Point(267.244, 72.355, 0.5),
        high=Point(267.638, 72.657, 6.686),
        area=1.5,
        facets=1,
    )
    text = report(
        Survey(
            triangles=found.triangles,
            extent=found.extent,
            sections=found.sections,
            walls=found.walls,
            flats=(),
            rounds=(),
            repeats=(
                Repeat(
                    one=facet,
                    steps=(Step(Vector(0.0, 60.0, 0.0), 2), Step(Vector(0.0, 121.5, 0.0), 2)),
                ),
            ),
        )
    )

    assert "4 on one line along +Y, in 2 groups of 2" in text
    assert "no candidate: one triangle, flat whatever surface it belongs to" in text
    assert "loft()" not in text.partition("REPEATS")[2]
    assert "candidate: grid(one, (2, 2)" in text


# ---- one feature, one entry ------------------------------------------------------------


def _piece(
    radius: float, centre: Point, axis: Vector, *, concave: bool = False, area: float = 2.4
) -> Round:
    """One step of a rounded edge that bends: a quarter turn, 1.764 mm along its own axis,
    boxed as the systainer handle's pieces are - a 2 x 2 x 1.8 mm block round its centre."""
    return Round(
        axis=axis,
        centre=centre,
        radius=radius,
        length=1.764,
        turn=math.pi / 2.0,
        concave=concave,
        spread=0.006,
        low=centre - Vector(1.0, 1.0, 0.9),
        high=centre + Vector(1.0, 1.0, 0.9),
        area=area,
        facets=11,
    )


def _turned(degrees: float) -> Vector:
    """A unit axis in the XY plane, ``degrees`` round from +X."""
    return Vector(math.cos(math.radians(degrees)), math.sin(math.radians(degrees)), 0.0)


def _bent(*rounds: Round, flats: tuple[Flat, ...] = ()) -> Survey:
    found = _plate()
    return Survey(
        triangles=found.triangles,
        extent=found.extent,
        sections=found.sections,
        walls=found.walls,
        flats=flats,
        rounds=rounds,
        repeats=(),
    )


def _rounds_block(text: str) -> str:
    return text.partition("ROUNDS standing alone")[2].partition("REPEATS")[0]


def test_touching_pieces_of_one_radius_whose_axes_turn_are_one_round_over() -> None:
    """The handle's 1 mm round-over comes round the end of a web as a piece per step of the
    bend, each touching the next with its axis a few degrees on: one rounded edge, one entry,
    with the largest piece in full and the rest counted and summed."""
    pieces = tuple(
        _piece(0.985 + 0.001 * k, Point(10.0 + 1.7 * k, 5.0, 3.0), _turned(8.0 * k), area=2.4 + k)
        for k in range(5)
    )
    text = _rounds_block(report(_bent(*pieces)))

    assert (
        "round-over in 5 pieces: radius 0.985 to 0.989 mm, convex, material inside it, each "
        "piece touching the next and turned from it" in text
    )
    assert "22.0 mm2 in all, the longest piece 1.764 mm" in text
    assert "in a box (9.000, 4.000, 2.100) to (17.800, 6.000, 3.900); the largest:" in text
    assert text.count("partial round:") == 1, "the largest piece is printed in full, once"
    assert "radius 0.989 mm over 90 degrees" in text, "and it is the largest"
    assert "and 4 more pieces, 15.6 mm2 between them, the smallest 2.4 mm2" in text


def test_two_touching_pieces_print_as_two_and_not_as_a_run() -> None:
    pieces = (
        _piece(0.985, Point(10.0, 5.0, 3.0), _turned(0.0)),
        _piece(0.986, Point(11.7, 5.0, 3.0), _turned(8.0)),
    )
    text = _rounds_block(report(_bent(*pieces)))

    assert "round-over in" not in text
    assert text.count("partial round:") == 2


def test_pieces_on_parallel_axes_are_not_a_run() -> None:
    """The handle's 18 mm grip and its 17.999 mm neighbour touch on axes 17 mm apart and
    parallel: two features. The survey kept them apart, and so does the report."""
    pieces = tuple(_piece(0.985, Point(10.0 + 1.7 * k, 5.0, 3.0), _turned(0.0)) for k in range(4))
    text = _rounds_block(report(_bent(*pieces)))

    assert "round-over in" not in text
    assert text.count("partial round:") == 4


def test_pieces_whose_axes_step_more_than_a_facet_may_are_not_a_run() -> None:
    """Two round-overs of one radius meeting at a right angle are two edges, not a bend."""
    pieces = tuple(
        _piece(0.985, Point(10.0 + 1.7 * k, 5.0, 3.0), _turned(90.0 * k)) for k in range(3)
    )
    text = _rounds_block(report(_bent(*pieces)))

    assert "round-over in" not in text
    assert text.count("partial round:") == 3


def test_a_piece_of_another_radius_or_side_or_place_is_not_in_the_run() -> None:
    run = tuple(_piece(0.985, Point(10.0 + 1.7 * k, 5.0, 3.0), _turned(8.0 * k)) for k in range(3))
    other_radius = _piece(1.2, Point(15.1, 5.0, 3.0), _turned(24.0))
    other_side = _piece(0.985, Point(15.1, 5.0, 3.0), _turned(24.0), concave=True)
    far_away = _piece(0.985, Point(40.0, 5.0, 3.0), _turned(24.0))
    text = _rounds_block(report(_bent(*run, other_radius, other_side, far_away)))

    assert "round-over in 3 pieces" in text
    assert text.count("partial round:") == 4, "the run's largest and the three that are not in it"
    assert "radius 1.200 mm over 90 degrees" in text
    assert "concave, material outside it, box" in text


def test_a_full_bore_is_never_a_piece_of_a_run() -> None:
    """A bore of a square millimetre is a bore whatever it touches: the one thing a run must
    never sum away, because hole() is what a maker types from it."""
    run = tuple(_piece(0.985, Point(10.0 + 1.7 * k, 5.0, 3.0), _turned(8.0 * k)) for k in range(3))
    bore = Round(
        axis=_turned(8.0),
        centre=Point(11.7, 5.0, 3.0),
        radius=0.99,
        length=1.5,
        turn=2.0 * math.pi,
        concave=True,
        spread=0.001,
        low=Point(10.7, 4.0, 2.0),
        high=Point(12.7, 6.0, 4.0),
        area=9.3,
        facets=24,
    )
    text = _rounds_block(report(_bent(*run, bore)))

    assert "round-over in 3 pieces" in text
    assert "bore: diameter 1.980 mm (radius 0.990)" in text
    assert "candidate: hole(body, ..., diameter=1.980, depth=1.500)" in text


def test_every_piece_of_a_run_is_still_counted_against_the_triangles() -> None:
    run = tuple(_piece(0.985, Point(10.0 + 1.7 * k, 5.0, 3.0), _turned(8.0 * k)) for k in range(4))
    text = report(_bent(*run))

    assert f"account for {4 * 11} of 336 triangles" in text


def _facet(k: int, *, lean: float = 45.0, count: int = 24, area: float = 2.2) -> Flat:
    """Facet ``k`` of a cone about Z tessellated ``count`` ways: two triangles, leaning
    ``lean`` degrees off vertical, boxed where it sits round the ring."""
    around = 2.0 * math.pi * k / count
    n = Vector(
        math.sin(math.radians(lean)) * math.cos(around),
        math.sin(math.radians(lean)) * math.sin(around),
        math.cos(math.radians(lean)),
    )
    centre = Point(100.0 + 3.0 * math.cos(around), 60.0 + 3.0 * math.sin(around), 3.0)
    return Flat(
        normal=n,
        centre=centre,
        low=centre - Vector(1.1, 1.1, 1.0),
        high=centre + Vector(1.1, 1.1, 1.0),
        area=area,
        facets=2,
    )


def _flats_block(text: str) -> str:
    return text.partition("FLATS standing alone")[2].partition("ROUNDS")[0]


def test_a_ring_of_alike_facets_leaning_alike_is_a_cone_in_one_entry() -> None:
    """The base plate's four bores each wear a 45 degree countersink, which the survey reads
    as 24 flats of two triangles, one per facet. One cone, one entry, hole()'s countersink
    offered beside a loft() - and the largest facet in full."""
    text = _flats_block(report(_bent(flats=tuple(_facet(k) for k in range(24)))))

    assert (
        "24 flats in a run, 2.2 to 2.2 mm2 each and each touching the next with every normal "
        "45 degrees off +Z and stepping round it - the facets of a cone about +Z" in text
    )
    assert "52.8 mm2 in all" in text
    assert text.count("degrees off horizontal") == 1, "the largest facet only"
    assert "and 23 more flats, 50.6 mm2 between them, the smallest 2.2 mm2" in text
    assert (
        "candidate: a cone about +Z - the countersink or the chamfer of a hole() if it rings a "
        "bore, a loft() between two circles if it is a body's side" in text
    )


def test_alike_touching_flats_at_shallow_angles_are_one_entry_and_called_neither() -> None:
    """The handle's grip is topped by three 619 mm2 flats a few degrees apart: the coarse
    facets of its round, or three faces meant as facets. The report says one faceted surface
    and does not pick, and the largest keeps its own candidate."""
    big = tuple(
        Flat(
            normal=Vector(
                0.0, math.sin(math.radians(6.0 + 11.0 * k)), math.cos(math.radians(6.0 + 11.0 * k))
            ),
            centre=Point(125.0, 10.0 + 0.9 * k, 17.0 + 0.3 * k),
            low=Point(0.0, 9.5 + 0.9 * k, 16.8 + 0.3 * k),
            high=Point(250.0, 10.5 + 0.9 * k, 17.2 + 0.3 * k),
            area=619.3,
            facets=20,
        )
        for k in range(3)
    )
    text = _flats_block(report(_bent(flats=big)))

    assert (
        "3 flats in a run, 619.3 to 619.3 mm2 each and each touching the next with normals a "
        "step apart - one faceted surface, a curve too coarse for the round test or facets "
        "meant as they are: 1857.9 mm2 in all" in text
    )
    assert "not faces" not in text
    assert text.count("candidate: a face that leans is a loft()") == 1, "the largest keeps its own"
    assert "cone" not in text


def test_faces_meeting_at_right_angles_or_of_unlike_size_are_not_a_run() -> None:
    """The handle's real 20 mm faces of 658 mm2 meet their neighbours squarely, and a big
    face touching a small facet at a shallow angle is a face beside a facet, not a curve."""
    found = _plate()
    square = found.flats
    shallow = (
        Flat(
            normal=Vector(0.0, 0.0, 1.0),
            centre=Point(30.0, 20.0, 3.0),
            low=Point(0.0, 0.0, 3.0),
            high=Point(60.0, 40.0, 3.0),
            area=658.0,
            facets=2,
        ),
        Flat(
            normal=Vector(0.0, math.sin(math.radians(20.0)), math.cos(math.radians(20.0))),
            centre=Point(30.0, 40.5, 3.2),
            low=Point(0.0, 40.0, 3.0),
            high=Point(60.0, 41.0, 3.4),
            area=64.0,
            facets=2,
        ),
        Flat(
            normal=Vector(0.0, math.sin(math.radians(40.0)), math.cos(math.radians(40.0))),
            centre=Point(30.0, 41.5, 3.6),
            low=Point(0.0, 41.0, 3.4),
            high=Point(60.0, 42.0, 3.8),
            area=64.0,
            facets=2,
        ),
    )
    text = _flats_block(report(_bent(flats=(*square, *shallow))))

    assert "in a run" not in text
    assert text.count("candidate:") == len(square) + len(shallow)


def test_a_grid_whose_steps_share_a_line_is_said_as_places_on_that_line() -> None:
    """The base plate's foot sockets sit at 0, 60, 121.5 and 181.5 mm along Y: two pairs,
    which the survey rightly finds as a 2 x 2 lattice with both steps along Y. grid() puts
    them exactly there, so the candidate stands; the wording says what a reader would see."""
    found = _plate()
    text = report(
        Survey(
            triangles=found.triangles,
            extent=found.extent,
            sections=found.sections,
            walls=found.walls,
            flats=found.flats,
            rounds=found.rounds,
            repeats=(
                Repeat(
                    one=found.repeats[0].one,
                    steps=(Step(Vector(0.0, 121.5, 0.0), 2), Step(Vector(0.0, 60.0, 0.0), 2)),
                ),
            ),
        )
    )

    assert (
        "4 on one line along +Y, in 2 groups of 2: 60.000 mm apart within a group and the "
        "groups 121.500 mm apart, at 0.000, 60.000, 121.500 and 181.500 mm from the first one:"
        in text
    )
    assert "grid, 60.000 mm apart along +Y and 121.500 mm along +Y" not in text
    assert (
        "candidate: grid(one, (2, 2), (Vector(0.000, 60.000, 0.000), Vector(0.000, 121.500, "
        "0.000))) - grid() takes two steps along one line as readily as two across" in text
    )


def test_runs_and_lines_render_the_same_however_the_records_arrive() -> None:
    pieces = tuple(
        _piece(0.985 + 0.001 * k, Point(10.0 + 1.7 * k, 5.0, 3.0), _turned(8.0 * k), area=2.4 + k)
        for k in range(5)
    )
    facets = tuple(_facet(k) for k in range(24))
    found = _plate()
    steps = (Step(Vector(0.0, 60.0, 0.0), 2), Step(Vector(0.0, 121.5, 0.0), 2))
    forward = Survey(
        triangles=found.triangles,
        extent=found.extent,
        sections=found.sections,
        walls=found.walls,
        flats=facets,
        rounds=pieces,
        repeats=(Repeat(one=found.repeats[0].one, steps=steps),),
    )
    backward = Survey(
        triangles=found.triangles,
        extent=found.extent,
        sections=found.sections,
        walls=found.walls,
        flats=tuple(reversed(facets)),
        rounds=tuple(reversed(pieces)),
        repeats=(Repeat(one=found.repeats[0].one, steps=tuple(reversed(steps))),),
    )

    assert report(forward) == report(backward)
    assert "round-over in 5 pieces" in report(forward)
    assert "24 flats in a run" in report(forward)
