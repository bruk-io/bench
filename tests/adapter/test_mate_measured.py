"""Adapter: parts put together by a face, measured by the modeller the app ships.

:mod:`mate_cases` is run inside Pyodide by :mod:`tools.stack` with the real kernel: the wall
vent's attachment put on its frame by :func:`bench.mate.mating` and by hand, a mate whose
contact is really an overlap, a mate at a slide fit, a part mated upside down, and pins put
into bores - one drawn right, one drawn without the concave allowance, one too tight, and one
with a head that seats. The pure
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


def test_a_pin_whose_head_sits_on_the_plate_reads_the_heads_zero(
    measured: dict[str, Any],
) -> None:
    """Whole bodies, as every check here measures: a headed pin whose head seats on the
    plate comes within nothing of it there, so its shank's slide reads as tight however right
    the bore is. A shoulder is a second pair, and this pins down that the round mate does not
    see past it - the gap round the shank alone is not what is measured."""
    scene = _ok(measured["pin_headed"])
    [found] = scene["violations"]
    assert found["refs"] == ["pin", "plate"]
    assert scene["stdout"].startswith("pin/shank/side-0 on plate/bore: clear by 0.000 mm")
