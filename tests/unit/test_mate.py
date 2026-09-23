"""Unit: :mod:`bench.mate` alone - where a mate puts a part, read back off the moved part's
own faces.

Everything here is the tree's arithmetic: the moved part's faces answer
:func:`~bench.solids.plane_of` wherever the move put them, so a mate is checked by asking the
moved face where it now is rather than by reading the transform. Measuring the pair is the
adapter layer's, with a real kernel.
"""

import math

import pytest

from bench import (
    CONTACT,
    ORIGIN,
    XY,
    Axis,
    Fit,
    Mate,
    Orient,
    Part,
    Plane,
    Point,
    Printed,
    Ref,
    Solid,
    Stock,
    Top,
    Vector,
    X,
    Y,
    Z,
    axis_of,
    bounds,
    circle,
    coaxial,
    cuboid,
    cut,
    cylinder,
    extrude,
    face,
    fill,
    gap_of,
    hole,
    mating,
    move,
    near,
    oriented,
    part,
    placing,
    plane_of,
    pocket,
    raised,
    rect,
    refs,
    rotate,
    rotation,
    translation,
    union,
)
from bench.library.print import PLA, clearance

pytestmark = pytest.mark.unit

PRINTED = Printed(PLA)
BASE = cuboid(40, 40, 5)
"""What the plates here are put on: its ``top`` is at z = 5, framed from the corner at the
origin, X along X."""


def _plate() -> Part:
    return part("plate", cuboid(20, 10, 4), PRINTED)


def _same(a: Plane, b: Plane) -> bool:
    """Two frames that agree to within the package's tolerance, origin, normal and X."""
    return near(a.origin, b.origin) and near(a.normal, b.normal) and near(a.x_dir, b.x_dir)


def _face_of(mate: Mate, at: str) -> Plane:
    shape = mate.part.shape
    assert isinstance(shape, Solid)
    return plane_of(shape, at)


# ---- where the moved face lands ---------------------------------------------------------


def test_a_mated_face_lies_on_the_fixed_face_with_its_normal_opposed() -> None:
    """The plate's bottom on the base's top: the bottom's frame is now the top's own, turned
    over - the same origin, the normal reversed, X running the same way."""
    top = plane_of(BASE, "top")
    mate = mating(BASE, "top", _plate(), "plate/bottom")
    bottom = _face_of(mate, "bottom")
    assert near(bottom.origin, top.origin)
    assert near(bottom.normal, -top.normal)
    assert near(bottom.x_dir, top.x_dir)
    assert mate.gap == pytest.approx(0.0)


def test_a_fit_stands_the_face_off_by_the_tables_own_gap() -> None:
    """A slide in PLA is the gap ``clearance`` reads, along the fixed face's normal - the
    same number every other printed fit comes out of."""
    top = plane_of(BASE, "top")
    mate = mating(BASE, "top", _plate(), "plate/bottom", fit=Fit.SLIDE)
    gap = clearance(Fit.SLIDE, PLA)
    assert mate.gap == gap
    assert near(_face_of(mate, "bottom").origin, top.origin + top.normal * gap)


def test_offset_slides_the_face_in_the_fixed_faces_own_x_and_y() -> None:
    top = plane_of(BASE, "top")
    mate = mating(BASE, "top", _plate(), "plate/bottom", offset=Vector(7.0, 3.0))
    assert near(_face_of(mate, "bottom").origin, top.origin + top.x_dir * 7.0 + top.y_dir * 3.0)


def test_spin_turns_the_face_about_the_fixed_normal_counter_clockwise_from_outside() -> None:
    """A quarter turn: the plate's X now runs along the base's Y, and its origin stays put."""
    top = plane_of(BASE, "top")
    mate = mating(BASE, "top", _plate(), "plate/bottom", spin=math.pi / 2)
    bottom = _face_of(mate, "bottom")
    assert near(bottom.x_dir, top.y_dir)
    assert near(bottom.origin, top.origin)
    assert near(bottom.normal, -top.normal)


def test_offset_and_spin_both_place_about_the_offset_point() -> None:
    """The face is turned about the point it was slid to, so its origin is the offset point
    whatever the spin."""
    top = plane_of(BASE, "top")
    mate = mating(BASE, "top", _plate(), "plate/bottom", offset=Vector(10, 10), spin=0.3)
    bottom = _face_of(mate, "bottom")
    assert near(bottom.origin, top.origin + Vector(10, 10))
    assert near(bottom.x_dir, rotation(Axis(ORIGIN, Z), 0.3) @ X)


