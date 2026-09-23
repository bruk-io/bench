"""End to end: task-47 - an open project is leased to one writer, and everyone else reads it.

decision-9's own case, driven for real: a desk and a tablet - two browser contexts - on one
host, one project between them. The first to open it writes (AC#1); the second reads it, runs
it, exports it and turns its knobs, is told why it cannot keep anything and who it is waiting
on, and keeps nothing (AC#2, AC#7); it can take the project over, after being told whose it
is, with nothing but controls in the page (AC#6). A lease whose holder goes quiet lapses and
the reader becomes the writer with nobody pressing anything (AC#3); a reload reclaims its own
lease at once (AC#4); a closed tab lets go at once, and the expiry is there for when it does
not (AC#5). A server restart voiding every lease (AC#8) is a question for the server alone,
and is asked in ``tests/adapter/test_projects_lease.py``.

Each check has a server of its own, and those that watch a lease lapse start it with a short
one (``BENCH_LEASE_MS``) rather than waiting a minute.
"""

import contextlib
import http.client
import json
import shutil
import time
import tomllib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import pytest

from tools import preview
from tools.projects import VARIABLE

pytestmark = pytest.mark.e2e

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page, Route

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

LEASE_VARIABLE = "BENCH_LEASE_MS"
"""How long a lease lasts unheard, in milliseconds - ``web/server/projects.ts``'s variable."""

PLATES = """\
from dataclasses import dataclass

from bench import *


@dataclass(frozen=True, slots=True, kw_only=True)
class Settings:
    n: int = knob(1, min=1, max=6, step=1, label="Plates")


def build(p: Settings) -> tuple[Part, ...]:
    return tuple(part(f"p{i}", face(rect(60, 40)), Stock(3, "ply")) for i in range(p.n))


show(build)
"""
"""A script with one knob, ``n``, whose value can be read off the view's own count of bodies."""

DOCUMENT = '[project]\nentry = "plates.py"\n\n[values]\nn = 2\n'

BODIES = "() => Number(document.querySelector('#canvas3d')?.dataset.bodies ?? 0)"

EDITOR_TEXT = (
    "() => Array.from(document.querySelectorAll('.cm-content .cm-line'),"
    " (line) => line.textContent).join('\\n')"
)

PENDING = """async () => {
    const db = await new Promise((resolve, reject) => {
        const asked = indexedDB.open('bench-outbox');
        asked.onsuccess = () => resolve(asked.result);
        asked.onerror = () => reject(asked.error);
    });
    if (!db.objectStoreNames.contains('pending')) return [];
    const rows = await new Promise((resolve, reject) => {
        const asked = db.transaction('pending', 'readonly').objectStore('pending').getAll();
        asked.onsuccess = () => resolve(asked.result);
        asked.onerror = () => reject(asked.error);
    });
    return rows.filter((row) => row.dirty).map((row) => `${row.project}/${row.file}`);
}"""
"""Every write this page's outbox is holding and has not landed - what AC#7 says must stay empty
for a reader, since a queued write is a write, whether or not it has gone yet."""


# ---- serving --------------------------------------------------------------------------


@contextlib.contextmanager
def _hosted(root: Path, expiry_ms: int | None = None) -> Iterator[str]:
    """The built app over ``root``, with leases lasting ``expiry_ms`` - or the app's own."""
    env = {VARIABLE: str(root)}
    if expiry_ms is not None:
        env[LEASE_VARIABLE] = str(expiry_ms)
    with preview.served(env=env) as url:
        yield url


def _seeded(tmp_path: Path) -> Path:
    """A root holding one project, ``plates``, whose values say two plates."""
    root = tmp_path / "projects"
    (root / "plates").mkdir(parents=True)
    (root / "plates" / "plates.py").write_text(PLATES)
    (root / "plates" / "bench.toml").write_text(DOCUMENT)
    return root


def _lease(url: str, method: str = "GET", act: str = "", holder: str = "") -> dict[str, object]:
    """Ask the route about ``plates``'s lease directly, as a client that is not a page."""
    parts = urlsplit(url)
    conn = http.client.HTTPConnection(parts.hostname or "localhost", parts.port, timeout=10)
    headers = {} if holder == "" else {"X-Bench-Holder": holder, "X-Bench-Client": "a script"}
    try:
        conn.request(
            method, "/__bench/leases/plates" + (f"?act={act}" if act else ""), headers=headers
        )
        found = json.loads(conn.getresponse().read())
    finally:
        conn.close()
    assert isinstance(found, dict)
    return found


# ---- the page -------------------------------------------------------------------------


def _opened(browser: Browser, url: str) -> Page:
    context = browser.new_context(
        viewport={"width": 1440, "height": 900}, color_scheme="light", accept_downloads=True
    )
    page = context.new_page()
    page.goto(url)
    _rendered(page)
    return page


def _settled(page: Page) -> None:
    page.wait_for_function(
        "() => document.querySelector('#state')?.dataset.state !== 'running'", timeout=BOOT_MS
    )


