"""Functional: hose and duct sizes and the fittings between them, with no kernel.

What the tree can answer on its own is asserted here - which side of each size its number
measures and where the number comes from, the diameters a spigot and a socket are drawn at
and that the fit's gap lands on exactly one of them, that every fitting stands on the bed
the way it prints, what its faces are called, and which fittings are refused. That each one
prints without support and has no wall under the plastic's minimum is a measurement, and
the adapter layer's (``tests/adapter/test_ducts_measured.py``).
"""

import math

import pytest

from bench import Fit, bounds, plane_of, refs
from bench.library import ducts
from bench.library.print import ASA, PLA, clearance

pytestmark = pytest.mark.functional

_GAP = clearance(Fit.SLIDE, PLA, concave=True)
"""The slide a side, with a concave arc's chord folded in: every joint here has a bore on
one side of it."""


# ---- the table ---------------------------------------------------------------------------


def test_a_hose_is_sold_by_its_inside_and_the_port_it_slips_over_by_its_outside() -> None:
    assert ducts.HOSE_4.side is ducts.Side.INSIDE
    assert ducts.PORT_4.side is ducts.Side.OUTSIDE
    assert ducts.HOSE_4.diameter == pytest.approx(101.6)
    assert ducts.PORT_4.diameter == ducts.HOSE_4.diameter
    assert ducts.HOSE_2_5.diameter == pytest.approx(63.5)


def test_every_size_cites_a_page_or_says_it_is_an_estimate() -> None:
    """The fit goes wrong if a size is guessed, so none is guessed quietly: a number read
    off a page names the page, and one that was not says so in its source as well as its
    flag."""
    assert set(ducts.SIZES.values()) == {
        ducts.HOSE_4,
        ducts.PORT_4,
        ducts.HOSE_2_5,
        ducts.PORT_2_5,
        ducts.VAC_1_25,
        ducts.VAC_2_5,
        ducts.DUCT_4,
        ducts.DUCT_6,
    }
    for size in ducts.SIZES.values():
        if size.estimate:
            assert size.source.startswith("estimate"), size.name
        else:
            assert size.source.startswith("https://"), size.name
    cited = {one.name for one in ducts.SIZES.values() if not one.estimate}
    assert cited == {"4 in dust hose", "4 in dust port", "2.5 in dust hose"}


# ---- the two sides of a joint ------------------------------------------------------------


@pytest.mark.parametrize("size", [ducts.HOSE_4, ducts.DUCT_6], ids=lambda s: s.name)
def test_a_size_measured_inside_puts_the_gap_on_the_spigot(size: ducts.Size) -> None:
    """A hose is female already: what slides into it is drawn a slide under, and a socket
    standing in for it is drawn at its own inside."""
    assert ducts.spigot_diameter(size) == pytest.approx(size.diameter - 2 * _GAP)
    assert ducts.socket_diameter(size) == pytest.approx(size.diameter)


@pytest.mark.parametrize("size", [ducts.PORT_4, ducts.VAC_2_5], ids=lambda s: s.name)
def test_a_size_measured_outside_puts_the_gap_on_the_socket(size: ducts.Size) -> None:
    assert ducts.spigot_diameter(size) == pytest.approx(size.diameter)
    assert ducts.socket_diameter(size) == pytest.approx(size.diameter + 2 * _GAP)


@pytest.mark.parametrize("size", list(ducts.SIZES.values()), ids=lambda s: s.name)
def test_a_spigot_slides_into_the_socket_of_its_own_size_at_the_slide(size: ducts.Size) -> None:
    across = ducts.socket_diameter(size) - ducts.spigot_diameter(size)
    assert across / 2 == pytest.approx(_GAP)
    assert across / 2 >= clearance(Fit.SLIDE, PLA)


def test_the_gap_is_the_fit_tables_so_a_plastic_or_a_fit_changes_it() -> None:
    loose = ducts.socket_diameter(ducts.PORT_4, fit=Fit.LOOSE)
    assert loose == pytest.approx(101.6 + 2 * clearance(Fit.LOOSE, PLA, concave=True))
    asa = ducts.spigot_diameter(ducts.HOSE_4, material=ASA)
    assert asa == pytest.approx(101.6 - 2 * clearance(Fit.SLIDE, ASA, concave=True))


# ---- the fittings, as drawn --------------------------------------------------------------


def test_a_spigot_is_its_diameter_across_and_its_length_tall() -> None:
    box = bounds(ducts.spigot(ducts.HOSE_4, length=40.0))
    assert box.x1 - box.x0 == pytest.approx(ducts.spigot_diameter(ducts.HOSE_4))
    assert (box.z0, box.z1) == pytest.approx((0.0, 40.0))


def test_a_socket_is_its_bore_and_a_wall_across() -> None:
    box = bounds(ducts.socket(ducts.PORT_4, wall=3.0))
    assert box.x1 - box.x0 == pytest.approx(ducts.socket_diameter(ducts.PORT_4) + 6.0)
    assert box.z0 == pytest.approx(0.0)


