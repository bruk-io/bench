"""Functional: hose and duct sizes and the fittings between them, with no kernel.

What the tree can answer on its own is asserted here - which side of each size its number
measures and where the number comes from, the diameters a spigot and a socket are drawn at
and that the fit's gap lands on exactly one of them, that every fitting stands on the bed
the way it prints, what its faces are called, and which fittings are refused. That each one
prints without support and has no wall under the plastic's minimum is a measurement, and
the adapter layer's (``tests/adapter/test_ducts_measured.py``).
"""

import math
from typing import get_args

import pytest

from bench import (
    ORIGIN,
    Axis,
    Fit,
    Plane,
    Point,
    Printed,
    Solid,
    Vector,
    X,
    Y,
    Z,
    bounds,
    move,
    part,
    plane_of,
    refs,
    rotate,
)
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


def test_the_size_names_are_a_type_a_knob_offers_as_a_menu() -> None:
    """``SizeName`` is the table's own names, in the table's order - so a knob typed with it
    is a menu of exactly the sizes there are, and a script copies nothing."""
    assert list(get_args(ducts.SizeName)) == list(ducts.SIZES)


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


# ---- a sharp square-to-round ---------------------------------------------------------------


def test_a_square_to_round_takes_a_sharp_corner_inside_and_keeps_a_wall_round_it() -> None:
    """At ``corner=0`` the opening is a plain rectangle - four sides, not eight - and the
    outside is still the opening grown by a wall, so it is rounded to the wall and stands the
    wall off the opening all round. That it prints and has no thin wall is measured."""
    hood = ducts.square_to_round(120.0, 50.0, ducts.PORT_2_5, corner=0.0, wall=2.0)
    named = {str(one) for one in refs(hood)}
    assert "bore/collar/side-3" in named
    assert "bore/collar/side-4" not in named
    assert "collar/side-7" in named
    box = bounds(hood)
    assert (box.x0, box.x1) == pytest.approx((-62.0, 62.0))
    with pytest.raises(ValueError, match="corner is a radius or 0"):
        ducts.square_to_round(120.0, 50.0, ducts.PORT_2_5, corner=-1.0)


# ---- a port that lies on its side ------------------------------------------------------------


def test_a_keyed_spigot_is_its_key_and_its_spigot_end_to_end() -> None:
    """The key a teardrop pointing ``+X`` - reaching the radius times root two that way -
    and the spigot round above it."""
    radius = ducts.spigot_diameter(ducts.PORT_4) / 2
    body = ducts.keyed_spigot(ducts.PORT_4, key=15.0, length=30.0)
    box = bounds(body)
    assert (box.z0, box.z1) == pytest.approx((0.0, 45.0))
    assert box.x1 == pytest.approx(radius * math.sqrt(2.0))
    assert (box.x0, box.y0, box.y1) == pytest.approx((-radius, -radius, radius))
    assert {"key", "spigot", "bore"} <= {str(one).split("/")[0] for one in refs(body)}


def test_a_keyed_socket_is_a_hole_from_its_floor_up_and_its_inlet_down() -> None:
    """Drawn from its floor at the origin: the socket up ``+Z`` past its depth, the inlet
    down ``-Z`` past the wall it goes through, each a teardrop pointing ``+X``."""
    hole = ducts.keyed_socket(ducts.PORT_4, 6.0, depth=20.0)
    box = bounds(hole)
    assert box.z0 < -6.0
    assert 20.0 < box.z1 <= 21.0
    assert box.x1 == pytest.approx(ducts.socket_diameter(ducts.PORT_4) / 2 * math.sqrt(2.0))
    with pytest.raises(ValueError, match="through must be positive"):
        ducts.keyed_socket(ducts.PORT_4, 0.0)


# ---- putting a fitting where it goes ---------------------------------------------------------


def _same(a: Plane, b: Plane) -> None:
    assert (a.origin.x, a.origin.y, a.origin.z) == pytest.approx(
        (b.origin.x, b.origin.y, b.origin.z)
    )
    assert (a.normal.x, a.normal.y, a.normal.z) == pytest.approx(
        (b.normal.x, b.normal.y, b.normal.z)
    )
    assert (a.x_dir.x, a.x_dir.y, a.x_dir.z) == pytest.approx((b.x_dir.x, b.x_dir.y, b.x_dir.z))


def test_placing_the_vents_hopper_is_its_hand_rotation_said_as_where_it_goes() -> None:
    """The wall vent turns its hopper a quarter about ``X`` and moves it, so it stands on its
    opening facing up into the chamber and its port runs down ``-Y``. ``place`` says that as
    where the start goes and which way it faces, and lands every face in the same place."""
    hopper = ducts.square_to_round(200.0, 90.0, ducts.PORT_4, collar=6.0)
    at = Point(100.0, -150.0, 50.0)
    by_hand = move(rotate(hopper, math.pi / 2, about=Axis(ORIGIN, X)), at - ORIGIN)
    placed = ducts.place(hopper, "start", at=at, toward=Y)
    for name in ("spigot/top", "collar/bottom", "collar/side-0"):
        _same(plane_of(placed, name), plane_of(by_hand, name))
    assert bounds(placed) == pytest.approx(bounds(by_hand))