def _rendered(page: Page) -> None:
    page.wait_for_selector("#canvas3d[data-bodies]:not([data-bodies='0'])", timeout=BOOT_MS)
    _settled(page)


def _bodies(page: Page) -> int:
    found = page.evaluate(BODIES)
    assert isinstance(found, int)
    return found


def _writer(page: Page, timeout: float = 15_000) -> None:
    """Wait until ``page`` holds the lease: its editor takes typing and it says nothing."""
    page.wait_for_function(
        "() => document.querySelector('#editor')?.dataset.readonly === 'false'"
        " && document.querySelector('#lease').hidden",
        timeout=timeout,
    )


def _reader(page: Page, timeout: float = 15_000) -> None:
    """Wait until ``page`` knows somebody else holds the lease."""
    page.wait_for_selector("#lease:not([hidden])", timeout=timeout)
    assert page.locator("#editor").get_attribute("data-readonly") == "true"


def _written(page: Page) -> list[str]:
    """Every request ``page`` sends that would change a project - from here on."""
    sent: list[str] = []
    page.on(
        "request",
        lambda request: (
            sent.append(f"{request.method} {request.url}")
            if request.method != "GET" and "/__bench/projects" in request.url
            else None
        ),
    )
    return sent


def _refused(route: Route, seen: list[str]) -> None:
    """Stop a request at the network, and note that it was tried."""
    seen.append(route.request.url)
    route.abort()


def _values(root: Path) -> dict[str, object]:
    found = tomllib.loads((root / "plates" / "bench.toml").read_text())["values"]
    assert isinstance(found, dict)
    return found


def _eventually(read: Callable[[], object], want: object, timeout: float = 15.0) -> object:
    deadline = time.monotonic() + timeout
    while True:
        found = read()
        if found == want or time.monotonic() > deadline:
            return found
        time.sleep(0.1)


def _shot(page: Page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / name))


# ---- AC#1, AC#2, AC#7: one writer; a reader runs, exports and turns knobs, keeping nothing ---


