import pytest

from bench import (
    XY,
    Bed,
    Build,
    Face,
    Label,
    Part,
    Point,
    Process,
    Ref,
    Text,
    Wire,
    bbox,
    contains,
    index,
    is_ccw,
    is_closed,
    nest,
    part_texts,
    refs,
    resolve,
)
from bench.library.gridfinity import (
    BASEPLATE_T,
    GRID,
    LIP,
    Z_UNIT,
    Spec,
    baseplate_scad,
    cabinet,
    derive,
    validate,
)

pytestmark = pytest.mark.functional

SHEET = 320.0


def _cut_list(build: Build) -> tuple[tuple[Part, int], ...]:
    """The build as :func:`nest` takes it: each part with how many of it to cut, in the
    order the assembly holds them."""
    return tuple(
        (placed.part, build.quantities[Ref(placed.part.label)]) for placed in build.assembly.parts
    )


def _shape(build: Build, ref: str) -> Face:
    found = resolve(build.assembly, Ref(ref))
    assert isinstance(found, Part)
    assert isinstance(found.shape, Face)
    return found.shape


def _hole(build: Build, ref: str) -> Wire:
    found = resolve(build.assembly, Ref(ref))
    assert isinstance(found, Wire)
    return found


def _part(build: Build, ref: str) -> Part:
    found = resolve(build.assembly, Ref(ref))
    assert isinstance(found, Part)
    return found


# ---- the gridfinity maths --------------------------------------------------------------


def test_a_drawer_holds_whole_gridfinity_units_and_a_millimetre_to_spare() -> None:
    d = derive(Spec(units_x=4, units_y=2))
    assert d.interior_w == pytest.approx(GRID * 4 + 1.0)
    assert d.interior_d == pytest.approx(GRID * 2 + 1.0)
    assert derive(Spec(units_x=7)).interior_w == pytest.approx(GRID * 7 + 1.0)


def test_a_drawer_is_tall_enough_for_the_bins_the_lip_and_the_baseplate() -> None:
    d = derive(Spec(height_u=3, baseplate=True))
    assert d.interior_h == pytest.approx(3 * Z_UNIT + LIP + 3.0 + BASEPLATE_T)
    assert d.interior_h == pytest.approx(21 + 4.4 + 3 + 4.65)
    bare = derive(Spec(height_u=3, baseplate=False))
    assert bare.interior_h == pytest.approx(21 + 4.4 + 3)
    assert d.interior_h - bare.interior_h == pytest.approx(BASEPLATE_T)


def test_a_drawer_outside_is_its_inside_plus_walls_and_one_bottom() -> None:
    spec = Spec()
    d = derive(spec)
    assert d.drawer_w == pytest.approx(d.interior_w + 2 * spec.drawer_t)
    assert d.drawer_d == pytest.approx(d.interior_d + 2 * spec.drawer_t)
    assert d.drawer_h == pytest.approx(d.interior_h + spec.drawer_t)


def test_the_carcass_follows_the_drawers_it_holds() -> None:
    spec = Spec()
    d = derive(spec)
    assert d.pitch == pytest.approx(spec.carcass_t + d.drawer_h + spec.drawer_gap)
    assert d.cab_w == pytest.approx(d.drawer_w + 2 * spec.side_clearance + 2 * spec.carcass_t)
    assert d.cab_d == pytest.approx(d.drawer_d + spec.carcass_t)
    assert d.cab_h == pytest.approx(2 * spec.carcass_t + spec.drawers * d.pitch)
    assert d.cab_h == pytest.approx(273.3)


def test_a_runner_is_set_back_from_the_drawer_and_as_wide_as_its_reach_and_tab() -> None:
    spec = Spec()
    d = derive(spec)
    assert d.runner_len == pytest.approx(d.drawer_d - spec.runner_setback)
    assert d.runner_w == pytest.approx(spec.runner_reach + spec.carcass_t)
    assert bbox(_shape(cabinet(spec), "runner")) == pytest.approx(
        (0.0, -spec.carcass_t, d.runner_len, spec.runner_reach)
    )


def test_drawers_are_numbered_unless_the_spec_names_them() -> None:
    numbered = cabinet(Spec(drawers=3))
    assert [str(p.part.label) for p in numbered.assembly.parts][:3] == [
        "drawer-front-1",
        "drawer-front-2",
        "drawer-front-3",
    ]
    named = cabinet(Spec(drawers=2, labels=("bits", "bobs")))
    assert [str(p.part.label) for p in named.assembly.parts][:2] == [
        "drawer-front-bits",
        "drawer-front-bobs",
    ]