def test_where_the_part_was_before_does_not_change_where_it_lands() -> None:
    """A plate that wandered off - turned about a skew axis, shifted - and one that did not
    land in the same place, face for face: the mate reads the face's own frame, not where the
    part happened to be."""
    wandered = part(
        "plate",
        move(rotate(cuboid(20, 10, 4), 1.1, about=Axis(Point(3, -7, 2), Vector(1, 2, 3))), Y * 9),
        PRINTED,
    )
    home = mating(BASE, "top", _plate(), "plate/bottom", offset=Vector(4, 5), spin=0.7)
    back = mating(BASE, "top", wandered, "plate/bottom", offset=Vector(4, 5), spin=0.7)
    for name in ("top", "bottom", "side-front", "side-right", "side-back", "side-left"):
        assert _same(_face_of(back, name), _face_of(home, name)), name


def test_a_move_the_mate_makes_is_rigid() -> None:
    """Every face of the plate keeps its distance from every other: the transform is a
    rotation and a translation, never a scale or a mirror."""
    mate = mating(BASE, "top", _plate(), "plate/bottom", offset=Vector(2, 3), spin=1.2)
    top, bottom = _face_of(mate, "top"), _face_of(mate, "bottom")
    assert abs((top.origin - bottom.origin) @ top.normal) == pytest.approx(4.0)
    assert near(top.y_dir, bottom.y_dir * -1.0)


def test_placing_is_the_frame_arithmetic_on_its_own() -> None:
    """The move itself, handed two frames: the moving frame's origin goes to the seat, and
    its normal to the seat's reversed."""
    seat = Plane(Point(1, 2, 3), Y, X)
    face_ = Plane(Point(-4, 0, 6), Z, Y)
    t = placing(seat, face_, gap=0.5)
    assert near(t @ face_.origin, Point(1, 2.5, 3))
    assert near(t @ face_.normal, -Y)
    assert near(t @ face_.x_dir, X)


# ---- onto a face a cut left --------------------------------------------------------------


def test_a_part_mated_onto_a_pockets_floor_sits_in_the_pocket() -> None:
    """The floor a pocket leaves faces up out of the base, into the pocket, so a plate laid on
    it sits in the pocket the right way up - its bottom on the floor, its top standing out
    of the base's top - not turned over and hanging below the floor."""
    sunk = pocket(BASE, fill(rect(20, 10), on=plane_of(BASE, "top")), 2.0, label="pocket")
    mate = mating(sunk, "pocket/bottom", _plate(), "plate/bottom")
    body = mate.part.shape
    assert isinstance(body, Solid)
    assert bounds(body) == pytest.approx((0.0, 0.0, 3.0, 20.0, 10.0, 7.0))
    assert near(_face_of(mate, "bottom").normal, -Z)
    stock = mate.part.stock
    assert isinstance(stock, Printed)
    assert near(stock.orient.up, Z)


def test_a_part_mated_under_a_cavitys_ceiling_hangs_from_it() -> None:
    """A slot cut through the middle of a block has a ceiling facing down out of the block,
    so a plate's top put on it hangs below it, inside the slot."""
    slot = cut(cuboid(40, 40, 10), cuboid(40, 20, 4, at=Point(0, 10, 3)), label="slot")
    mate = mating(slot, "slot/top", _plate(), "plate/top")
    body = mate.part.shape
    assert isinstance(body, Solid)
    low = bounds(body)
    assert (low.z0, low.z1) == pytest.approx((3.0, 7.0))


# ---- a pin in its bore ------------------------------------------------------------------


def _bored(r: float = 2.25) -> Part:
    """A 20 x 20 x 5 plate with a round hole drawn in its profile, labelled ``bore``: its
    axis runs up +Z from the plate's own bottom, at (10, 10)."""
    profile = cut(fill(rect(20, 20)), circle(r, Point(10, 10)), label="bore")
    return part("plate", extrude(profile, 5.0), PRINTED)


def _pin(r: float = 2.0, h: float = 12.0) -> Part:
    return part("pin", cylinder(r, h), PRINTED)


def _axis(mate: Mate, at: str) -> Plane:
    shape = mate.part.shape
    assert isinstance(shape, Solid)
    return axis_of(shape, at)


