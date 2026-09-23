"""Adapter: parts put together by a face, measured by the modeller the app ships.

:mod:`mate_cases` is run inside Pyodide by :mod:`tools.stack` with the real kernel: the wall
vent's attachment put on its frame by :func:`bench.mate.mating` and by hand, a mate whose
contact is really an overlap, a mate at a slide fit, a part mated upside down, pins put
into bores - one drawn right, one drawn without the concave allowance, one too tight, and a
pin with a head that seats on the plate: in a bore drawn right, in one too tight, driven
into the plate, slid out of its bore altogether, and in a bore :func:`bench.features.hole`
drilled - and a plate mated onto a pocket's floor. The pure
arithmetic of where a mate puts a face is ``tests/unit/test_mate.py``'s; what is asked here
is what only a built body can answer.
"""

from pathlib import Path
from typing import Any

import pytest

from bench import Severity
from bench.scene import OkScene
from tools import stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)

_CASES = Path(__file__).with_name("mate_cases.py")
_VENT = Path(__file__).resolve().parents[2] / "examples" / "wall_vent.py"

PROGRAM = """\
import json

from pyodide.ffi import JsException

import mate_cases
from bench.adapters.browser import JsKernel


def main(js, given):
    return json.dumps(mate_cases.measured(JsKernel(js, JsException), json.loads(given)["vent"]))
"""

_TINY = 1e-3
"""Float noise on a single-precision mesh vertex, in millimetres."""


@pytest.fixture(scope="module")
def measured() -> dict[str, Any]:
    """Every mate this module reads, built and measured once by the shipped kernel."""
    found: dict[str, Any] = stack.run(
        PROGRAM, {"vent": _VENT.read_text()}, modules={"mate_cases.py": _CASES.read_text()}
    )
    return found


def _ok(scene: Any) -> OkScene:
    if not scene["ok"]:
        error = scene["error"]
        pytest.fail(f"line {error['line']}: {error['message']}\n{error['traceback']}")
    ok: OkScene = scene
    return ok


def _lands_on(placed: dict[str, Any]) -> None:
    """Two placements of one body that are the same placement: the same box to float noise,
    the same volume, and all of either one inside the other."""
    mated, by_hand = placed["bounds"]
    assert mated == pytest.approx(by_hand, abs=_TINY)
    one, other = placed["volumes"]
    assert one == pytest.approx(other, rel=1e-9)
    assert placed["shared"] == pytest.approx(one, rel=1e-9)


def test_the_vents_attachment_mated_by_its_back_face_lands_where_the_hand_put_it(
    measured: dict[str, Any],
) -> None:
    """decision-10's acceptance: the attachment's back face on the flange's front face puts
    the attachment exactly where moving it up by the flange's thickness does - same box, same
    volume, and the two share every cubic millimetre of it."""
    _lands_on(measured["vent"]["mated"])


def test_an_attachment_that_wandered_off_is_mated_back_to_the_same_place(
    measured: dict[str, Any],
) -> None:
    """Turned about a skew axis and shifted first, then mated: the mate reads the face's own
    frame, so where the part was does not matter."""
    _lands_on(measured["vent"]["wandered"])


def test_a_mated_contact_that_is_really_an_overlap_lands_on_the_mated_part(
    measured: dict[str, Any],
) -> None:
    """A peg a millimetre proud of the plate's back face is sunk into the base by the mate.
    The call that put it there measured it, found the overlap, and recorded it - naming the
    mated plate first, because the body the mate handed back is the very object the scene's
    plate is made of."""
    scene = _ok(measured["pegged"])
    [found] = scene["violations"]
    assert found["check"] == "contact"
    assert found["severity"] == Severity.ERROR
    assert found["refs"] == ["plate", "base"]
    assert found["line"] == 8
    assert scene["stdout"].startswith("plate/bottom on base/top: overlap, asked contact: ")
    assert "16.000 mm3" in scene["stdout"]


def test_a_slide_mate_stands_its_faces_off_by_the_tables_own_gap(
    measured: dict[str, Any],
) -> None:
    """Measured, not asserted: the modeller finds the two plates exactly the slide apart,
    and the sentence says so beside what was asked."""
    scene = _ok(measured["slid"])
    assert scene["violations"] == []
    said = scene["stdout"].strip()
    assert said == "plate/bottom on base/top: clear by 0.200 mm, asked 0.200 (slide)"


def test_a_part_mated_upside_down_prints_as_it_was_authored(measured: dict[str, Any]) -> None:
    """A ridge that prints on its foot, mated crown down: its way up turned with it, so its
    overhangs measure as they did before it moved - none - and its foot is still what lies on
    the bed. Left with the way up it was authored with, the same moved body would read as
    printed on its crown, and fail."""
    turned = measured["turned"]
    assert turned["up"] == pytest.approx([0.0, 0.0, -1.0])
    assert turned["authored"] is None
    assert turned["carried"] is None
    assert turned["left_behind"] is not None
    assert "63" in turned["left_behind"]
    assert turned["bed"] == ["side-0"]


def test_a_plate_mated_onto_a_pockets_floor_sits_in_the_pocket(measured: dict[str, Any]) -> None:
    """task-65's acceptance: the floor a pocket leaves faces out of the base, so the plate
    laid on it is in the pocket - touching, sharing nothing - where the floor's old frame,
    the tool's own, would have turned it over and sunk it into the base below."""
    scene = _ok(measured["pocketed"])
    assert scene["violations"] == []
    assert scene["stdout"].strip() == "plate/bottom on base/pocket/bottom: touch, asked contact"
    plate = next(view for view in scene["parts"] if view["label"] == "plate")
    assert plate["bbox"] == pytest.approx([0.0, 0.0, 20.0, 10.0])


