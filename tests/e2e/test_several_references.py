"""End to end: task-49 - a project holds several references, one of them active.

decision-9 step 7, against a real host and read back off its disk: every mesh dropped on the
view is a file in the project's directory and is still there after a reload (AC#1); a second
drop adds a row beside the first rather than replacing it (AC#2); exactly one is active, and
choosing a row in the refs container is what makes it so (AC#3); ``[reference]`` is one table
naming that one, so a reload puts back the body it names with nothing to guard (AC#4); the
survey, *detect faces* and the pick panel are about the active one (AC#5); removing a reference
says what happens to the file - and to ``[reference]`` - before it is done (AC#6); and a reader
chooses and surveys one on its own view, writing nothing (AC#7).
"""

import base64
import contextlib
import shutil
import time
import tomllib
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

SCRIPT = "from bench import *\n\nshow((part('plate', face(rect(60, 40)), Stock(3, 'ply')),))\n"

DROPPED = """async ([name, base64]) => {
    const bytes = Uint8Array.from(atob(base64), (letter) => letter.charCodeAt(0));
    const file = new File([bytes], name, { type: 'model/stl' });
    const data = new DataTransfer();
    data.items.add(file);
    const pane = document.querySelector('#canvas3d');
    for (const type of ['dragenter', 'dragover', 'drop']) {
        const init = { bubbles: true, cancelable: true, dataTransfer: data };
        pane.dispatchEvent(new DragEvent(type, init));
    }
}"""
"""Drop a file on the view the way a drag from the desktop lands - ``test_app.py``'s own."""


def _mesh(w: float, h: float) -> bytes:
    """A ``w`` x ``h`` x 3 plate as the binary STL a maker would drop."""
    from bench import Stock, fill, part, rect, stl
    from bench.plates import plate

    swept = plate(part("body", fill(rect(w, h)), Stock(3, "ply")))
    assert swept is not None
    return stl(swept.mesh)


@contextlib.contextmanager
def _hosted(root: Path) -> Iterator[str]:
    with preview.served(env={VARIABLE: str(root)}) as url:
        yield url


def _opened(browser: Browser, url: str) -> Page:
    context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    page = context.new_page()
    page.goto(url)
    page.wait_for_selector("#canvas3d[data-bodies]:not([data-bodies='0'])", timeout=BOOT_MS)
    _settled(page)
    return page


def _settled(page: Page) -> None:
    page.wait_for_function(
        "() => document.querySelector('#state')?.dataset.state !== 'running'", timeout=BOOT_MS
    )


def _drop(page: Page, name: str, data: bytes) -> None:
    page.evaluate(DROPPED, [name, base64.b64encode(data).decode()])


def _chip(page: Page) -> str:
    return page.locator("#reference-name").inner_text().strip()


def _active(page: Page) -> list[str]:
    return [
        str(one.get_attribute("data-reference"))
        for one in page.locator("bench-refs-tree .row.reference[data-active='true']").all()
    ]


def _reference(root: Path) -> object:
    """The ``[reference]`` table in ``plates``'s ``bench.toml``, or ``None``."""
    document = root / "plates" / "bench.toml"
    if not document.is_file():
        return None
    return tomllib.loads(document.read_text()).get("reference")


def _eventually(read: Callable[[], object], want: object, timeout: float = 15.0) -> object:
    deadline = time.monotonic() + timeout
    while True:
        found = read()
        if found == want or time.monotonic() > deadline:
            return found
        time.sleep(0.1)


def _rows_are(page: Page, rows: list[str], active: str) -> None:
    page.wait_for_function(
        """([rows, active]) => {
            const tree = document.querySelector('bench-refs-tree');
            return JSON.stringify(tree?.references) === JSON.stringify(rows)
                && tree?.activeReference === active;
        }""",
        arg=[rows, active],
        timeout=20_000,
    )


def _seeded(tmp_path: Path) -> Path:
    root = tmp_path / "projects"
    (root / "plates").mkdir(parents=True)
    (root / "plates" / "plates.py").write_text(SCRIPT)
    return root


# ---- AC#1-#5: kept, added, one active, named by [reference], and what measures is about it --


