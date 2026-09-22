"""Unit: :mod:`bench.library.print` alone - the filament profiles and the fit table.

Data, read back. The point of these checks is that the numbers are the review's and that
they hold their shape against each other: every material answers every fit, the gaps widen
in the order the enum names them, and PETG and ASA are looser than PLA wherever the review
says they are.
"""

import math

import pytest

from bench.fasteners import Fit
from bench.library.print import ASA, BEDS, H2D, MATERIALS, PETG, PLA, Volume, clearance
from bench.topology import CHORD

pytestmark = pytest.mark.unit


def test_the_fit_table_is_the_reviews_own_numbers() -> None:
    """Per side, 0.4 mm nozzle, 0.2 mm layer, calibrated flow - the whole table, written
    out, because this is the one place these numbers exist."""
    assert [[clearance(fit, m) for fit in Fit] for m in (PLA, PETG, ASA)] == [
        [-0.05, 0.05, 0.10, 0.20, 0.30, 0.50],
        [-0.05, 0.05, 0.125, 0.25, 0.35, 0.55],
        [0.00, 0.075, 0.15, 0.30, 0.40, 0.60],
    ]


def test_every_material_answers_every_fit_and_widens_with_it() -> None:
    """The drift guard on this side: a :class:`~bench.fasteners.Fit` added without a row in
    the table fails here, and a table typed out of order fails here too."""
    for material in MATERIALS:
        gaps = [clearance(fit, material) for fit in Fit]
        assert len(gaps) == len(Fit)
        assert gaps == sorted(gaps), f"{material.name} does not loosen with the fit"


def test_an_interference_fit_is_the_one_gap_that_is_not_a_gap() -> None:
    """A crush-rib magnet pocket is a hole *smaller* than the thing in it, which is why the
    table is signed and why a check for a positive number would be wrong."""
    assert clearance(Fit.INTERFERENCE, PLA) < 0.0
    assert clearance(Fit.INTERFERENCE, ASA) == pytest.approx(0.0)


def test_the_stiffer_the_plastic_the_wider_the_gap_it_needs() -> None:
    for fit in Fit:
        assert clearance(fit, PLA) <= clearance(fit, PETG) <= clearance(fit, ASA)


def test_a_concave_fit_folds_in_the_chord_sag_and_nothing_else_gets_it() -> None:
    """A concave arc's mesh bulges into the gap by up to `CHORD`, so `concave=True` adds
    exactly that - the existing tolerance, not a new one - and the default is untouched."""
    for material in MATERIALS:
        for fit in Fit:
            assert clearance(fit, material, concave=True) == pytest.approx(
                clearance(fit, material) + CHORD
            )
    assert clearance(Fit.SLIDE, PLA) == pytest.approx(0.20)


def test_the_material_profiles_carry_the_reviews_other_numbers() -> None:
    assert (PLA.hole_compensation, PETG.hole_compensation, ASA.hole_compensation) == (
        0.20,
        0.25,
        0.30,
    )
    assert (PLA.foot, PETG.foot, ASA.foot) == (0.15, 0.20, 0.25)
    assert (PLA.shrink, PETG.shrink, ASA.shrink) == (0.003, 0.004, 0.007)
    assert (PLA.min_wall, PETG.min_wall, ASA.min_wall) == (0.86, 0.86, 1.2)
    assert (PLA.bridge_max, PETG.bridge_max, ASA.bridge_max) == (10.0, 8.0, 6.0)
    assert all(m.layer == pytest.approx(0.2) for m in MATERIALS)


def test_an_overhang_limit_is_an_angle_in_radians() -> None:
    """Radians, like every other angle in the package, and off the build direction: 45
    degrees for PLA and PETG, 40 for ASA."""
    assert PLA.max_overhang == pytest.approx(math.radians(45.0))
    assert PETG.max_overhang == pytest.approx(math.radians(45.0))
    assert ASA.max_overhang == pytest.approx(math.radians(40.0))


def test_the_build_volume_is_the_machine_in_the_room() -> None:
    assert Volume(350.0, 320.0, 325.0) == H2D
    assert BEDS["h2d"] == H2D
    assert BEDS["p1s"] == BEDS["a1"] == Volume(256.0, 256.0, 256.0)


def test_the_print_domain_reads_from_one_module() -> None:
    """The vocabulary a printed part needs is importable from here whichever layer it
    actually lives in - the records from ``model``, the geometry from ``ops``."""
    from bench.library import print as print_domain

    for name in print_domain.__all__:
        assert hasattr(print_domain, name), name
