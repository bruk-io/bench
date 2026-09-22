"""Functional: :func:`bench.features.hole` over the closed ``Face | Solid`` union.

One verb, two shapes, and the same sentence either way: a circle out of a flat part and a
bore into a body. Nothing here is evaluated - there is no kernel in this layer - so what is
asserted is the tree: which refs a hole adds, how wide and how deep the tool it cuts with
reaches, and what the verb refuses to do. The diameter a printer actually leaves behind is
measured in the adapter layer, against the real modeller.
"""

import math

import pytest

from bench import (
    INSERT_M3,
    M3,
    M4,
    XY,
    Fit,
    Label,
    Point,
    Printed,
    Process,
    Ref,
    Solid,
    Stock,
    Top,
    bbox,
    bounds,
    circle,
    cuboid,
    cut,
    d_bore,
    fill,
    hole,
    nest,
    open_box,
    part,
    plane_of,
    rect,
    refs,
    resolve,
)
from bench.library.print import PLA
from bench.nest import Bed

pytestmark = pytest.mark.functional

PLY = Stock(3.0, "ply", kerf=0.25)
PRINT = Printed(PLA)


def _tool(body: Solid, at: str) -> Solid:
    """The labelled body a hole cut with, read back out of the tree."""
    found = resolve(body, Ref(at))
    assert isinstance(found, Solid)
    return found


# ---- a hole in a flat part -------------------------------------------------------------


def test_a_hole_in_a_face_is_the_circle_a_laser_cuts() -> None:
    """The box from the README, drilled with the verb instead of by hand: same wire, same
    label, same part, and it still nests onto a sheet."""
    box = open_box(w=120, d=80, h=50, t=3, finger=12.0)
    drilled = hole(box.side_left, Point(40, 25), diameter=20.0, label="hole")
    by_hand = cut(box.side_left, circle(10.0, Point(40, 25)), label=Label("hole"))
    assert drilled == by_hand
    panel = part("side-left", drilled, PLY)
    assert panel.process is Process.LASER
    assert Ref("side-left/hole") in refs(panel)
    sheets, warnings = nest((panel,), Bed(320.0, 320.0))
    assert warnings == () and len(sheets) == 1


def test_a_hole_in_a_face_is_sized_off_the_same_table_a_bore_is() -> None:
    """A clearance hole for an M4 is 4.5 mm whether it is drilled, milled or lasered: the
    table is the fastener's, and only the printed compensation is the plastic's."""
    panel = fill(rect(40, 20), label="panel")
    drilled = hole(panel, Point(20, 10), screw=M4, label="m4")
    assert bbox(drilled.inner[0]).w == pytest.approx(4.5)
    snug = hole(panel, Point(20, 10), screw=M4, fit=Fit.SLIDE, label="m4")
    assert bbox(snug.inner[0]).w == pytest.approx(4.3)


def test_a_face_refuses_what_only_a_bore_has() -> None:
    """A cutter has one depth, the stock's, and no way to sink a head into it. Ignoring the
    keyword would hand back a panel that does not hold the screw it was drawn for."""
    panel = fill(rect(40, 20))
    with pytest.raises(ValueError, match="describes a bore"):
        hole(panel, Point(20, 10), screw=M3, depth=2.0, label="m3")
    with pytest.raises(ValueError, match="describes a bore"):
        hole(panel, Point(20, 10), screw=M3, countersink=True, label="m3")
    with pytest.raises(ValueError, match="describes a bore"):
        hole(panel, Point(20, 10), screw=M3, counterbore=True, label="m3")
    with pytest.raises(ValueError, match="describes a bore"):
        hole(panel, Point(20, 10), profile=d_bore(5.0, 2.0), depth=2.0, label="d")


# ---- a bore in a body ------------------------------------------------------------------


def test_a_through_bore_names_its_own_faces_and_comes_out_the_other_side() -> None:
    plate = cuboid(60, 40, 5)
    drilled = hole(
        plate, Point(20, 20), on=plane_of(plate, "top"), screw=M3, top=Top.ROUND, label="m3"
    )
    assert refs(drilled) == (
        Ref("top"),
        Ref("bottom"),
        Ref("side-front"),
        Ref("side-right"),
        Ref("side-back"),
        Ref("side-left"),
        Ref("m3"),
        Ref("m3/top"),
        Ref("m3/bottom"),
        Ref("m3/side-0"),
    )
    box = bounds(_tool(drilled, "m3"))
    assert box.z0 < 0.0 and box.z1 > 5.0, "a through bore leaves the material at both ends"
    assert box.x1 - box.x0 == pytest.approx(3.4)  # M3 clearance, no material to compensate for
    assert bounds(drilled) == pytest.approx(bounds(plate))


