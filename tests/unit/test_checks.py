"""Unit: :mod:`bench.checks` alone - what a check answers with nothing to measure with.

Five of the seven checks need a solid modeller, and this layer has none: what is asserted here
is that they say so, in a record, rather than raising or quietly passing. The other two -
``fits`` and ``exportable`` - read the tree's own bounds and shape, and are answered in full.
The measurements themselves are the adapter layer's, against a real kernel.
"""

import pytest

from bench import (
    CONTACT,
    XY,
    Fit,
    Fitted,
    Point,
    Printed,
    Process,
    Ref,
    RoundPair,
    Sampled,
    Severity,
    Stock,
    Vector,
    Violation,
    Y,
    Z,
    cuboid,
    cut,
    cylinder,
    extrude,
    fill,
    part,
    rect,
    unit,
)
from bench.checks import (
    bed_along,
    clearance_between,
    contact_between,
    exportable,
    fit_between,
    fits,
    overhangs,
    sampling,
    wall,
)
from bench.library.print import H2D, PLA, Orient, Volume

pytestmark = pytest.mark.unit


def test_a_part_inside_the_build_volume_is_no_violation_at_all() -> None:
    """A check that found nothing answers ``None``: a scene's violations are what went
    wrong, not a transcript of what was asked."""
    assert fits(cuboid(200, 100, 50), H2D) is None
    assert fits(fill(rect(300, 300)), H2D) is None


def test_a_part_too_big_for_the_machine_says_which_way_and_by_how_much() -> None:
    found = fits(cuboid(400, 100, 50), H2D)
    assert found is not None
    assert found.check == "fits"
    assert found.severity is Severity.ERROR
    assert "x 400.0 mm against 350.0 mm" in found.message
    assert "y" not in found.message.split(":")[1].split(",")[0]


def test_fits_reads_a_bound_that_is_conservative_under_a_cut() -> None:
    """A hole never makes a part smaller as far as the tree is concerned, so a body that
    only fits once it is drilled is still reported - which is the direction a build-volume
    check has to err in."""
    drilled = cut(cuboid(400, 100, 50), cylinder(20, 50, at=Point(200, 50)), label="bore")
    assert fits(drilled, H2D) is not None


def test_fits_measures_a_standing_part_on_its_print_axes() -> None:
    """task-68: the wall vent's hood, reproduced as a box of its dimensions - 272 x ~120 mm
    footprint, 322 mm tall standing on its outlet, ``Orient(up=Y)``. Drawn, its own Y is the
    322 mm and reads against H2D's 320 mm depth, over by 2.4 mm; given the ``Orient`` it
    prints by, that Y is turned to +Z first and reads against H2D's 325 mm height instead,
    which is the box it actually stands in on the bed."""
    hood = cuboid(272.0, 322.0, 120.0)
    assert fits(hood, H2D) is not None, "drawn, its own y is over H2D's d - the bug this fixes"
    assert fits(hood, H2D, Orient(up=Y)) is None


def test_fits_with_no_orient_measures_the_shape_as_drawn() -> None:
    """A shape with no print orientation - a sheet part, or a solid nobody has yet said
    prints on end - keeps the plain box it always had; ``orient`` defaults to ``None``
    rather than guessing one."""
    box = cuboid(200, 100, 50)
    assert fits(box, H2D, None) == fits(box, H2D)


def test_fits_with_orient_still_names_the_axis_that_overflows() -> None:
    """Laid down first, a part that still does not fit is reported on the box it actually
    stands in, not the one it was drawn in."""
    hood = cuboid(272.0, 322.0, 120.0)
    small = Volume(280.0, 130.0, 300.0)
    found = fits(hood, small, Orient(up=Y))
    assert found is not None
    assert "z 322.0 mm against 300.0 mm" in found.message
    assert found.message.count(" mm against ") == 1


def test_fits_reads_a_printed_parts_own_orient() -> None:
    """decision-11: a ``Part`` already says how it prints, so handing ``fits`` the part
    itself - not its bare ``shape`` and a repeated ``orient`` - is enough. The wall vent's
    hood, this time as the ``Part`` a script would actually show."""
    hood = part("hood", cuboid(272.0, 322.0, 120.0), Printed(PLA, Orient(up=Y)))
    assert fits(hood, H2D) is None


