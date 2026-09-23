"""End to end: task-48 - the sidebar's Projects list becomes a switcher and the open project's tree.

decision-9's split, driven against a real host: the container lists what is *in* the open
project - ``bench.toml``, its scripts, the meshes dropped into it - and another project is one
control above it (AC#1, AC#2). A row opens in the editor group, a second script included
(AC#3); rename, duplicate and delete act on the row they are asked of, not on whatever is open
(AC#4); and a delete says where the files go on the host and puts them there - the root's
``.trash/`` - rather than unlinking anything (AC#5). The read-only half (AC#6) is driven beside
the lease, in ``test_write_lease.py``, and the files story in ``test_app.py`` drives the
switcher's own New, rename, delete, duplicate and download (AC#8).
"""

import contextlib
import re
import shutil
import time
from collections.abc import Callable, Iterator
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

PLATES = (
    "from bench import *\n\n"
    "show(tuple(part(f'p{{i}}', face(rect(60, 40)), Stock(3, 'ply')) for i in range({n})))\n"
)
"""A script that makes ``n`` plates, so which script ran can be read off the view's count."""

BODIES = "() => Number(document.querySelector('#canvas3d')?.dataset.bodies ?? 0)"


def _mesh() -> bytes:
    """A 60 x 40 x 3 plate as the binary STL a maker would drop - ``test_project_directory``'s."""
    from bench import Stock, fill, part, rect, stl
    from bench.plates import plate

    swept = plate(part("foot", fill(rect(60, 40)), Stock(3, "ply")))
    assert swept is not None, "the foot did not sweep as a plate"
    return stl(swept.mesh)


@contextlib.contextmanager
def _page(browser: Browser, root: Path) -> Iterator[Page]:
    """The built app over ``root``, booted and drawn, with the project container open."""
    with preview.served(env={VARIABLE: str(root)}) as url:
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        page = context.new_page()
        page.goto(url)
        _drawn(page)
        page.click("#rail-files")
        try:
            yield page
        finally:
            context.close()


def _drawn(page: Page) -> None:
    page.wait_for_selector("#canvas3d[data-bodies]:not([data-bodies='0'])", timeout=BOOT_MS)
    page.wait_for_function(
        "() => document.querySelector('#state')?.dataset.state !== 'running'", timeout=BOOT_MS
    )


def _seeded(tmp_path: Path) -> Path:
    """A root with ``cabinet`` - two scripts, its document, a mesh - and ``bracket`` beside it."""
    root = tmp_path / "projects"
    cabinet = root / "cabinet"
    cabinet.mkdir(parents=True)
    (cabinet / "cabinet.py").write_text(PLATES.format(n=1))
    (cabinet / "parts.py").write_text(PLATES.format(n=3))
    (cabinet / "bench.toml").write_text('[project]\nentry = "cabinet.py"\n')
    (cabinet / "foot.stl").write_bytes(_mesh())
    (root / "bracket").mkdir()
    (root / "bracket" / "bracket.py").write_text(PLATES.format(n=2))
    return root


def _tree(page: Page) -> list[str]:
    """The rows of the open project's tree, by file name."""
    return [
        str(one.get_attribute("data-file"))
        for one in page.locator("bench-explorer .list[aria-label^='Files'] .file").all()
    ]


def _act(page: Page, row: str, action: str) -> None:
    page.locator(f'bench-explorer [aria-label="Actions for {row}"]').click()
    page.locator("bench-explorer .acts button", has_text=action).click()


def _bodies_are(page: Page, count: int) -> None:
    page.wait_for_function(f"() => ({BODIES})() === {count}", timeout=BOOT_MS)


def _trashed(root: Path) -> set[str]:
    """Everything in the root's trash, as ``<project>/<file>`` with the time taken off - and
    the ``-2`` a second delete inside one second adds."""
    trash = root / ".trash"
    if not trash.is_dir():
        return set()
    found: set[str] = set()
    for one in trash.rglob("*"):
        if one.is_file():
            folder = one.relative_to(trash).parts[0]
            # 20260923-101503-cabinet(-2) -> cabinet
            project = re.sub(r"-\d+$", "", folder.split("-", 2)[2])
            found.add(f"{project}/{one.name}")
    return found


# ---- AC#1, AC#2, AC#3: the tree, the switcher, and a row opening in the editor group -------


