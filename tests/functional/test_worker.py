"""Functional: :mod:`bench.worker`, the entry the browser's worker calls.

Real runs through the runner :func:`~bench.worker.start` gives back, with a telemetry object
that keeps what it is handed - which is exactly what the page's two functions are to Python.
No modeller is handed in, so the kernel's own calls are the adapter layer's to test.
"""

import ast
import base64
import json
import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import bench
from bench.survey import ROUND
from bench.worker import detected, level, start, surveyed

pytestmark = pytest.mark.functional

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "gridfinity_cabinet.py"


class _Refused(Exception):
    """What a modeller that is not here would raise."""


@dataclass
class _Telemetry:
    spans: list[tuple[str, float, float, dict[str, object]]] = field(default_factory=list)
    logs: list[tuple[str, str, str, float, dict[str, object]]] = field(default_factory=list)

    def span(self, name: str, start: float, duration: float, attributes: str, /) -> None:
        self.spans.append((name, start, duration, json.loads(attributes)))

    def log(self, level: str, logger: str, message: str, time: float, attributes: str, /) -> None:
        self.logs.append((level, logger, message, time, json.loads(attributes)))


@pytest.fixture(autouse=True)
def _logging_put_back() -> Iterator[None]:
    """:func:`start` configures ``bench``'s logger, which is its job; each test gets it back
    the way it found it."""
    logger = logging.getLogger("bench")
    handlers, was = list(logger.handlers), logger.level
    yield
    logger.handlers[:] = handlers
    logger.setLevel(was)


def test_a_run_comes_back_as_the_scene_on_the_wire() -> None:
    text, buffers = start(_Telemetry(), _Refused)(EXAMPLE.read_text(), "{}", None)
    scene = json.loads(text)
    assert scene["ok"] is True
    assert scene["parts"]
    assert len(buffers) == 2 * len(scene["parts"]), "a plate needs no modeller"


def test_overrides_arrive_as_json_and_reach_the_script() -> None:
    text, _ = start(_Telemetry(), _Refused)(EXAMPLE.read_text(), '{"units_x": 6}', None)
    assert json.loads(text)["values"]["units_x"] == 6


def test_every_span_reaches_the_page_in_milliseconds_since_the_epoch() -> None:
    telemetry = _Telemetry()
    before = time.time() * 1000
    start(telemetry, _Refused)(EXAMPLE.read_text(), "{}", None)
    names = [one[0] for one in telemetry.spans]
    assert {"bench.run", "bench.script.exec", "bench.scene.wire"} <= set(names)
    for _, begun, duration, _ in telemetry.spans:
        assert begun >= before - 1
        assert duration >= 0
    [run] = [one for one in telemetry.spans if one[0] == "bench.run"]
    assert run[3]["bench.run.ok"] is True


def test_a_runs_log_record_reaches_the_page_with_its_fields() -> None:
    telemetry = _Telemetry()
    start(telemetry, _Refused)(EXAMPLE.read_text(), "{}", None)
    start(telemetry, _Refused)("from bench import *\n\nshow(1 / 0)\n", "{}", None)
    said = [one for one in telemetry.logs if one[1] == "bench.script"]
    assert (said[0][0], said[0][2]) == ("info", "run finished")
    assert said[0][4]["bench.parts"] == 14
    assert said[1][0] == "warn"
    assert said[1][4] == {"code.lineno": 3}


def test_a_dropped_body_crosses_as_base64_and_reaches_the_script() -> None:
    """The seam a drop on the view lands in: bytes out of a file, text across the edge, and a
    mesh the script can measure. The STL is written by bench's own exporter, so the test
    hands the runner exactly what the page would."""
    triangle = bench.Mesh((0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 4.0, 0.0), (0, 1, 2), (None,))
    source = (
        "from bench import *\n\n"
        "print(survey(reference).triangles, reference.refs)\n"
        "show(part('plate', fill(rect(4, 4)), Stock(3, 'ply')))\n"
    )

    text, _ = start(_Telemetry(), _Refused)(
        source, "{}", None, base64.b64encode(bench.stl(triangle)).decode()
    )

    assert json.loads(text)["stdout"] == "1 (None,)\n"