def test_fits_reads_a_sheet_parts_stock_as_no_orient_at_all() -> None:
    """AC#3 on the ``Part`` path: a ``Part`` cut from sheet ``Stock`` has no ``Orient`` to
    read - a sheet has no way up - so it keeps the plain box exactly as a bare shape would,
    even though it is handed as a ``Part`` and not a shape."""
    sheet = part("hood", cuboid(272.0, 322.0, 120.0), Stock(3.0, "ply"))
    assert fits(sheet, H2D) is not None


def test_fits_orient_overrides_a_printed_parts_own() -> None:
    """An explicit ``orient`` is the question a script is actually asking, so it wins over
    whatever a ``Printed`` part's own ``Orient`` already says - asking "would it fit some
    other way up" without having to rebuild the part to find out."""
    hood = part("hood", cuboid(272.0, 322.0, 120.0), Printed(PLA, Orient(up=Y)))
    assert fits(hood, H2D, Orient()) is not None, "drawn (+Z), its own y is over H2D's d"


def test_fits_settles_the_turn_bed_along_leaves_free() -> None:
    """``bed_along`` - the face an ``Orient.bed_face`` names - settles the spin ``up`` alone
    leaves free, exactly as it does for ``export.as_printed`` (task-68's ``bed_along`` is the
    same resolver). A footprint lopsided enough that swapping its two horizontal axes flips
    whether it fits: ``side-front`` keeps the footprint as drawn and misses on X;
    ``side-right`` turns it a quarter and clears both."""
    box = cuboid(300.0, 100.0, 50.0)
    small = Volume(150.0, 350.0, 60.0)
    assert fits(box, small, Orient(up=Z, bed_face=Ref("side-front"))) is not None
    assert fits(box, small, Orient(up=Z, bed_face=Ref("side-right"))) is None


def test_bed_along_reads_the_named_faces_own_x() -> None:
    """:func:`bed_along` is the resolver ``fits`` and ``views._as_printed`` share, read
    straight from :func:`~bench.solids.plane_of`'s own frame for the named face - and
    ``None`` when the ``Orient`` names none, so ``laid_down`` is left the turn it would pick
    on its own."""
    box = cuboid(300.0, 100.0, 50.0)
    assert bed_along(box, Orient(up=Z, bed_face=Ref("side-right"))) == Vector(0.0, 1.0, 0.0)
    assert bed_along(box, Orient()) is None


def test_fits_reads_a_round_face_conservatively_under_an_oblique_up() -> None:
    """No ``Orient`` seen building the wall vent turns a round face off every axis, but
    nothing stops a script from writing one, so this pins the direction the check has to
    err in when it does. A cylinder stood on a corner - ``up=Vector(1, 1, 1)`` - truly
    stands about 27.9 mm tall, over a 25 mm build height: turning the tree and re-bounding
    it would have read about 23.1 mm, under the limit, and falsely passed; turning the drawn
    box's own corners instead reads 34.6 mm - wider than the truth, the safe side of wrong -
    and still calls it a violation. Exact once ``up`` is back on an axis, which every other
    test in this file is."""
    tilted = unit(Vector(1.0, 1.0, 1.0))
    upright = cylinder(10.0, 20.0)
    too_short = Volume(100.0, 100.0, 25.0)
    assert fits(upright, too_short, Orient(up=tilted)) is not None


def test_every_axis_of_the_volume_is_checked() -> None:
    tall = fits(cuboid(10, 10, 400), H2D)
    assert tall is not None and "z 400.0 mm against 325.0 mm" in tall.message
    small = Volume(10.0, 10.0, 10.0)
    all_three = fits(cuboid(20, 20, 20), small)
    assert all_three is not None and all_three.message.count(" mm against ") == 3


