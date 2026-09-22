"""Functional: :func:`bench.transport.scene_wire`, a scene as the worker posts it to the page.

Real runs read back out of the JSON and the buffers: the cabinet, whose plates have bodies
even with no kernel and whose drawer fronts are lettered, and a box with an engraved line on
it, so the marks' buffers are there to be found.
"""

import json
from pathlib import Path

import pytest

from bench import script
from bench.scene import OkScene
from bench.transport import scene_json, scene_wire

pytestmark = pytest.mark.functional

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "gridfinity_cabinet.py"

SCORED = """\
from bench import *

plate = face(rect(60, 40))
score = rect(20, 10, Point(20, 15), label="score")
show(part("plate", plate, Stock(3.0, "ply"), Process.LASER, engravings=(score,)))
"""

PRINTED_ONLY = """\
from bench import *
from bench.library.print import PLA

show(part("block", cuboid(20, 20, 5), Printed(PLA)))
"""


def _ok(source: str) -> OkScene:
    scene = script.run(source)
    assert scene["ok"], scene
    return scene


def test_a_meshs_long_lists_leave_the_json_for_buffers_it_names_by_number() -> None:
    scene = _ok(EXAMPLE.read_text())
    text, buffers = scene_wire(scene)
    first = scene["parts"][0]["mesh"]
    assert first is not None
    wired = json.loads(text)["parts"][0]["mesh"]
    assert wired == {"positions": 0, "ref_index": 1, "refs": first["refs"]}
    assert buffers[0].typecode == "f"
    assert list(buffers[0]) == pytest.approx(first["positions"], abs=1e-4)
    assert (buffers[1].typecode, list(buffers[1])) == ("I", first["ref_index"])


def test_every_mesh_takes_the_next_two_buffers() -> None:
    scene = _ok(EXAMPLE.read_text())
    text, buffers = scene_wire(scene)
    parts = json.loads(text)["parts"]
    assert [part["mesh"]["positions"] for part in parts] == list(range(0, 2 * len(parts), 2))
    assert len(buffers) == 2 * len(parts), "no engraved wires on the cabinet, so no marks"


def test_marks_take_the_two_buffers_after_their_mesh() -> None:
    scene = _ok(SCORED)
    marks = scene["parts"][0]["marks"]
    assert marks is not None
    text, buffers = scene_wire(scene)
    wired = json.loads(text)["parts"][0]
    assert wired["marks"] == {"segments": 2, "ref_index": 3, "refs": ["plate/score"]}
    assert (buffers[2].typecode, len(buffers[2])) == ("f", 6 * 4)
    assert (buffers[3].typecode, list(buffers[3])) == ("I", [1, 1, 1, 1])


def test_everything_but_the_long_lists_is_the_scene_as_it_was() -> None:
    scene = _ok(SCORED)
    text, _ = scene_wire(scene)
    wired = json.loads(text)
    plain = json.loads(scene_json(scene))
    for part in (*wired["parts"], *plain["parts"]):
        part.pop("mesh")
        part.pop("marks")
    assert wired == plain


def test_a_part_with_no_body_keeps_its_nulls() -> None:
    text, buffers = scene_wire(_ok(PRINTED_ONLY))
    [part] = json.loads(text)["parts"]
    assert (part["mesh"], part["marks"], buffers) == (None, None, [])


def test_a_failed_run_is_its_json_and_no_buffers() -> None:
    failed = script.run("from bench import *\n\nshow(1 / 0)\n")
    assert scene_wire(failed) == (scene_json(failed), [])