def test_a_blind_bore_stops_where_it_was_told_to() -> None:
    plate = cuboid(60, 40, 10)
    drilled = hole(
        plate,
        Point(30, 20),
        on=plane_of(plate, "top"),
        screw=M3,
        depth=4.0,
        printed=PRINT,
        label="m3",
    )
    box = bounds(_tool(drilled, "m3"))
    assert box.z0 == pytest.approx(6.0), "measured from the face it was drilled into"
    assert box.z1 > 10.0, "and started outside the material, not exactly on it"


def test_a_bore_drilled_from_a_side_goes_sideways() -> None:
    """``on`` is the face the hole is drilled into, and ``at`` is read in that face's own
    frame - the same promise ``fill`` makes about a sketch."""
    plate = cuboid(60, 40, 20)
    drilled = hole(
        plate,
        Point(30, 10),
        on=plane_of(plate, "side-front"),
        diameter=6.0,
        top=Top.ROUND,
        label="pin",
    )
    box = bounds(_tool(drilled, "pin"))
    assert box.y0 < 0.0, "it starts outside the front face"
    assert box.y1 > 40.0, "and comes out the back"
    assert (box.x0 + box.x1) / 2 == pytest.approx(30.0)
    assert (box.z0 + box.z1) / 2 == pytest.approx(10.0)


def test_a_countersink_is_a_cone_of_the_screws_own_head() -> None:
    plate = cuboid(60, 40, 6)
    drilled = hole(
        plate,
        Point(20, 20),
        on=plane_of(plate, "top"),
        screw=M3,
        countersink=True,
        printed=PRINT,
        label="m3",
    )
    assert Ref("m3/head") in refs(drilled)
    head = bounds(_tool(drilled, "m3/head"))
    assert head.x1 - head.x0 == pytest.approx(M3.countersink_d, abs=0.05)
    # a 90 degree cone sinks half the difference between the head and the bore
    assert head.z0 == pytest.approx(6.0 - (M3.countersink_d - (3.4 + PLA.hole_compensation)) / 2)


def test_a_countersink_angle_is_exposed_and_a_shallower_cone_sinks_deeper() -> None:
    plate = cuboid(60, 40, 8)
    shallow = hole(
        plate,
        Point(20, 20),
        on=plane_of(plate, "top"),
        screw=M3,
        countersink=True,
        angle=math.radians(60.0),
        printed=PRINT,
        label="m3",
    )
    deep = bounds(_tool(shallow, "m3/head"))
    sunk = (M3.countersink_d - (3.4 + PLA.hole_compensation)) / 2 / math.tan(math.pi / 6)
    assert deep.z0 == pytest.approx(8.0 - sunk)


def test_a_counterbore_is_the_flat_bottomed_hole_a_socket_cap_drops_into() -> None:
    plate = cuboid(60, 40, 10)
    drilled = hole(
        plate,
        Point(20, 20),
        on=plane_of(plate, "top"),
        screw=M3,
        counterbore=True,
        printed=PRINT,
        label="m3",
    )
    head = bounds(_tool(drilled, "m3/head"))
    assert head.x1 - head.x0 == pytest.approx(M3.counterbore_d, abs=0.05)
    assert head.z0 == pytest.approx(10.0 - M3.counterbore_depth)


def test_a_head_needs_a_screw_and_is_one_thing_or_the_other() -> None:
    plate = cuboid(20, 20, 5)
    top = plane_of(plate, "top")
    with pytest.raises(ValueError, match="the screw's own head"):
        hole(plate, Point(10, 10), on=top, diameter=3.0, countersink=True, printed=PRINT, label="h")
    with pytest.raises(ValueError, match="sunk or it is buried"):
        hole(
            plate,
            Point(10, 10),
            on=top,
            screw=M3,
            countersink=True,
            counterbore=True,
            printed=PRINT,
            label="h",
        )


def test_a_hole_is_one_of_three_things_and_says_so() -> None:
    plate = cuboid(20, 20, 5)
    top = plane_of(plate, "top")
    with pytest.raises(ValueError, match="give exactly one"):
        hole(plate, Point(10, 10), on=top, label="h")
    with pytest.raises(ValueError, match="give exactly one"):
        hole(plate, Point(10, 10), on=top, screw=M3, diameter=3.0, label="h")
    with pytest.raises(ValueError, match="give exactly one"):
        hole(plate, Point(10, 10), on=top, screw=M3, insert=INSERT_M3, label="h")
    with pytest.raises(ValueError, match="give exactly one"):
        hole(plate, Point(10, 10), on=top, diameter=3.0, profile=d_bore(3.0, 1.0), label="h")


