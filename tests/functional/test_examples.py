"""Functional: every script under ``examples/`` runs, and runs clean.

The scripts are the acceptance test for the vocabulary - five parts a maker builds in the
first month, plus the two flat ones - so they are run the way the browser runs them: through
:func:`bench.script.run`, with no kernel, from the file on disk. What is asserted is what a
clean run means here: it produced a scene, it named the parts it should, nothing was
declined by the nest, and no check came back an error. A check that needs a modeller comes
back ``unchecked`` without one, which is not a failure and is what the browser sees today.

The measurements those checks make when there *is* a modeller are the adapter layer's, in
``tests/adapter/test_examples.py``.
"""

from pathlib import Path

import pytest

from bench import Severity
from bench.scene import OkScene, Scene

pytestmark = pytest.mark.functional

_EXAMPLES = Path(__file__).resolve().parents[2] / "examples"

_PARTS = {
    "box_with_hole.py": ("front", "back", "side-left", "side-right", "bottom"),
    "gridfinity_cabinet.py": (
        "drawer-front-1",
        "drawer-back",
        "drawer-side",
        "drawer-bottom",
        "cabinet-side-left",
        "cabinet-side-right",
        "cabinet-top-bottom",
        "cabinet-back",
        "runner",
    ),
    "gridfinity_bin.py": ("bin",),
    "pipe_bracket.py": ("bracket",),
    "enclosure_lid.py": ("box", "lid"),
    "depth_stop_collar.py": ("collar",),
    "hinge.py": ("leaf-a", "leaf-b", "pin"),
    "systainer_tote.py": ("tote",),
    "fulcrum_hinge.py": (
        "base",
        "link-1",
        "link-2",
        "link-3",
        "arm",
        "shaft-1",
        "shaft-2",
        "shaft-3",
        "shaft-4",
        "pin-1",
        "pin-2",
        "pin-3",
    ),
}
"""What each example must show. Not every part of the cabinet - it has one front per drawer
- but every part whose name a reader of the script would expect to find."""


def _scripts() -> tuple[Path, ...]:
    return tuple(sorted(_EXAMPLES.glob("*.py")))


def _ok(scene: Scene, name: str) -> OkScene:
    if not scene["ok"]:
        error = scene["error"]
        pytest.fail(f"{name} line {error['line']}: {error['message']}\n{error['traceback']}")
    return scene


def test_every_example_is_listed_here() -> None:
    """A new example is a new acceptance test, so it has to say what it makes. Without this
    the table below silently stops covering the directory."""
    assert {path.name for path in _scripts()} == set(_PARTS)


@pytest.mark.parametrize("path", _scripts(), ids=lambda p: p.name)
def test_an_example_runs_clean_and_makes_its_parts(path: Path) -> None:
    from bench import run

    scene = _ok(run(path.read_text()), path.name)
    made = {view["label"] for view in scene["parts"]}
    assert set(_PARTS[path.name]) <= made
    assert scene["warnings"] == [], "a clean run declines nothing"
    errors = [one for one in scene["violations"] if one["severity"] == Severity.ERROR]
    assert errors == [], "a clean run breaks no check it asked for"
    assert scene["refs"], "every part answers to a ref"


@pytest.mark.parametrize("path", _scripts(), ids=lambda p: p.name)
def test_an_example_declares_its_parameters(path: Path) -> None:
    """Every example is a panel in the browser as well as a script."""
    from bench import run

    scene = _ok(run(path.read_text()), path.name)
    assert scene["params"], "an example with no parameters is a drawing, not a script"
    assert all(view["name"] in scene["values"] for view in scene["params"])


@pytest.mark.parametrize("path", _scripts(), ids=lambda p: p.name)
def test_a_printed_example_reports_the_numbers_that_matter(path: Path) -> None:
    """Each of the five bodies prints the dimensions a maker would otherwise have to
    measure off the model - the bore it drilled, the gap it left, the size it came to."""
    from bench import run

    if path.name in {"box_with_hole.py"}:
        pytest.skip("the flat hello-world prints nothing and is the README's own example")
    scene = _ok(run(path.read_text()), path.name)
    assert scene["stdout"].strip()


def test_a_printed_part_is_not_a_nest_warning() -> None:
    """The bodies are not cut from a sheet and saying so five times is not a report. A part
    that is *sheet* stock and not planar still is a mistake, and still says so."""
    from bench import run

    scene = _ok(run((_EXAMPLES / "hinge.py").read_text()), "hinge.py")
    assert scene["sheets"] == []
    assert scene["warnings"] == []
