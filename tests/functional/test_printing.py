"""Functional: how a printed part prints, as the scene says it - task-89's facts for the view's
*On bed* and the inspector's "How it is made".

These run real scripts with no kernel, so no body is built and no part is laid anywhere: what
is asked is everything a run knows *without* one - which way each printed part is up, the face
it stands on, whether it fits the bed and which bed that is, and that a part that is not
printed says nothing about printing. Where a built body lands on the bed, and the areas of its
faces, are ``tests/adapter/test_on_bed.py``'s.
"""

import pytest

from bench import Printer, Volume, run
from bench.library.print import H2D, PRINTER
from bench.scene import OkScene, Scene

pytestmark = pytest.mark.functional

PAIR = """\
from bench import *
from bench.library.print import PLA

plate = part("plate", fill(rect(60, 40)), Stock(3, "ply"))
block = part("block", cuboid(20, 20, 5), Printed(PLA, Orient(up=-Z, bed_face="top")))
show((plate, block))
"""
"""A laser part and a printed one, stood on its top: nothing names a printer."""

BEAM = """\
from bench import *
from bench.library.print import H2D, PLA

beam = part("beam", cuboid(400, 20, 10), Printed(PLA))
{check}
show(beam)
"""
"""A printed part too long for the H2D, with a line for a ``check_fits`` to go in."""


def _ok(scene: Scene) -> OkScene:
    if not scene["ok"]:
        pytest.fail(f"{scene['error']['message']}\n{scene['error']['traceback']}")
    return scene


def test_a_printed_part_says_which_way_is_up_and_the_face_it_stands_on() -> None:
    """AC#6: the orientation is the part's own ``Orient``, its face under the part's label."""
    block = _ok(run(PAIR, printer=PRINTER))["parts"][1]
    assert block["printing"] is not None
    assert block["printing"]["up"] == [0.0, 0.0, -1.0]
    assert block["printing"]["bed_face"] == "block/top"


def test_a_part_that_is_not_printed_says_nothing_about_printing() -> None:
    plate = _ok(run(PAIR, printer=PRINTER))["parts"][0]
    assert plate["printing"] is None


def test_without_a_kernel_nothing_is_laid_but_the_fit_is_still_answered() -> None:
    """``check_fits`` needs no kernel, and neither does the fit the view marks: it is the same
    question of the same tree. Only the placement waits for a body to lay."""
    printing = _ok(run(PAIR, printer=PRINTER))["parts"][1]["printing"]
    assert printing is not None
    assert (printing["fits"], printing["over"], printing["placement"]) == (True, None, None)


def test_the_hosts_printer_is_the_bed_when_the_script_names_none() -> None:
    bed = _ok(run(PAIR, printer=PRINTER))["bed"]
    assert bed is not None
    assert (bed["printer"], bed["said"], bed["volume"]) == ("H2D", "host", [350.0, 320.0, 325.0])
    assert bed["floor"][:6] == [0.0, 0.0, 0.0, 0.0, 320.0, 0.0]


def test_no_printer_from_anybody_is_no_bed_and_no_fit_asked() -> None:
    """A host that names no printer - a test, ``tools.build`` - and a script that asks
    ``check_fits`` nothing: there is no bed to draw and no volume to fit, and ``fits`` says
    ``None`` rather than a fit nothing measured."""
    scene = _ok(run(PAIR))
    assert scene["bed"] is None
    printing = scene["parts"][1]["printing"]
    assert printing is not None
    assert (printing["fits"], printing["placement"]) == (None, None)


def test_the_view_marks_the_fit_check_fits_answers() -> None:
    """The beam is 400 mm and the H2D 350: the view's mark and the check's finding say the
    same thing in the same words, because the one rule answers both."""
    scene = _ok(run(BEAM.format(check="check_fits(beam, H2D)"), printer=PRINTER))
    printing = scene["parts"][0]["printing"]
    assert printing is not None
    assert printing["fits"] is False
    [found] = [one for one in scene["violations"] if one["check"] == "fits"]
    assert printing["over"] == found["message"]


def test_the_volume_a_script_checks_against_is_the_bed_it_is_laid_on() -> None:
    """A 500 mm machine the host has never heard of: the beam fits it, the bed is that one and
    is named by its size, and the host's own H2D is not asked at all."""
    big = "check_fits(beam, Volume(500, 500, 500))"
    scene = _ok(run(BEAM.format(check=big), printer=PRINTER))
    bed = scene["bed"]
    assert bed is not None
    assert (bed["printer"], bed["said"]) == ("500 x 500 x 500 mm", "script")
    printing = scene["parts"][0]["printing"]
    assert printing is not None
    assert printing["fits"] is True


def test_the_first_volume_a_script_asks_about_is_the_one() -> None:
    twice = "check_fits(beam, H2D)\ncheck_fits(beam, Volume(500, 500, 500))"
    bed = _ok(run(BEAM.format(check=twice), printer=Printer("H2D", H2D)))["bed"]
    assert bed is not None
    assert (bed["printer"], bed["said"]) == ("H2D", "script")


def test_a_script_naming_a_volume_is_laid_on_it_with_no_host_printer_at_all() -> None:
    scene = _ok(run(BEAM.format(check="check_fits(beam, Volume(500, 400, 300))")))
    bed = scene["bed"]
    assert bed is not None
    assert bed["volume"] == [500.0, 400.0, 300.0]
    assert Volume(*bed["volume"]) == Volume(500, 400, 300)