def test_the_container_is_the_open_projects_files_and_another_project_is_one_control(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = _seeded(tmp_path)
    with _page(browser, root) as page:
        assert page.locator("#head-files").text_content() == "Project"
        assert page.locator("#project-switcher").inner_text().strip() == "bracket"
        assert _tree(page) == ["bench.toml", "bracket.py"]
        assert page.locator("bench-explorer #projects").is_hidden()

        page.click("#project-switcher")
        rows = page.locator("bench-explorer .project").all_inner_texts()
        assert [row.strip() for row in rows] == ["bracket", "cabinet"]
        page.locator("bench-explorer .project", has_text="cabinet").click()
        _bodies_are(page, 1)
        assert page.locator("bench-explorer #projects").is_hidden()
        # Its own files: the document, the entry first, the other script, and the mesh as a
        # reference - none of them another project.
        page.wait_for_function(
            "() => document.querySelector('bench-explorer')?.files.meshes.length === 1",
            timeout=15_000,
        )
        assert _tree(page) == ["bench.toml", "cabinet.py", "parts.py", "foot.stl"]
        page.screenshot(path=str(OUT / "switcher-tree.png"))

        # A second script opens in the editor group, and is what runs.
        page.locator("bench-explorer .file[data-file='parts.py']").click()
        _bodies_are(page, 3)
        assert page.locator("#tab-script").inner_text().strip() == "parts.py"
        # The document to its tab.
        page.locator("bench-explorer .file[data-file='bench.toml']").click()
        assert page.locator("#values-text").is_visible()
        assert "entry" in page.locator("#values-text").inner_text()
        # A mesh onto the view, its survey opening beside the script.
        page.locator("bench-explorer .file[data-file='foot.stl']").click()
        page.wait_for_selector("#tab-report", timeout=BOOT_MS)
        assert page.locator("#tab-report").inner_text().strip().startswith("foot.stl")

        page.click("#project-switcher")
        page.screenshot(path=str(OUT / "switcher-open.png"))


# ---- AC#4, AC#5: row actions, and a delete that is a move into the trash --------------------


def test_row_actions_act_on_their_row_and_a_delete_goes_to_the_trash_it_names(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = _seeded(tmp_path)
    cabinet = root / "cabinet"
    with _page(browser, root) as page:
        page.click("#project-switcher")
        page.locator("bench-explorer .project", has_text="cabinet").click()
        _bodies_are(page, 1)
        page.wait_for_function(
            "() => document.querySelector('bench-explorer')?.files.meshes.length === 1",
            timeout=15_000,
        )

        # Renamed from its own row while cabinet.py is the one open.
        _act(page, "parts.py", "Rename…")
        page.fill("#file-name", "bits")
        page.click("#file-rename-confirm")
        page.wait_for_function(
            "() => (document.querySelector('bench-explorer')?.files.scripts ?? [])"
            ".includes('bits.py')"
        )
        assert page.locator("#tab-script").inner_text().strip() == "cabinet.py"
        _eventually_file(cabinet / "bits.py")

        # Duplicated from its row: the copy opens.
        _act(page, "bits.py", "Duplicate")
        _bodies_are(page, 3)
        assert page.locator("#tab-script").inner_text().strip() == "bits-2.py"
        _eventually_file(cabinet / "bits-2.py")

        # Deleted from its row, having said where it goes.
        _act(page, "bits-2.py", "Delete…")
        said = page.locator("bench-explorer #file-delete-what").inner_text()
        assert f"{root.resolve()}/.trash/" in said
        page.screenshot(path=str(OUT / "tree-delete-asks.png"))
        page.click("#file-delete-confirm")
        _eventually(lambda: "cabinet/bits-2.py" in _trashed(root))
        assert not (cabinet / "bits-2.py").exists()
        assert "moved to" in page.locator("bench-explorer .said").inner_text()

        # A mesh: into the trash, straight through.
        _act(page, "foot.stl", "Delete…")
        page.click("#file-delete-confirm")
        _eventually(lambda: "cabinet/foot.stl" in _trashed(root))
        assert not (cabinet / "foot.stl").exists()
        page.wait_for_function(
            "() => document.querySelector('bench-explorer')?.files.meshes.length === 0"
        )
        page.screenshot(path=str(OUT / "tree-deleted.png"))

        # The whole project: its directory, everything in it, into the trash - nothing left.
        page.click("#project-switcher")
        _act(page, "cabinet", "Delete…")
        page.click("#file-delete-confirm")
        _eventually(lambda: not cabinet.exists())
        assert {"cabinet/cabinet.py", "cabinet/bench.toml"} <= _trashed(root)
        page.wait_for_function(
            "() => document.querySelector('#open-name')?.textContent === 'bracket'"
        )


def _eventually(check: Callable[[], object], timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while not check():
        assert time.monotonic() < deadline, "never happened"
        time.sleep(0.1)


def _eventually_file(path: Path) -> None:
    _eventually(path.is_file)
