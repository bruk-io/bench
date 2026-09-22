"""Unit: :mod:`bench.model` alone - the refs a part and an assembly name, and the
duplicates they refuse to be built with."""

import pytest

from bench import (
    XY,
    FaceRole,
    Label,
    Orient,
    Placed,
    Point,
    Printed,
    Process,
    Ref,
    SolidFace,
    Stock,
    Text,
    Vector,
    Volume,
    assembly,
    bounds,
    cuboid,
    cut,
    face,
    fill,
    index,
    part,
    process_of,
    rect,
    ref,
    refs,
    resolve,
    translation,
)
from bench.library.print import PLA
from bench.model import moved_part

pytestmark = pytest.mark.unit


def test_refs_and_resolve() -> None:
    pull = rect(30, 9, Point(70, 20), Label("pull"))
    outline = rect(175, 36, label=Label("outline"))
    front = face(outline, holes=(pull,), label=Label("front"))
    stock = Stock(3.0, "birch ply", kerf=0.25)
    drawer = part(Label("drawer-3"), front, stock, Process.LASER)
    cab = assembly(Label("cabinet"), (Placed(drawer, XY),))
    assert refs(cab) == (
        Ref("drawer-3"),
        Ref("drawer-3/front"),
        Ref("drawer-3/front/outline"),
        Ref("drawer-3/front/pull"),
    )
    assert resolve(cab, Ref("drawer-3/front/pull")) is pull
    assert index(cab)[Ref("drawer-3/front")] is front
    with pytest.raises(LookupError):
        resolve(cab, Ref("drawer-3/back"))


def test_an_assembly_is_laid_out_unless_it_says_it_is_already_posed() -> None:
    """``posed`` is the whole of decision-6's data change: off by default, so every assembly
    written before it existed means exactly what it meant, and the parts are the same parts
    either way - it says where they are looked at, never what they are."""
    front = face(rect(175, 36, label=Label("outline")), label=Label("front"))
    placed = (Placed(part(Label("drawer-3"), front, Stock(3.0, "ply"), Process.LASER), XY),)
    assert assembly(Label("cabinet"), placed).posed is False
    stack = assembly(Label("stack"), placed, posed=True)
    assert stack.posed is True
    assert stack.parts == placed
    assert refs(stack) == refs(assembly(Label("stack"), placed))


def test_duplicate_refs_are_rejected_at_build() -> None:
    a = rect(10, 10, label=Label("edge"))
    b = rect(5, 5, Point(2, 2), Label("edge"))
    with pytest.raises(ValueError):
        part(Label("p"), face(a, holes=(b,)), Stock(3, "ply"), Process.LASER)


def test_engravings_are_named_like_the_shape() -> None:
    front = face(rect(60, 20, label=Label("outline")), label=Label("front"))
    mark = Text("3", Point(5, 5), 6.0, Label("number"))
    score = rect(40, 2, Point(10, 15), Label("score"))
    drawer = part(
        Label("drawer-3"),
        front,
        Stock(3.0, "birch ply"),
        Process.LASER,
        engravings=(mark, score),
    )
    assert drawer.engravings == (mark, score)
    assert refs(drawer) == (
        Ref("front"),
        Ref("front/outline"),
        Ref("number"),
        Ref("score"),
    )
    assert resolve(drawer, Ref("number")) is mark
    assert resolve(drawer, Ref("score")) is score


def test_a_part_without_engravings_has_none() -> None:
    f = face(rect(10, 10), label=Label("front"))
    assert part(Label("p"), f, Stock(3, "ply"), Process.LASER).engravings == ()


def test_an_engraving_cannot_take_a_name_the_shape_already_uses() -> None:
    front = face(rect(10, 10, label=Label("outline")), label=Label("front"))
    with pytest.raises(ValueError):
        part(
            Label("p"),
            front,
            Stock(3, "ply"),
            Process.LASER,
            engravings=(Text("x", Point(1, 1), 3.0, Label("front")),),
        )


# ---- a body in the ref table -------------------------------------------------------------


