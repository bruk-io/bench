"""Adapter: task-71's eased rim, measured by the modeller the app ships.

Two things only a built body can answer, both read straight off
:func:`bench.library.print.rim`'s own docstring:

* **A hull erases the names it wraps, and a union erases a face two solids share.**
  :func:`bench.topology.index` promises ``top`` and ``bottom`` on the tree alone, before a
  kernel sees it - :mod:`tests.functional.test_rim` checks that promise. What a real body
  keeps once it is triangles is narrower: the end a straight run shares with an eased cap
  is an internal, coincident face, and the union that joins them leaves no triangle
  answering to it.
* **Which way an eased rim overhangs depends on which way it narrows.** A round rim that
  narrows going up is a dome - every slice sits inside the one below it - and a round rim
  that narrows going down widens as it rises off the bed, crossing a horizontal tangent on
  the way. ``check_overhangs`` is how a script tells the two apart; this is that check,
  against a real mesh, on both.

:mod:`rim_cases` builds the bodies inside the runtime and makes the kernel calls; every
assertion is here.
"""

from pathlib import Path
from typing import Any

import pytest

from tools import stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)

_CASES = Path(__file__).with_name("rim_cases.py")

PROGRAM = """\
import json

from pyodide.ffi import JsException

import rim_cases
from bench.adapters.browser import JsKernel


def main(js, given):
    return json.dumps(rim_cases.measured(JsKernel(js, JsException)))
"""


@pytest.fixture(scope="module")
def measured() -> dict[str, Any]:
    """Every rim this module reads, built and measured once by the shipped kernel."""
    found: dict[str, Any] = stack.run(PROGRAM, {}, modules={"rim_cases.py": _CASES.read_text()})
    return found


def test_a_straight_runs_side_survives_both_rims_eased(measured: dict[str, Any]) -> None:
    """Both ends eased leaves the straight run's own side and nothing named at either end -
    the top and bottom each disappear into the union with their own eased cap."""
    assert measured["both_names"] == ["side-0"]


def test_the_flat_end_keeps_its_name_when_only_the_other_is_eased(measured: dict[str, Any]) -> None:
    """Only the top eased: the bottom is a real, untouched face of the straight run and
    keeps answering to ``bottom``; ease the other end instead and it is ``top`` that
    survives."""
    assert measured["top_only_names"] == ["bottom", "side-0"]
    assert measured["bottom_only_names"] == ["side-0", "top"]


def test_a_top_rim_narrowing_upward_has_no_overhang(measured: dict[str, Any]) -> None:
    """A round top rim is a dome: every slice toward the tip sits inside the one below it,
    so nothing in it leans past what the plastic holds up."""
    assert measured["top_round_overhang"] is None


def test_a_bottom_rim_narrowing_downward_does_overhang(measured: dict[str, Any]) -> None:
    """A round bottom rim widens as it rises off the bed and crosses a horizontal tangent
    on the way - the fillet `docs/printing.md` says to chamfer rather than round, and
    `check_overhangs` is how a script finds out it needs to."""
    found = measured["bottom_round_overhang"]
    assert found is not None
    assert "PLA holds up 45" in found
