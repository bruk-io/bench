"""Adapter: ``tools.build --modeller`` runs a host project with the shipped modeller (task-79).

Without the flag, ``tools.build`` loads no kernel and every check that has to measure a body
reads ``unchecked`` - ``tests/functional/test_build_tool.py`` pins that. With it, the same
project is run the way the app runs it: :func:`bench.script.run` inside the pinned Pyodide,
with the app's own Manifold modeller as its kernel, on :mod:`tools.stack`. Nothing stands in
for any of it - the fixture project is written to disk, resolved by ``--project`` under a
projects root of the test's own, and its entry's ``import sizes`` reaches the sibling module
written beside ``bench`` in the runtime.

What is asserted is that the check *answered*, not the words it answered in: the overhang
check is being reworded elsewhere, and the point here is only that nothing reads
``unchecked`` any more and a body came back to write.
"""

from pathlib import Path

import pytest

from bench import Mesh, stl
from bench.script import run
from tests import fixture_project
from tools import build, projects, stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)


def test_a_projects_kernel_check_reports_with_the_modeller(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC#2: the stand's cap overhangs its post, and with the modeller the overhang check
    measures it and says so - a warning naming the cap - rather than reading ``unchecked``;
    ``--out`` writes the printed body the kernel meshed."""
    root = tmp_path / "projects"
    fixture_project.seeded(root)
    out = tmp_path / "out"

    code = build.main(
        ("--project", fixture_project.NAME, build.MODELLER, "--out", str(out)),
        {projects.VARIABLE: str(root)},
    )

    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "unchecked" not in printed
    assert build.MODELLER not in printed
    found = [line for line in printed.splitlines() if " overhangs " in line]
    assert found, printed
    assert all(line.strip().startswith(("warning", "error")) for line in found)
    assert any("stand/cap" in line for line in found)
    assert any(one.suffix == ".stl" and one.stat().st_size > 0 for one in out.iterdir())


_REFERENCED = """\
from bench import *

xs, zs = reference.vertices[0::3], reference.vertices[2::3]
print(f"x {min(xs):.3f}..{max(xs):.3f} z {min(zs):.3f}..{max(zs):.3f}")
show(part("plate", fill(rect(20, 20)), Stock(3, "ply")))
"""
"""A script that says where the body it was handed sits - so a reference placed inside the
runtime can be held against the same reference placed out here."""


def test_a_reference_is_placed_inside_the_runtime_as_it_is_out_here(tmp_path: Path) -> None:
    """A placed mesh cannot cross into Pyodide, so the modeller's run is handed the STL's
    bytes and its table and places it there: the body the script sees must sit exactly where
    the plain run's :func:`tools.build._reference_placed` puts it - decision-4's placement,
    once on each side."""
    directory = tmp_path / "held"
    directory.mkdir()
    script = directory / "held.py"
    script.write_text(_REFERENCED)
    # The systainer foot's box, decision-4's own example, well away from the origin - so a
    # placement that did nothing would print different numbers from one that moved it.
    corners = (
        (606.795, -116.868, 0.0),
        (651.795, -116.868, 0.0),
        (651.795, -78.868, 0.0),
        (606.795, -78.868, 0.0),
        (606.795, -116.868, 6.8),
        (651.795, -116.868, 6.8),
        (651.795, -78.868, 6.8),
        (606.795, -78.868, 6.8),
    )
    vertices = tuple(one for corner in corners for one in corner)
    triangles = (0, 1, 2, 0, 2, 3, 4, 5, 6, 4, 6, 7)
    (directory / "foot.stl").write_bytes(stl(Mesh(vertices, triangles, (None,) * 4)))
    table: dict[str, object] = {"file": "foot.stl", "origin": "low", "up": "+Z", "along": "+X"}

    modelled = build._modelled(script, {}, table, directory)
    plain = run(_REFERENCED, reference=build._reference_placed(script, table)[0])

    assert modelled["ok"], modelled
    assert plain["ok"], plain
    assert modelled["stdout"] == plain["stdout"]
    assert modelled["stdout"].startswith("x 0.000..45.000")
