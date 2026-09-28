"""Functional: ``context(body, label=...)``, a body shown beside the parts and never made.

task-90, decision-12's "context bodies": a script can put a reference piece in its seated pose,
or the ghost of a module's body, in the scene without it becoming a part. These run real
scripts with no kernel, so a context body has no mesh here - what is asked is everything a
run makes *without* one: that the parts, their refs, their sheets, their files, their counts
and their findings are exactly what they are without the context, and that a mistake in
calling it stops the run at the line that made it. The bytes of a built body's STL and 3MF,
which only a kernel writes, are ``tests/adapter/test_export_as_printed.py``'s.
"""

import pytest

import bench
from bench import run
from bench.scene import ErrorView, OkScene, Scene

pytestmark = pytest.mark.functional

PLAIN = """\
from bench import *
from bench.library.print import PLA

plate = part("plate", fill(rect(60, 40)), Stock(3, "ply"))
block = cuboid(20, 20, 5)
check_fits(block, Volume(10, 10, 10))
printed = part("block", block, Printed(PLA))
show(assembly("pair", (Placed(plate, XY), Placed(printed, XY)), posed=True))
"""
"""A laser part and a printed one, and a check that fails - one of everything a run offers."""

PIN = 'context(move(cylinder(5, 30), Z * -10), label="pin")\n'
"""A pin through the pair, shown for context."""


def _ok(scene: Scene) -> OkScene:
    if not scene["ok"]:
        pytest.fail(f"{scene['error']['message']}\n{scene['error']['traceback']}")
    return scene


def _error(scene: Scene) -> ErrorView:
    if scene["ok"]:
        pytest.fail("that script was meant to fail")
    return scene["error"]


def test_a_context_body_reaches_the_scene_under_its_label() -> None:
    scene = _ok(run(PLAIN + PIN))
    assert scene["context"] == [{"ref": "pin", "mesh": None}], "no kernel, so nothing built"


def test_a_scene_with_no_context_says_so_with_an_empty_list() -> None:
    assert _ok(run(PLAIN))["context"] == []


def test_context_changes_nothing_a_run_makes() -> None:
    """Not a part, not a sheet, not a file, not a count, not a ref, not a finding."""
    plain = _ok(run(PLAIN))
    shown = _ok(run(PLAIN + PIN))
    for key in ("parts", "refs", "sheets", "files", "summary", "violations", "warnings"):
        assert shown[key] == plain[key], key
    assert [part["ref"] for part in shown["parts"]] == ["plate", "block"]
    assert not any(ref.startswith("pin") for ref in shown["refs"])
    assert not any("pin" in name for name in shown["files"])


def test_context_is_this_runs_own_and_from_bench_import_star_cannot_replace_it() -> None:
    """``PLAIN`` starts ``from bench import *``; the name is still the run's own."""
    assert "context" not in bench.__all__
    assert _ok(run(PLAIN + PIN))["context"][0]["ref"] == "pin"


def test_a_build_can_show_context_that_depends_on_its_settings() -> None:
    source = """\
from dataclasses import dataclass

from bench import *


@dataclass(frozen=True)
class Pin:
    length: float = knob(30.0, min=10.0, max=60.0)


def build(p: Pin) -> Part:
    context(cylinder(5, p.length), label="pin")
    context(cuboid(4, 4, p.length), label="key")
    return part("plate", fill(rect(60, 40)), Stock(3, "ply"))


show(build)
"""
    scene = _ok(run(source, {"length": 45.0}))
    assert [one["ref"] for one in scene["context"]] == ["pin", "key"], "in the order said"


def test_context_said_before_show_is_shown_all_the_same() -> None:
    source = PIN + PLAIN.replace("from bench import *\n", "")
    scene = _ok(run("from bench import *\n" + source))
    assert [one["ref"] for one in scene["context"]] == ["pin"]


def test_a_flat_face_is_not_a_body_to_show_for_context() -> None:
    error = _error(run(PLAIN + 'context(fill(rect(4, 4)), label="tab")\n'))
    assert "context() shows a body" in error["message"]
    assert error["line"] == PLAIN.count("\n") + 1


def test_a_part_is_refused_and_told_where_its_body_is() -> None:
    error = _error(run(PLAIN + 'context(plate, label="again")\n'))
    assert "'Part'" in error["message"]
    assert ".shape" in error["message"]


def test_a_label_said_twice_stops_the_run() -> None:
    error = _error(run(PLAIN + PIN + PIN))
    assert "already given a body labelled 'pin'" in error["message"]
    assert error["line"] == PLAIN.count("\n") + 2


def test_a_label_that_cannot_be_a_label_stops_the_run() -> None:
    error = _error(run(PLAIN + 'context(cylinder(5, 30), label="pin/head")\n'))
    assert "joins labels into a ref" in error["message"]


def test_a_context_body_labelled_as_a_part_is_refused() -> None:
    """A ref under the one label would name both, and lighting one would light the other."""
    error = _error(run(PLAIN + 'context(cylinder(5, 30), label="block")\n'))
    assert "context 'block' has the label of a part" in error["message"]
