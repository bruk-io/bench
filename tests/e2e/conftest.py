"""What the end-to-end checks are driven through: one build, a server per page, one browser.

The app under test is the built one - ``web/dist`` served by ``vite preview`` on whatever
port it picks for itself - because that is what a user gets: the bundled Python sources,
the self-hosted Pyodide, the real worker. Both of those are :mod:`tools.preview`, which
``tools/qa.py`` drives the same app through by hand; the build is made when a content hash
of everything it is made from has changed since the last one, so a check never passes
against a stale bundle and never rebuilds when nothing it depends on has. Each page is
served over a projects root of its own (``serve``), since the host is where its projects
live, and the server is stopped with the page whatever the tests do.

Everything is shared: the same chromium page walks through the checks in file order, the
way a person walks through the app, and ``page_errors`` collects everything the console
complained about along the way so one test at the end can insist there was nothing.
"""

import contextlib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pytest

from tools import preview
from tools.projects import VARIABLE

if TYPE_CHECKING:
    from playwright.sync_api import Browser, ConsoleMessage, Page

OUT = preview.WEB / "e2e" / "out"
"""Where the screenshots land - gitignored, and kept for looking at afterwards."""

BOOT_MS = 240_000
"""How long the app may take to boot Python and draw the first scene, in milliseconds."""


# ---- the built app, served ------------------------------------------------------------


@pytest.fixture(scope="session")
def built_app() -> Path:
    """``web/dist``, built when what it is made from has changed since it was."""
    return preview.built()


class Hosted(NamedTuple):
    """The app served with a projects root of its own: where to point a browser, and the
    directory the projects it keeps land in."""

    url: str
    root: Path


type Serve = Callable[[], contextlib.AbstractContextManager[Hosted]]
"""A fresh server over a fresh, empty projects root, for as long as the ``with`` lasts."""


@pytest.fixture(scope="session")
def serve(built_app: Path, tmp_path_factory: pytest.TempPathFactory) -> Serve:
    """Hand a fixture a server of its own, over a projects root of its own.

    Since task-46 the host is where every project lives, so two browser contexts on one server
    share every project on it - exactly what a desktop and a tablet should do, and exactly what
    a check that wants a first visit must not. So each page below gets a root of its own
    (``BENCH_PROJECTS``) and a ``vite preview`` over it; one costs about a quarter of a second,
    and it keeps every check off the repository's own ``projects/``.
    """

    @contextlib.contextmanager
    def served() -> Iterator[Hosted]:
        root = tmp_path_factory.mktemp("projects")
        with preview.served(env={VARIABLE: str(root)}) as url:
            yield Hosted(url, root)

    return served


@pytest.fixture(scope="session")
def screenshots() -> Path:
    """Where a test leaves a picture of what it saw."""
    OUT.mkdir(parents=True, exist_ok=True)
    return OUT