# ---- what the plastic changes ----------------------------------------------------------


def test_a_printed_bore_is_cut_wider_by_what_the_plastic_takes_back() -> None:
    """The table is the metal figure; the material adds its compensation on top, and only
    to the hole. A part with no material gets the table's number unchanged."""
    plate = cuboid(60, 40, 5)
    top = plane_of(plate, "top")
    plain = hole(plate, Point(20, 20), on=top, diameter=6.0, top=Top.ROUND, label="h")
    printed = hole(plate, Point(20, 20), on=top, diameter=6.0, printed=PRINT, label="h")
    assert bounds(_tool(plain, "h")).x1 - bounds(_tool(plain, "h")).x0 == pytest.approx(6.0)
    wide = bounds(_tool(printed, "h"))
    assert wide.x1 - wide.x0 == pytest.approx(6.0 + PLA.hole_compensation)


def test_an_insert_bore_is_the_inserts_own_hole_and_not_a_fit_of_the_screw() -> None:
    plate = cuboid(60, 40, 8)
    drilled = hole(
        plate,
        Point(20, 20),
        on=plane_of(plate, "top"),
        insert=INSERT_M3,
        depth=6.0,
        printed=PRINT,
        label="insert",
    )
    box = bounds(_tool(drilled, "insert"))
    assert box.x1 - box.x0 == pytest.approx(INSERT_M3.bore + PLA.hole_compensation)
    assert box.z0 == pytest.approx(2.0)


def test_a_leaning_bore_gets_a_teardrop_without_being_asked() -> None:
    """The horizontal-hole rule, through the verb: the part carries an orientation, the hole
    is drilled across it, and the top of the bore comes out pointed rather than arched."""
    plate = cuboid(60, 40, 20)
    drilled = hole(
        plate,
        Point(30, 10),
        on=plane_of(plate, "side-front"),
        diameter=6.0,
        printed=PRINT,
        label="pin",
    )
    r = (6.0 + PLA.hole_compensation) / 2
    box = bounds(_tool(drilled, "pin"))
    assert box.z1 - 10.0 == pytest.approx(r * math.sqrt(2.0)), "an apex, not an arc"
    assert 10.0 - box.z0 == pytest.approx(r), "and a round bottom, which needs no help"
    # a bore of the same size drilled downward is a stack of circles and gets nothing
    upright = hole(
        plate, Point(30, 20), on=plane_of(plate, "top"), diameter=6.0, printed=PRINT, label="down"
    )
    straight = bounds(_tool(upright, "down"))
    assert straight.x1 - straight.x0 == pytest.approx(2 * r)
    assert straight.y1 - straight.y0 == pytest.approx(2 * r)


def test_a_counterbore_that_must_stay_round_is_bridged_in_layers() -> None:
    """Where roundness matters and the span is short enough, the bore keeps its circle and
    the counterbore's floor is stepped so a slicer has something straight to print onto."""
    plate = cuboid(60, 40, 20)
    drilled = hole(
        plate,
        Point(30, 10),
        on=plane_of(plate, "side-front"),
        screw=M4,
        counterbore=True,
        printed=PRINT,
        label="cap",
    )
    found = refs(drilled)
    assert Ref("cap/head") in found
    assert Ref("cap/bridge-1") in found and Ref("cap/bridge-3") in found
    first = bounds(_tool(drilled, "cap/bridge-1"))
    second = bounds(_tool(drilled, "cap/bridge-2"))
    # each step is one layer thick, and the next one is turned a quarter
    assert first.y1 - first.y0 == pytest.approx(PLA.layer)
    assert second.y0 == pytest.approx(first.y0 + PLA.layer)
    assert (first.x1 - first.x0, first.z1 - first.z0) == pytest.approx(
        (second.z1 - second.z0, second.x1 - second.x0)
    )


def test_a_bore_that_cannot_tell_which_way_is_up_says_so() -> None:
    """``Top.AUTO`` on a part with no orientation is the one question the rule refuses to
    guess at - and a part that says which way it prints gets an answer."""
    plate = cuboid(60, 40, 20)
    front = plane_of(plate, "side-front")
    with pytest.raises(ValueError, match="cannot tell which way is up"):
        hole(plate, Point(30, 10), on=front, diameter=6.0, label="pin")
    assert (
        hole(plate, Point(30, 10), on=front, diameter=6.0, top=Top.ROUND, label="pin") is not None
    )