def test_two_drops_are_two_references_one_active_chosen_by_its_row_and_kept_over_a_reload(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = _seeded(tmp_path)
    first, second = _mesh(60, 40), _mesh(30, 20)
    with _hosted(root) as url:
        page = _opened(browser, url)
        page.click("#rail-refs")
        _drop(page, "bracket.stl", first)
        _rows_are(page, ["bracket.stl"], "bracket.stl")
        _drop(page, "foot.stl", second)
        # AC#2: added, not replaced - both files, both rows, the new one active.
        _rows_are(page, ["bracket.stl", "foot.stl"], "foot.stl")
        assert (root / "plates" / "bracket.stl").read_bytes() == first
        assert (root / "plates" / "foot.stl").read_bytes() == second
        assert _eventually(lambda: _reference(root), {"file": "foot.stl"}) == {"file": "foot.stl"}
        assert _chip(page).startswith("foot.stl")

        # AC#3: a row chooses the active one; AC#4: [reference] names it.
        page.locator("bench-refs-tree [data-reference='bracket.stl']").click()
        _rows_are(page, ["bracket.stl", "foot.stl"], "bracket.stl")
        assert _active(page) == ["bracket.stl"]
        assert _chip(page).startswith("bracket.stl")
        assert _eventually(lambda: _reference(root), {"file": "bracket.stl"}) == {
            "file": "bracket.stl"
        }

        # AC#5: the survey, detect faces and the pick panel are the active one's.
        page.wait_for_selector("#reference-report:not([disabled])", timeout=BOOT_MS)
        page.click("#reference-report")
        assert page.locator("#tab-report").inner_text().strip().startswith("bracket.stl")
        assert "60.000 x 40.000" in page.locator("#report-text").inner_text()
        page.click("#reference-detect")
        page.wait_for_selector("#pick:not([hidden])", timeout=BOOT_MS)
        page.wait_for_function(
            "() => document.querySelector('#reference-detect')?.textContent.trim()"
            " === 'detect faces'",
            timeout=BOOT_MS,
        )
        page.screenshot(path=str(OUT / "references-two-one-active.png"))

        # AC#1: a reload keeps both, and puts back the one [reference] names.
        page.reload()
        page.wait_for_selector("#canvas3d[data-bodies]:not([data-bodies='0'])", timeout=BOOT_MS)
        page.click("#rail-refs")
        _rows_are(page, ["bracket.stl", "foot.stl"], "bracket.stl")
        assert _chip(page).startswith("bracket.stl")
        page.context.close()


# ---- AC#6: removing a reference says what happens to the file first ------------------------


def test_removing_the_active_reference_says_where_it_goes_and_that_reference_is_cleared(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = _seeded(tmp_path)
    (root / "plates" / "bracket.stl").write_bytes(_mesh(60, 40))
    (root / "plates" / "foot.stl").write_bytes(_mesh(30, 20))
    (root / "plates" / "bench.toml").write_text('[reference]\nfile = "foot.stl"\n')
    with _hosted(root) as url:
        page = _opened(browser, url)
        page.click("#rail-refs")
        _rows_are(page, ["bracket.stl", "foot.stl"], "foot.stl")
        page.click("#rail-files")
        page.locator('bench-explorer [aria-label="Actions for foot.stl"]').click()
        page.locator("bench-explorer .acts button", has_text="Delete…").click()
        said = " ".join(page.locator("bench-explorer #file-delete-what").inner_text().split())
        assert f"moves on the host into {root.resolve()}/.trash/" in said
        assert "It is the active reference, so [reference] is cleared with it" in said
        page.screenshot(path=str(OUT / "references-remove-asks.png"))
        page.click("#file-delete-confirm")

        assert _eventually(lambda: (root / "plates" / "foot.stl").exists(), False) is False
        assert list((root / ".trash").glob("*-plates/foot.stl")), "not in the trash"
        assert _eventually(lambda: _reference(root), None) is None
        page.click("#rail-refs")
        page.wait_for_function(
            "() => JSON.stringify(document.querySelector('bench-refs-tree')?.references)"
            " === JSON.stringify(['bracket.stl'])",
            timeout=20_000,
        )
        assert page.locator("#reference").is_hidden()
        page.context.close()


# ---- AC#7: a reader chooses and surveys a reference, and writes nothing ----------------------


def test_a_reader_chooses_and_surveys_a_reference_without_writing_anything(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = _seeded(tmp_path)
    (root / "plates" / "bracket.stl").write_bytes(_mesh(60, 40))
    (root / "plates" / "foot.stl").write_bytes(_mesh(30, 20))
    (root / "plates" / "bench.toml").write_text('[reference]\nfile = "foot.stl"\n')
    before = {one.name: one.read_bytes() for one in (root / "plates").iterdir()}
    with _hosted(root) as url:
        desk = _opened(browser, url)
        tablet = _opened(browser, url)
        tablet.wait_for_selector("#lease:not([hidden])", timeout=15_000)
        sent: list[str] = []
        tablet.on(
            "request",
            lambda request: (
                sent.append(f"{request.method} {request.url}")
                if request.method != "GET" and "/__bench/projects" in request.url
                else None
            ),
        )
        tablet.click("#rail-refs")
        _rows_are(tablet, ["bracket.stl", "foot.stl"], "foot.stl")
        tablet.locator("bench-refs-tree [data-reference='bracket.stl']").click()
        _rows_are(tablet, ["bracket.stl", "foot.stl"], "bracket.stl")
        tablet.wait_for_selector("#reference-report:not([disabled])", timeout=BOOT_MS)
        tablet.click("#reference-report")
        assert tablet.locator("#tab-report").inner_text().strip().startswith("bracket.stl")
        tablet.screenshot(path=str(OUT / "references-reader-chooses.png"))
        tablet.wait_for_timeout(1500)
        assert sent == [], f"a reader wrote: {sent}"
        assert {one.name: one.read_bytes() for one in (root / "plates").iterdir()} == before
        # The writer's own view is its own: it still has the one [reference] names.
        assert _chip(desk).startswith("foot.stl")
        desk.context.close()
        tablet.context.close()