def test_a_pin_in_a_bore_drawn_with_the_concave_clearance_measures_the_slide_it_asked(
    measured: dict[str, Any],
) -> None:
    """task-60's acceptance: a pin mated into its bore sits on the bore's axis, and the gap
    round it is measured, not assumed. The bore is drawn ``clearance(Fit.SLIDE, PLA,
    concave=True)`` wider than the pin - the table's slide plus the chord sag of a meshed
    concave wall - and the kernel finds the pin clear by more than the slide all round."""
    scene = _ok(measured["pin_concave"])
    assert scene["violations"] == []
    said = scene["stdout"].strip()
    assert said == "pin/side-0 on plate/bore: clear by 0.245 mm, asked 0.200 (slide)"


def test_a_bore_drawn_with_the_bare_slide_measures_short_once_meshed(
    measured: dict[str, Any],
) -> None:
    """What ``concave=`` is for, measured: a bore drawn the plain slide wider than its pin has
    its wall meshed into chords that stand inside the circle, and the pin comes within
    0.196 mm of it. The ask is the table's own figure, so that is a finding."""
    scene = _ok(measured["pin_plain"])
    [found] = scene["violations"]
    assert found["check"] == "fit"
    assert found["severity"] == Severity.ERROR
    assert "0.196 mm" in found["message"]


def test_a_pin_too_fat_for_its_fit_is_a_finding_on_both_parts(measured: dict[str, Any]) -> None:
    """A 2 mm pin in a bore of 1.9: the mate puts it on the axis all the same - it was
    asked to - and the measurement finds the two sharing material, which lands on the pin and
    on the plate, by identity, on the line of the mate."""
    scene = _ok(measured["pin_fat"])
    [found] = scene["violations"]
    assert found["check"] == "fit"
    assert found["severity"] == Severity.ERROR
    assert found["refs"] == ["pin", "plate"]
    assert found["line"] == 9
    assert "within 0.000 mm" in found["message"]


def test_a_pin_whose_head_sits_on_the_plate_is_measured_on_its_shank(
    measured: dict[str, Any],
) -> None:
    """task-66's acceptance, and the rewrite of what task-60 recorded as a limitation - a
    headed pin read its head's zero as the shank's slide and failed. Now the gap round the
    pin is measured over the length the shank and the bore share, so the shank's slide reads
    as the headless pin's does and passes, and the head's seat - a second pair, declared by
    the script with ``check_fit`` at ``CONTACT`` - reads as the touch it is."""
    scene = _ok(measured["pin_headed"])
    assert scene["violations"] == []
    said = scene["stdout"].splitlines()
    assert said == [
        "pin/shank/side-0 on plate/bore: clear by 0.245 mm, asked 0.200 (slide)",
        "touch, asked contact",
    ]


def test_a_headed_pin_too_fat_for_its_fit_still_fails_on_both_parts(
    measured: dict[str, Any],
) -> None:
    """Measuring over the shank does not look past a shank that is too fat: in a bore of 1.9
    it overlaps the bore wall inside the shared length, the mate finds it on the pin and the
    plate on its own line, and the seat's contact check - which asks whether the two share
    material - finds the same overlap on its."""
    scene = _ok(measured["pin_headed_fat"])
    fit, seat = scene["violations"]
    assert (fit["check"], fit["severity"], fit["refs"], fit["line"]) == (
        "fit",
        Severity.ERROR,
        ["pin", "plate"],
        9,
    )
    assert "within 0.000 mm" in fit["message"]
    assert (seat["check"], seat["severity"], seat["refs"], seat["line"]) == (
        "contact",
        Severity.ERROR,
        ["pin", "plate"],
        11,
    )


def test_a_head_driven_into_the_plate_is_found_though_the_shank_clears(
    measured: dict[str, Any],
) -> None:
    """Slid half a millimetre too far, the head sinks into the plate. The shank still clears
    its bore by the slide - the gap round it is right - but a clearance fit round a pin
    shares no material anywhere, so the mate asks the whole bodies that as well and finds the
    head's 17 mm3."""
    scene = _ok(measured["pin_headed_sunk"])
    fit = scene["violations"][0]
    assert (fit["check"], fit["severity"], fit["refs"], fit["line"]) == (
        "fit",
        Severity.ERROR,
        ["pin", "plate"],
        9,
    )
    assert "17.000 mm3" in fit["message"]
    assert scene["stdout"].startswith("pin/shank/side-0 on plate/bore: clear by 0.245 mm")


def test_a_pin_slid_out_of_its_bore_has_no_fit_to_measure(measured: dict[str, Any]) -> None:
    """Slid twenty millimetres down the axis, the shank and the bore share no length at all.
    There is no gap round a pin that is not in its bore, and saying so is a warning, not a
    quiet fall back to the nearest the whole bodies come."""
    scene = _ok(measured["pin_headed_out"])
    fit = scene["violations"][0]
    assert (fit["check"], fit["severity"], fit["line"]) == ("fit", Severity.WARNING, 9)
    assert "share no length" in fit["message"]


def test_a_headed_pin_in_a_drilled_hole_is_measured_where_the_plate_stops_the_bore(
    measured: dict[str, Any],
) -> None:
    """A bore :func:`bench.features.hole` drilled runs a hundredth proud of the plate, and
    the headed pin put in it stands its head that hundredth off the top. How long the bore
    is is read off the mesh, where the plate stops it, so the shank's slide is what is
    measured and not the hundredth under the head."""
    scene = _ok(measured["pin_holed"])
    assert scene["violations"] == []
    said = scene["stdout"].strip()
    assert said == "pin/shank/side-0 on plate/bore/side-0: clear by 0.305 mm, asked 0.200 (slide)"
