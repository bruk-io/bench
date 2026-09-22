"""Functional: the script a new file starts as runs clean.

``templates/untitled.py`` is what the Files menu's *New file* puts in the editor, so it is the
first run a person writing their own script sees. It is held to what an example is held to -
a scene, its part, a panel, no warnings and no failed checks - and to staying short.
"""

from pathlib import Path

import pytest

from bench import Severity, run
from bench.scene import OkScene

pytestmark = pytest.mark.functional

STARTER = Path(__file__).resolve().parents[2] / "templates" / "untitled.py"


def _scene() -> OkScene:
    scene = run(STARTER.read_text())
    if not scene["ok"]:
        error = scene["error"]
        pytest.fail(f"untitled.py line {error['line']}: {error['message']}\n{error['traceback']}")
    return scene


def test_the_starter_runs_clean_and_draws_its_plate() -> None:
    scene = _scene()
    assert [view["label"] for view in scene["parts"]] == ["plate"]
    assert "plate/hole" in scene["refs"], "the hole answers to a click"
    assert len(scene["sheets"]) == 1
    assert scene["warnings"] == []
    assert [one for one in scene["violations"] if one["severity"] == Severity.ERROR] == []


def test_the_starter_has_a_panel() -> None:
    """A new file shows the Parameters tab working from its first run."""
    scene = _scene()
    assert scene["params"]
    assert all(view["name"] in scene["values"] for view in scene["params"])


def test_the_starter_stays_short() -> None:
    """A starting point, not an example: the Examples menu is where the long reads are."""
    assert len(STARTER.read_text().splitlines()) <= 40