# ---- the parts and their refs ----------------------------------------------------------


def test_every_ref_in_the_build_is_unique_and_the_expected_ones_are_there() -> None:
    build = cabinet(Spec())
    table = index(build.assembly)
    assert len(table) == len(refs(build.assembly))
    for ref in (
        "drawer-front-1",
        "drawer-front-1/pull",
        "drawer-front-1/label",
        "drawer-front-6/pull",
        "drawer-back",
        "drawer-side",
        "drawer-bottom",
        "cabinet-side-left",
        "cabinet-side-left/slot-0",
        "cabinet-side-right/slot-5",
        "cabinet-top-bottom",
        "cabinet-back",
        "runner",
        "runner/bottom",
    ):
        assert Ref(ref) in table, ref


def test_identical_panels_appear_once_and_are_counted_instead() -> None:
    build = cabinet(Spec(drawers=6))
    counted = {str(p.label): n for p, n in _cut_list(build)}
    assert counted["drawer-front-1"] == 1
    assert counted["drawer-back"] == 6
    assert counted["drawer-side"] == 12
    assert counted["drawer-bottom"] == 6
    assert counted["cabinet-side-left"] == 1
    assert counted["cabinet-side-right"] == 1
    assert counted["cabinet-top-bottom"] == 2
    assert counted["cabinet-back"] == 1
    assert counted["runner"] == 12
    assert sum(counted.values()) == 7 * 6 + 5


def test_columns_cut_the_same_cabinet_again_without_changing_a_dimension() -> None:
    one, two = cabinet(Spec()), cabinet(Spec(columns=2))
    assert derive(Spec()) == derive(Spec(columns=2))
    assert refs(one.assembly) == refs(two.assembly)
    for ref, count in one.quantities.items():
        assert two.quantities[ref] == 2 * count


def test_every_part_is_a_planar_laser_cut_panel_of_its_own_stock() -> None:
    spec = Spec()
    build = cabinet(spec)
    thicknesses = {}
    for placed in build.assembly.parts:
        assert placed.on == XY
        assert isinstance(placed.part.shape, Face)
        assert placed.part.process is Process.LASER
        assert placed.part.stock.material == "ply"
        assert placed.part.stock.kerf == spec.kerf
        thicknesses[str(placed.part.label)] = placed.part.stock.thickness
    assert thicknesses["drawer-front-1"] == spec.drawer_t
    assert thicknesses["drawer-bottom"] == spec.drawer_t
    assert thicknesses["cabinet-back"] == spec.carcass_t
    assert thicknesses["runner"] == spec.carcass_t


def test_every_panel_is_closed_and_every_hole_and_letter_is_named() -> None:
    build = cabinet(Spec(drawers=3))
    for placed in build.assembly.parts:
        shape = placed.part.shape
        assert isinstance(shape, Face)
        assert shape.label is None, "a part names the panel, so its face is transparent"
        assert is_closed(shape.outer) and is_ccw(shape.outer)
        for hole in shape.inner:
            assert hole.label is not None
            assert is_closed(hole)
        for engraving in placed.part.engravings:
            assert engraving.label == Label("label")


# ---- the drawer front ------------------------------------------------------------------


def test_the_pull_is_centred_below_the_top_edge_and_is_a_hole_in_the_front() -> None:
    spec = Spec()
    d = derive(spec)
    build = cabinet(spec)
    box = bbox(_hole(build, "drawer-front-1/pull"))
    assert box.w == pytest.approx(spec.pull_w)
    assert box.h == pytest.approx(spec.pull_h)
    assert (box.x0 + box.x1) / 2 == pytest.approx(d.drawer_w / 2)
    assert d.drawer_h - box.y1 == pytest.approx(spec.pull_margin)
    front = _shape(build, "drawer-front-1")
    assert not contains(front, Point(d.drawer_w / 2, (box.y0 + box.y1) / 2))
    assert contains(front, Point(d.drawer_w / 2, box.y0 - 2.0))


def test_the_label_sits_between_the_bottom_joint_and_the_pull() -> None:
    spec = Spec()
    d = derive(spec)
    build = cabinet(spec)
    pull = bbox(_hole(build, "drawer-front-3/pull"))
    text = part_texts(_part(build, "drawer-front-3"))
    assert len(text) == 1
    assert (text[0].text, text[0].size) == ("3", spec.label_size)
    assert spec.drawer_t <= text[0].y
    assert text[0].y + spec.label_size <= pull.y0
    middle = (spec.drawer_t + pull.y0) / 2
    assert text[0].y + spec.label_size / 2 == pytest.approx(middle)
    assert text[0].x < d.drawer_w / 2 < text[0].x + spec.label_size


