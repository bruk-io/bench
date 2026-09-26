"""Unit: :mod:`bench.fasteners` alone - the table as data, and the one function over it.

Nothing here builds geometry. What is asserted is that the numbers are the ones the review
tabulated, that :func:`bore` reads a column rather than inventing a figure, and that the
:class:`Fit` enum and the :class:`Screw` record cannot drift apart without this file
failing.
"""

import math
from itertools import pairwise

import pytest

from bench.fasteners import (
    BUGLE,
    COUNTERSINK,
    COUNTERSINK_82,
    DRYWALL_6,
    DRYWALL_SCREWS,
    IMPERIAL_SCREWS,
    INSERT_M3,
    INSERT_M4,
    INSERT_M5,
    LEAD_IN,
    M2,
    M2_5,
    M3,
    M4,
    M5,
    M6,
    M8,
    MACHINE_8_32,
    MACHINE_SCREWS,
    MAGNET_6X2,
    SCREWS,
    WOOD_8,
    WOOD_SCREWS,
    Fit,
    Screw,
    bore,
    nut_trap,
)

pytestmark = pytest.mark.unit


# ---- the table -----------------------------------------------------------------------


def test_the_clearance_columns_are_the_reviews_own_numbers() -> None:
    """ISO 273's three holes, read straight off the review's table for every size it
    tabulated. M8 is not in that table and is ISO 273's own row."""
    assert [(s.close, s.normal, s.loose) for s in (M2, M2_5, M3, M4, M5, M6)] == [
        (2.2, 2.4, 2.6),
        (2.7, 2.9, 3.1),
        (3.2, 3.4, 3.6),
        (4.3, 4.5, 4.8),
        (5.3, 5.5, 5.8),
        (6.4, 6.6, 7.0),
    ]
    assert (M8.close, M8.normal, M8.loose) == (8.4, 9.0, 10.0)


def test_a_plastic_self_tap_is_a_bigger_hole_than_a_metal_tap_drill() -> None:
    """The distinction the review insists on: 3.3 is what you drill to cut an M4 thread in
    aluminium, 3.4 is what you print to drive the same screw into PLA. One table entry
    would have been wrong for one of them."""
    assert (M4.tap, M4.self_tap) == (3.3, 3.4)
    for screw in SCREWS:
        assert screw.tap < screw.self_tap < screw.diameter


def test_the_head_columns_are_the_reviews_own_numbers() -> None:
    assert [
        (s.socket_head_d, s.counterbore_d, s.counterbore_depth, s.countersink_d)
        for s in (M2, M2_5, M3, M4, M5, M6)
    ] == [
        (3.8, 4.3, 2.2, 4.4),
        (4.5, 5.0, 2.7, 5.5),
        (5.5, 6.2, 3.2, 6.3),
        (7.0, 7.6, 4.2, 8.4),
        (8.5, 9.2, 5.2, 10.4),
        (10.0, 10.8, 6.2, 12.6),
    ]


def test_every_countersink_is_the_iso_ninety_degrees() -> None:
    """Not the imperial 82: a printed countersink wants the shallowest cone whose wall is
    still a 45 degree overhang."""
    assert pytest.approx(math.radians(90.0)) == COUNTERSINK
    assert all(s.countersink_angle == COUNTERSINK for s in SCREWS)


def test_a_counterbore_swallows_the_head_it_is_cut_for() -> None:
    for screw in SCREWS:
        assert screw.counterbore_d > screw.socket_head_d
        assert screw.counterbore_depth > screw.socket_head_h
        assert screw.countersink_d > screw.flat_head_d


def test_a_nut_trap_is_wider_and_deeper_than_the_nut_in_it() -> None:
    trap = nut_trap(M3)
    assert (trap.size, trap.across_flats, trap.depth, trap.lead_in) == ("M3", 5.6, 2.6, LEAD_IN)
    # the review's own parenthesised column, size by size
    assert [nut_trap(s).across_flats for s in (M2, M2_5, M3, M4, M5, M6)] == [
        4.1,
        5.1,
        5.6,
        7.2,
        8.2,
        10.2,
    ]
    for screw in SCREWS:
        one = nut_trap(screw)
        assert one.across_flats > screw.nut_across_flats
        assert one.depth > screw.nut_thickness