def test_a_pin_goes_on_the_bores_axis_running_the_way_the_bore_does() -> None:
    """Two round faces are a round pair: the pin's axis is the bore's own frame, origin,
    direction and zero, so its foot is on the plane the hole was drawn on and it stands up
    through the plate. Nothing about the gap round it was placed - the radii say it."""
    plate = _bored()
    mate = mating(plate, "plate/bore", _pin(), "pin/side-0", fit=Fit.SLIDE)
    assert _same(_axis(mate, "side-0"), axis_of(_body(plate), "bore"))
    low = bounds(_body(mate.part))
    assert (low.x0, low.y0, low.z0, low.z1) == pytest.approx((8.0, 8.0, 0.0, 12.0))
    assert mate.gap == clearance(Fit.SLIDE, PLA)
    assert mate.faces == ("pin/side-0", "plate/bore")


def test_along_slides_the_pin_up_the_bores_axis_and_spin_turns_it_about_it() -> None:
    """Both explicit: a pin has no one place along its bore or one way round in it, so the
    script says. Spin is counter-clockwise seen from the end the axis points to."""
    bore = axis_of(_body(_bored()), "bore")
    mate = mating(_bored(), "plate/bore", _pin(), "pin/side-0", along=-3.0, spin=math.pi / 2)
    axis = _axis(mate, "side-0")
    assert near(axis.origin, bore.origin + bore.normal * -3.0)
    assert near(axis.normal, bore.normal)
    assert near(axis.x_dir, Y)
    assert bounds(_body(mate.part)).z0 == pytest.approx(-3.0)


def test_a_pin_that_wandered_off_goes_back_in_the_same_way() -> None:
    """The mate reads the pin's own axis, not where the pin was: turned about a skew axis
    and shifted first, it lands face for face where an unmoved one does."""
    wandered = part(
        "pin",
        move(rotate(cylinder(2.0, 12.0), 1.1, about=Axis(Point(3, -7, 2), Vector(1, 2, 3))), Y),
        PRINTED,
    )
    home = mating(_bored(), "plate/bore", _pin(), "pin/side-0", along=1.0, spin=0.4)
    back = mating(_bored(), "plate/bore", wandered, "pin/side-0", along=1.0, spin=0.4)
    assert _same(_axis(back, "side-0"), _axis(home, "side-0"))
    for name in ("top", "bottom"):
        assert _same(_face_of(back, name), _face_of(home, name)), name


def test_the_end_a_pin_was_swept_from_is_the_end_that_goes_in_first() -> None:
    """A headed pin swept up from its head goes in shank first with the head left at the
    bore's mouth; the same pin swept down from its tip goes in tip first, and the head ends
    up past the far side. Which end leads is how the pin was drawn - never guessed."""
    head = cylinder(4.0, 2.0, label="head")
    up = union(head, extrude(fill(circle(2.0), on=raised(XY, 2.0)), 10.0, label="shank"))
    down = union(head, extrude(fill(circle(2.0), on=raised(XY, 12.0)), -10.0, label="shank"))
    headfirst = mating(_bored(), "plate/bore", part("pin", up, PRINTED), "pin/shank/side-0")
    tipfirst = mating(_bored(), "plate/bore", part("pin", down, PRINTED), "pin/shank/side-0")
    assert _face_of(headfirst, "head/top").origin.z == pytest.approx(0.0)
    assert bounds(_body(headfirst.part)).z0 == pytest.approx(-2.0)
    assert _face_of(tipfirst, "head/top").origin.z == pytest.approx(10.0)
    assert bounds(_body(tipfirst.part)).z1 == pytest.approx(12.0)


def test_a_hole_bores_axis_starts_at_its_mouth_just_outside_the_material() -> None:
    """``hole`` draws its tool from a hair above the face it is drilled from and sweeps it
    down, so a pin at ``along=0`` stands that hair proud of the plate and runs down into it:
    the authored frame is the rule, and ``along`` is how it is corrected."""
    plate = cuboid(20, 20, 5)
    plate = hole(
        plate,
        Point(10, 10),
        on=plane_of(plate, "top"),
        diameter=4.4,
        fit=Fit.SLIDE,
        printed=PRINTED,
        label="bore",
    )
    axis = axis_of(plate, "bore/side-0")
    assert near(axis.normal, -Z)
    assert axis.origin.z == pytest.approx(5.01)
    mate = mating(part("plate", plate, PRINTED), "plate/bore/side-0", _pin(), "pin/side-0")
    low = bounds(_body(mate.part))
    assert (low.x0, low.y0, low.x1, low.y1) == pytest.approx((8.0, 8.0, 12.0, 12.0))
    assert (low.z0, low.z1) == pytest.approx((5.01 - 12.0, 5.01))