def test_a_bare_solid_is_a_root_and_its_faces_are_leaves() -> None:
    """``index`` takes a body on its own so a script can ask it about its own faces before
    it is part of anything - which is what ``plane_of(plate, "top")`` needs."""
    plate = cuboid(40, 30, 5, label=Label("plate"))
    assert refs(plate) == (
        Ref("top"),
        Ref("bottom"),
        Ref("side-front"),
        Ref("side-right"),
        Ref("side-back"),
        Ref("side-left"),
    )
    top = resolve(plate, Ref("top"))
    assert isinstance(top, SolidFace)
    assert top.role is FaceRole.TOP
    assert index(plate)[Ref("side-front")].label == Label("side-front")


def test_a_solid_under_a_part_puts_every_face_under_the_parts_name() -> None:
    body = cut(cuboid(40, 30, 5), cuboid(4, 4, 2, at=Point(10, 10, 3)), label=Label("notch"))
    holder = part(Label("bracket"), body, Stock(0.0, "PLA"), Process.PRINT)
    cab = assembly(Label("kit"), (Placed(holder, XY),))
    assert refs(cab)[:3] == (
        Ref("bracket"),
        Ref("bracket/top"),
        Ref("bracket/bottom"),
    )
    assert Ref("bracket/notch/bottom") in refs(cab)
    assert resolve(cab, Ref("bracket/notch")).label == Label("notch")


def test_a_part_holding_a_body_moves_with_its_engravings() -> None:
    body = cuboid(10, 10, 4, label=Label("body"))
    holder = part(
        Label("p"),
        body,
        Stock(0.0, "PLA"),
        Process.PRINT,
        engravings=(Text("3", Point(1, 1), 3.0, Label("number")),),
    )
    lifted = moved_part(holder, translation(Vector(0, 0, 6)))
    assert bounds(lifted.shape) == pytest.approx((0, 0, 6, 10, 10, 10))
    mark = lifted.engravings[0]
    assert isinstance(mark, Text)
    assert mark.at == Point(1, 1, 6)


# ---- what a part is made of ------------------------------------------------------------


def test_a_printed_part_is_not_a_sheet_with_zeroes_in_it() -> None:
    """The second arm of the union. ``Stock(0.0, "PLA")`` said a print was 0 mm thick with
    no kerf, which were three lies in one record; a :class:`Printed` says the two things
    that are true of it instead."""
    printed = Printed(PLA)
    assert printed.material is PLA
    assert printed.orient == Orient()
    assert printed.orient.up == Vector(0, 0, 1)
    assert printed.orient.bed_face is None
    assert printed == Printed(PLA, Orient())
    assert len({printed, printed}) == 1


def test_the_process_is_read_off_the_stock_rather_than_said_twice() -> None:
    assert process_of(Stock(3.0, "ply", kerf=0.25)) is Process.LASER
    assert process_of(Printed(PLA)) is Process.PRINT


def test_a_part_takes_the_process_its_stock_implies() -> None:
    """``part()`` still takes one when a script wants to say so - a milled panel is cut
    from sheet stock and is nobody's laser job - and works it out when the script does not."""
    panel = fill(rect(20, 10))
    assert part("lid", panel, Printed(PLA)).process is Process.PRINT
    assert part("side", panel, Stock(3.0, "ply")).process is Process.LASER
    assert part("side", panel, Stock(18.0, "mdf"), Process.CNC).process is Process.CNC


def test_a_printed_part_is_indexed_like_any_other() -> None:
    """Nothing about naming changes with the stock: a printed body's refs are the tree's,
    exactly as a cut panel's are the face's."""
    body = cuboid(20, 20, 5)
    made = part("block", body, Printed(PLA, Orient(up=Vector(0, 1, 0), bed_face=ref("bottom"))))
    assert refs(made)[:2] == (Ref("top"), Ref("bottom"))
    assert isinstance(made.stock, Printed)
    assert made.stock.orient.bed_face == Ref("bottom")


def test_a_build_volume_is_three_millimetres() -> None:
    assert Volume(350.0, 320.0, 325.0).w == pytest.approx(350.0)
    assert tuple(Volume(1.0, 2.0, 3.0)) == (1.0, 2.0, 3.0)
