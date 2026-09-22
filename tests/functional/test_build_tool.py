"""Functional: :mod:`tools.build`, the command-line host.

A script on disk, a TOML beside it, and what :func:`bench.script.run` makes of the pair. The
point of the tool is the seam - a file's values reaching a run as the overrides it already
takes - so that is what is asserted here, against real scripts rather than a double.
"""

import tomllib
from pathlib import Path

import pytest

from bench import Mesh, stl
from tools import build

pytestmark = pytest.mark.functional

SCRIPT = """\
from dataclasses import dataclass

from bench import *


@dataclass(frozen=True, slots=True, kw_only=True)
class Panel:
    w: float = knob(60.0, min=10.0, max=200.0, label="Width")
    d: float = knob(40.0, min=10.0, max=200.0, label="Depth")
    tag: str = knob("plate", label="What to call it")


def build_it(p: Panel) -> Part:
    print(f"{p.tag} {p.w:.0f} x {p.d:.0f}")
    return part(p.tag, fill(rect(p.w, p.d)), Stock(3, "ply"))


show(build_it)
"""


def _project(at: Path, toml: str | None = None) -> Path:
    """A script on disk, with a values file beside it when one is asked for."""
    script = at / "panel.py"
    script.write_text(SCRIPT)
    if toml is not None:
        script.with_suffix(".toml").write_text(toml)
    return script


def _foot_stl(at: Path) -> None:
    """The systainer foot's box, decision-4's own example, written as a binary STL."""
    vertices = (
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
    )
    triangles = (0, 1, 2, 0, 2, 3, 4, 5, 6, 4, 6, 7)
    at.write_bytes(stl(Mesh(vertices, triangles, (None, None, None, None))))


_REFERENCE_TOML = "[reference]\nfile = 'obj_2.stl'\norigin = 'low'\nup = '+Z'\nalong = '+X'\n"


def test_a_script_with_nothing_beside_it_runs_on_its_own_defaults(tmp_path: Path) -> None:
    """The file is optional, which is what keeps every example working as it does today."""
    script = _project(tmp_path)

    assert build.values_beside(script) == {}
    assert build.main((str(script),)) == 0


def test_the_values_beside_a_script_are_what_it_builds(tmp_path: Path) -> None:
    script = _project(tmp_path, "[values]\nw = 120.0\ntag = 'lid'\n")

    assert build.values_beside(script) == {"w": 120.0, "tag": "lid"}


def test_a_field_the_file_leaves_out_keeps_its_default(tmp_path: Path) -> None:
    """The dataclass declares and provides the fallback; the file says which one you build."""
    script = _project(tmp_path, "[values]\nw = 120.0\n")
    values = build.values_beside(script)

    assert "d" not in values, "the file says nothing about depth"
    assert build.main((str(script),)) == 0


def test_a_file_with_no_values_table_is_not_a_mistake(tmp_path: Path) -> None:
    """A project may hold other tables - measurements, one day - and say nothing about
    parameters."""
    script = _project(tmp_path, "[measured]\nwall = 2.4\n")

    assert build.values_beside(script) == {}


def test_a_file_that_is_not_toml_says_so_and_names_itself(tmp_path: Path) -> None:
    """Rather than losing every value in it to a typed comma."""
    script = _project(tmp_path, "[values\nw = 120.0\n")

    with pytest.raises(ValueError, match=r"panel\.toml"):
        build.values_beside(script)


def test_a_values_table_that_is_not_a_table_is_refused(tmp_path: Path) -> None:
    script = _project(tmp_path, "values = 3\n")

    with pytest.raises(ValueError, match="not a table"):
        build.values_beside(script)


def test_a_value_its_field_cannot_read_is_refused_by_name(tmp_path: Path) -> None:
    """`configured` raises naming the field, `run` turns that into an error scene, and the
    tool reports it and answers non-zero rather than pretending it built something."""
    script = _project(tmp_path, "[values]\nw = 'wide'\n")

    assert build.main((str(script),)) == 1


def test_a_script_that_is_not_there_is_said_rather_than_traced(tmp_path: Path) -> None:
    assert build.main((str(tmp_path / "nothing.py"),)) == 1


def test_no_arguments_prints_what_the_tool_is_for(tmp_path: Path) -> None:
    assert build.main(()) == 1


def test_what_a_run_made_can_be_written_out(tmp_path: Path) -> None:
    """The reason to have this at all: a cut sheet without opening a browser."""
    script = _project(tmp_path)
    out = tmp_path / "out"

    assert build.main((str(script), "--out", str(out))) == 0
    made = sorted(one.name for one in out.iterdir())
    assert made, "a run that nested a part wrote nothing"
    assert any(one.endswith(".svg") for one in made), made


def test_a_written_sheet_is_the_svg_the_run_made(tmp_path: Path) -> None:
    script = _project(tmp_path)
    out = tmp_path / "out"
    build.main((str(script), "--out", str(out)))

    svg = next(one for one in out.iterdir() if one.suffix == ".svg")
    assert svg.read_text().lstrip().startswith("<?xml") or "<svg" in svg.read_text()


def test_the_toml_shape_is_the_one_the_decision_describes(tmp_path: Path) -> None:
    """Guards the file format itself: `[values]`, flat, scalars - what a panel edit would
    write back and what a person would type by hand."""
    script = _project(tmp_path, "[values]\nw = 120.0\nd = 80.0\ntag = 'lid'\n")
    whole = tomllib.loads(script.with_suffix(".toml").read_text())

    assert set(whole) == {"values"}
    assert all(not isinstance(one, dict) for one in whole["values"].values())


def test_a_project_with_no_reference_table_places_nothing(tmp_path: Path) -> None:
    """task-26 criterion #3: a project that says nothing about a placement behaves exactly as
    it does today."""
    script = _project(tmp_path)

    assert build.reference_beside(script) is None
    assert build.main((str(script),)) == 0


def test_the_reference_table_is_what_tools_build_reads(tmp_path: Path) -> None:
    script = _project(tmp_path, _REFERENCE_TOML)

    assert build.reference_beside(script) == {
        "file": "obj_2.stl",
        "origin": "low",
        "up": "+Z",
        "along": "+X",
    }


def test_a_reference_table_with_no_file_is_not_a_mistake(tmp_path: Path) -> None:
    """A project may hold `[values]` and nothing about a reference, exactly as `values_beside`
    treats a file with no `[values]`."""
    script = _project(tmp_path, "[values]\nw = 120.0\n")

    assert build.reference_beside(script) is None


def test_a_reference_table_places_the_stl_and_prints_the_frame(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """decision-4's rule: the host says what it did."""
    script = _project(tmp_path, _REFERENCE_TOML)
    _foot_stl(script.parent / "obj_2.stl")

    assert build.main((str(script),)) == 0
    out = capsys.readouterr().out
    assert "panel.toml: reference=obj_2.stl" in out
    assert "origin=(606.795, -116.868, 0.000)" in out
    assert "up=(0.000, 0.000, 1.000)" in out
    assert "along=(1.000, 0.000, 0.000)" in out


def test_a_reference_naming_a_file_that_is_not_there_is_refused(tmp_path: Path) -> None:
    """`placement`'s own `ValueError` is caught the same way a value a field cannot read is -
    named and answered `1`, not traced."""
    script = _project(tmp_path, _REFERENCE_TOML)

    assert build.main((str(script),)) == 1


def test_a_reference_table_that_is_not_a_table_is_refused(tmp_path: Path) -> None:
    script = _project(tmp_path, "reference = 3\n")

    with pytest.raises(ValueError, match="not a table"):
        build.reference_beside(script)
