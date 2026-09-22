"""Adapter: the scene JSON against the closed TypedDicts the browser is typed from.

The boundary here is the wire: :func:`bench.script.run` builds a scene, :func:`scene_json`
serialises it, and the app parses that text into the TypeScript mirror of
:mod:`bench.scene`'s TypedDicts. So every check runs the real example script, round-trips
it through JSON, and reads the result back against the types themselves - the required keys
come from ``__required_keys__`` and the field types from :func:`typing.get_type_hints`, so
a field added to :class:`~bench.scene.PartView` is checked the moment it is declared and
a field dropped from the scene builder fails here rather than in the browser.

``scene-fixture.json`` is the same parsed scene with the bulky text - ``files`` and every
sheet's ``svg`` - stored as lengths, so the TypeScript side has a small stable shape to
check against. Regenerate it with ``BENCH_UPDATE_FIXTURES=1 uv run pytest tests/adapter``.
"""

import json
import os
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints, is_typeddict

import pytest

from bench import script
from bench.scene import ErrorScene, Kind, OkScene
from bench.transport import scene_json

ROOT = Path(__file__).resolve().parents[2]
"""The repository root: the example and the fixture are read from it."""

EXAMPLE = ROOT / "examples" / "gridfinity_cabinet.py"
"""The script the app loads on a first visit - the scene every contract check is made of."""

FIXTURE = Path(__file__).with_name("scene-fixture.json")
"""The stored shape of the default scene, regenerated only when asked for."""

UPDATE = os.environ.get("BENCH_UPDATE_FIXTURES") == "1"
"""Whether this run rewrites :data:`FIXTURE` instead of checking against it."""

FILE_SUFFIXES = (".svg", ".dxf", ".scad")
"""What a downloadable file can be: cut sheets, per-part outlines, a printed baseplate."""


# ---- the scene under test ------------------------------------------------------------


def _scene(**overrides: object) -> dict[str, Any]:
    """The example script run for real, serialised, and parsed back as the browser gets it."""
    parsed = json.loads(scene_json(script.run(EXAMPLE.read_text(), overrides)))
    assert isinstance(parsed, dict), f"scene_json produced {type(parsed).__name__}, not an object"
    return parsed


def _ran(source: str) -> dict[str, Any]:
    """``source`` run for real and round-tripped, for the scripts that are meant to fail."""
    parsed = json.loads(scene_json(script.run(source)))
    assert isinstance(parsed, dict), f"scene_json produced {type(parsed).__name__}, not an object"
    return parsed


# ---- the scene read against its own types --------------------------------------------


def _problems(value: object, annotation: object, where: str) -> list[str]:
    """Everywhere ``value`` disagrees with ``annotation``, named by its path in the scene."""
    if is_typeddict(annotation):
        return _dict_problems(value, annotation, where)
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return _enum_problems(value, annotation, where)
    origin = get_origin(annotation)
    if origin is Literal:
        return _literal_problems(value, get_args(annotation), where)
    if origin is Union or origin is UnionType:
        return _union_problems(value, get_args(annotation), where)
    if origin is list:
        return _list_problems(value, get_args(annotation)[0], where)
    if origin is dict:
        return _table_problems(value, get_args(annotation)[1], where)
    return _scalar_problems(value, annotation, where)


def _dict_problems(value: object, shape: Any, where: str) -> list[str]:
    """``value`` against a closed TypedDict: every required key, no unknown key, and each
    field against what the type says it is."""
    if not isinstance(value, dict):
        return [f"{where} is {type(value).__name__}, not an object"]
    hints = get_type_hints(shape)
    required: frozenset[str] = shape.__required_keys__
    known = required | shape.__optional_keys__
    problems = [
        f"{where} is missing required key {key!r}" for key in sorted(required - value.keys())
    ]
    problems += [
        f"{where} has key {key!r}, and {shape.__name__} is closed"
        for key in sorted(value.keys() - known)
    ]
    for key in sorted(value.keys() & hints.keys()):
        problems += _problems(value[key], hints[key], f"{where}.{key}")
    return problems


