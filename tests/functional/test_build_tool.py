"""Functional: :mod:`tools.build`, the command-line host.

A script on disk, a TOML beside it, and what :func:`bench.script.run` makes of the pair. The
point of the tool is the seam - a file's values reaching a run as the overrides it already
takes - so that is what is asserted here, against real scripts rather than a double.
"""

import tomllib
from pathlib import Path

import pytest

from bench import Mesh, stl
from tools import build, projects

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


def test_a_reference_table_that_only_names_the_active_mesh_hands_it_over_as_exported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """task-49: `[reference]` names the project's active mesh whether or not it is placed yet,
    and one that is only named is the mesh as exported - not a placement missing its keys."""
    script = _project(tmp_path, '[reference]\nfile = "obj_2.stl"\n')
    _foot_stl(script.parent / "obj_2.stl")

    assert build.main((str(script),)) == 0
    out = capsys.readouterr().out
    assert "panel.toml: reference=obj_2.stl as exported, not placed" in out


def test_a_reference_table_placing_only_in_part_is_still_refused(tmp_path: Path) -> None:
    """Naming is the table with no placing key at all; one with some of them is a placement,
    and `placement` refuses it for what it lacks."""
    script = _project(tmp_path, '[reference]\nfile = "obj_2.stl"\norigin = "low"\n')
    _foot_stl(script.parent / "obj_2.stl")

    assert build.main((str(script),)) == 1


def test_a_reference_naming_a_file_that_is_not_there_is_refused(tmp_path: Path) -> None:
    """`placement`'s own `ValueError` is caught the same way a value a field cannot read is -
    named and answered `1`, not traced."""
    script = _project(tmp_path, _REFERENCE_TOML)

    assert build.main((str(script),)) == 1


def test_a_reference_table_that_is_not_a_table_is_refused(tmp_path: Path) -> None:
    script = _project(tmp_path, "reference = 3\n")

    with pytest.raises(ValueError, match="not a table"):
        build.reference_beside(script)


# ---- the projects root: the one the app's route serves -----------------------------------


def test_a_project_under_the_root_is_run_by_name(tmp_path: Path) -> None:
    """`--project` reads the script from the root `BENCH_PROJECTS` names - the directory the
    app's route serves, resolved by the same rule - so the two cannot disagree about which
    file a project's script is."""
    root = tmp_path / "projects"
    (root / "panel").mkdir(parents=True)
    _project(root / "panel", "[values]\nw = 120.0\n")

    environ = {projects.VARIABLE: str(root)}
    assert build.main(("--project", "panel", "panel.py"), environ) == 0
    assert build.main(("panel.py", "--project", "panel"), environ) == 0
    assert build.main(("--project", "panel", "nothing.py"), environ) == 1


def test_a_project_or_script_that_is_not_a_plain_name_is_refused(tmp_path: Path) -> None:
    """The route's rule, kept on the command line too: a name, never a path."""
    root = tmp_path / "projects"
    (root / "panel").mkdir(parents=True)
    _project(tmp_path)
    environ = {projects.VARIABLE: str(root)}

    assert build.main(("--project", "..", "panel.py"), environ) == 1
    assert build.main(("--project", "panel", "../../panel.py"), environ) == 1
    assert build.main(("--project", ".hidden", "panel.py"), environ) == 1
    with pytest.raises(ValueError, match="plain name"):
        projects.project_file("panel", "a\x00.py", environ)


def test_the_root_is_the_default_unless_named_and_never_relative() -> None:
    assert projects.projects_root({}) == projects.DEFAULT
    assert projects.projects_root({projects.VARIABLE: ""}) == projects.DEFAULT
    assert projects.projects_root({projects.VARIABLE: "/srv/projects"}) == Path("/srv/projects")
    with pytest.raises(ValueError, match="absolute"):
        projects.projects_root({projects.VARIABLE: "projects"})


# ---- a directory as the project, task-50 -----------------------------------------------


def _two_files(at: Path, helper_w: float = 10.0) -> tuple[Path, Path]:
    """A project of two files: an entry that imports a sibling module for the one number it
    builds with, and the module itself - the minimal case `[project] entry` exists for."""
    entry = at / "entry.py"
    entry.write_text(
        "from bench import *\n"
        "import helper\n\n"
        "show(part('p', fill(rect(helper.W, helper.W)), Stock(3, 'ply')))\n"
    )
    (at / "helper.py").write_text(f"W = {helper_w}\n")
    return entry, at / "helper.py"


def test_a_directory_with_bench_toml_runs_its_declared_entry(tmp_path: Path) -> None:
    """AC#1: `[project] entry` says which script runs, `[values]` is what it builds with."""
    project = tmp_path / "cabinet"
    project.mkdir()
    (project / "cabinet.py").write_text(SCRIPT)
    (project / "bench.toml").write_text('[project]\nentry = "cabinet.py"\n\n[values]\nw = 90.0\n')

    assert build.main((str(project),)) == 0
    assert build.values_beside(project / "cabinet.py") == {"w": 90.0}