def test_a_run_with_nothing_dropped_leaves_the_reference_empty() -> None:
    source = (
        "from bench import *\n\n"
        "print(reference)\n"
        "show(part('plate', fill(rect(4, 4)), Stock(3, 'ply')))\n"
    )

    text, _ = start(_Telemetry(), _Refused)(source, "{}", None)

    assert json.loads(text)["stdout"] == "None\n"


_BOX = bench.Mesh(
    (
        606.795,
        -116.868,
        0.0,
        651.795,
        -116.868,
        0.0,
        651.795,
        -78.868,
        0.0,
        606.795,
        -78.868,
        0.0,
        606.795,
        -116.868,
        6.8,
        651.795,
        -116.868,
        6.8,
        651.795,
        -78.868,
        6.8,
        606.795,
        -78.868,
        6.8,
    ),
    (0, 1, 2, 0, 2, 3, 4, 5, 6, 4, 6, 7),
    (None, None, None, None, None, None, None, None),
)
"""The systainer foot from decision-4, as a mesh: a box from (606.795, -116.868, 0.0) to
(651.795, -78.868, 6.8), already right way up. Shared by the placement tests below, so a run
and a survey of the same drop are checked against the same body."""

_TABLE = json.dumps({"origin": "low", "up": "+Z", "along": "+X"})
"""A `[reference]` table that puts the foot's low corner on the origin - decision-4's own
worked example, one line in the file."""


def test_a_run_with_a_table_places_the_reference_before_the_script_sees_it() -> None:
    """The box's low corner - the mesh's first vertex - lands on the origin, as ``origin =
    "low"`` says."""
    source = (
        "from bench import *\n\n"
        "print(tuple(reference.vertices[:3]))\n"
        "show(part('plate', fill(rect(4, 4)), Stock(3, 'ply')))\n"
    )
    stl = base64.b64encode(bench.stl(_BOX)).decode()

    text, _ = start(_Telemetry(), _Refused)(source, "{}", None, stl, _TABLE)

    assert json.loads(text)["stdout"] == "(0.0, 0.0, 0.0)\n"


def test_a_run_with_a_stl_and_no_table_leaves_the_reference_as_exported() -> None:
    source = (
        "from bench import *\n\n"
        "print(tuple(reference.vertices[:3]))\n"
        "show(part('plate', fill(rect(4, 4)), Stock(3, 'ply')))\n"
    )
    stl = base64.b64encode(bench.stl(_BOX)).decode()

    text, _ = start(_Telemetry(), _Refused)(source, "{}", None, stl)

    # A binary STL holds 32-bit floats, so the mesh comes back close to the mesh's own numbers
    # rather than exactly equal to them - the STL round trip's own precision, nothing to do
    # with placement, which is not applied here at all.
    x, y, z = ast.literal_eval(json.loads(text)["stdout"])
    assert (round(x, 3), round(y, 3), round(z, 3)) == (606.795, -116.868, 0.0)


def test_a_bad_table_fails_a_run_the_way_a_bad_value_does() -> None:
    source = "from bench import *\n\nshow(part('p', fill(rect(4, 4)), Stock(3, 'ply')))\n"
    stl = base64.b64encode(bench.stl(_BOX)).decode()

    with pytest.raises(ValueError, match="origin"):
        start(_Telemetry(), _Refused)(
            source, "{}", None, stl, json.dumps({"up": "+Z", "along": "+X"})
        )


def test_surveyed_with_no_table_reports_the_mesh_exactly_as_exported() -> None:
    stl = base64.b64encode(bench.stl(_BOX)).decode()
    assert "from (606.795, -116.868, 0.000)" in surveyed(stl)