# ---- the browser ---------------------------------------------------------------------


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    """One headless chromium for the session."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as play:
        found = play.chromium.launch()
        try:
            yield found
        finally:
            found.close()


@pytest.fixture(scope="module")
def page_errors() -> list[str]:
    """Everything the page threw or logged as an error while the module ran."""
    return []


@pytest.fixture(scope="module")
def page(browser: Browser, serve: Serve, page_errors: list[str]) -> Iterator[Page]:
    """The app in a light-themed desktop window, booted and showing its first scene."""
    with serve() as served:
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            color_scheme="light",
            accept_downloads=True,
        )
        found = context.new_page()
        found.on("pageerror", lambda problem: page_errors.append(str(problem)))
        found.on("console", lambda message: _logged(message, page_errors))
        found.goto(served.url)
        _rendered(found)
        try:
            yield found
        finally:
            context.close()


@pytest.fixture(scope="module")
def dark_page(browser: Browser, serve: Serve) -> Iterator[Page]:
    """The app again from a clean slate, in the dark theme: nothing typed, nothing stored."""
    with serve() as served:
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        found = context.new_page()
        found.goto(served.url)
        _rendered(found)
        try:
            yield found
        finally:
            context.close()


def _logged(message: ConsoleMessage, errors: list[str]) -> None:
    if message.type == "error":
        errors.append(message.text)


@pytest.fixture
def clean_host(serve: Serve) -> Iterator[Hosted]:
    """The server and projects root ``clean_page`` is served from, for a check that reads what
    the page kept on the host."""
    with serve() as served:
        yield served


@pytest.fixture
def clean_page(browser: Browser, clean_host: Hosted) -> Iterator[Page]:
    """The app on a slate of its own: nothing remembered, nothing on its host, booted, showing
    its first scene.

    A check that cares about what is kept, or about what the app does on a reload, cannot
    share the session page - the kept source and overrides are exactly what it is about.
    """
    context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    found = context.new_page()
    found.goto(clean_host.url)
    _rendered(found)
    try:
        yield found
    finally:
        context.close()


@pytest.fixture
def booting_page(browser: Browser, serve: Serve) -> Iterator[Page]:
    """A page caught on its way up: ``goto`` returns as soon as the document commits, so
    what the app says while the runtime downloads is still on screen to be read."""
    with serve() as served:
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        found = context.new_page()
        found.goto(served.url, wait_until="commit")
        try:
            yield found
        finally:
            context.close()


@pytest.fixture(scope="module")
def printed_errors() -> list[str]:
    """Everything the printed-part page threw or logged as an error while the module ran."""
    return []


@pytest.fixture(scope="module")
def printed_page(browser: Browser, serve: Serve, printed_errors: list[str]) -> Iterator[Page]:
    """The app showing a printed part: the Gridfinity bin, built by the browser's own
    Manifold and drawn in the 3D pane.

    One page for the whole printed story - it renders, a face answers to a ref, the ref goes
    into the script, the STL and the 3MF come down, a laser example puts the drawing back,
    and a check that fails is reported - because that is the order a person does them in and
    because booting Python costs seconds.
    """
    with serve() as served:
        context = browser.new_context(
            viewport={"width": 1440, "height": 900}, color_scheme="light", accept_downloads=True
        )
        found = context.new_page()
        found.on("pageerror", lambda problem: printed_errors.append(str(problem)))
        found.on("console", lambda message: _logged(message, printed_errors))
        found.goto(served.url)
        _rendered(found)
        _example(found, "gridfinity_bin.py")
        try:
            yield found
        finally:
            context.close()


@pytest.fixture(scope="module")
def no_modeller_page(browser: Browser, serve: Serve) -> Iterator[Page]:
    """The app with the solid modeller taken away: every request under ``/manifold/`` is
    refused, so the worker's load of it fails and the run is given no kernel at all.

    Not a stand-in for anything - the app under test is the built one and the only change is
    that half a megabyte does not arrive, which is a blocked CDN, a truncated deploy or a
    browser without WASM. What has to survive is everything a laser part needs.
    """
    with serve() as served:
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        context.route("**/manifold/**", lambda route: route.abort())
        found = context.new_page()
        found.goto(served.url)
        _rendered(found)
        try:
            yield found
        finally:
            context.close()


def _example(page: Page, name: str) -> None:
    """Pick one of the shipped examples and wait for the run it starts."""
    page.click("#examples-button")
    page.locator("#examples").get_by_role("button", name=name, exact=True).click()
    _settled(page)


@pytest.fixture(scope="session")
def example() -> Callable[[Page, str], None]:
    """Hand a test the "pick an example and wait for it" walk the fixtures use."""
    return _example


@pytest.fixture(scope="module")
def runaway_page(browser: Browser, serve: Serve) -> Iterator[Page]:
    """One page for the runaway-script story, which is three checks in sequence: the
    watchdog stops it, a reload does not replay it, and the app still works afterwards."""
    with serve() as served:
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        found = context.new_page()
        found.goto(served.url)
        _rendered(found)
        try:
            yield found
        finally:
            context.close()


@pytest.fixture(scope="module")
def files_host(serve: Serve) -> Iterator[Hosted]:
    """The server and projects root ``files_page`` is served from, so the files story can read
    what it kept off the disk it was kept on."""
    with serve() as served:
        yield served


@pytest.fixture(scope="module")
def files_page(browser: Browser, files_host: Hosted) -> Iterator[Page]:
    """One page for the files story, in the order a person meets it: a new project, the one
    before it still there, an example arriving beside them, and a rename and a delete that
    a reload keeps."""
    context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    found = context.new_page()
    found.goto(files_host.url)
    _rendered(found)
    try:
        yield found
    finally:
        context.close()


# ---- waiting -------------------------------------------------------------------------


def _settled(page: Page) -> None:
    """Wait until the app is not mid-run."""
    page.wait_for_function(
        "() => document.querySelector('#state')?.dataset.state !== 'running'",
        timeout=BOOT_MS,
    )


def _rendered(page: Page) -> None:
    """Wait for the first scene: Python boots, runs the example, and the view draws it."""
    page.wait_for_selector("#canvas3d[data-bodies]:not([data-bodies='0'])", timeout=BOOT_MS)
    _settled(page)


@pytest.fixture(scope="session")
def settle() -> Callable[[Page], None]:
    """Hand a test the wait for "the app has finished running", so it can act and then let
    the debounce and the worker catch up."""
    return _settled