def test_a_round_mate_hands_the_measurement_its_faces_and_the_bores_axis() -> None:
    """What the gap round a pin is measured along: the bore's own axis, and the two round
    faces by the refs each body's mesh tags them with - the pin's first - so the shared
    length is read off the triangles of those faces and nothing else. A flat pair has no
    such thing, and its gap is the nearest the two bodies come."""
    plate = _bored()
    mate = mating(plate, "plate/bore", _pin(), "pin/side-0", fit=Fit.SLIDE)
    assert mate.pair is not None
    assert _same(mate.pair.axis, axis_of(_body(plate), "bore"))
    assert mate.pair.faces == (Ref("side-0"), Ref("bore"))
    assert set(mate.pair.faces) <= set(refs(_body(mate.part))) | set(refs(_body(plate)))
    assert mating(BASE, "top", _plate(), "plate/bottom").pair is None


def test_a_round_mates_faces_are_named_without_a_bodys_own_label() -> None:
    """A body with a label of its own is asked for a face with or without it in front, as
    ``plane_of`` is; its mesh names the face without it either way."""
    profile = cut(fill(rect(20, 20)), circle(2.25, Point(10, 10)), label="bore")
    slab = extrude(profile, 5.0, label="slab")
    mate = mating(
        slab, "slab/bore", part("pin", cylinder(2.0, 12.0, label="rod"), PRINTED), "rod/side-0"
    )
    assert mate.pair is not None
    assert mate.pair.faces == (Ref("side-0"), Ref("bore"))


def test_a_drilled_bores_wall_facing_its_axis_does_not_move_the_axis() -> None:
    """A cut's faces are turned over so a drilled bore's wall faces its axis, out of the plate
    that is left; the axis a pin goes on is the line the drill ran along, which turning the
    wall's frame over does not touch - so the pin still goes in down the drill's way."""
    plate = cuboid(20, 20, 5)
    plate = hole(
        plate, Point(10, 10), on=plane_of(plate, "top"), diameter=4.4, top=Top.ROUND, label="d"
    )
    wall = plane_of(plate, "d/side-0", around=0.0, along=1.0)
    axis = axis_of(plate, "d/side-0")
    assert near(wall.normal, -axis.x_dir), "the wall faces the axis"
    assert near(axis.normal, -Z)
    mate = mating(part("plate", plate, PRINTED), "plate/d/side-0", _pin(), "pin/side-0")
    assert _same(_axis(mate, "side-0"), axis)


def test_coaxial_is_the_frame_arithmetic_on_its_own() -> None:
    seat = Plane(Point(1, 2, 3), Y, Z)
    axis = Plane(Point(-4, 0, 6), X, Y)
    t = coaxial(seat, axis, along=2.0, spin=math.pi / 2)
    assert near(t @ axis.origin, Point(1, 4, 3))
    assert near(t @ axis.normal, Y)
    assert near(t @ axis.x_dir, X)


def test_a_round_face_goes_in_a_round_one_and_a_flat_one_on_a_flat_one() -> None:
    with pytest.raises(ValueError, match=r"pin/side-0 is round and plate/top is not"):
        mating(_bored(), "plate/top", _pin(), "pin/side-0")
    with pytest.raises(ValueError, match=r"plate/bore is round and pin/bottom is not"):
        mating(_bored(), "plate/bore", _pin(), "pin/bottom")


def test_a_round_pair_has_nothing_to_offset_and_a_flat_one_nothing_to_slide_along() -> None:
    with pytest.raises(ValueError, match="nothing to offset="):
        mating(_bored(), "plate/bore", _pin(), "pin/side-0", offset=Vector(1, 0))
    with pytest.raises(ValueError, match="are flat"):
        mating(BASE, "top", _plate(), "plate/bottom", along=2.0)


def test_a_round_pairs_way_up_turns_with_it_like_a_flat_ones() -> None:
    """A pin put into a bore that runs along X is lying down, and prints the way it was
    drawn - standing on its foot - because its way up turned with it."""
    lying = part("plate", rotate(_body(_bored()), math.pi / 2, about=Axis(ORIGIN, Y)), PRINTED)
    mate = mating(lying, "plate/bore", _pin(), "pin/side-0")
    stock = mate.part.stock
    assert isinstance(stock, Printed)
    assert near(stock.orient.up, X)


def _body(one: Part) -> Solid:
    shape = one.shape
    assert isinstance(shape, Solid)
    return shape


# ---- what a mate is handed ---------------------------------------------------------------