def test_a_directory_with_no_bench_toml_and_one_script_reads_its_own_toml(tmp_path: Path) -> None:
    """decision-3's older shape, task-46 AC#3's rule kept for the command line: a directory
    with no `bench.toml` still opens, on its one script's own `<script>.toml`."""
    project = tmp_path / "panel"
    project.mkdir()
    _project(project, "[values]\nw = 77.0\n")

    assert build.main((str(project),)) == 0
    assert build.values_beside(project / "panel.py") == {"w": 77.0}


def test_a_directory_with_an_unknown_table_is_not_an_error(tmp_path: Path) -> None:
    project = tmp_path / "cabinet"
    project.mkdir()
    (project / "cabinet.py").write_text(SCRIPT)
    (project / "bench.toml").write_text(
        '[project]\nentry = "cabinet.py"\n\n[measured]\nwall = 2.4\n'
    )

    assert build.main((str(project),)) == 0


def test_project_name_alone_runs_the_entry(tmp_path: Path) -> None:
    """`--project NAME` with no script named is the same as passing the directory - task-50's
    answer to what `--project` becomes: a fresh open of the app, from the command line."""
    root = tmp_path / "projects"
    project = root / "cabinet"
    project.mkdir(parents=True)
    (project / "cabinet.py").write_text(SCRIPT)
    (project / "bench.toml").write_text('[project]\nentry = "cabinet.py"\n\n[values]\nw = 55.0\n')
    environ = {projects.VARIABLE: str(root)}

    assert build.main(("--project", "cabinet"), environ) == 0
    assert build.values_beside(project / "cabinet.py") == {"w": 55.0}


def test_a_declared_entry_not_among_the_scripts_falls_back(tmp_path: Path) -> None:
    """Mirrors `web/src/project-files.ts`'s `entryOf`: a declared entry naming a file that is
    not there falls back to the script named for the directory, or the first by name - it
    does not refuse the directory."""
    project = tmp_path / "cabinet"
    project.mkdir()
    (project / "cabinet.py").write_text(SCRIPT)
    (project / "bench.toml").write_text('[project]\nentry = "gone.py"\n')

    assert build.main((str(project),)) == 0


def test_a_two_file_project_imports_its_sibling_module(tmp_path: Path) -> None:
    """AC#3: a script can import another module beside it - the command line's half, which
    `web/src/worker.py` mirrors for the browser."""
    project = tmp_path / "widget"
    project.mkdir()
    _two_files(project)

    assert build.main((str(project),)) == 0


def test_a_project_or_script_import_that_is_not_there_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC#5: not a raw `ModuleNotFoundError` buried in stderr - the run catches it the way
    every other exception a script raises is caught, and it is printed with the run's other
    output, naming the module."""
    project = tmp_path / "widget"
    project.mkdir()
    entry = project / "entry.py"
    entry.write_text(
        "from bench import *\nimport helper\n\nshow(part('p', fill(rect(1, 1)), Stock(3, 'ply')))\n"
    )

    assert build.main((str(entry),)) == 1
    out = capsys.readouterr().out
    assert "No module named 'helper'" in out


def test_a_project_file_that_would_shadow_the_standard_library_is_refused(
    tmp_path: Path,
) -> None:
    """AC#3-5: a project module cannot shadow `bench` or the stdlib silently - refused by
    name, before anything is mounted, rather than quietly answering with the wrong module."""
    project = tmp_path / "widget"
    project.mkdir()
    (project / "entry.py").write_text(SCRIPT.replace("panel.py", "entry.py"))
    (project / "os.py").write_text("X = 1\n")

    assert build.main((str(project / "entry.py"),)) == 1


def test_a_project_named_bench_is_refused_too(tmp_path: Path) -> None:
    project = tmp_path / "widget"
    project.mkdir()
    (project / "entry.py").write_text(SCRIPT)
    (project / "bench.py").write_text("X = 1\n")

    assert build.main((str(project / "entry.py"),)) == 1


def test_two_projects_with_a_same_named_helper_do_not_leak_into_each_other(
    tmp_path: Path,
) -> None:
    """The risk a shared `sys.modules` cache creates: two projects, each with its own
    `helper.py`, run back to back must each see its own, not the one imported first."""
    first = tmp_path / "a"
    second = tmp_path / "b"
    first.mkdir()
    second.mkdir()
    _two_files(first, helper_w=10.0)
    _two_files(second, helper_w=20.0)

    scene_a = build.main((str(first / "entry.py"),))
    scene_b = build.main((str(second / "entry.py"),))
    assert scene_a == 0
    assert scene_b == 0
    # Run the first again after the second: if `helper` were left in `sys.modules`, this would
    # come back holding the second project's `W` instead of the first's.
    import sys

    assert "helper" not in sys.modules


def test_a_run_writes_no_bytecode_into_the_project_directory(tmp_path: Path) -> None:
    """A `__pycache__` under a maker's project is not this tool's file to leave there."""
    project = tmp_path / "widget"
    project.mkdir()
    _two_files(project)

    assert build.main((str(project / "entry.py"),)) == 0
    assert not (project / "__pycache__").exists()
