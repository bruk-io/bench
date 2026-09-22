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
    COUNTERSINK,
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
    MAGNET_6X2,
    SCREWS,
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