def test_placing_the_vents_side_port_is_its_hand_rotation_said_as_where_it_goes() -> None:
    """The side port is turned a quarter about ``Y`` and moved, so its start faces back into
    the socket along ``-X``. Said with ``place``, the spigot's ends are where they were."""
    spigot = ducts.spigot(ducts.PORT_4, length=50.0)
    at = Point(10.0, 20.0, 30.0)
    by_hand = move(rotate(spigot, math.pi / 2, about=Axis(ORIGIN, Y)), at - ORIGIN)
    placed = ducts.place(spigot, at=at, toward=-X)
    assert bounds(placed) == pytest.approx(bounds(by_hand))
    start, end = ducts.end_of(placed, "start"), ducts.end_of(placed)
    assert (start.origin.x, start.normal.x) == pytest.approx((10.0, -1.0))
    assert (end.origin.x, end.normal.x) == pytest.approx((60.0, 1.0))


@pytest.mark.parametrize(
    ("fitting", "end", "named"),
    [
        (ducts.elbow(ducts.PORT_2_5, math.radians(30.0)), "end", "end"),
        (ducts.branch(ducts.PORT_4), "end", "run/top"),
        (ducts.branch(ducts.PORT_4), "tap", "tap/end"),
        (ducts.square_to_round(120.0, 50.0, ducts.PORT_2_5), "end", "spigot/top"),
    ],
    ids=["elbow", "branch", "tap", "square_to_round"],
)
def test_an_end_with_a_face_is_that_face(fitting: Solid, end: ducts.End, named: str) -> None:
    _same(ducts.end_of(fitting, end), plane_of(fitting, named))


def test_an_end_put_on_a_point_facing_a_way_is_there_facing_that_way() -> None:
    """Whichever end is placed, it lands on ``at`` facing ``toward`` - an elbow by its end,
    a coupler by its start, even facing straight back the way it did."""
    elbow = ducts.elbow(ducts.PORT_2_5, math.radians(30.0))
    toward = Vector(1.0, 2.0, -2.0)
    ends: tuple[tuple[Solid, ducts.End], ...] = (
        (elbow, "end"),
        (ducts.coupler(ducts.PORT_4), "start"),
    )
    for fitting, end in ends:
        for way in (toward, Z, -Z):
            placed = ducts.place(fitting, end, at=Point(5.0, 6.0, 7.0), toward=way)
            there = ducts.end_of(placed, end)
            assert (there.origin.x, there.origin.y, there.origin.z) == pytest.approx(
                (5.0, 6.0, 7.0)
            )
            length = abs(way)
            assert (there.normal.x, there.normal.y, there.normal.z) == pytest.approx(
                (way.x / length, way.y / length, way.z / length)
            )


def test_across_says_which_way_an_elbow_turns() -> None:
    """Stood up the way it prints and turned with ``across=Y``, an elbow turns towards
    ``+Y`` rather than ``+X``."""
    turn = math.radians(30.0)
    elbow = ducts.elbow(ducts.PORT_2_5, turn)
    placed = ducts.place(elbow, at=ORIGIN, toward=-Z, across=Y)
    end = ducts.end_of(placed)
    assert (end.normal.x, end.normal.y, end.normal.z) == pytest.approx(
        (0.0, math.sin(turn), math.cos(turn))
    )


def test_a_placed_part_still_prints_standing_on_its_start() -> None:
    """A part's way up turns with it: a spigot whose start faces ``+X`` runs from there along
    ``-X``, and prints with ``-X`` up - standing on its start as it was drawn. So does an
    elbow put by its end facing any way at all: its start still faces straight down the way
    it prints."""
    stock = Printed(PLA, ducts.UPRIGHT)
    placed = ducts.place(part("port", ducts.spigot(ducts.PORT_4), stock), at=ORIGIN, toward=X)
    assert isinstance(placed.stock, Printed)
    up = placed.stock.orient.up
    assert (up.x, up.y, up.z) == pytest.approx((-1.0, 0.0, 0.0))
    elbow = ducts.elbow(ducts.PORT_2_5, math.radians(30.0))
    turned = ducts.place(
        part("elbow", elbow, stock), "end", at=Point(1.0, 2.0, 3.0), toward=Vector(1.0, -2.0, 0.5)
    )
    assert isinstance(turned.stock, Printed) and isinstance(turned.shape, Solid)
    up, start = turned.stock.orient.up, ducts.end_of(turned.shape, "start").normal
    assert (up.x, up.y, up.z) == pytest.approx((-start.x, -start.y, -start.z))


def test_a_placement_that_cannot_be_is_refused() -> None:
    spigot = ducts.spigot(ducts.PORT_4)
    with pytest.raises(LookupError, match="only a branch has a tap"):
        ducts.end_of(spigot, "tap")
    with pytest.raises(ValueError, match="cannot run along"):
        ducts.place(spigot, at=ORIGIN, toward=X, across=-X)
    with pytest.raises(ValueError, match="has no length"):
        ducts.place(spigot, at=ORIGIN, toward=Vector(0.0, 0.0, 0.0))
