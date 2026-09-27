"""End to end: ``tools.qa --project NAME`` looks at a host project the way it looks at the
examples (task-79).

The command itself, run as a person runs it - its own process, its own browser, the built app
served by :mod:`tools.preview` - over a projects root holding the fixture project, with
``--out`` so it never clears a person's own ``web/qa/out``. Which scripts it picks is
functional-tested in ``tests/functional/test_qa_tool.py``; what only the whole walk can show is
here: every script named is opened and shot, the view and the Problems panel both; the
browser's modeller answered the kernel check rather than reading ``unchecked``; and the
project on disk is exactly as it was, since the walk is served off a copy of it.
"""

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests import fixture_project
from tools import preview
from tools.projects import VARIABLE

pytestmark = pytest.mark.e2e

try:
    import playwright.sync_api  # ruff: ignore[unused-import]  # the import is the check
except ImportError:
    pytest.skip("playwright is not installed - uv pip install playwright", allow_module_level=True)

if not (preview.WEB / "node_modules").is_dir():
    pytest.skip("web/node_modules missing - run npm ci in web/", allow_module_level=True)
if shutil.which("npx") is None:
    pytest.skip("npx not on PATH", allow_module_level=True)

WALK_SECONDS = 600
"""How long the whole look round may take: a boot of the app per script it visits."""


def _fingerprint(directory: Path) -> dict[str, str]:
    """Every file under ``directory``, by its path inside it, and a hash of what it holds."""
    return {
        str(one.relative_to(directory)): hashlib.sha256(one.read_bytes()).hexdigest()
        for one in sorted(directory.rglob("*"))
        if one.is_file()
    }


def test_a_look_round_of_a_project_shoots_each_script_and_leaves_it_untouched(
    tmp_path: Path, built_app: Path
) -> None:
    """AC#1 and AC#3: both of the fixture's scripts - the entry and the one beside it - are
    opened and shot as an example is, with the Problems panel on its own too; the entry's
    overhang is measured by the browser's modeller; and the project it read is unchanged."""
    root = tmp_path / "projects"
    directory = fixture_project.seeded(root)
    before = _fingerprint(directory)
    out = tmp_path / "out"

    done = subprocess.run(
        (
            sys.executable,
            "-m",
            "tools.qa",
            "--project",
            fixture_project.NAME,
            fixture_project.ENTRY,
            fixture_project.OTHER,
            "--out",
            str(out),
        ),
        cwd=preview.ROOT,
        env={**os.environ, VARIABLE: str(root)},
        capture_output=True,
        text=True,
        timeout=WALK_SECONDS,
        check=False,
    )

    assert done.returncode == 0, done.stdout[-4000:] + done.stderr[-4000:]
    shots = {one.name for one in out.glob("*.png")}
    for number, script in enumerate((fixture_project.ENTRY, fixture_project.OTHER), start=1):
        stem = f"qa-{number:02d}-{script.removesuffix('.py')}"
        for suffix in ("", "-problems", "-parameters", "-export"):
            assert f"{stem}{suffix}.png" in shots, sorted(shots)
    log = (out / "qa-log.txt").read_text()
    overhangs = [line for line in log.splitlines() if " violations " in line]
    assert overhangs, log
    assert any("warning overhangs" in line and "stand/cap" in line for line in overhangs)
    assert "unchecked" not in log
    assert _fingerprint(directory) == before
