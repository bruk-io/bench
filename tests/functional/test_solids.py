"""Functional: a body built as a tree, through the public vocabulary.

Nothing here is evaluated - there is no kernel yet and no mesh - so what is asserted is the
only thing the tree can answer on its own: what every face of it is called, where the
named planes are, and what a part made of one refuses to be built with.
"""

import pytest

from bench import (
    XY,
    Label,
    Placed,
    Point,
    Process,
    Ref,
    Solid,
    Stock,
    Vector,
    assembly,
    boss,
    bounds,
    circle,
    cuboid,
    cut,
    cylinder,
    extrude,
    fill,
    index,
    near,
    open_box,
    part,
    plane_of,
    pocket,
    rect,
    refs,
    union,
)

pytestmark = pytest.mark.functional

PLA = Stock(0.0, "PLA")


def _plate() -> Solid:
    """The reviewer's example: a plate with a boss on it, a pocket in it and a bore through
    it, every feature named as it enters the tree.

    The root extrusion is anonymous, as a library's own root is - the part names it - so
    its faces come out as ``plate/top`` and the features under ``plate/boss``. A sketch is
    drawn flat and lifted onto the face it belongs to; ``plane_of`` says where that is.
    """
    plate = extrude(fill(rect(60, 40, label="outline")), 5.0)
    top = plane_of(plate, "top")
    plate = boss(plate, fill(circle(8, Point(15, 20)), on=top), 4.0, label="boss")
    plate = pocket(plate, fill(rect(20, 10, Point(30, 15)), on=top), 2.0, label="pocket")
    return cut(plate, cylinder(2.0, 5.0, at=Point(50, 10)), label="bore")


def test_a_plate_with_a_boss_a_pocket_and_a_bore_names_every_face_it_will_have() -> None:
    shown = assembly(Label("thing"), (Placed(part("plate", _plate(), PLA, Process.PRINT), XY),))
    assert refs(shown) == (
        Ref("plate"),
        Ref("plate/top"),
        Ref("plate/bottom"),
        Ref("plate/side-0"),
        Ref("plate/side-1"),
        Ref("plate/side-2"),
        Ref("plate/side-3"),
        Ref("plate/boss"),
        Ref("plate/boss/top"),
        Ref("plate/boss/bottom"),
        Ref("plate/boss/side-0"),
        Ref("plate/pocket"),
        Ref("plate/pocket/top"),
        Ref("plate/pocket/bottom"),
        Ref("plate/pocket/side-0"),
        Ref("plate/pocket/side-1"),
        Ref("plate/pocket/side-2"),
        Ref("plate/pocket/side-3"),
        Ref("plate/bore"),
        Ref("plate/bore/top"),
        Ref("plate/bore/bottom"),
        Ref("plate/bore/side-0"),
    )


def test_the_plates_features_stand_where_the_sketch_put_them() -> None:
    plate = _plate()
    assert near(plane_of(plate, "boss/top").origin, Point(0, 0, 9))
    floor = plane_of(plate, "pocket/bottom")
    assert near(floor.origin, Point(0, 0, 3))
    assert near(floor.normal, Vector(0, 0, -1))
    assert near(plane_of(plate, "pocket/top").origin, Point(0, 0, 5))
    # the boss grew the body upward; the pocket and the bore, being cuts, left the bound
    # where it was, which is what makes a bound conservative rather than wrong
    assert bounds(plate) == pytest.approx((0, 0, 0, 60, 40, 9))


def test_a_part_refuses_two_anonymous_bodies_and_says_which_ref_repeats() -> None:
    """The rule the naming table implies: at most one anonymous body per part. Both
    extrusions call a face ``top``, so the pair has no unique refs - naming one settles it."""
    with pytest.raises(ValueError, match="duplicate ref 'top' in stack"):
        part(
            "stack",
            union(cuboid(10, 10, 4), cuboid(10, 10, 4, at=Point(0, 0, 4))),
            PLA,
            Process.PRINT,
        )
    named = part(
        "stack",
        union(cuboid(10, 10, 4), cuboid(10, 10, 4, at=Point(0, 0, 4), label="lid")),
        PLA,
        Process.PRINT,
    )
    assert Ref("lid/top") in refs(named)


def test_an_extruded_panel_keeps_its_edge_names_clear_of_its_own_ends() -> None:
    """The reason ``side-`` is in the rule at all: :func:`open_box` labels a panel's edges
    ``bottom``, ``right``, ``top`` and ``left``, and the panel swept into a board has a
    ``top`` and a ``bottom`` of its own. Without the prefix the part would not build."""
    box = open_box(w=80.0, d=60.0, h=40.0, t=3.0, finger=12.0)
    board = part("front", extrude(box.front, 3.0), Stock(3.0, "ply"), Process.PRINT)
    found = refs(board)
    assert found[:2] == (Ref("top"), Ref("bottom"))
    assert Ref("side-top") in found
    assert Ref("side-bottom") in found
    assert Ref("side-left") in found
    assert Ref("side-right") in found
    # every jagged run keeps its own numbered name, and none of them collides
    assert len(set(found)) == len(found)
    assert len(found) == 2 + len(box.front.outer.edges)
    assert index(board)[Ref("side-left")].label == Label("side-left")
