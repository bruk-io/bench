"""Functional: the printed Gridfinity bin, through the public API and with no kernel.

What the tree can answer on its own is what is asserted here - the footprint, the four
meanings of height, what every feature is called, and which parameter :func:`validate`
names when a bin will not print. The measurements that need a modeller - that it stacks,
what it weighs - are the adapter layer's.
"""

import math

import pytest

from bench import Magnet, Printed, Process, Ref, Solid, bounds, part, refs
from bench.fasteners import Fit
from bench.library import gridfinity3d as g3
from bench.library.print import ASA, PLA, clearance

pytestmark = pytest.mark.functional


def _body(spec: g3.Spec) -> Solid:
    """The one body the build hands back."""
    shape = g3.bin_(spec).assembly.parts[0].part.shape
    assert isinstance(shape, Solid)
    return shape


# ---- the standard's own numbers --------------------------------------------------------


def test_the_footprint_is_the_grid_less_the_standards_own_gap() -> None:
    """42 mm a unit, 41.5 mm of bin: a quarter of a millimetre a side, which is what lets a
    2 x 1 bin drop into two pockets of a baseplate."""
    box = bounds(_body(g3.Spec(units_x=2, units_y=1)))
    assert (box.x1 - box.x0, box.y1 - box.y0) == pytest.approx((83.5, 41.5))
    wide = bounds(_body(g3.Spec(units_x=4, units_y=3)))
    assert (wide.x1 - wide.x0, wide.y1 - wide.y0) == pytest.approx((4 * 42 - 0.5, 3 * 42 - 0.5))


def test_the_base_profile_is_the_review_table_and_the_lip_is_it_plus_the_fit() -> None:
    assert g3.BASE_PROFILE == ((0.0, 0.0), (0.8, 0.8), (0.8, 2.6), (2.95, 4.75))
    assert g3.BASE_PROFILE[-1][1] == pytest.approx(g3.BASE_HEIGHT)
    assert pytest.approx(0.5) == g3.GRID - g3.BASE_TOP
    spec = g3.Spec()
    dims = g3.derive(spec)
    assert dims.stack == clearance(spec.fit, spec.material)
    # the lip is the base profile with the fit round it, so it is that much shallower
    assert dims.total - dims.height == pytest.approx(g3.BASE_HEIGHT - dims.stack)


def test_a_tighter_fit_makes_a_deeper_lip_and_a_different_plastic_a_different_one() -> None:
    snug = g3.derive(g3.Spec(fit=Fit.SNUG))
    loose = g3.derive(g3.Spec(fit=Fit.LOOSE))
    assert snug.total - snug.height > loose.total - loose.height
    asa = g3.derive(g3.Spec(material=ASA))
    assert asa.stack == clearance(Fit.CLEARANCE, ASA)


# ---- the four meanings of height --------------------------------------------------------


def test_height_means_four_things_and_each_one_lands_where_it_says() -> None:
    lip = g3.BASE_HEIGHT - clearance(Fit.CLEARANCE, PLA)
    units = g3.derive(g3.Spec(height=g3.Units(3)))
    assert units.height == pytest.approx(21.0)
    assert units.total == pytest.approx(21.0 + lip)
    external = g3.derive(g3.Spec(height=g3.External(40.0)))
    assert external.height == pytest.approx(40.0)
    with_lip = g3.derive(g3.Spec(height=g3.ExternalWithLip(40.0)))
    assert with_lip.total == pytest.approx(40.0)
    internal = g3.derive(g3.Spec(height=g3.Internal(30.0)))
    assert internal.height - internal.floor_z == pytest.approx(30.0)


def test_a_bin_with_no_lip_is_as_tall_as_it_says_it_is() -> None:
    flat = g3.derive(g3.Spec(lip=False, height=g3.ExternalWithLip(40.0)))
    assert flat.height == pytest.approx(40.0) and flat.total == pytest.approx(40.0)
    box = bounds(_body(g3.Spec(lip=False)))
    assert box.z1 - box.z0 == pytest.approx(21.0)


# ---- what everything is called ----------------------------------------------------------


def test_every_feature_is_named_as_it_enters_the_tree() -> None:
    spec = g3.Spec(
        units_x=2, units_y=1, divisions=(2, 1), scoop=0.5, label_tab=g3.Tab.FULL, magnets=True
    )
    found = set(refs(g3.bin_(spec).assembly))
    for ref in (
        "bin/foot-1",
        "bin/foot-2",
        "bin/lip",
        "bin/lip/void",
        "bin/compartment-1",
        "bin/compartment-2",
        "bin/scoop-1",
        "bin/tab-2",
        "bin/magnet-1",
        "bin/magnet-8",
        "bin/ribs-1/rib-8",
        "bin/bridge-1/step-3",
    ):
        assert Ref(ref) in found, ref


def test_a_bin_is_one_printed_part_and_one_of_it() -> None:
    build = g3.bin_(g3.Spec())
    one = build.assembly.parts[0].part
    assert one.label == "bin"
    assert one.process is Process.PRINT
    assert isinstance(one.stock, Printed)
    assert build.quantities == {Ref("bin"): 1}
    assert build.files == {}


def test_the_part_builds_again_from_the_shape_it_handed_back() -> None:
    """Every ref unique is not a promise the library makes and then keeps by accident:
    ``part()`` is what enforces it, so building one from the same shape must not raise."""
    shape = _body(g3.Spec(units_x=2, units_y=2, divisions=(2, 2), scoop=1.0, label_tab=g3.Tab.LEFT))
    assert part("again", shape, Printed(PLA)).label == "again"


# ---- validation -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "parameter"),
    [
        (g3.Spec(units_x=0), "units_x"),
        (g3.Spec(units_y=-1), "units_y"),
        (g3.Spec(wall=0.0), "wall"),
        (g3.Spec(wall=0.5), "wall"),
        (g3.Spec(floor=0.0), "floor"),
        (g3.Spec(scoop=1.5), "scoop"),
        (g3.Spec(tab_angle=0.0), "tab_angle"),
        (g3.Spec(tab_angle=math.pi), "tab_angle"),
        (g3.Spec(divisions=(0, 1)), "divisions"),
        (g3.Spec(divisions=(30, 1)), "divisions"),
        (g3.Spec(height=g3.Units(0)), "height"),
        (g3.Spec(height=g3.Internal(-5.0)), "height"),
        (g3.Spec(tab_width=200.0, label_tab=g3.Tab.LEFT), "tab_width"),
        (
            g3.Spec(magnets=True, magnet=Magnet(d=6.0, h=4.6, hole=6.5, ribs=8, rib_d=5.9)),
            "magnets",
        ),
    ],
)
def test_validate_names_the_parameter_that_will_not_print(spec: g3.Spec, parameter: str) -> None:
    with pytest.raises(ValueError, match=parameter):
        g3.validate(spec)


def test_a_bin_that_validates_builds() -> None:
    for spec in (
        g3.Spec(),
        g3.Spec(units_x=1, units_y=1, height=g3.Units(1), lip=False),
        g3.Spec(divisions=(3, 2), scoop=1.0, label_tab=g3.Tab.CENTRE, tab_width=20.0),
        g3.Spec(magnets=True, screws=True, material=ASA, fit=Fit.SNUG),
    ):
        g3.validate(spec)
        assert bounds(_body(spec)).z1 > 0.0