def test_the_first_to_open_writes_and_the_second_reads_is_told_why_and_keeps_nothing(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = _seeded(tmp_path)
    with _hosted(root) as url:
        desk = _opened(browser, url)
        _writer(desk)
        assert desk.locator("#standing").is_hidden()
        held = _lease(url)["holder"]
        assert isinstance(held, dict), "the desk opened the project and holds nothing"

        tablet = _opened(browser, url)
        _reader(tablet)
        title = tablet.locator("#lease-title").inner_text()
        assert title.startswith("plates is open for writing in ")
        assert str(held["label"]) in title
        assert str(held["address"]) in title
        assert "nothing you change is kept" in tablet.locator("#lease-why").inner_text()
        assert tablet.locator("#standing").inner_text() == "read-only"
        # It runs: the view is the project's own two plates.
        assert _bodies(tablet) == 2
        before = (root / "plates" / "bench.toml").read_text()
        script = (root / "plates" / "plates.py").read_text()
        sent = _written(tablet)

        # It cannot be typed into ...
        tablet.click(".cm-content")
        tablet.keyboard.type("# a reader typed this\n")
        assert "a reader typed this" not in str(tablet.evaluate(EDITOR_TEXT))

        # ... nor renamed or deleted, and it can still be exported.
        tablet.click("#rail-files")
        # Its files are listed, and no row in the tree offers an action at all (task-48 AC#6).
        rows = tablet.locator("bench-explorer .file").all_inner_texts()
        assert [row.split()[0] for row in rows] == ["bench.toml", "plates.py"]
        assert tablet.locator("bench-explorer .list .file ~ .more").count() == 0
        tablet.click("#project-switcher")
        tablet.locator('bench-explorer [aria-label="Actions for plates"]').click()
        offered = tablet.locator("bench-explorer .acts button").all_inner_texts()
        assert [one.strip() for one in offered] == ["Duplicate"]
        _shot(tablet, "lease-reader-explorer.png")
        with tablet.expect_download() as download:
            tablet.click("#project-download")
        assert download.value.suggested_filename == "plates.zip"

        # AC#7: a knob turns, the model runs on it, and the value goes nowhere at all.
        tablet.click("#rail-parameters")
        assert tablet.locator("#params-unkept").is_visible()
        tablet.fill("#param-n", "4")
        tablet.wait_for_function(f"() => ({BODIES})() === 4", timeout=BOOT_MS)
        _settled(tablet)
        tablet.wait_for_timeout(1500)  # past every debounce a write would have waited out
        _shot(tablet, "lease-reader.png")
        _shot(desk, "lease-writer.png")
        assert sent == [], f"a reader wrote to the host: {sent}"
        assert tablet.evaluate(PENDING) == [], "a reader queued a write"
        assert (root / "plates" / "bench.toml").read_text() == before
        assert (root / "plates" / "plates.py").read_text() == script

        # The writer is untouched by any of it, and still writes.
        desk.click("#rail-parameters")
        desk.fill("#param-n", "3")
        desk.wait_for_function(f"() => ({BODIES})() === 3", timeout=BOOT_MS)
        assert _eventually(lambda: _values(root), {"n": 3}) == {"n": 3}
        desk.context.close()
        tablet.context.close()


# ---- AC#6: a person can take a lease that is still held, having been told whose it is ------


def test_a_reader_can_take_the_project_over_after_being_told_whose_it_is(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = _seeded(tmp_path)
    # Short, so the desk hears it was taken over on its next renewal, two seconds away.
    with _hosted(root, expiry_ms=8000) as url:
        desk = _opened(browser, url)
        _writer(desk)
        tablet = _opened(browser, url)
        _reader(tablet)
        tablet.click("#lease-take")
        confirm = tablet.locator("#lease-confirm-text")
        assert confirm.is_visible()
        said = confirm.inner_text()
        assert said.startswith("Take plates from ")
        assert "an edit it has not saved yet is refused" in said
        _shot(tablet, "lease-take-over.png")
        tablet.click("#lease-take-yes")
        _writer(tablet)

        _reader(desk)
        assert "took over writing plates" in desk.locator("#lease-title").inner_text()
        _shot(desk, "lease-taken-over.png")

        # The new writer writes, and the old one can no longer.
        tablet.click("#rail-parameters")
        tablet.fill("#param-n", "5")
        assert _eventually(lambda: _values(root), {"n": 5}) == {"n": 5}
        desk_sent = _written(desk)
        desk.click("#rail-parameters")
        desk.fill("#param-n", "1")
        desk.wait_for_function(f"() => ({BODIES})() === 1", timeout=BOOT_MS)
        desk.wait_for_timeout(1500)
        assert desk_sent == []
        assert _values(root) == {"n": 5}
        desk.context.close()
        tablet.context.close()


# ---- AC#3: a lease whose holder stops renewing lapses, and nobody has to do anything ------


def test_a_lease_nobody_renews_lapses_and_the_reader_becomes_the_writer_by_itself(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = _seeded(tmp_path)
    with _hosted(root, expiry_ms=4000) as url:
        # A holder that takes the project and is never heard from again: a tablet put to
        # sleep mid-edit, which lets nothing go.
        assert _lease(url, "POST", "take", "ghost-0123456789abcdef")["yours"] is True
        # Not `_opened`: Python can take longer to come up than this lease takes to lapse, and
        # the lease is asked for as soon as the project is read, long before the first run.
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        page = context.new_page()
        page.goto(url)
        _reader(page, timeout=4000)
        assert "a script" in page.locator("#lease-title").inner_text()
        # Nothing is pressed from here on.
        _writer(page, timeout=15_000)
        _rendered(page)
        assert page.locator("#standing").is_hidden()
        page.click("#rail-parameters")
        page.fill("#param-n", "3")
        assert _eventually(lambda: _values(root), {"n": 3}) == {"n": 3}
        page.context.close()


# ---- AC#4: a reload reclaims the tab's own lease at once ------------------------------


def test_a_reload_reclaims_its_own_lease_at_once_without_waiting_for_it_to_lapse(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = _seeded(tmp_path)
    # The app's own expiry, a minute: a reload that had to wait for its old lease to lapse
    # would sit read-only for most of that.
    with _hosted(root) as url:
        desk = _opened(browser, url)
        _writer(desk)
        tablet = _opened(browser, url)
        _reader(tablet)
        holder = desk.evaluate("() => sessionStorage.getItem('bench.holder')")

        # The reload must not be able to let go on its way out: what is being shown is that
        # the tab's own id reclaims the lease, not that the release happened to land.
        stopped: list[str] = []
        desk.context.route(
            lambda target: "/__bench/leases/" in target and "act=release" in target,
            lambda route: _refused(route, stopped),
        )
        started = time.monotonic()
        desk.reload()
        _rendered(desk)
        _writer(desk, timeout=10_000)
        assert time.monotonic() - started < 30, "the reload waited for its own lease"
        assert stopped, "the reload let go of nothing, so this showed nothing about reclaiming"
        assert desk.evaluate("() => sessionStorage.getItem('bench.holder')") == holder
        # And the tablet never had it in between.
        assert tablet.locator("#editor").get_attribute("data-readonly") == "true"
        assert _lease(url)["holder"] is not None
        desk.context.close()
        tablet.context.close()


# ---- AC#5: a closed tab lets go promptly, and the expiry is there for when it does not ------


def test_closing_the_writers_tab_lets_the_reader_have_it_well_before_the_lease_would_lapse(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = _seeded(tmp_path)
    # Twelve seconds, renewed every three: a lease let go on close is taken on the reader's
    # next ask, while one left to lapse is at least nine seconds away.
    with _hosted(root, expiry_ms=12_000) as url:
        desk = _opened(browser, url)
        _writer(desk)
        tablet = _opened(browser, url)
        _reader(tablet)
        started = time.monotonic()
        desk.close()
        _writer(tablet, timeout=15_000)
        assert time.monotonic() - started < 8, "the reader waited for the lease to lapse"
        desk.context.close()
        tablet.context.close()
