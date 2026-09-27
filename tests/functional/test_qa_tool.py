"""Functional: :mod:`tools.qa`'s own output hygiene.

A look round writes screenshots as it walks and a log beside them - see :func:`tools.qa._said`
and :data:`tools.qa.LOG`. A walk that raises before it finishes never reaches a line that
rewrites that log, so without :func:`tools.qa._reset` an old, unrelated walk's log stays behind
next to this walk's fresh screenshots - two runs that look like one and do not agree, which is
`task-53`'s own bug: a stale ``qa-log.txt`` from an earlier walk of `systainer_tote.py` sitting
beside a fresh, unrelated screenshot of `gridfinity_bin.py`, misread as one run.
"""

from pathlib import Path

import pytest

from tests import fixture_project
from tools.projects import VARIABLE
from tools.qa import _project_stops, _reset, main

pytestmark = pytest.mark.functional


def test_a_stale_log_does_not_survive_a_fresh_walk(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    stale_log = out / "qa-log.txt"
    stale_log.write_text("violations     warning overhangs: ... (tote/socket-1, line 257)\n")
    stale_shot = out / "qa-01-systainer_tote.png"
    stale_shot.write_bytes(b"stale")

    _reset(out)

    assert list(out.iterdir()) == []


def test_a_look_round_with_nothing_behind_it_is_left_alone(tmp_path: Path) -> None:
    """A fresh :data:`tools.qa.OUT` - the common case - is not a failure to clear."""
    out = tmp_path / "out"

    _reset(out)  # does not raise on a directory that does not exist yet

    assert not out.exists()


# ---- --project: which scripts of a host project a look round visits (task-79) -------------


def test_a_project_with_nothing_named_is_visited_at_its_declared_entry(tmp_path: Path) -> None:
    """The entry by the app's own rule - ``bench.toml``'s ``[project] entry``, which the
    fixture names something other than the directory - and the directory itself."""
    root = tmp_path / "projects"
    directory = fixture_project.seeded(root)

    found = _project_stops(fixture_project.NAME, (), {VARIABLE: str(root)})

    assert found == (directory, (fixture_project.ENTRY,))


def test_the_scripts_named_are_visited_in_order_with_py_supplied(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    fixture_project.seeded(root)
    other = fixture_project.OTHER.removesuffix(".py")

    _, stops = _project_stops(
        fixture_project.NAME, (other, fixture_project.ENTRY), {VARIABLE: str(root)}
    )

    assert stops == (fixture_project.OTHER, fixture_project.ENTRY)


def test_a_project_or_script_that_is_not_there_is_refused_before_anything_is_built(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Said and answered ``1`` up front - not a build of the app and a browser left waiting
    for a script the route will never serve."""
    root = tmp_path / "projects"
    fixture_project.seeded(root)
    environ = {VARIABLE: str(root)}
    out = tmp_path / "out"

    assert main(("--project", "nothing", "--out", str(out)), environ) == 1
    assert "there is no project at" in capsys.readouterr().err
    assert main(("--project", fixture_project.NAME, "gone.py", "--out", str(out)), environ) == 1
    assert "probe has no gone.py" in capsys.readouterr().err
    assert main(("--project", "..", "--out", str(out)), environ) == 1
    assert main(("--project",), environ) == 1
    assert main(("--out",), environ) == 1
    assert not out.exists()
