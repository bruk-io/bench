"""Adapter: ``bench`` inside the Pyodide runtime the app ships, with its modeller, under Node.

The browser never imports this package the way pytest does: the worker boots Pyodide,
writes every module of ``src/bench`` into ``/lib`` of its filesystem, puts ``/lib`` on
``sys.path`` and calls :func:`bench.script.run` in there with the modeller as its kernel.
That is the boundary this module tests, on :mod:`tools.stack` - the real runtime from
``web/node_modules/pyodide``, the real Manifold WASM, the app's own ``modeller.ts`` and no
stand-ins - and the checks compare what came back against running the same script in
process.

The file map is built from ``src/bench/**/*.py`` rather than read from the generated
``web/src/generated/pysources.ts``, so this test needs no ``npm run generate`` and fails if
the runtime disagrees with the sources as they are on disk.

A boot takes a few seconds, so every run this needs - the defaults, one override and a
printed part - happens in one module-scoped boot.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from bench import script, transport
from tools import stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
"""The repository root: the examples hang off it."""

EXAMPLE = ROOT / "examples" / "gridfinity_cabinet.py"
"""The script both sides run."""

PRINTED = ROOT / "examples" / "gridfinity_bin.py"
"""A script whose part is a body, so the runtime's modeller has something to build."""

PROGRAM = """\
import builtins
import json
import sys

from pyodide.ffi import JsException

from bench.adapters.browser import JsKernel
from bench.script import run


def main(js, given):
    given = json.loads(given)
    kernel = JsKernel(js, JsException)
    return json.dumps({
        "version": " ".join(sys.version.split()),
        "has_frozendict": hasattr(builtins, "frozendict"),
        "default": run(given["example"], {}, kernel=kernel),
        "wider": run(given["example"], {"units_x": 6}, kernel=kernel),
        "printed": run(given["printed"], kernel=kernel),
    })
"""


@pytest.fixture(scope="module")
def runtime() -> dict[str, Any]:
    """The interpreter the runtime is, and the scenes it made: the example with the
    parameters it declares, with the override a panel edit would send, and a printed part."""
    found: dict[str, Any] = stack.run(
        PROGRAM, {"example": EXAMPLE.read_text(), "printed": PRINTED.read_text()}
    )
    return found


def _width(scene: dict[str, Any], ref: str) -> float:
    """The width in millimetres of one part of ``scene``.

    Raises:
        AssertionError: if the scene has no such part.
    """
    for part in scene["parts"]:
        if part["ref"] == ref:
            box = part["bbox"]
            return float(box[2]) - float(box[0])
    raise AssertionError(f"the scene has no part {ref!r}")


def test_the_runtime_is_python_315(runtime: dict[str, Any]) -> None:
    assert runtime["version"].startswith("3.15"), runtime["version"]


def test_the_runtime_has_frozendict(runtime: dict[str, Any]) -> None:
    """``bench.script.run`` defaults an argument to ``frozendict()``, so the runtime has to
    be new enough to have it - the one language feature the browser could lag on."""
    assert runtime["has_frozendict"], f"no frozendict in {runtime['version']}"


def test_the_runtime_produces_an_ok_scene(runtime: dict[str, Any]) -> None:
    scene = runtime["default"]
    assert scene["ok"] is True, scene.get("error")
    assert scene["sheets"], "the runtime nested nothing"
    assert scene["files"], "the runtime offered nothing to download"


def test_the_runtime_builds_the_same_parts_as_this_interpreter(runtime: dict[str, Any]) -> None:
    """The same script, the same sources, two interpreters: the cut list must not depend on
    which one ran it."""
    there = runtime["default"]
    here = json.loads(transport.scene_json(script.run(EXAMPLE.read_text())))
    assert here["ok"] is True, here.get("error")
    assert {part["ref"] for part in there["parts"]} == {part["ref"] for part in here["parts"]}
    assert [sheet["name"] for sheet in there["sheets"]] == [
        sheet["name"] for sheet in here["sheets"]
    ]


def test_an_override_crosses_into_the_runtime(runtime: dict[str, Any]) -> None:
    """``units_x=6`` is the edit a panel makes: it arrives as JSON on the other side of the
    boundary, and the geometry that comes back is wider for it."""
    wider = runtime["wider"]
    assert wider["ok"] is True, wider.get("error")
    assert wider["values"]["units_x"] == 6
    narrow = _width(runtime["default"], "drawer-front-1")
    wide = _width(wider, "drawer-front-1")
    assert wide > narrow, f"{narrow} mm -> {wide} mm"


def test_a_printed_part_comes_back_built_by_the_runtimes_modeller(runtime: dict[str, Any]) -> None:
    """The kernel crosses too: a part that is a body comes back with triangles, each named."""
    scene = runtime["printed"]
    assert scene["ok"] is True, scene.get("error")
    mesh = scene["parts"][0]["mesh"]
    assert mesh is not None, "the runtime's modeller built nothing"
    assert len(mesh["ref_index"]) > 100
    assert len(mesh["positions"]) == 9 * len(mesh["ref_index"])
    assert all(place <= len(mesh["refs"]) for place in mesh["ref_index"])
