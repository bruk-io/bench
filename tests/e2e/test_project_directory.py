"""End to end: task-46 - a project is a directory on the host, with one ``bench.toml`` in it,
and nothing about it lives in the browser any more but which one this browser has open.

Every check here serves the built app over a projects root of its own and reads what the app
did off that root's own disk - the same files ``tools.build``, ``git`` and a maker's editor
would read. What the pure mapping does with a directory is driven a layer down, in
``web/src/project-files.test.ts``, ``files.test.ts`` and ``values.test.ts``; what only a real
browser against a real route can show is here: a panel edit landing in ``bench.toml`` (AC#1),
the entry running and then the script a person opens (AC#2), an older directory and a newer
document both opening and neither losing anything (AC#3), the one-time adoption of what a
browser kept, asked in the page (AC#4), a page with no host saying so (AC#5), and a dropped
mesh landing in the project's own directory (AC#7).
"""

import base64
import contextlib
import functools
import http.server
import shutil
import threading
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

TEMPLATE = (preview.ROOT / "templates" / "untitled.py").read_text()
"""A script with knobs (``w``, ``hole_r``, …) - what a new project starts as."""

PLATES = (
    "from bench import *\n\n"
    "show(tuple(part(f'p{{i}}', face(rect(60, 40)), Stock(3, 'ply')) for i in range({n})))\n"
)
"""A script that makes ``n`` plates, so which script ran can be read off the view's own count."""

DRAWN = "#canvas3d[data-bodies]:not([data-bodies='0'])"

BODIES = "() => Number(document.querySelector('#canvas3d')?.dataset.bodies ?? 0)"

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


# ---- serving --------------------------------------------------------------------------


@contextlib.contextmanager
def _hosted(root: Path) -> Iterator[str]:
    """The built app over the projects root ``root``."""
    with preview.served(env={VARIABLE: str(root)}) as url:
        yield url


@contextlib.contextmanager
def _static() -> Iterator[str]:
    """``web/dist`` behind a plain file server - decision-9's "dumb file server with no
    ``/__bench/projects`` behind it", which the web README used to call a deployment."""
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(preview.DIST.parent)
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()


# ---- the page -------------------------------------------------------------------------


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


def _ran(page: Page) -> None:
    page.wait_for_timeout(500)
    _settled(page)


def _bodies(page: Page) -> int:
    found = page.evaluate(BODIES)
    assert isinstance(found, int)
    return found


def _open_name(page: Page) -> str:
    return page.locator("#open-name").inner_text().strip()


def _saved(page: Page) -> None:
    """Wait until every edit has reached the host - the reach chip's own "saved to host"."""
    page.wait_for_timeout(400)  # past the outbox's debounce, so "saved" is about this edit
    page.wait_for_function(
        "() => document.querySelector('#reach')?.dataset.state === 'ok'", timeout=20_000
    )


def _eventually(read: Callable[[], object], want: object, timeout: float = 15.0) -> object:
    """``read()`` once it answers ``want``, or whatever it last answered when ``timeout``
    seconds are up - so a failing check says what it found."""
    deadline = time.monotonic() + timeout
    while True:
        found = read()
        if found == want or time.monotonic() > deadline:
            return found
        time.sleep(0.1)


def _document(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text()) if path.is_file() else {}


def _files(root: Path) -> set[str]:
    """Every file under ``root``, as ``project/file``."""
    return {str(one.relative_to(root)) for one in root.rglob("*") if one.is_file()}


def _seed(root: Path, project: str, files: dict[str, str | bytes]) -> Path:
    directory = root / project
    directory.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        if isinstance(body, bytes):
            (directory / name).write_bytes(body)
        else:
            (directory / name).write_text(body)
    return directory


def _shot(page: Page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / name))


# ---- AC#1: a project is a directory, and a panel edit lands in its bench.toml -----------