def test_surveyed_and_a_run_agree_on_placed_coordinates() -> None:
    """decision-4's own rule: what the viewer draws and what the report says always agree -
    a run's own ``survey(reference)`` and the worker's ``surveyed`` are measured off the same
    placed mesh, so the extent each one reports for the same drop and the same table matches."""
    stl = base64.b64encode(bench.stl(_BOX)).decode()

    report = surveyed(stl, _TABLE)
    assert "from (0.000, 0.000, 0.000) to (45.000, 38.000, 6.800)" in report

    source = (
        "from bench import *\n\n"
        "e = survey(reference).extent\n"
        "print((round(e.low.x, 3), round(e.low.y, 3), round(e.low.z, 3)),"
        " (round(e.high.x, 3), round(e.high.y, 3), round(e.high.z, 3)))\n"
        "show(part('plate', fill(rect(4, 4)), Stock(3, 'ply')))\n"
    )
    text, _ = start(_Telemetry(), _Refused)(source, "{}", None, stl, _TABLE)
    assert json.loads(text)["stdout"] == "(0.0, 0.0, 0.0) (45.0, 38.0, 6.8)\n"


def test_detected_finds_one_flat_per_face_of_the_box() -> None:
    """The foot fixture is its top and bottom faces, two triangles each - both are one flat,
    and every triangle of it says which."""
    stl = base64.b64encode(bench.stl(_BOX)).decode()

    found = json.loads(detected(stl))

    assert len(found["flats"]) == 2
    assert found["flat_index"] == [0, 0, 1, 1] or found["flat_index"] == [1, 1, 0, 0]
    assert {round(f["area"]) for f in found["flats"]} == {1710}


def test_detected_and_surveyed_agree_on_placed_coordinates() -> None:
    """The same rule as ``surveyed``: a detected flat's own numbers are measured off the
    same placed mesh a run and a survey already agree on."""
    stl = base64.b64encode(bench.stl(_BOX)).decode()

    found = json.loads(detected(stl, _TABLE))

    centres = {tuple(round(c, 3) for c in f["centre"]) for f in found["flats"]}
    assert (22.5, 19.0, 0.0) in centres
    assert (22.5, 19.0, 6.8) in centres


def test_detected_reports_the_points_a_pick_may_resolve_to_a_word() -> None:
    """decision-7's pick needs three points and one distance to say whether the corner
    somebody clicked *is* the corner a `[reference]` table calls `"low"`. They ride with the
    detection because a pick happens in the same mode, on the same body."""
    stl = base64.b64encode(bench.stl(_BOX)).decode()

    found = json.loads(detected(stl))

    assert [one["name"] for one in found["origins"]] == ["low", "high", "centre"]
    assert found["origins"][0]["point"] == pytest.approx([606.795, -116.868, 0.0])
    assert found["origins"][1]["point"] == pytest.approx([651.795, -78.868, 6.8])
    assert found["origins"][2]["point"] == pytest.approx([629.295, -97.868, 3.4])
    assert found["round"] == ROUND


def test_detecteds_origins_are_in_the_same_placed_frame_its_flats_are() -> None:
    """Anything else would snap a pick to a word that meant somewhere else: the origins are
    measured off the very mesh the flats were, table and all."""
    stl = base64.b64encode(bench.stl(_BOX)).decode()

    found = json.loads(detected(stl, _TABLE))

    named = {one["name"]: one["point"] for one in found["origins"]}
    assert named["low"] == pytest.approx([0.0, 0.0, 0.0])
    assert named["high"] == pytest.approx([45.0, 38.0, 6.8])


def test_detected_with_a_bad_table_fails_the_way_surveyed_does() -> None:
    stl = base64.b64encode(bench.stl(_BOX)).decode()

    with pytest.raises(ValueError, match="origin"):
        detected(stl, json.dumps({"up": "+Z", "along": "+X"}))


def test_something_that_is_not_a_binary_stl_comes_back_as_the_readers_own_reason() -> None:
    """It is not caught and turned into an error scene: the page shows the run failing, and
    what it says is what the reader said."""
    source = "from bench import *\n\nshow(part('p', fill(rect(4, 4)), Stock(3, 'ply')))\n"
    ascii_stl = base64.b64encode(b"solid box\n facet normal 0 0 1\n endsolid box\n").decode()

    with pytest.raises(ValueError, match="ASCII"):
        start(_Telemetry(), _Refused)(source, "{}", None, ascii_stl)


