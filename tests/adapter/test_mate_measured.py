"""Adapter: parts put together by a face, measured by the modeller the app ships.

:mod:`mate_cases` is run inside Pyodide by :mod:`tools.stack` with the real kernel: the wall
vent's attachment put on its frame by :func:`bench.mate.mating` and by hand, a mate whose
contact is really an overlap, a mate at a slide fit, and a part mated upside down. The pure
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
