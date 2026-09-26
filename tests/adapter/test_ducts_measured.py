"""Adapter: every duct fitting, built by the modeller the app ships and measured.

:mod:`ducts_cases` is run inside Pyodide by :mod:`tools.stack` with the real kernel, and what
comes back is checked here against the fit table and arithmetic done by hand:

* **every fitting prints the way it says** - standing on its start (``ducts.UPRIGHT``), in PLA
  and in ASA, the overhang check finds nothing leaning past the plastic's limit and the wall
  check nothing under its minimum. Both need a mesh, which is why this is the adapter's;
* **a spigot slides into the socket of its own size at the slide** - for a size measured on
  its inside and one measured on its outside, the nearest the two come is the fit table's
  slide and no more than a chord's sag over it, and they share nothing;
* **a socket is as deep and as wide as it was asked** - read off the triangles its bore's
  name is on;
* **an elbow is the ring swept round its path** - Pappus's volume, to the chords.
"""

import math
from pathlib import Path
from typing import Any

import pytest

from bench import Fit
from bench.library import ducts
from bench.library.print import PLA, clearance
from bench.topology import CHORD
from tests.adapter.ducts_cases import DEPTH, ELBOW
from tools import stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)

_CASES = Path(__file__).with_name("ducts_cases.py")

PROGRAM = """\
import json

from pyodide.ffi import JsException

import ducts_cases
from bench.adapters.browser import JsKernel


def main(js, given):
    return json.dumps(ducts_cases.measured(JsKernel(js, JsException)))
"""

_TINY = 1e-3
"""Millimetres: float noise on a single-precision mesh vertex at these sizes."""

_FITTINGS = (
    "spigot",
    "socket",
    "coupler",
    "reducer",
    "reducer_up",
    "elbow",
    "elbow_small",
    "branch",
    "branch_smaller_tap",
    "square_to_round",
    "square_to_round_narrow",
)


@pytest.fixture(scope="module")
def measured() -> dict[str, Any]:
    """Every fitting this module reads, built and measured once by the shipped kernel."""
    found: dict[str, Any] = stack.run(PROGRAM, {}, modules={"ducts_cases.py": _CASES.read_text()})
    return found


def _sides(radius: float) -> int:
    """How many chords a circle of that radius is cut into - the package's one chord rule,
    restated so the expected numbers are worked out here rather than read off the code."""
    return math.ceil(math.tau / (2.0 * math.acos(1.0 - CHORD / radius)))


def _polygon_area(radius: float) -> float:
    """The area of the regular polygon a circle of that radius actually becomes."""
    n = _sides(radius)
    return 0.5 * n * radius * radius * math.sin(math.tau / n)


# ---- every fitting prints the way it says ------------------------------------------------


@pytest.mark.parametrize("plastic", ["PLA", "ASA"])
@pytest.mark.parametrize("fitting", _FITTINGS)
def test_a_fitting_standing_on_its_start_needs_no_support(
    measured: dict[str, Any], plastic: str, fitting: str
) -> None:
    found = measured["printable"][plastic][fitting]
    assert found["overhangs"] is None, found["overhangs"]


@pytest.mark.parametrize("plastic", ["PLA", "ASA"])
@pytest.mark.parametrize("fitting", _FITTINGS)
def test_a_fittings_thinnest_wall_is_no_thinner_than_the_plastic_prints(
    measured: dict[str, Any], plastic: str, fitting: str
) -> None:
    found = measured["printable"][plastic][fitting]
    assert found["wall"] is None, found["wall"]


@pytest.mark.parametrize(
    ("fitting", "limit"), [("elbow-90-PLA", 45), ("elbow-45-ASA", 40), ("branch-60-PLA", 45)]
)
def test_a_turn_past_what_the_plastic_holds_up_is_drawn_and_the_overhang_check_flags_it(
    measured: dict[str, Any], fitting: str, limit: int
) -> None:
    """A 90 degree elbow in PLA, a 45 in ASA, a branch leaving at 60: each is built, and
    standing on its start the inside of its bend leans past the plastic's limit - which the
    overhang check measures and says, on the bend's own faces. The same 45 degree elbow in
    PLA passes (``test_a_fitting_standing_on_its_start_needs_no_support[elbow-PLA]``)."""
    found = measured["steep"][fitting]
    assert found is not None, f"{fitting} was not flagged"
    message, faces = found
    leans = int(message.split("leans ")[1].split(" degrees")[0])
    assert leans > limit
    assert f"holds up {limit}" in message
    assert faces


# ---- a spigot in a socket ----------------------------------------------------------------


@pytest.mark.parametrize("size", ["4 in dust hose", "4 in dust port"])
def test_a_spigot_slides_into_the_socket_of_its_own_size_at_the_slide(
    measured: dict[str, Any], size: str
) -> None:
    """The slide the table asks for, measured: the gap goes on the spigot for a hose and on
    the socket for a port, and either way the two stand the slide apart - drawn with the
    concave allowance, so no nearer than the slide and no further than a chord past it."""
    joint = measured["joints"][size]
    slide = clearance(Fit.SLIDE, PLA)
    assert slide - _TINY <= joint["gap"] <= clearance(Fit.SLIDE, PLA, concave=True) + _TINY
    assert joint["shared"] == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize("size", [ducts.HOSE_4, ducts.PORT_4], ids=lambda s: s.name)
def test_a_sockets_bore_runs_as_deep_and_as_wide_as_it_was_asked(
    measured: dict[str, Any], size: ducts.Size
) -> None:
    """Read off the triangles named ``inside/side-socket``: from the mouth on the bed to
    ``DEPTH``, where the stop's cone begins, and round the socket's own diameter - its
    corners on the circle, a chord's sag inside it at most."""
    bore = measured["joints"][size.name]["bore"]
    heights = [z for _, _, z in bore]
    assert min(heights) == pytest.approx(0.0, abs=_TINY)
    assert max(heights) == pytest.approx(DEPTH, abs=_TINY)
    reach = max(math.hypot(x, y) for x, y, _ in bore)
    assert reach == pytest.approx(ducts.socket_diameter(size) / 2, abs=_TINY)


# ---- the elbow ---------------------------------------------------------------------------


def test_an_elbow_is_its_ring_swept_round_its_path(measured: dict[str, Any]) -> None:
    """The ring's area times the length of the path its centre runs: two straight legs and
    the bend. The bend is cut into chords, which takes a few parts in ten thousand off, and
    nothing adds any."""
    size, turn, radius, leg = ELBOW
    outside = ducts.spigot_diameter(size) / 2
    ring = _polygon_area(outside) - _polygon_area(outside - ducts.WALL)
    pappus = ring * (2 * leg + radius * math.radians(turn))
    assert pappus * (1 - 1e-3) < measured["elbow"] < pappus