def test_each_front_carries_its_own_label_and_fronts_are_the_only_parts_that_differ() -> None:
    build = cabinet(Spec(drawers=2, labels=("bits", "bobs")))
    assert part_texts(_part(build, "drawer-front-bits"))[0].text == "bits"
    assert part_texts(_part(build, "drawer-front-bobs"))[0].text == "bobs"
    assert _part(build, "drawer-back").engravings == ()
    assert _shape(build, "drawer-back").inner == ()


def test_an_engraving_is_a_text_and_never_a_cut() -> None:
    build = cabinet(Spec(drawers=1))
    engravings = _part(build, "drawer-front-1").engravings
    assert len(engravings) == 1
    assert isinstance(engravings[0], Text)


# ---- the cabinet sides -----------------------------------------------------------------


def test_a_side_is_slotted_once_per_runner_tab_at_the_drawer_pitch() -> None:
    spec = Spec()
    d = derive(spec)
    build = cabinet(spec)
    side = _shape(build, "cabinet-side-left")
    assert bbox(side) == pytest.approx((0.0, 0.0, d.cab_h, d.cab_d))
    assert len(side.inner) == 2 * spec.drawers
    for i in range(spec.drawers):
        box = bbox(_hole(build, f"cabinet-side-left/slot-{i}"))
        assert box.x0 == pytest.approx(spec.carcass_t + i * d.pitch)
        assert box.w == pytest.approx(spec.carcass_t)
        assert box.h == pytest.approx(16.0)
        assert box.y0 == pytest.approx(spec.carcass_t + 6.0)
    assert not contains(side, Point(spec.carcass_t + 3.0, spec.carcass_t + 14.0))
    assert contains(side, Point(spec.carcass_t + 3.0, d.cab_d / 2))


def test_the_right_side_is_the_left_one_with_its_slots_mirrored() -> None:
    spec = Spec()
    d = derive(spec)
    build = cabinet(spec)
    left, right = _shape(build, "cabinet-side-left"), _shape(build, "cabinet-side-right")
    assert bbox(left) == pytest.approx(bbox(right))
    assert len(left.inner) == len(right.inner)
    for i in range(spec.drawers):
        here = bbox(_hole(build, f"cabinet-side-left/slot-{i}"))
        there = bbox(_hole(build, f"cabinet-side-right/slot-{i}"))
        assert there.x0 == pytest.approx(d.cab_h - here.x1)
        assert there.x1 == pytest.approx(d.cab_h - here.x0)
        assert (there.y0, there.y1) == pytest.approx((here.y0, here.y1))


def test_a_long_runner_earns_a_third_tab_in_the_middle_and_a_third_slot() -> None:
    short, long = Spec(units_y=2), Spec(units_y=3)
    assert derive(short).runner_len < 100.0 < derive(long).runner_len
    assert len(_shape(cabinet(short), "cabinet-side-left").inner) == 2 * short.drawers
    assert len(_shape(cabinet(long), "cabinet-side-left").inner) == 3 * long.drawers
    build = cabinet(long)
    middle = bbox(_hole(build, "cabinet-side-left/slot-0-1"))
    assert (middle.y0 + middle.y1) / 2 == pytest.approx(
        long.carcass_t + derive(long).runner_len / 2
    )


def test_a_runner_tab_lands_where_the_slot_it_goes_through_is() -> None:
    spec = Spec()
    build = cabinet(spec)
    runner = _shape(build, "runner")
    tabs = tuple(
        e for e in runner.outer.edges if e.label is not None and str(e.label).startswith("bottom")
    )
    assert len(tabs) == 9  # two tabs: four steps each, plus the run between them
    slot = bbox(_hole(build, "cabinet-side-left/slot-0"))
    assert slot.y0 - spec.carcass_t == pytest.approx(6.0)
    assert slot.h == pytest.approx(16.0)


# ---- nesting ---------------------------------------------------------------------------


def test_the_default_cabinet_nests_onto_a_laser_bed_without_complaint() -> None:
    sheets, warnings = nest(_cut_list(cabinet(Spec())), Bed(SHEET, SHEET))
    assert warnings == ()
    assert sheets
    assert sum(len(s.parts) for s in sheets) == 7 * 6 + 5
    assert {s.thickness for s in sheets} == {3.0, 6.0}