def test_an_insert_is_keyed_on_the_insert_and_not_on_the_screw() -> None:
    """The review's point, and InsertGuide's: the hole comes from the insert's own outside
    diameter, so it is a different part with its own record - and it is nothing like the
    screw's clearance hole."""
    assert (INSERT_M3.bore, INSERT_M4.bore, INSERT_M5.bore) == (4.2, 5.6, 6.8)
    assert INSERT_M3.bore > M3.loose
    for insert, screw in ((INSERT_M3, M3), (INSERT_M4, M4), (INSERT_M5, M5)):
        assert insert.size == screw.name
        assert insert.bore >= insert.od


def test_the_gridfinity_magnet_pocket_is_the_one_gridfinity_rebuilt_uses() -> None:
    assert (MAGNET_6X2.d, MAGNET_6X2.h) == (6.0, 2.0)
    assert (MAGNET_6X2.hole, MAGNET_6X2.ribs, MAGNET_6X2.rib_d) == (6.5, 8, 5.9)
    # the ribs stand proud of the pocket and under the magnet: that is the press fit
    assert MAGNET_6X2.rib_d < MAGNET_6X2.d < MAGNET_6X2.hole


# ---- bore, over every fit --------------------------------------------------------------


def test_bore_answers_every_fit_for_every_size_and_never_shrinks() -> None:
    """The six fits are ordered, so the holes they ask for are too - no interpolation, no
    special cases, and nowhere for a transposed pair of numbers to hide."""
    for screw in SCREWS:
        holes = [bore(screw, fit) for fit in Fit]
        assert holes == sorted(holes), f"{screw.name} does not widen with the fit"
        assert holes[0] < screw.diameter < holes[-1]


def test_bore_reads_a_column_of_the_screw_rather_than_inventing_a_number() -> None:
    """The drift guard. Every fit must land on one of the screw's own figures, and the six
    of them must land on six *different* ones: a :class:`Fit` added without a column to read
    it from would have to double up, and a column dropped from :class:`Screw` would stop
    being reachable."""
    for screw in SCREWS:
        columns = {
            screw.tap,
            screw.self_tap,
            screw.diameter,
            screw.close,
            screw.normal,
            screw.loose,
        }
        answers = {bore(screw, fit) for fit in Fit}
        assert answers <= columns, f"{screw.name}: a fit answered with a number not in the table"
        assert len(answers) == len(Fit), f"{screw.name}: two fits read the same column"


def test_m3_reads_the_table_exactly() -> None:
    """One size written out, so a reader can check the mapping against the docstring."""
    assert [bore(M3, fit) for fit in Fit] == [2.5, 2.6, 3.0, 3.2, 3.4, 3.6]


def test_every_screw_is_wider_at_every_column_than_the_size_below_it() -> None:
    """A table transposed by a line would break this and nothing else would notice."""
    for smaller, bigger in pairwise(SCREWS):
        for field in ("diameter", "close", "normal", "loose", "tap", "self_tap"):
            assert getattr(smaller, field) < getattr(bigger, field), field


def test_a_screw_is_a_value_and_two_of_the_same_size_are_equal() -> None:
    """Frozen and dumb, like every other record here: no identity, no state, hashable."""
    assert Screw(**{f: getattr(M3, f) for f in M3.__slots__}) == M3
    assert len({M3, M3}) == 1


# ---- imperial: wood, drywall and machine screws (task-69) -----------------------------


def test_a_wood_screws_diameter_is_asme_b18_6_1s_own_formula() -> None:
    """D = 0.060 + 0.013 * gauge, in inches, converted to millimetres like the rest of the
    table."""
    assert [round(s.diameter, 2) for s in WOOD_SCREWS] == [3.51, 4.17, 4.83]
    # a #8 wood screw and an 8-32 machine screw share a gauge and so a major diameter
    assert WOOD_8.diameter == MACHINE_8_32.diameter


def test_wood_screw_clearance_holes_are_the_inch_tables_own() -> None:
    """ANSI/ASME B18.2.8's designated drills for #6, #8 and #10, the inch counterpart of
    the metric table's ISO 273."""
    assert [(s.close, s.normal, s.loose) for s in WOOD_SCREWS] == [
        (3.91, 4.31, 4.70),
        (4.57, 4.98, 5.41),
        (5.22, 5.61, 6.05),
    ]


