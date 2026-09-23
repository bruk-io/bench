"""End to end: task-50 - a script in the browser can import another module beside it, and an
import naming a module that is not in the project fails saying so.

Follows ``tests/e2e/test_project_directory.py``'s own pattern: the built app served over a
projects root of its own, seeded with real files on disk, driven with a real browser. What the
worker does with a project's other scripts is unit-tested in
``tests/functional/test_worker.py``; what only a real browser against the real route and the
real Pyodide runtime can show is here - a two-file project running (AC#3), and the message a
missing import fails with, on screen rather than only in a console (AC#5).
"""

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tools import preview
from tools.projects import VARIABLE

pytestmark = pytest.mark.e2e

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page

try:
    import playwright.sync_api  # ruff: ignore[unused-import]  # the import is the check
except ImportError:
    pytest.skip("playwright is not installed - uv pip install playwright", allow_module_level=True)

if not (preview.WEB / "node_modules").is_dir():
    pytest.skip("web/node_modules missing - run npm ci in web/", allow_module_level=True)
if shutil.which("npx") is None:
    pytest.skip("npx not on PATH", allow_module_level=True)

BOOT_MS = 240_000

OUT = preview.WEB / "e2e" / "out"

DRAWN = "#canvas3d[data-bodies]:not([data-bodies='0'])"

BODIES = "() => Number(document.querySelector('#canvas3d')?.dataset.bodies ?? 0)"

ENTRY = (
    "from bench import *\n"
    "import parts\n\n"
    "show(tuple(part(f'p{i}', face(rect(60, 40)), Stock(3, 'ply')) for i in range(parts.N)))\n"
)
"""An entry that imports a sibling module for the one number it builds with - the minimal
case ``[project] entry`` exists for (decision-9 step 9)."""

MISSING = (
    "from bench import *\nimport sidekick\n\nshow(part('p', face(rect(60, 40)), Stock(3, 'ply')))\n"
)
"""An entry that imports a module the project does not hold."""


@contextmanager
def _hosted(root: Path) -> Iterator[str]:
    """The built app over the projects root ``root``."""
    with preview.served(env={VARIABLE: str(root)}) as url:
        yield url


def _opened(browser: Browser, url: str) -> Page:
    context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    page = context.new_page()
    page.goto(url)
    _rendered(page)
    return page


def _settled(page: Page) -> None:
    page.wait_for_function(
        "() => document.querySelector('#state')?.dataset.state !== 'running'", timeout=BOOT_MS
    )


def _rendered(page: Page) -> None:
    page.wait_for_selector(DRAWN, timeout=BOOT_MS)
    _settled(page)


def _bodies(page: Page) -> int:
    found = page.evaluate(BODIES)
    assert isinstance(found, int)
    return found


def _seed(root: Path, project: str, files: dict[str, str]) -> Path:
    directory = root / project
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (directory / name).write_text(text)
    return directory


def _shot(page: Page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / name))


def test_a_two_file_projects_entry_imports_its_sibling_module(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    """AC#3: a fresh open runs the entry (AC#4), and the entry's ``import parts`` reaches the
    ``parts.py`` beside it - the same project a script cannot be more than one file without,
    before this task."""
    root = tmp_path / "projects"
    _seed(
        root,
        "widget",
        {
            "entry.py": ENTRY,
            "parts.py": "N = 2\n",
            "bench.toml": '[project]\nentry = "entry.py"\n\n[values]\n',
        },
    )
    with _hosted(root) as url:
        page = _opened(browser, url)
        assert page.locator("#tab-script").inner_text().strip() == "entry.py"
        assert _bodies(page) == 2, "the entry did not see parts.N through its own import"
        _shot(page, "task50-two-file-project.png")
        page.context.close()


def test_an_import_naming_a_module_not_in_the_project_fails_saying_so(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    """AC#5: not a raw ``ModuleNotFoundError`` buried in the console - the run catches it the
    way any other exception a script raises is caught, and the Problems panel names the
    module that was not there."""
    root = tmp_path / "projects"
    _seed(root, "widget", {"entry.py": MISSING})
    with _hosted(root) as url:
        # Not `_opened`: it waits for a body on screen, which a failed run never draws.
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        page = context.new_page()
        page.goto(url)
        page.wait_for_selector('#state[data-state="error"]', timeout=BOOT_MS)
        error = page.locator("#error")
        error.first.wait_for(timeout=BOOT_MS)
        assert "No module named 'sidekick'" in error.inner_text()
        _shot(page, "task50-missing-module.png")
        context.close()
