"""Unit: :mod:`bench.checks` alone - what a check answers with nothing to measure with.

Four of the five checks need a solid modeller, and this layer has none: what is asserted
here is that they say so, in a record, rather than raising or quietly passing. The fifth
reads the tree's own bounds and is answered in full. The measurements themselves are the
adapter layer's, against a real kernel.
"""

import pytest

from bench import (
    CONTACT,
    Fit,
    Fitted,
    Point,
    Ref,
    Sampled,
    Severity,
    Violation,
    cuboid,
    cut,
    cylinder,
    fill,
    rect,
)
from bench.checks import (
    clearance_between,
    contact_between,
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