def test_wood_screw_pilot_holes_are_tighter_in_softwood_than_hardwood() -> None:
    """``tap`` reads as the softwood pilot and ``self_tap`` the hardwood one - shop
    practice, not a dimensional standard, but ordered the same tightest-first way the
    metric table's own ``tap`` < ``self_tap`` already is."""
    for screw in WOOD_SCREWS:
        assert screw.tap < screw.self_tap < screw.diameter


def test_a_drywall_screw_shares_its_wood_screws_thread_and_holes() -> None:
    """A bugle head changes the head, not what the screw drives into."""
    for wood, drywall in zip(WOOD_SCREWS, DRYWALL_SCREWS, strict=True):
        assert drywall.diameter == wood.diameter
        assert (drywall.close, drywall.normal, drywall.loose) == (
            wood.close,
            wood.normal,
            wood.loose,
        )
        assert (drywall.tap, drywall.self_tap) == (wood.tap, wood.self_tap)
        assert drywall.flat_head_d == wood.flat_head_d
        assert drywall.countersink_d == wood.countersink_d


def test_a_bugle_head_is_not_the_flat_heads_82_degrees_either() -> None:
    """task-69: honoured or its difference stated. Neither ASME table gives a bugle head's
    angle, so :data:`BUGLE` is an estimate the module says is one, and it is what every
    drywall screw's own ``countersink_angle`` carries - narrower than the flat head's cited
    82 degrees, and narrower again than the metric table's ISO 90."""
    assert math.radians(60.0) < BUGLE < math.radians(63.0)
    assert BUGLE < COUNTERSINK_82 < COUNTERSINK
    for screw in DRYWALL_SCREWS:
        assert screw.countersink_angle == BUGLE
    for screw in WOOD_SCREWS + MACHINE_SCREWS:
        assert screw.countersink_angle == COUNTERSINK_82


def test_wood_and_drywall_screws_have_no_socket_or_nut_columns() -> None:
    """Nobody makes a wood or a drywall screw with a hex socket or a nut, so those columns
    are ``0.0`` rather than a number invented to fill the field - a check that fails on a
    zero-size cutter, not a lie."""
    for screw in WOOD_SCREWS + DRYWALL_SCREWS:
        assert (screw.socket_head_d, screw.socket_head_h) == (0.0, 0.0)
        assert (screw.button_head_d, screw.button_head_h) == (0.0, 0.0)
        assert (screw.counterbore_d, screw.counterbore_depth) == (0.0, 0.0)
        assert screw.nut_across_flats == pytest.approx(0.0)


def test_the_vents_number_6_drywall_screw_can_be_written_as_the_real_size() -> None:
    """decision-11's own example: the vent's #6 drywall screws were drawn as M4 for want of
    a table entry. ``DRYWALL_6`` is not M4 - close to M3.5, and printed with a real bugle
    countersink rather than a borrowed metric one."""
    assert DRYWALL_6.diameter != M4.diameter
    assert M3.diameter < DRYWALL_6.diameter < M4.diameter
    assert bore(DRYWALL_6, Fit.CLEARANCE) == pytest.approx(4.31)


def test_machine_screw_clearance_and_tap_holes_are_the_inch_tables_own() -> None:
    """ANSI/ASME B18.2.8 for clearance, the ANSI 75 percent tap drill for ``tap``."""
    assert [(s.close, s.normal, s.loose, s.tap) for s in MACHINE_SCREWS] == [
        (4.57, 4.98, 5.41, 3.45),
        (5.22, 5.61, 6.05, 3.80),
        (6.75, 7.14, 7.54, 5.11),
    ]


def test_machine_screw_socket_and_button_heads_are_asme_b18_3s_own() -> None:
    """A socket head cap screw and a button head cap screw are real products in these three
    sizes, unlike a wood or a drywall screw's - ASME B18.3, not B18.6.3."""
    for screw in MACHINE_SCREWS:
        assert screw.socket_head_d > screw.diameter
        assert screw.button_head_d > screw.diameter
        assert screw.socket_head_h > 0.0
        assert screw.button_head_h > 0.0


def test_a_bore_reads_the_same_way_for_an_imperial_screw_as_a_metric_one() -> None:
    """:func:`bore` never special-cases the table it reads from - the drift guard that
    already runs over :data:`SCREWS`, run again over the imperial ones."""
    for screw in IMPERIAL_SCREWS:
        holes = [bore(screw, fit) for fit in Fit]
        assert holes == sorted(holes), f"{screw.name} does not widen with the fit"
        assert holes[0] < screw.diameter < holes[-1]