def test_a_cabinet_too_tall_for_the_bed_is_warned_about_rather_than_dropped() -> None:
    sheets, warnings = nest(_cut_list(cabinet(Spec(drawers=12))), Bed(SHEET, SHEET))
    assert warnings
    assert all("does not fit" in w for w in warnings)
    assert any("cabinet-side-left" in w for w in warnings)
    assert sheets


# ---- validation ------------------------------------------------------------------------


def test_validate_passes_the_defaults_and_the_spec_a_script_writes_builds_them() -> None:
    validate(Spec())
    assert cabinet(Spec(units_x=4, drawers=6)).quantities == cabinet(Spec()).quantities


@pytest.mark.parametrize(
    ("spec", "parameter"),
    [
        (Spec(units_x=0), "units_x"),
        (Spec(units_y=-1), "units_y"),
        (Spec(height_u=0), "height_u"),
        (Spec(drawers=0), "drawers"),
        (Spec(columns=0), "columns"),
        (Spec(drawer_t=0.0), "drawer_t"),
        (Spec(carcass_t=-6.0), "carcass_t"),
        (Spec(finger=0.0), "finger"),
        (Spec(kerf=-0.1), "kerf"),
        (Spec(drawer_gap=-1.0), "drawer_gap"),
        (Spec(finger=6.0), "finger"),
        (Spec(height_u=1, drawer_t=6.0), "drawer_t"),
        (Spec(carcass_t=20.0, finger=40.0), "carcass_t"),
        (Spec(pull_w=9.0), "pull_w"),
        (Spec(pull_w=400.0), "pull_w"),
        (Spec(pull_margin=40.0), "pull_margin"),
        (Spec(pull_h=25.0), "pull_margin"),
        (Spec(units_y=1, runner_setback=20.0), "runner_setback"),
        (Spec(drawers=2, labels=("one",)), "labels"),
        (Spec(drawers=2, labels=("same", "same")), "labels"),
        (Spec(drawers=1, labels=("a/b",)), "labels"),
        (Spec(drawers=1, labels=("",)), "labels"),
    ],
)
def test_validate_names_the_parameter_that_does_not_work(spec: Spec, parameter: str) -> None:
    with pytest.raises(ValueError, match=parameter):
        validate(spec)
    with pytest.raises(ValueError, match=parameter):
        cabinet(spec)


def test_a_drawer_of_one_unit_is_still_buildable() -> None:
    build = cabinet(Spec(units_x=1, units_y=1, height_u=1, drawers=2, pull_w=20.0))
    assert Ref("drawer-front-2/pull") in index(build.assembly)


# ---- the printed baseplate -------------------------------------------------------------


def test_the_scad_text_says_how_many_units_it_is_and_how_tall() -> None:
    scad = baseplate_scad(4, 2)
    assert "units_x = 4;" in scad
    assert "units_y = 2;" in scad
    assert f"height = {BASEPLATE_T};" in scad
    assert "grid = 42;" in scad
    assert "baseplate();" in scad
    assert baseplate_scad(7, 3).count("units_x = 7;") == 1


def test_the_pocket_is_the_hull_of_the_four_gridfinity_slices() -> None:
    scad = baseplate_scad(1, 1)
    assert "hull()" in scad
    for call in (
        "_slice(36.3, 1.15, 0);",
        "_slice(37.7, 1.85, 0.7);",
        "_slice(37.7, 1.85, 2.5);",
        "_slice(42, 4, 4.65);",
    ):
        assert call in scad, call
    assert scad.count("_slice(") == 5  # the module and its four calls


def test_a_floor_is_only_there_when_it_is_asked_for() -> None:
    assert "floor_t = 0;" in baseplate_scad(2, 2)
    assert "floor_t = 1.2;" in baseplate_scad(2, 2, floor_t=1.2)


def test_the_build_carries_the_scad_file_only_when_the_spec_wants_a_baseplate() -> None:
    assert "units_x = 4;" in cabinet(Spec(units_x=4, baseplate=True)).files["baseplate.scad"]
    assert cabinet(Spec(baseplate=False)).files == {}


def test_baseplate_scad_refuses_nonsense() -> None:
    with pytest.raises(ValueError, match="one unit"):
        baseplate_scad(0, 2)
    with pytest.raises(ValueError, match="one unit"):
        baseplate_scad(2, -1)
    with pytest.raises(ValueError, match="floor_t"):
        baseplate_scad(2, 2, floor_t=-1.0)
