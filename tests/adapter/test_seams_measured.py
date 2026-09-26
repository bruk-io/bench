"""Adapter: pieces put together the obvious way, measured by the modeller the app ships.

task-77 found four ways of building a hollow part out of pieces that left the overhang and
wall checks reading something nobody drew, every one of them measured on this kernel before
it was fixed (the numbers in each test's text are those readings):

* **Pieces hollowed one by one and set end to end** - a collar, a loft and a spigot, each
  :func:`~bench.shell.shell`-ed and unioned. The spigot's underside stayed in the part as a
  ceiling leaning 90 degrees, and the loft's rim as a 0.17 mm wall.
* **A loft stood on a plate**, face to face, unioned - the vent's funnel on its base. The
  loft's whole underside stayed in the part as a ceiling leaning 90 degrees.
* **A shelled elbow open at a leaning end.** Slivers a hair wide at the far end, read as a
  0.32 mm wall and a face leaning 60 degrees - on a straight end and on a bend alike.
* **A tap drilled straight into a run of its own size.** Its flat end is tangent to the
  run's side, and the lip that tangency leaves read as a face leaning ``90 - TAP`` degrees.

The first two were the modeller's own bridge rounding a body onto 32-bit floats in one place
and not another, so two faces drawn on the same numbers landed micrometres apart and a union
kept both; the third was the shell laying a ring of its cavity on the leaning end's own plane;
the fourth is facets, and the overhang check now leaves out a patch narrower than
:data:`~bench.topology.CHORD`. Beside them, a real overhang and a real thin wall, which the
checks still find.
"""

import math
from pathlib import Path
from typing import Any

import pytest

from bench.library.print import ASA
from bench.topology import CHORD
from tests.adapter.seam_cases import TAP
from tools import stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)

_CASES = Path(__file__).with_name("seam_cases.py")

PROGRAM = """\
import json

from pyodide.ffi import JsException

import seam_cases
from bench.adapters.browser import JsKernel


def main(js, given):
    return json.dumps(seam_cases.measured(JsKernel(js, JsException)))
"""

_TINY = 1e-3
"""Millimetres: float noise on a single-precision mesh vertex at these sizes."""


@pytest.fixture(scope="module")
def measured() -> dict[str, Any]:
    """Every join this module reads, built and measured once by the shipped kernel."""
    found: dict[str, Any] = stack.run(PROGRAM, {}, modules={"seam_cases.py": _CASES.read_text()})
    return found


def _found(measured: dict[str, Any], body: str, plastic: str) -> dict[str, Any]:
    one: dict[str, Any] = measured["bodies"][body][plastic]
    return one


# ---- the four joins read nothing that is not there ----------------------------------------


@pytest.mark.parametrize("body", ["stacked", "on_a_plate"])
def test_pieces_set_face_to_face_and_unioned_are_one_body(
    measured: dict[str, Any], body: str
) -> None:
    """Before: the stacked boot read ``a face leans 90 degrees`` on the spigot's ``bottom``
    and a 0.17 mm wall; the plate read 90 degrees on the loft's underside. Both are drawn to
    lean PLA's 45 degrees at most, so that is the plastic they are read in."""
    found = _found(measured, body, "PLA")
    assert found["overhangs"] is None, found["overhangs"]
    assert found["wall"] is None, found["wall"]


@pytest.mark.parametrize("plastic", ["PLA", "ASA"])
@pytest.mark.parametrize("body", ["elbow_on_a_straight", "elbow_on_the_bend"])
def test_a_shelled_elbow_open_at_a_leaning_end_has_no_slivers_there(
    measured: dict[str, Any], body: str, plastic: str
) -> None:
    """Turned ``TAP`` degrees - ASA's limit - so nothing real leans past either plastic.
    Before: a 0.32 mm wall and a face leaning 60 degrees at the far end, in both."""
    found = _found(measured, body, plastic)
    assert found["overhangs"] is None, found["overhangs"]
    assert found["wall"] is None, found["wall"]


@pytest.mark.parametrize("plastic", ["PLA", "ASA"])
def test_a_tap_drilled_straight_into_its_own_size_has_no_false_overhang(
    measured: dict[str, Any], plastic: str
) -> None:
    """Before: ``a face leans 50 degrees`` on ``tap/start``, in both plastics."""
    found = _found(measured, "tap", plastic)
    assert found["overhangs"] is None, found["overhangs"]
    assert found["wall"] is None, found["wall"]


def test_the_taps_lip_is_there_and_no_wider_than_the_chords(measured: dict[str, Any]) -> None:
    """What the overhang check now leaves out is really in the mesh, and is only facets: the
    tap's start does lean ``90 - TAP`` degrees past ASA's limit, and every corner of that
    lip stands within a chord's sag of the run's own circle - the run's chords sit up to
    ``CHORD`` inside it, and the tap's circle, the same size, pokes through them."""
    lip = measured["lip"]
    assert lip["leans"], "the tap left no lip to leave out"
    assert all(one == pytest.approx(90.0 - TAP, abs=0.1) for one in lip["leans"])
    assert all(one > math.degrees(ASA.max_overhang) for one in lip["leans"])
    radius = lip["radius"]
    assert all(radius - CHORD <= one <= radius + _TINY for one in lip["reach"])


# ---- and what is there is still found -------------------------------------------------------


@pytest.mark.parametrize("plastic", ["PLA", "ASA"])
def test_an_elbow_turned_past_the_plastic_still_overhangs(
    measured: dict[str, Any], plastic: str
) -> None:
    """The same shelled elbow turned 60 degrees: the inside of its bend leans 60, and that is
    found, on the elbow's own faces."""
    message, refs = _found(measured, "elbow_too_far", plastic)["overhangs"]
    assert "leans 60 degrees" in message
    assert refs


@pytest.mark.parametrize("plastic", ["PLA", "ASA"])
def test_a_ledge_four_tenths_wide_still_overhangs(measured: dict[str, Any], plastic: str) -> None:
    """A real ledge 0.4 mm across, eight chords' sag wide, leaning 60 degrees: found."""
    message, _ = _found(measured, "ledge", plastic)["overhangs"]
    assert "leans 60 degrees" in message


@pytest.mark.parametrize("plastic", ["PLA", "ASA"])
def test_a_shelled_elbow_under_the_plastics_wall_is_still_thin(
    measured: dict[str, Any], plastic: str
) -> None:
    """Shelled at 0.5 mm, under PLA's minimum and ASA's: the wall check says so, and reads
    the wall itself - 0.5 mm less at most the sag of the outer chords, which cut inside it."""
    thin = _found(measured, "thin_elbow", plastic)["wall"]
    assert thin is not None
    through = float(thin.split("wall is ")[1].split(" mm")[0])
    assert 0.5 - CHORD - 0.01 <= through <= 0.5
