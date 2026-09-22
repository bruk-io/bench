"""Functional: a plate answers to the refs its cut paths already carry, in every example.

The promise that let the flat drawing become an export: a laser part drawn as a plate is
clicked the way its cut file names it. So every shipped script, and the one a new file starts
as, is run with no kernel, and for each laser part two things are read off the scene itself -
the refs its plate, its engraved lines and its lettering answer to, and the ``data-ref`` on
every path of its own SVG - and held to each other: nothing on the plate is a name the scene
does not have, and nothing the cut file names is missing from the plate.
"""

import re
from pathlib import Path

import pytest

from bench import run
from bench.scene import OkScene, PartView

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[2]

SCRIPTS = (*sorted((ROOT / "examples").glob("*.py")), ROOT / "templates" / "untitled.py")

_DATA_REF = re.compile(r'data-ref="([^"]+)"')


def _ok(path: Path) -> OkScene:
    scene = run(path.read_text())
    if not scene["ok"]:
        pytest.fail(f"{path.name}: {scene['error']['message']}")
    return scene


def _plate_refs(part: PartView) -> set[str]:
    mesh, marks = part["mesh"], part["marks"]
    assert mesh is not None, f"{part['ref']} is a laser part with no plate"
    found = set(mesh["refs"])
    if marks is not None:
        found |= set(marks["refs"])
    return found | {one["ref"] for one in part["lettering"] if one["ref"] is not None}


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda path: path.name)
def test_every_plate_answers_only_to_refs_the_scene_names(path: Path) -> None:
    scene = _ok(path)
    named = set(scene["refs"])
    for part in scene["parts"]:
        if part["process"] != "laser":
            continue
        stray = _plate_refs(part) - named
        assert not stray, f"{part['ref']}: {sorted(stray)}"


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda path: path.name)
def test_every_ref_a_cut_path_carries_is_on_its_plate(path: Path) -> None:
    """On a wall itself, or on the walls of the edges named under it - a wire whose edges all
    have names of their own is clicked edge by edge. The part's own ref is what an unnamed
    triangle already means, so it needs no triangle of its own."""
    scene = _ok(path)
    for part in scene["parts"]:
        if part["process"] != "laser":
            continue
        on_plate = _plate_refs(part)
        cut = set(_DATA_REF.findall(scene["files"][f"part-{part['label']}.svg"])) - {part["ref"]}
        missing = {
            ref
            for ref in cut
            if ref not in on_plate and not any(one.startswith(f"{ref}/") for one in on_plate)
        }
        assert not missing, f"{part['ref']}: {sorted(missing)}"
