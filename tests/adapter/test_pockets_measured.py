"""Adapter: blind pockets whose end faces down as they print, built by the modeller the app ships.

task-82, from the vent: the adapter's 12.5 mm magnet pockets open downward as it prints, so a
flat pocket end is a 12.5 mm ceiling - past PLA's longest bridge, and a face leaning 90
degrees to the overhang check. :func:`~bench.features.hole` now ends such a pocket in a cone
at the material's ``max_overhang`` by itself, reading ``printed=`` the way ``Top`` does for a
bore lying on its side. What only a built body can say:

* **No overhang past the limit** - the whole block reads clean, and the cone's own
  triangles lean no further than PLA's 45 degrees, upright or on an axis leaning 20.
* **The seat is where it was asked** - the pocket's full diameter reaches exactly the depth
  asked for, and the cone starts there, so whatever sits in the pocket seats at that depth
  on the ring where the cone begins.
* **The check is live, and nothing else changed** - the same pocket kept flat still reads
  its 90 degree ceiling, and a pocket opening upward keeps its flat floor.
"""

import math
from pathlib import Path
from typing import Any

import pytest

from bench.library.print import PLA
from bench.topology import CHORD
from tests.adapter.pocket_cases import LEAN, MAGNET, PRINTED
from tools import stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)

_CASES = Path(__file__).with_name("pocket_cases.py")

PROGRAM = """\
import json

from pyodide.ffi import JsException

import pocket_cases
from bench.adapters.browser import JsKernel


def main(js, given):
    return json.dumps(pocket_cases.measured(JsKernel(js, JsException)))
"""

_TINY = 1e-3
"""Millimetres: float noise on a single-precision mesh vertex at these sizes."""

_LIMIT = math.degrees(PLA.max_overhang) + 0.01
"""PLA's limit in degrees, with the check's own hundredth of a degree of slack."""

_RADIUS = (MAGNET[0] + PLA.hole_compensation) / 2
"""The radius the pocket is cut at: the magnet's, plus what the plastic takes back."""


@pytest.fixture(scope="module")
def measured() -> dict[str, Any]:
    """Every pocket this module reads, built and measured once by the shipped kernel."""
    found: dict[str, Any] = stack.run(PROGRAM, {}, modules={"pocket_cases.py": _CASES.read_text()})
    return found


def _face(measured: dict[str, Any], body: str, ref: str) -> dict[str, list[float]]:
    one: dict[str, list[float]] = measured[body]["faces"][ref]
    return one


def test_a_pocket_opening_downward_ends_in_a_cone_and_reads_no_overhang(
    measured: dict[str, Any],
) -> None:
    """Before: the flat end is ``magnet/top``, a ceiling leaning 90 degrees. Now the block
    reads clean, and the cone's own triangles lean the limit at most."""
    assert measured["down"]["overhangs"] is None, measured["down"]["overhangs"]
    assert "magnet/top" not in measured["down"]["faces"], "no flat end is left"
    cone = _face(measured, "down", "magnet/side-cone")
    assert max(cone["leans"]) <= _LIMIT
    assert max(cone["leans"]) > _LIMIT - 1.0, "and leans the limit, not some safer angle"


def test_the_pocket_keeps_its_diameter_to_the_depth_asked_and_the_cone_starts_there(
    measured: dict[str, Any],
) -> None:
    """The seat: the side runs at the full radius from the mouth to exactly ``depth``, and
    the cone begins at ``depth`` on that radius and closes to a point ``r`` further on, which
    is what 45 degrees makes of it."""
    side = _face(measured, "down", "magnet/side-0")
    assert max(side["deep"]) == pytest.approx(MAGNET[1], abs=_TINY)
    assert min(side["out"]) >= _RADIUS - CHORD - _TINY
    assert max(side["out"]) <= _RADIUS + _TINY
    cone = _face(measured, "down", "magnet/side-cone")
    assert min(cone["deep"]) == pytest.approx(MAGNET[1], abs=_TINY)
    assert max(cone["out"]) == pytest.approx(_RADIUS, abs=_TINY)
    assert max(cone["deep"]) == pytest.approx(MAGNET[1] + _RADIUS, abs=_TINY)


def test_a_leaning_pockets_cone_leans_no_further_than_the_limit(
    measured: dict[str, Any],
) -> None:
    """On an axis ``LEAN`` degrees off the build direction the cone is narrowed by as much,
    so its steepest side still leans the limit and no more. The block itself, turned, reads
    its own underside - that is the block's and not the pocket's, so only the pocket's faces
    are read here."""
    cone = _face(measured, "leaning", "magnet/side-cone")
    assert max(cone["leans"]) <= _LIMIT
    side = _face(measured, "leaning", "magnet/side-0")
    assert max(side["deep"]) == pytest.approx(MAGNET[1], abs=_TINY)
    half = PLA.max_overhang - math.radians(LEAN)
    point = MAGNET[1] + _RADIUS / math.tan(half)
    assert max(cone["deep"]) == pytest.approx(point, abs=_TINY)


def test_the_same_pocket_kept_flat_still_reads_its_ceiling(measured: dict[str, Any]) -> None:
    """The check is live: ``end=End.FLAT`` leaves the ceiling, and it is found."""
    message, refs = measured["down_flat"]["overhangs"]
    assert "leans 90 degrees" in message
    assert refs == ["magnet/top"]


def test_a_pocket_opening_upward_keeps_its_flat_floor(measured: dict[str, Any]) -> None:
    """Standing on its floor it needs nothing, and gets nothing: a flat floor at the depth
    asked, facing up, and no cone."""
    assert PRINTED.orient.up.z > 0.0
    assert measured["up"]["overhangs"] is None
    faces = measured["up"]["faces"]
    assert "magnet/side-cone" not in faces
    floor = faces["magnet/top"]
    assert all(one == pytest.approx(MAGNET[1], abs=_TINY) for one in floor["deep"])
    assert all(one == pytest.approx(-90.0) for one in floor["leans"])