def test_a_first_visit_writes_nothing_and_a_panel_edit_writes_one_directory(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    """A host with nothing on it opens the first example without making a directory for it -
    a page loading is not a reason to write on somebody's disk - and the first knob turned
    writes the project as decision-9 draws it: a directory, its script, one ``bench.toml``."""
    root = tmp_path / "projects"
    root.mkdir()
    with _hosted(root) as url:
        page = _opened(browser, url)
        assert _open_name(page) == "gridfinity_cabinet"
        page.wait_for_timeout(1500)
        assert _files(root) == set(), "a first visit wrote something"

        page.click("#rail-parameters")
        page.fill("#param-units_x", "5")
        _ran(page)
        _saved(page)
        document = root / "gridfinity_cabinet" / "bench.toml"
        assert _eventually(lambda: _document(document).get("values"), {"units_x": 5}) == {
            "units_x": 5
        }
        assert _document(document)["project"] == {"entry": "gridfinity_cabinet.py"}
        assert _files(root) == {
            "gridfinity_cabinet/gridfinity_cabinet.py",
            "gridfinity_cabinet/bench.toml",
        }
        page.context.close()


def test_which_project_is_open_is_each_browsers_own(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    """Two browsers on one host - task-47's desktop and tablet. One switching projects writes
    nothing to the host and does not move the other: which project is open is kept in each
    browser, and no file on the host says it (task-52's ``_workspace.toml`` is gone)."""
    root = tmp_path / "projects"
    _seed(root, "alpha", {"alpha.py": PLATES.format(n=1)})
    _seed(root, "beta", {"beta.py": PLATES.format(n=2)})
    before = _files(root)
    with _hosted(root) as url:
        desk = _opened(browser, url)
        tablet = _opened(browser, url)
        assert _open_name(desk) == _open_name(tablet) == "alpha"

        written: list[str] = []
        # A lambda rather than an annotated function: Playwright reads a handler's signature,
        # and an annotation naming a type imported only for checking cannot be read at run time.
        desk.on(
            "request",
            lambda request: (
                written.append(f"{request.method} {request.url}")
                if request.method != "GET" and "/__bench/projects" in request.url
                else None
            ),
        )
        desk.click("#rail-files")
        desk.click("#project-switcher")
        desk.locator("bench-explorer .project", has_text="beta").click()
        desk.wait_for_function(f"() => ({BODIES})() === 2", timeout=BOOT_MS)
        desk.wait_for_timeout(1000)
        assert written == [], f"switching projects wrote to the host: {written}"

        desk.reload()
        tablet.reload()
        _rendered(desk)
        _rendered(tablet)
        assert _open_name(desk) == "beta"
        assert _open_name(tablet) == "alpha", "one browser's switch moved the other"
        assert _files(root) == before, f"something was written: {_files(root) - before}"
        desk.context.close()
        tablet.context.close()


# ---- AC#2: the entry runs, and so does the script a person opens ------------------------


def test_the_entry_runs_on_a_fresh_open_and_the_script_a_person_opens_runs_after(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    """decision-9's answer to "which script runs": ``entry`` names the default, and the script
    you have open runs. A project of two scripts opens on the one ``bench.toml`` names; clicking
    the other's tab opens it and runs it; ``entry`` on disk is not changed by looking."""
    root = tmp_path / "projects"
    project = _seed(
        root,
        "shelf",
        {
            "one.py": PLATES.format(n=1),
            "two.py": PLATES.format(n=2),
            "bench.toml": '[project]\nentry = "one.py"\n\n[values]\n',
        },
    )
    with _hosted(root) as url:
        page = _opened(browser, url)
        assert _bodies(page) == 1, "the entry did not run"
        assert page.locator("#tab-script").inner_text().strip() == "one.py"
        assert page.locator("#tab-values").inner_text().strip() == "bench.toml"
        _shot(page, "task46-project-open-from-host.png")

        page.locator("#tab-file-two\\.py").click()
        page.wait_for_function(f"() => ({BODIES})() === 2", timeout=BOOT_MS)
        _settled(page)
        assert page.locator("#tab-script").inner_text().strip() == "two.py"
        assert page.locator("#tab-file-one\\.py").count() == 1

        # Which script is open is this browser's, and survives its reload.
        page.reload()
        _rendered(page)
        assert _bodies(page) == 2
        assert page.locator("#tab-script").inner_text().strip() == "two.py"
        assert _document(project / "bench.toml")["project"] == {"entry": "one.py"}
        page.context.close()


# ---- AC#3: an older directory, and a newer document, still open ------------------------


def test_a_directory_from_before_bench_toml_opens_on_its_own_values(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    """decision-3's shape - ``<script>.toml`` beside the script, no ``bench.toml`` - opens on
    the values it holds; the next panel edit writes ``bench.toml``, and the old file is left
    exactly where it was, since it is somebody's and ``tools.build`` still reads it."""
    root = tmp_path / "projects"
    legacy = "[values]\nw = 140\n"
    project = _seed(root, "plate", {"plate.py": TEMPLATE, "plate.toml": legacy})
    with _hosted(root) as url:
        page = _opened(browser, url)
        page.click("#rail-parameters")
        assert page.locator("#param-w").input_value() == "140"
        page.fill("#param-w", "150")
        _ran(page)
        _saved(page)
        document = project / "bench.toml"
        assert _eventually(lambda: _document(document).get("values"), {"w": 150}) == {"w": 150}
        assert _document(document)["project"] == {"entry": "plate.py"}
        assert (project / "plate.toml").read_text() == legacy, "the older file was changed"
        page.context.close()


def test_a_bench_toml_this_version_cannot_read_opens_and_is_never_written_over(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    """A value this version has no reader for - an array, which a later bench might write -
    makes the whole document unreadable here. The project still opens, on the script's own
    defaults, says why on the values tab, and a knob turned does not regenerate the file over
    what it could not read."""
    root = tmp_path / "projects"
    text = (
        '[project]\nentry = "plate.py"\n\n[values]\nw = [140, 150]\n\n[[measured]]\nname = "wall"\n'
    )
    project = _seed(root, "plate", {"plate.py": TEMPLATE, "bench.toml": text})
    with _hosted(root) as url:
        page = _opened(browser, url)
        page.click("#tab-values")
        said = page.locator("#values-text").inner_text()
        assert "bench could not read this file (line 5" in said, said
        assert said.endswith(text.rstrip("\n")) or text in said, said
        page.click("#tab-script")
        assert page.locator("#tab-values").get_attribute("data-flag") == "error"

        page.click("#rail-parameters")
        page.fill("#param-w", "120")
        _ran(page)
        page.wait_for_timeout(1500)
        assert (project / "bench.toml").read_text() == text, "the unreadable file was written over"
        page.context.close()


def test_a_bench_toml_with_tables_this_version_does_not_know_opens_and_keeps_them(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    """A document a later bench wrote - a root key, a ``[project]`` key, a ``[[measured]]``
    table - opens, and a panel edit rewrites ``[values]`` without dropping any of it."""
    root = tmp_path / "projects"
    newer = "\n".join(
        [
            'owner = "workshop"',
            "[project]",
            'entry = "plate.py"',
            'modules = ["parts.py"]',
            "",
            "[values]",
            "w = 140",
            "",
            "[[measured]]",
            'name = "wall"',
            "value = 2.41",
            "",
            "[[measured]]",
            'name = "boss-spacing"',
            "value = 42.0",
            "",
        ]
    )
    project = _seed(root, "plate", {"plate.py": TEMPLATE, "bench.toml": newer})
    with _hosted(root) as url:
        page = _opened(browser, url)
        page.click("#rail-parameters")
        assert page.locator("#param-w").input_value() == "140"
        page.fill("#param-w", "150")
        _ran(page)
        _saved(page)
        document = project / "bench.toml"
        assert _eventually(lambda: _document(document).get("values"), {"w": 150}) == {"w": 150}
        kept = _document(document)
        assert kept["owner"] == "workshop"
        assert kept["project"] == {"entry": "plate.py", "modules": ["parts.py"]}
        assert kept["measured"] == [
            {"name": "wall", "value": 2.41},
            {"name": "boss-spacing", "value": 42.0},
        ]
        page.context.close()


# ---- AC#4: what this browser kept is adopted once, after asking --------------------------

MINE_CABINET = PLATES.format(n=3)
"""A cabinet somebody wrote, kept under the first example's own name - not the example."""

KEPT = """([cabinet, mine]) => {
    window.localStorage.setItem('bench.files', JSON.stringify({
        files: [
            { name: 'gridfinity_cabinet.py', source: cabinet, values: '[values]\\n' },
            { name: 'mine.py', source: mine, values: '[values]\\nw = 150\\n' },
        ],
        current: 'mine.py',
    }));
}"""
"""What a browser from before task-46 kept: two projects under ``bench.files``, in the shape
``store-local.ts`` wrote. The first is not an example as shipped (its text differs), so both are
somebody's work."""


def _kept_before(page: Page) -> None:
    """Put a browser from before task-46 behind ``page``, and reload into it: the projects go
    into its ``localStorage`` once, by hand, the way that browser would have left them - not
    on every load, which would hide a question asked twice."""
    page.evaluate(KEPT, [MINE_CABINET, TEMPLATE])
    page.reload()
    _rendered(page)


def test_a_browsers_own_projects_are_adopted_once_after_asking_naming_the_directories(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = tmp_path / "projects"
    root.mkdir()
    with _hosted(root) as url:
        page = _opened(browser, url)
        _kept_before(page)
        page.wait_for_selector("#adopt:not([hidden])", timeout=20_000)
        named = [one.strip() for one in page.locator("#adopt-list li").all_inner_texts()]
        where = str(root.resolve())
        assert named == [f"{where}/gridfinity_cabinet/", f"{where}/mine/"], named
        _shot(page, "task46-adoption-prompt.png")
        page.wait_for_timeout(1000)
        assert _files(root) == set(), "something was written before the question was answered"

        page.click("#adopt-yes")
        assert page.locator("#adopt").is_hidden()
        _ran(page)
        _saved(page)
        assert _open_name(page) == "gridfinity_cabinet"
        mine = root / "mine"
        assert _eventually(lambda: (mine / "mine.py").is_file(), True) is True
        assert (mine / "mine.py").read_text() == TEMPLATE
        assert _eventually(lambda: _document(mine / "bench.toml").get("values"), {"w": 150}) == {
            "w": 150
        }
        assert (root / "gridfinity_cabinet" / "gridfinity_cabinet.py").read_text() == MINE_CABINET

        page.reload()
        _rendered(page)
        page.wait_for_timeout(2000)
        assert page.locator("#adopt").is_hidden(), "it asked again"
        page.context.close()


def test_declining_adoption_writes_nothing_and_is_not_asked_again(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = tmp_path / "projects"
    root.mkdir()
    with _hosted(root) as url:
        page = _opened(browser, url)
        _kept_before(page)
        page.wait_for_selector("#adopt:not([hidden])", timeout=20_000)
        page.click("#adopt-no")
        assert page.locator("#adopt").is_hidden()
        page.wait_for_timeout(1500)
        assert _files(root) == set(), f"declining wrote {_files(root)}"

        page.reload()
        _rendered(page)
        page.wait_for_timeout(2000)
        assert page.locator("#adopt").is_hidden(), "it asked again"
        # What the browser kept is left where it was - declining is not deleting.
        assert page.evaluate("() => window.localStorage.getItem('bench.files') !== null")
        page.context.close()


def test_a_browser_holding_only_untouched_examples_is_not_asked(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    """Every browser that ever opened bench kept the first example, because the app always
    opened one. Carrying that onto somebody's disk is not adoption, so it is not asked about."""
    root = tmp_path / "projects"
    root.mkdir()
    with _hosted(root) as url:
        page = _opened(browser, url)
        # The first example exactly as the bundle ships it - the page's own editor holds it.
        page.evaluate(
            """() => {
                const text = Array.from(
                    document.querySelectorAll('.cm-content .cm-line'), (l) => l.textContent
                ).join('\\n');
                window.localStorage.setItem('bench.files', JSON.stringify({
                    files: [{ name: 'gridfinity_cabinet.py', source: text, values: '[values]\\n' }],
                    current: 'gridfinity_cabinet.py',
                }));
            }"""
        )
        page.reload()
        _rendered(page)
        page.wait_for_timeout(2000)
        assert page.locator("#adopt").is_hidden()
        page.context.close()


# ---- AC#5: no host says so ------------------------------------------------------------


def test_a_page_with_no_host_behind_it_says_so_and_does_not_appear_to_work(
    browser: Browser, built_app: Path
) -> None:
    with _static() as url:
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        page = context.new_page()
        page.goto(url)
        page.wait_for_selector("#no-host:not([hidden])", timeout=BOOT_MS)
        assert "There is no host behind this page." in page.locator("#no-host").inner_text()
        assert "without bench's projects route" in page.locator("#no-host-why").inner_text()
        assert page.locator("#reach").inner_text().strip() == "no host"
        assert page.locator("#run").is_disabled()
        # Python booting behind the message does not paint over it, and the run shortcut -
        # which a document-level listener hears past the inert controls - runs nothing.
        page.wait_for_timeout(8000)
        page.keyboard.press("ControlOrMeta+Enter")
        page.wait_for_timeout(1000)
        assert "no host" in page.locator("#status").inner_text()
        assert page.locator("#state").get_attribute("data-state") == "error"
        assert page.locator("#canvas3d").get_attribute("data-bodies") in {None, "0"}
        _shot(page, "task46-no-host.png")
        context.close()


def test_a_browser_that_has_used_the_host_is_told_there_is_none_rather_than_left_waiting(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    """A browser whose every write has landed still has rows in its outbox - one per file, as a
    version cache - and must not be kept on "waiting for host…" by them when the host answers
    that it has no projects root. Only a write that has not landed is a reason to wait."""
    root = tmp_path / "projects"
    _seed(root, "plate", {"plate.py": TEMPLATE})
    with _hosted(root) as url:
        page = _opened(browser, url)
        page.click("#rail-parameters")
        page.fill("#param-w", "150")
        _ran(page)
        _saved(page)
        shutil.rmtree(root)
        page.reload()
        page.wait_for_selector("#no-host:not([hidden])", timeout=30_000)
        assert "The host is running" in page.locator("#no-host-why").inner_text()
        page.context.close()


def test_a_host_whose_projects_root_is_missing_says_that(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    missing = tmp_path / "not-there"
    with _hosted(missing) as url:
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        page = context.new_page()
        page.goto(url)
        page.wait_for_selector("#no-host:not([hidden])", timeout=BOOT_MS)
        said = page.locator("#no-host-why").inner_text()
        assert "The host is running" in said and "not-there" in said, said
        _shot(page, "task46-no-root.png")
        context.close()
    assert not missing.exists(), "a named root was created"


# ---- AC#7: a dropped mesh is written into the project's own directory ---------------------


def _bracket() -> bytes:
    """A 60 x 40 x 3 ply plate with a 6 mm bore, as the binary STL a maker would drop."""
    from bench import Point, Stock, circle, cut, fill, part, rect, stl
    from bench.plates import plate

    face = cut(fill(rect(60, 40)), circle(3, Point(15, 20)), label="bore")
    swept = plate(part("bracket", face, Stock(3, "ply")))
    assert swept is not None, "the bracket did not sweep as a plate"
    return stl(swept.mesh)


def _drop(page: Page, name: str, data: bytes) -> None:
    page.evaluate(DROPPED, [name, base64.b64encode(data).decode()])


def test_a_dropped_mesh_is_written_into_the_projects_own_directory(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = tmp_path / "projects"
    project = _seed(root, "cabinet", {"cabinet.py": PLATES.format(n=1)})
    body = _bracket()
    with _hosted(root) as url:
        page = _opened(browser, url)
        _drop(page, "bracket.stl", body)
        page.wait_for_selector("#reference:not([hidden])", timeout=BOOT_MS)
        landed = project / "bracket.stl"
        assert _eventually(lambda: landed.is_file() and landed.read_bytes() == body, True) is True

        # The same body again is already there: nothing is written and nothing is refused.
        _drop(page, "bracket.stl", body)
        page.wait_for_timeout(1500)
        assert "not kept" not in page.locator("#reference-name").inner_text()

        # A different body under the same name is not written over the one the project holds.
        other = body[:80] + (0).to_bytes(4, "little")
        _drop(page, "bracket.stl", other)
        page.wait_for_function(
            "() => document.querySelector('#reference-name')?.textContent.includes('not kept')",
            timeout=20_000,
        )
        assert landed.read_bytes() == body, "a drop wrote over the project's own mesh"
        page.context.close()


def test_a_placement_brings_back_the_mesh_it_names_from_the_project(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    """The point of writing the drop into the project: a reload used to keep the placement and
    lose the body it placed. Now ``[reference]`` names a file the project holds, and opening the
    project puts that body back on the view, placed."""
    root = tmp_path / "projects"
    _seed(
        root,
        "cabinet",
        {
            "cabinet.py": PLATES.format(n=1),
            "bracket.stl": _bracket(),
            "bench.toml": '[project]\nentry = "cabinet.py"\n\n[values]\n\n[reference]\n'
            'file = "bracket.stl"\norigin = "low"\nup = "+Z"\nalong = "+X"\n',
        },
    )
    with _hosted(root) as url:
        page = _opened(browser, url)
        page.wait_for_selector("#reference:not([hidden])", timeout=BOOT_MS)
        page.wait_for_function(
            "() => document.querySelector('#reference-name')?.textContent.includes('placed')",
            timeout=BOOT_MS,
        )
        assert page.locator("#reference-name").inner_text().strip() == "bracket.stl · placed"
        # Put back quietly: its survey waits behind the chip rather than covering the script.
        page.wait_for_function(
            "() => document.querySelector('#reference-report')?.textContent.trim() === 'survey'",
            timeout=BOOT_MS,
        )
        assert page.locator("#tab-report").count() == 0
        page.context.close()