def test_a_socket_stops_its_spigot_with_a_cone_as_steep_as_the_plastic_holds() -> None:
    """The collar runs ``depth`` inside, then narrows to the size's own tube over a cone
    leaning ``max_overhang`` - so the socket is as tall as its depth, the corner hollowing
    moves, the cone and a wall of tube."""
    depth, wall = 20.0, 2.0
    lean = PLA.max_overhang
    step = ducts.socket_diameter(ducts.PORT_4) / 2 + wall - ducts.spigot_diameter(ducts.PORT_4) / 2
    tall = depth + wall * math.tan(lean / 2) + step / math.tan(lean) + wall
    box = bounds(ducts.socket(ducts.PORT_4, depth=depth, wall=wall))
    assert box.z1 == pytest.approx(tall)


def test_every_fitting_stands_on_the_bed_at_the_origin() -> None:
    """Drawn the way it prints, on its start and rising up +Z - what UPRIGHT says."""
    assert ducts.UPRIGHT.up.z == pytest.approx(1.0)
    for body in (
        ducts.spigot(ducts.HOSE_4),
        ducts.socket(ducts.PORT_4),
        ducts.coupler(ducts.PORT_4, ducts.PORT_2_5),
        ducts.reducer(ducts.HOSE_4, ducts.HOSE_2_5),
        ducts.branch(ducts.PORT_4),
        ducts.square_to_round(120.0, 50.0, ducts.PORT_2_5),
    ):
        assert bounds(body).z0 == pytest.approx(0.0)
    elbow = ducts.elbow(ducts.HOSE_4, math.radians(45.0))
    assert plane_of(elbow, "start").origin.z == pytest.approx(0.0)


def test_an_elbow_ends_on_a_face_turned_as_far_as_it_was_asked() -> None:
    turn = math.radians(30.0)
    end = plane_of(ducts.elbow(ducts.PORT_4, turn), "end")
    assert end.normal.x == pytest.approx(math.sin(turn))
    assert end.normal.z == pytest.approx(math.cos(turn))


def test_the_faces_are_named_for_the_joints_they_make() -> None:
    coupler = {str(one) for one in refs(ducts.coupler(ducts.PORT_4))}
    assert {"side-inlet", "side-outlet", "inside/side-inlet", "inside/side-waist"} <= coupler
    elbow = {str(one) for one in refs(ducts.elbow(ducts.HOSE_4, 0.5))}
    assert elbow == {"start", "end", "side-0", "bore"}
    branch = {str(one) for one in refs(ducts.branch(ducts.PORT_4))}
    assert {"run/bottom", "run/top", "tap/end", "bore/run", "bore/tap"} <= branch
    hood = {str(one) for one in refs(ducts.square_to_round(120.0, 50.0, ducts.PORT_2_5))}
    assert {"collar/bottom", "transition", "spigot/top", "bore/transition"} <= hood


def test_a_reducer_prints_standing_on_either_end() -> None:
    down = bounds(ducts.reducer(ducts.HOSE_4, ducts.HOSE_2_5))
    up = bounds(ducts.reducer(ducts.HOSE_2_5, ducts.HOSE_4))
    assert down.z1 == pytest.approx(up.z1)


# ---- what is refused ---------------------------------------------------------------------


def test_a_wall_under_the_plastics_minimum_is_refused() -> None:
    with pytest.raises(ValueError, match=r"under the 0\.86 mm PLA prints"):
        ducts.spigot(ducts.HOSE_4, wall=0.6)
    with pytest.raises(ValueError, match=r"under the 1\.2 mm ASA prints"):
        ducts.coupler(ducts.PORT_4, wall=1.0, material=ASA)


def test_a_square_to_rounds_wall_is_held_to_the_minimum_across_its_leaning_side() -> None:
    """1 mm is PLA's minimum and more, level; leaning 45 degrees it is 0.71 mm through."""
    ducts.spigot(ducts.PORT_2_5, wall=1.0)
    with pytest.raises(ValueError, match=r"0\.71 mm wall"):
        ducts.square_to_round(120.0, 50.0, ducts.PORT_2_5, wall=1.0)


def test_an_elbow_is_drawn_at_any_turn_and_refused_only_one_that_turns_nothing() -> None:
    """A 90 degree elbow is the commonest fitting there is, and it can be built: whether it
    prints unsupported is ``check_overhangs``' to say, measured in the adapter layer."""
    for degrees in (45.0, 90.0, 135.0):
        end = plane_of(ducts.elbow(ducts.HOSE_4, math.radians(degrees)), "end")
        assert end.normal.x == pytest.approx(math.sin(math.radians(degrees)))
    with pytest.raises(ValueError, match="turns less than a whole turn"):
        ducts.elbow(ducts.HOSE_4, 0.0)


def test_a_branch_is_drawn_steep_and_refused_only_where_it_is_no_wye() -> None:
    ducts.branch(ducts.PORT_4, angle=math.radians(60.0))
    with pytest.raises(ValueError, match="between 0 and 90 degrees"):
        ducts.branch(ducts.PORT_4, angle=math.radians(120.0))
    with pytest.raises(ValueError, match="no wider than its run"):
        ducts.branch(ducts.PORT_2_5, ducts.PORT_4)


def test_a_length_that_is_not_one_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="length must be positive"):
        ducts.reducer(ducts.HOSE_4, ducts.HOSE_2_5, length=0.0)
    with pytest.raises(ValueError, match="depth must be positive"):
        ducts.socket(ducts.PORT_4, depth=-1.0)
    with pytest.raises(ValueError, match="no bore"):
        ducts.spigot(ducts.VAC_1_25, wall=16.0)
