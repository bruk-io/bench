"""End to end: task-86 - *Open in slicer*, clicked in the built app, lands a file and starts a
slicer.

The inspector's export offers *Open in slicer* beside the run's 3MF and beside each printed
part's STL; a click hands the file to the host, which writes it into the open project's
``prints/`` and starts its slicer with it. The slicer here is a program of the test's own,
named by ``BENCH_SLICER`` where the server is started - a script that writes the arguments it
was handed to a file and exits - so what is checked is the real click, the real route, the real
``execFile`` and the file on disk, and never the maker's installed Bambu Studio. What the route
refuses is ``tests/adapter/test_slicer_route.py``'s.
"""

import json
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pytest

from tools import preview
from tools.projects import VARIABLE

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page

pytestmark = pytest.mark.e2e

BOOT_MS = 240_000


class Slicing(NamedTuple):
    """The page, the projects root it keeps its projects in, and what the slicer recorded."""

    page: Page
    root: Path
    record: Path


def _launches(record: Path) -> list[list[str]]:
    """Every argument list the recording slicer was started with, oldest first."""
    if not record.exists():
        return []
    return [json.loads(line) for line in record.read_text().splitlines()]


@pytest.fixture(scope="module")
def slicing(
    built_app: Path, browser: Browser, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Slicing]:
    """The app served over a root of its own with its slicer a recording script, showing the
    enclosure - two printed parts, so one 3MF and two STLs."""
    base = tmp_path_factory.mktemp("slicing")
    root = base / "projects"
    root.mkdir()
    record = base / "launched.jsonl"
    slicer = base / "record-argv"
    slicer.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        f"with open({str(record)!r}, 'a') as out:\n"
        "    out.write(json.dumps(sys.argv[1:]) + '\\n')\n"
    )
    slicer.chmod(0o755)
    with preview.served(env={VARIABLE: str(root), "BENCH_SLICER": str(slicer)}) as url:
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        page = context.new_page()
        page.goto(url)
        page.wait_for_selector("#canvas3d[data-bodies]:not([data-bodies='0'])", timeout=BOOT_MS)
        page.click("#examples-button")
        page.locator("#examples").get_by_role("button", name="enclosure_lid.py", exact=True).click()
        page.wait_for_function(
            "() => document.querySelector('#state')?.dataset.state !== 'running'", timeout=BOOT_MS
        )
        page.wait_for_selector("#outputs bench-file-row .name:text-matches('\\\\.3mf$')")
        try:
            yield Slicing(page, root, record)
        finally:
            context.close()


def _landed(root: Path, name: str) -> Path:
    """The one file called ``name`` in any project's ``prints/`` under ``root``."""
    found = list(root.glob(f"*/prints/{name}"))
    assert len(found) == 1, found
    return found[0]


def test_open_in_slicer_beside_the_3mf_lands_it_in_prints_and_starts_the_slicer(
    slicing: Slicing, screenshots: Path
) -> None:
    """AC#1 and AC#4: the click writes the run's 3MF - the bytes the row would download - into
    the project's ``prints/``, starts the configured slicer with that file as its one argument,
    and says so under the row."""
    page = slicing.page
    page.click("#crumb-project")
    name = page.locator("#outputs bench-file-row .name", has_text=".3mf").first.inner_text().strip()
    row = page.locator("#outputs bench-file-row", has_text=name)
    row.locator("button", has_text="Open in slicer").click()
    said = page.locator(f'.opening.opened[data-file="{name}"]')
    said.wait_for(state="visible", timeout=15_000)
    assert said.inner_text().strip() == f"Opened prints/{name} in record-argv."
    landed = _landed(slicing.root, name)
    assert landed.read_bytes()[:2] == b"PK", "the 3MF that landed is not a zip"
    assert _launches(slicing.record)[-1] == [str(landed.resolve())]
    page.locator("#inspector").screenshot(path=str(screenshots / "task-86-open-in-slicer-3mf.png"))


def test_open_in_slicer_beside_a_parts_stl(slicing: Slicing, screenshots: Path) -> None:
    """AC#1: a printed part's own export offers it beside the part's STL, and the STL lands and
    opens the same way."""
    page = slicing.page
    page.click("#crumb-project")
    page.locator('#parts .part[data-part="lid"]').click()
    before = len(_launches(slicing.record))
    page.locator("#outputs bench-file-row", has_text="lid.stl").locator(
        "button", has_text="Open in slicer"
    ).click()
    page.locator('.opening.opened[data-file="lid.stl"]').wait_for(state="visible", timeout=15_000)
    landed = _landed(slicing.root, "lid.stl")
    assert landed.read_bytes()[:5] != b"solid", "an STL a run makes is binary"
    assert _launches(slicing.record)[before:] == [[str(landed.resolve())]]
    page.locator("#inspector").screenshot(path=str(screenshots / "task-86-open-in-slicer-stl.png"))


def test_a_page_with_a_host_offers_it_only_where_a_printer_reads_the_file(
    slicing: Slicing, settle: Callable[[Page], None]
) -> None:
    """Every file a printer reads has it, and nothing else does - not a sheet, not a drawing."""
    page = slicing.page
    page.click("#crumb-project")
    settle(page)
    names = page.locator("#outputs bench-file-row").filter(
        has=page.locator("button", has_text="Open in slicer")
    )
    offered = sorted(one.strip() for one in names.locator(".name").all_inner_texts())
    assert offered, "nothing offers Open in slicer"
    assert all(one.endswith((".stl", ".3mf")) for one in offered), offered