def test_a_hole_returns_the_kind_of_shape_it_was_given() -> None:
    """One verb over the closed union: a face in, a face out; a body in, a body out. The
    binding never quietly changes what it holds."""
    panel = fill(rect(40, 20), on=XY)
    assert isinstance(hole(panel, Point(20, 10), screw=M3, label="a"), type(panel))
    body = cuboid(20, 20, 5)
    bored = hole(body, Point(10, 10), on=plane_of(body, "top"), screw=M3, printed=PRINT, label="b")
    assert isinstance(bored, Solid)


# ---- a bore or a hole cut from a profile, not a diameter -------------------------------


def test_a_profile_in_a_face_is_the_wire_cut_out_of_it() -> None:
    """A face hole is not only round either: the same D that keys a shaft could just as
    well be laser-cut, moved to ``at`` the same way ``cut`` would have taken it by hand -
    compared by geometry, since ``hole`` moves the wire rather than build it in place, which
    leaves an incidental field or two different from a hand-built one of the same shape."""
    panel = fill(rect(40, 20), label="panel")
    d = d_bore(5.0, 2.0, Point(20, 10))
    drilled = hole(panel, Point(20, 10), profile=d_bore(5.0, 2.0), label="d")
    by_hand = cut(panel, d, label=Label("d"))
    assert drilled.inner[0].label == "d"
    got, want = bounds(fill(drilled.inner[0])), bounds(fill(by_hand.inner[0]))
    assert (got.x0, got.x1, got.y0, got.y1) == pytest.approx((want.x0, want.x1, want.y0, want.y1))


def test_a_profile_cuts_a_bore_shaped_like_the_wire_it_was_given() -> None:
    """A bore swept from a profile is exactly the wire it was given, translated to ``at`` -
    :func:`printable_top`'s rule never runs, because there is no single diameter for it to
    read."""
    plate = cuboid(60, 40, 20)
    d = d_bore(5.0, 2.0, Point(20, 20))
    drilled = hole(
        plate, Point(20, 20), on=plane_of(plate, "top"), profile=d_bore(5.0, 2.0), label="d"
    )
    box = bounds(_tool(drilled, "d"))
    want = bounds(fill(d))
    assert (box.x0, box.x1, box.y0, box.y1) == pytest.approx((want.x0, want.x1, want.y0, want.y1))


def test_a_profile_bore_grows_by_the_same_compensation_a_round_one_does() -> None:
    """Half the material's ``hole_compensation`` on every edge of the profile is the same
    growth a round hole gets on its diameter: the same amount on the side that matters."""
    plate = cuboid(60, 40, 20)
    top = plane_of(plate, "top")
    bare = bounds(
        _tool(hole(plate, Point(20, 20), on=top, profile=d_bore(5.0, 2.0), label="d"), "d")
    )
    grown = bounds(
        _tool(
            hole(plate, Point(20, 20), on=top, profile=d_bore(5.0, 2.0), printed=PRINT, label="d"),
            "d",
        )
    )
    assert grown.x1 - grown.x0 == pytest.approx((bare.x1 - bare.x0) + PLA.hole_compensation)


def test_a_profile_has_no_head_and_no_printable_top_of_its_own() -> None:
    """Countersink and counterbore are a screw's own head, which a profiled bore never has;
    and a profile has no single diameter for :func:`printable_top` to make a decision from,
    so it is drawn already safe to print and ``top`` stays at its default."""
    plate = cuboid(60, 40, 10)
    top = plane_of(plate, "top")
    with pytest.raises(ValueError, match="screw to size one from"):
        hole(plate, Point(20, 20), on=top, profile=d_bore(5.0, 2.0), countersink=True, label="d")
    with pytest.raises(ValueError, match="screw to size one from"):
        hole(plate, Point(20, 20), on=top, profile=d_bore(5.0, 2.0), counterbore=True, label="d")
    with pytest.raises(ValueError, match="no round top"):
        hole(
            plate,
            Point(20, 20),
            on=top,
            profile=d_bore(5.0, 2.0),
            top=Top.TEARDROP,
            printed=PRINT,
            label="d",
        )


def test_a_d_bore_needs_a_flat_between_the_centre_and_the_rim() -> None:
    with pytest.raises(ValueError, match="positive radius"):
        d_bore(0.0, 1.0)
    with pytest.raises(ValueError, match="centre and the rim"):
        d_bore(3.0, 0.0)
    with pytest.raises(ValueError, match="centre and the rim"):
        d_bore(3.0, 3.0)