def test_a_face_is_named_the_way_the_scene_names_it_or_without_the_part() -> None:
    """``frame/flange/top`` is what a click inserts; ``flange/top`` is what the part's own
    body calls it. Both find the same face, and the mate names them the scene's way."""
    frame = part("frame", extrude(face(rect(40, 40)), 5.0, label="flange"), PRINTED)
    one = mating(frame, "frame/flange/top", _plate(), "plate/bottom")
    other = mating(frame, "flange/top", _plate(), "bottom")
    assert _same(_face_of(one, "bottom"), _face_of(other, "bottom"))
    assert one.faces == ("plate/bottom", "frame/flange/top") == other.faces
    assert one.on is frame.shape


def test_a_mate_is_not_measured_until_the_edge_measures_it() -> None:
    mate = mating(BASE, "top", _plate(), "plate/bottom")
    assert mate.fitted is None
    assert str(mate) == "plate/bottom on top: not measured"


def test_an_offset_with_a_z_is_refused_because_the_gap_is_the_fits() -> None:
    with pytest.raises(ValueError, match="no Z"):
        mating(BASE, "top", _plate(), "plate/bottom", offset=Vector(0, 0, 1))


def test_a_round_face_is_not_a_planar_pair() -> None:
    """A cylinder's side has no one plane to lay another face on; round pairs are their own
    kind, and a planar mate refuses one where ``plane_of`` does."""
    with pytest.raises(ValueError, match="round"):
        mating(cylinder(10, 20), "side-0", _plate(), "plate/bottom")


def test_a_face_that_is_not_there_is_a_lookup_error() -> None:
    with pytest.raises(LookupError, match="underneath"):
        mating(BASE, "top", _plate(), "plate/underneath")


def test_a_flat_part_has_no_face_to_put_on_anything() -> None:
    sheet = part("panel", face(rect(40, 40)), Stock(3.0, "ply"))
    with pytest.raises(ValueError, match="cut from sheet"):
        mating(sheet, "top", _plate(), "plate/bottom")
    with pytest.raises(ValueError, match="cut from sheet"):
        mating(BASE, "top", sheet, "panel/top")


# ---- the gap a fit means -----------------------------------------------------------------


def test_a_contact_is_no_gap_and_needs_no_material() -> None:
    assert gap_of(CONTACT, None) == pytest.approx(0.0)


def test_a_fits_gap_is_the_materials_own_per_side_figure() -> None:
    for fit in (Fit.PRESS, Fit.SNUG, Fit.SLIDE, Fit.CLEARANCE, Fit.LOOSE):
        assert gap_of(fit, PLA) == clearance(fit, PLA)


def test_a_fit_with_no_material_to_read_is_refused() -> None:
    with pytest.raises(ValueError, match="slide fit is a gap in some plastic"):
        gap_of(Fit.SLIDE, None)


def test_an_interference_is_not_a_gap_two_faces_stand_at() -> None:
    with pytest.raises(ValueError, match="CONTACT"):
        gap_of(Fit.INTERFERENCE, PLA)


# ---- which way up it prints --------------------------------------------------------------


def test_a_prints_way_up_turns_with_the_body_and_keeps_its_bed_face() -> None:
    """Turned over about X: what was up is down, in the moved part's own coordinates, and
    the face that lay on the bed is the same face by the same name."""
    stock = Printed(PLA, Orient(up=Z, bed_face=Ref("bottom")))
    turned = oriented(stock, rotation(Axis(ORIGIN, X), math.pi))
    assert isinstance(turned, Printed)
    assert near(turned.orient.up, -Z)
    assert turned.orient.bed_face == Ref("bottom")
    assert turned.material is PLA


def test_a_move_that_only_translates_leaves_the_way_up_alone() -> None:
    stock = Printed(PLA, Orient(up=X))
    moved = oriented(stock, translation(Vector(5, 6, 7)))
    assert isinstance(moved, Printed)
    assert near(moved.orient.up, X)


def test_a_sheet_has_no_way_up_to_turn() -> None:
    sheet = Stock(3.0, "ply")
    assert oriented(sheet, rotation(Axis(ORIGIN, X), 1.0)) is sheet


def test_a_part_mated_upside_down_carries_its_way_up_upside_down() -> None:
    """A plate whose top is put on the base's top is upside down, and so is the way up its
    stock now says: it still prints on its own bottom, wherever it sits."""
    mate = mating(BASE, "top", _plate(), "plate/top")
    stock = mate.part.stock
    assert isinstance(stock, Printed)
    assert near(stock.orient.up, -Z)
    assert near(_face_of(mate, "bottom").normal, Z)


def test_the_moved_part_keeps_its_label_and_is_a_new_body() -> None:
    plate = _plate()
    mate = mating(BASE, "top", plate, "plate/bottom")
    assert mate.part.label == plate.label
    assert mate.part.shape is not plate.shape