def test_a_check_that_needs_a_kernel_answers_unchecked_rather_than_passing() -> None:
    """The distinction the whole module turns on. Without a modeller nothing was measured,
    and "I could not tell" is not "it is fine" - a check that passed here would pass in the
    browser and fail on the desk."""
    a, b = cuboid(10, 10, 10), cuboid(10, 10, 10, at=Point(20, 0, 0))
    answers = (
        clearance_between(a, b, 0.3, kernel=None),
        contact_between(a, b, kernel=None),
        wall(a, 1.2, kernel=None),
        overhangs(a, Orient(), PLA, kernel=None),
    )
    assert [one.severity for one in answers if one is not None] == [Severity.UNCHECKED] * 4
    assert [one.check for one in answers if one is not None] == [
        "clearance",
        "contact",
        "wall",
        "overhangs",
    ]
    for one in answers:
        assert one is not None and "no kernel in this run" in one.message


def test_a_violation_is_a_plain_frozen_record() -> None:
    """Refs and a line, both optional: the line is filled in at the edge by the closure
    :mod:`bench.script` injects, because only the edge knows whose stack it is."""
    one = Violation(check="wall", message="too thin", severity=Severity.ERROR)
    assert (one.refs, one.line) == ((), None)
    assert one == Violation(check="wall", message="too thin", severity=Severity.ERROR)
    assert len({one, one}) == 1
    named = Violation("wall", "too thin", Severity.ERROR, (Ref("lid/top"),), 12)
    assert named.refs == (Ref("lid/top"),) and named.line == 12


# ---- a motion is poses, and says so ------------------------------------------------------


def test_a_motion_is_sampled_at_both_ends_and_evenly_between_them() -> None:
    """Both ends are in on purpose: the closed and open poses of a mechanism are the two
    somebody has already thought about, and a sampling that left one out would be measuring
    where nobody asked instead of where they did. The last value is the end itself rather
    than the end plus whatever the arithmetic drifted by."""
    assert sampling((0.0, 1.0), 5) == (0.0, 0.25, 0.5, 0.75, 1.0)
    assert sampling((0.0, 1.0), 2) == (0.0, 1.0)
    assert sampling((10.0, 20.0), 3) == (10.0, 15.0, 20.0)


def test_a_motion_of_one_pose_or_no_width_is_refused() -> None:
    """One pose is a picture. A range with no width samples the same pose over and over and
    calls it a travel - both are answers that would read as a pass for something nothing
    measured."""
    with pytest.raises(ValueError, match="at least twice, not 1"):
        sampling((0.0, 1.0), 1)
    with pytest.raises(ValueError, match=r"1\.0 to 0\.0 does not"):
        sampling((1.0, 0.0), 5)


def test_what_a_sampled_motion_says_is_never_stronger_than_what_it_did() -> None:
    """The record exists for this sentence. It names the number of poses and the spacing,
    says in as many words that it sampled rather than swept, and says what it is not about -
    where a maker reads it, not only in a docstring a maker never opens."""
    said = str(
        Sampled(least=0.2, over=(0.0, 1.0), samples=21, spacing=0.05, findings=(), measured=True)
    )
    assert "sampled at 21 poses from 0.000 to 1.000, one every 0.0500" in said
    assert "Sampled, not swept" in said
    assert "force, friction or binding" in said
    assert "throughout" not in said


def test_a_motion_nothing_could_measure_says_that_and_not_how_it_sampled() -> None:
    """No kernel, no poses built, no spacing to quote: claiming one would be claiming the
    work was done. It says it was not measured, in the same words every other check uses."""
    said = str(
        Sampled(least=0.2, over=(0.0, 1.0), samples=21, spacing=0.0, findings=(), measured=False)
    )
    assert said == (
        "the motion was not measured: there is no kernel in this run, so nothing measured it"
    )


# ---- exportable: what a shape, its stock and its process can actually be cut from -----


def test_a_face_on_sheet_stock_is_exportable_whatever_its_process() -> None:
    """The ordinary laser case, and the point of the whole check: nothing here refuses a
    part that was always fine."""
    face = fill(rect(50, 50))
    assert exportable(face, Stock(3.0, "ply"), Process.LASER) is None
    assert exportable(face, Stock(3.0, "ply"), Process.CNC) is None