def _enum_problems(value: object, kind: type[Enum], where: str) -> list[str]:
    """``value`` against an enum the scene carries as its own value: a :class:`~enum.StrEnum`
    member is a ``str`` when it is written, so what comes back out of JSON is that string."""
    allowed = {one.value for one in kind}
    if value in allowed:
        return []
    return [f"{where} is {value!r}, not one of {sorted(allowed)}"]


def _literal_problems(value: object, allowed: tuple[object, ...], where: str) -> list[str]:
    if any(_same(value, one) for one in allowed):
        return []
    return [f"{where} is {value!r}, not one of {allowed!r}"]


def _union_problems(value: object, branches: tuple[object, ...], where: str) -> list[str]:
    if any(not _problems(value, branch, where) for branch in branches):
        return []
    return [f"{where} is {value!r}, which is none of {_names(branches)}"]


def _list_problems(value: object, item: object, where: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{where} is {type(value).__name__}, not an array"]
    problems: list[str] = []
    for at, one in enumerate(value):
        problems += _problems(one, item, f"{where}[{at}]")
    return problems


def _table_problems(value: object, item: object, where: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{where} is {type(value).__name__}, not an object"]
    problems: list[str] = []
    for key, one in value.items():
        if not isinstance(key, str):
            problems.append(f"{where} is keyed by {key!r}, not a string")
        problems += _problems(one, item, f"{where}[{key!r}]")
    return problems


def _scalar_problems(value: object, annotation: object, where: str) -> list[str]:
    """``value`` against one of the types JSON has. ``bool`` is checked before ``int``
    because it is one, and an ``int`` stands in for a ``float`` because JSON drops the
    point off a round number."""
    if annotation is type(None):
        return [] if value is None else [f"{where} is {value!r}, not null"]
    if annotation is bool:
        return [] if isinstance(value, bool) else [f"{where} is {value!r}, not a bool"]
    if annotation is int:
        ok = isinstance(value, int) and not isinstance(value, bool)
        return [] if ok else [f"{where} is {value!r}, not an int"]
    if annotation is float:
        ok = isinstance(value, int | float) and not isinstance(value, bool)
        return [] if ok else [f"{where} is {value!r}, not a number"]
    if annotation is str:
        return [] if isinstance(value, str) else [f"{where} is {value!r}, not a string"]
    return [f"{where}: the test cannot read the annotation {annotation!r}"]


def _same(value: object, literal: object) -> bool:
    """Whether ``value`` is that literal, keeping ``True`` and ``1`` apart."""
    if isinstance(literal, bool) or isinstance(value, bool):
        return value is literal
    return bool(value == literal)


def _names(annotations: tuple[object, ...]) -> str:
    return ", ".join(getattr(one, "__name__", repr(one)) for one in annotations)


# ---- the shape the TypeScript side checks against ------------------------------------


def _shaped(scene: dict[str, Any]) -> dict[str, Any]:
    """``scene`` as the fixture stores it: the sheet SVGs, the downloadable files and every
    part's long lists by length, so the file stays small and a changed coordinate - or a
    chord more round a hole - does not rewrite it."""
    return dict(
        scene,
        parts=[_shaped_part(part) for part in scene["parts"]],
        sheets=[
            dict(sheet, svg=len(sheet["svg"]), preview=len(sheet["preview"]))
            for sheet in scene["sheets"]
        ],
        files={name: len(text) for name, text in scene["files"].items()},
    )


def _shaped_part(part: dict[str, Any]) -> dict[str, Any]:
    """A part with its mesh's and its marks' number lists written as their lengths."""
    mesh, marks = part["mesh"], part["marks"]
    return dict(
        part,
        mesh=None
        if mesh is None
        else dict(mesh, positions=len(mesh["positions"]), ref_index=len(mesh["ref_index"])),
        marks=None
        if marks is None
        else dict(marks, segments=len(marks["segments"]), ref_index=len(marks["ref_index"])),
    )


def _skeleton(value: object) -> object:
    """``value`` with every leaf replaced by the name of its JSON kind: what is compared
    when the fixture is checked, so keys, array lengths and kinds matter and the
    millimetres inside them do not."""
    match value:
        case dict():
            return {key: _skeleton(one) for key, one in value.items()}
        case list():
            return [_skeleton(one) for one in value]
        case bool():
            return "bool"
        case int() | float():
            return "number"
        case str():
            return "string"
        case None:
            return "null"
        case _:
            return f"unexpected {type(value).__name__}"


def _written(shape: dict[str, Any]) -> None:
    FIXTURE.write_text(json.dumps(shape, indent=2) + "\n")


# ---- the contract --------------------------------------------------------------------


@pytest.mark.adapter
def test_the_default_scene_is_an_ok_scene() -> None:
    scene = _scene()
    assert scene["ok"] is True, scene.get("error")
    assert _problems(scene, OkScene, "scene") == []


@pytest.mark.adapter
def test_an_override_crosses_the_json_boundary() -> None:
    """An override arrives as JSON, so it is read back as the default's type, and the scene
    it produces is still an ok scene."""
    scene = _scene(units_x="6")
    assert scene["ok"] is True, scene.get("error")
    assert scene["values"]["units_x"] == 6
    assert _problems(scene, OkScene, "scene") == []


@pytest.mark.adapter
def test_a_script_that_raises_is_an_error_scene_on_its_line() -> None:
    scene = _ran("from bench import *\n\nshow(1 / 0)\n")
    assert scene["ok"] is False
    assert _problems(scene, ErrorScene, "scene") == []
    assert scene["error"]["line"] == 3
    assert isinstance(scene["error"]["line"], int)


@pytest.mark.adapter
def test_a_script_that_shows_nothing_is_an_error_scene_with_no_line() -> None:
    scene = _ran("units = 4\n")
    assert scene["ok"] is False
    assert _problems(scene, ErrorScene, "scene") == []
    assert scene["error"]["line"] is None


@pytest.mark.adapter
def test_every_param_kind_is_in_the_closed_set() -> None:
    kinds = set(get_args(Kind))
    declared = [param["kind"] for param in _scene()["params"]]
    assert declared, "the example declares parameters; the scene lost them"
    assert set(declared) <= kinds, f"{sorted(set(declared) - kinds)} is not a kind"


@pytest.mark.adapter
def test_every_part_bbox_is_four_numbers() -> None:
    for part in _scene()["parts"]:
        box = part["bbox"]
        assert len(box) == 4, f"{part['ref']} has a bbox of {len(box)} numbers"
        assert all(isinstance(one, int | float) and not isinstance(one, bool) for one in box)
        assert box[0] <= box[2] and box[1] <= box[3], f"{part['ref']} has an inverted bbox"


@pytest.mark.adapter
def test_refs_are_unique() -> None:
    refs = _scene()["refs"]
    assert len(refs) == len(set(refs)), "the ref table the editor reads has duplicates"


@pytest.mark.adapter
def test_every_nested_part_is_a_part_of_the_scene() -> None:
    scene = _scene()
    parts = {part["ref"] for part in scene["parts"]}
    for sheet in scene["sheets"]:
        unknown = sorted(set(sheet["parts"]) - parts)
        assert not unknown, f"{sheet['name']} nests {unknown}, which the scene has no part for"


@pytest.mark.adapter
def test_every_file_is_a_sheet_a_part_or_a_baseplate() -> None:
    for name in _scene()["files"]:
        assert name.endswith(FILE_SUFFIXES), f"{name} is not one of {FILE_SUFFIXES}"


@pytest.mark.adapter
def test_the_scene_matches_the_stored_fixture() -> None:
    """The shape the TypeScript side is checked against. Run with ``BENCH_UPDATE_FIXTURES=1``
    to rewrite it; otherwise it is compared by keys, array lengths and JSON kinds, so the
    file only changes when the contract does."""
    shape = _shaped(_scene())
    if UPDATE:
        _written(shape)
    assert FIXTURE.exists(), (
        f"{FIXTURE.name} is missing; regenerate it with BENCH_UPDATE_FIXTURES=1"
    )
    assert _skeleton(json.loads(FIXTURE.read_text())) == _skeleton(shape)