def test_starting_again_replaces_the_handler_rather_than_doubling_every_record() -> None:
    first, second = _Telemetry(), _Telemetry()
    start(first, _Refused)
    start(second, _Refused)(EXAMPLE.read_text(), "{}", None)
    assert first.logs == []
    assert len([one for one in second.logs if one[1] == "bench.script"]) == 1


@pytest.mark.parametrize(
    ("name", "spelled"),
    [
        ("DEBUG", "debug"),
        ("INFO", "info"),
        ("WARNING", "warn"),
        ("ERROR", "error"),
        ("CRITICAL", "error"),
    ],
)
def test_logging_levels_are_spelled_the_way_the_page_reads_them(name: str, spelled: str) -> None:
    assert level(name) == spelled


# ---- a project's other scripts, mounted for a run to import (task-50) --------------------

_ENTRY = (
    "from bench import *\nimport parts\n\n"
    "show(part('p', fill(rect(parts.W, parts.W)), Stock(3, 'ply')))\n"
)


def test_an_entry_imports_a_module_the_project_hands_over_beside_it() -> None:
    text, _ = start(_Telemetry(), _Refused)(
        _ENTRY, "{}", None, None, None, json.dumps({"parts.py": "W = 12.0\n"})
    )
    scene = json.loads(text)
    assert scene["ok"] is True, scene


def test_a_module_the_project_does_not_hold_fails_by_name_not_by_trace() -> None:
    """task-50 AC#5 / task-56 AC#1: not a raw `ModuleNotFoundError` buried in stderr - the run
    catches it as any other exception a script raises, the message names the project's own
    missing file and says the project has none, and Python's own message is still there for
    anyone debugging."""
    text, _ = start(_Telemetry(), _Refused)(_ENTRY, "{}", None)
    scene = json.loads(text)
    assert scene["ok"] is False
    message = scene["error"]["message"]
    assert "No module named 'parts'" in message, "the original exception is still readable"
    assert "there is no parts.py (it has none)" in message


def test_a_module_the_project_does_not_hold_lists_the_ones_it_has() -> None:
    """task-56 AC#1: a project of more than one file names them all, not only that the missing
    one is not among them."""
    entry = (
        "from bench import *\nimport sidekick\n\n"
        "show(part('p', fill(rect(4, 4)), Stock(3, 'ply')))\n"
    )
    text, _ = start(_Telemetry(), _Refused)(
        entry, "{}", None, None, None, json.dumps({"parts.py": "W = 12.0\n"})
    )
    scene = json.loads(text)
    assert scene["ok"] is False
    assert "there is no sidekick.py (it has: parts.py)" in scene["error"]["message"]


def test_switching_projects_does_not_leak_the_first_ones_module_into_the_second() -> None:
    """The worker is one long-lived process: a run with no modules of its own must not still
    see the previous run's `parts`, and a second project's own `parts` must not answer with
    the first project's number."""
    runner = start(_Telemetry(), _Refused)
    first, _ = runner(_ENTRY, "{}", None, None, None, json.dumps({"parts.py": "W = 10.0\n"}))
    assert json.loads(first)["ok"] is True

    without_modules, _ = runner(_ENTRY, "{}", None)
    assert json.loads(without_modules)["ok"] is False, "the first project's parts must be gone"

    second, _ = runner(_ENTRY, "{}", None, None, None, json.dumps({"parts.py": "W = 20.0\n"}))
    scene = json.loads(second)
    assert scene["ok"] is True
    assert scene["values"] == {}, "parts.W is not a declared setting, only read by the script"


def test_a_project_module_that_would_shadow_the_standard_library_is_refused() -> None:
    with pytest.raises(ValueError, match="shadow"):
        start(_Telemetry(), _Refused)(
            EXAMPLE.read_text(), "{}", None, None, None, json.dumps({"os.py": "X = 1\n"})
        )


def test_a_project_module_named_bench_is_refused_too() -> None:
    with pytest.raises(ValueError, match="shadow"):
        start(_Telemetry(), _Refused)(
            EXAMPLE.read_text(), "{}", None, None, None, json.dumps({"bench.py": "X = 1\n"})
        )