def test_a_solid_on_sheet_stock_is_refused_naming_what_a_sheet_part_is() -> None:
    """A sheet part is cut from a flat Face; a solid was never one, whatever it is marked."""
    solid = extrude(fill(rect(50, 50)), 10)
    found = exportable(solid, Stock(19.05, "ply"), Process.LASER)
    assert found is not None
    assert found.check == "exportable"
    assert found.severity is Severity.ERROR
    assert "Face" in found.message
    assert "Printed" in found.message


def test_a_solid_marked_cnc_is_refused_saying_milling_is_not_modelled() -> None:
    """The bug report's own case: ``Process.CNC`` over a solid asks to mill a billet, and
    nothing here builds one yet - whatever the stock is."""
    solid = extrude(fill(rect(50, 50)), 10)
    on_sheet = exportable(solid, Stock(19.05, "ply"), Process.CNC)
    on_filament = exportable(solid, Printed(PLA), Process.CNC)
    for found in (on_sheet, on_filament):
        assert found is not None
        assert found.severity is Severity.ERROR
        assert "milling is not modelled yet" in found.message


def test_a_solid_on_printed_stock_is_exportable_unless_marked_cnc() -> None:
    """The ordinary printed case: a body on filament, built by a kernel rather than cut -
    :func:`exportable` has nothing to say about it."""
    solid = extrude(fill(rect(50, 50)), 10)
    assert exportable(solid, Printed(PLA), Process.PRINT) is None


# ---- a pair put together at a fit --------------------------------------------------------


def test_a_fit_with_no_kernel_is_unchecked_and_says_what_it_asked() -> None:
    """The answer still says what was asked, so a browser before the modeller has loaded
    reads the fit the script meant even though nothing measured it."""
    fitted = fit_between(cuboid(10, 10, 10), cuboid(10, 10, 10), Fit.SLIDE, 0.2, kernel=None)
    assert fitted.gap is None
    assert fitted.finding is not None
    assert fitted.finding.severity is Severity.UNCHECKED
    assert str(fitted).startswith("asked 0.200 (slide), not measured:")
    assert str(fit_between(cuboid(1, 1, 1), cuboid(1, 1, 1), CONTACT, 0.0, kernel=None)).startswith(
        "asked contact, not measured:"
    )


def test_a_round_fit_with_no_kernel_is_unchecked_before_anything_is_meshed() -> None:
    """The gap round a pin is read off the mesh of its faces, and with no kernel there is no
    mesh: the answer is the same ``UNCHECKED`` a flat fit's is, not a failure to find the
    faces."""
    pair = RoundPair(XY, (Ref("side-0"), Ref("bore")))
    fitted = fit_between(
        cylinder(2.0, 12.0), cuboid(10, 10, 10), Fit.SLIDE, 0.2, kernel=None, pair=pair
    )
    assert fitted.gap is None
    assert fitted.finding is not None
    assert fitted.finding.severity is Severity.UNCHECKED


def test_a_fit_says_what_it_measured_against_what_it_asked() -> None:
    """The sentence a maker reads, pass or fail: the measured gap beside the asked one."""
    assert str(Fitted(Fit.SLIDE, 0.2, 0.2, None)) == "clear by 0.200 mm, asked 0.200 (slide)"
    assert str(Fitted(Fit.SLIDE, 0.2, 1.2, None)) == (
        "clear by more than 1.200 mm, asked 0.200 (slide)"
    )
    tight = Violation("fit", "too close", Severity.ERROR)
    assert str(Fitted(Fit.SLIDE, 0.2, 0.15, tight)) == (
        "clear by 0.150 mm, asked 0.200 (slide): too close"
    )


def test_a_contact_says_whether_it_touched_overlapped_or_never_met() -> None:
    overlap = Violation("contact", "shares material", Severity.ERROR)
    apart = Violation("fit", "stands apart", Severity.WARNING)
    assert str(Fitted(CONTACT, 0.0, 0.0, None)) == "touch, asked contact"
    assert str(Fitted(CONTACT, 0.0, 0.0, overlap)) == "overlap, asked contact: shares material"
    assert str(Fitted(CONTACT, 0.0, 3.0, apart)) == (
        "stand 3.000 mm apart, asked contact: stands apart"
    )
