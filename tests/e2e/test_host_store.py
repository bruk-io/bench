"""End to end: task-52's other implementation of `store.ts`'s protocol - the host route from
task-45, with the outbox (`web/src/outbox.ts`) in front of it for whatever has not landed there
yet - against a real server and a real browser.

`tests/adapter/test_projects_route.py` and `tests/e2e/test_projects_preview.py` drive the route
itself; `web/src/outbox.test.ts` drives the outbox's coalescing and persistence against real
IndexedDB, with no server behind it at all. What only a real browser against a real route can
show is what this file is for: a write blocked at the network and drained once it is not, several
edits while blocked landing as one PUT, a write the route refuses as `moved` reported and left
alone, and typing continuously against a reachable host never conflicting with itself.

Each test gets its own project root and its own `vite preview`, seeded with one project
directory - `cabinet/`, a script and its `bench.toml`, the shape `web/src/project-files.ts` maps
a project onto since task-46 - so the app boots straight onto it.
"""

import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tools import preview
from tools.projects import VARIABLE

pytestmark = pytest.mark.e2e

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page, Response

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

PROJECT = "cabinet"
SCRIPT = "from bench import *\n\nshow((part('plate', face(rect(60, 40)), Stock(3, 'ply')),))\n"
VALUES = '[project]\nentry = "cabinet.py"\n\n[values]\n'

ROUTE = re.compile(r"/__bench/projects/")

_REACH_TEXT_EXPR = "document.querySelector('#reach')?.textContent ?? ''"
_REACH_STATE_EXPR = "document.querySelector('#reach')?.dataset.state ?? ''"


def _reach_text(page: Page) -> str:
    text = page.evaluate(f"() => {_REACH_TEXT_EXPR}")
    assert isinstance(text, str)
    return text


def _reach_state(page: Page) -> str:
    state = page.evaluate(f"() => {_REACH_STATE_EXPR}")
    assert isinstance(state, str)
    return state


def _wait_reach_state(page: Page, want: str, timeout: int = 20_000) -> None:
    page.wait_for_function(f"() => ({_REACH_STATE_EXPR}) === '{want}'", timeout=timeout, polling=50)


def _wait_reach_shown(page: Page) -> None:
    page.wait_for_function(f"() => ({_REACH_TEXT_EXPR}) !== ''", timeout=BOOT_MS, polling=50)


def _seed(root: Path) -> Path:
    """A projects root with `cabinet/cabinet.py` and its `bench.toml` already on it, so the app
    boots onto that project."""
    project = root / PROJECT
    project.mkdir(parents=True)
    (project / "cabinet.py").write_text(SCRIPT)
    (project / "bench.toml").write_text(VALUES)
    return project


def _wait_editor(page: Page, text: str) -> None:
    """Wait until the editor shows `text` - the project read off the host and put on screen,
    which is later than the reach chip's first "ok": that is said the moment the host is found,
    before the boot's own read of the project has finished."""
    lines = "Array.from(document.querySelectorAll('.cm-content .cm-line'), (l) => l.textContent)"
    page.wait_for_function(f"() => {lines}.join('\\n').includes({text!r})", timeout=BOOT_MS)


def _type(page: Page, text: str) -> None:
    page.locator(".cm-content").click()
    page.keyboard.press("ControlOrMeta+A")
    page.keyboard.type(text)


def _block_writes(context: BrowserContext) -> None:
    """Refuse every write the route would otherwise take - PUT, POST, DELETE - while letting
    the reads a boot needs (GET) through, so the app boots normally and only what the outbox
    sends afterwards is blocked."""
    context.route(
        ROUTE,
        lambda route: route.continue_() if route.request.method == "GET" else route.abort(),
    )


def test_a_write_blocked_at_the_network_survives_a_reload_and_drains_once_unblocked(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = tmp_path / "projects"
    project = _seed(root)
    with preview.served(env={VARIABLE: str(root)}) as url:
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(url)
        _wait_reach_shown(page)
        _wait_reach_state(page, "ok")
        _block_writes(context)

        _type(page, SCRIPT + "# edited while blocked\n")
        _wait_reach_state(page, "warn")
        assert _reach_text(page) == "not yet reached host"
        OUT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(OUT / "host-store-not-reached.png"))
        assert "edited while blocked" not in (project / "cabinet.py").read_text()

        context.unroute(ROUTE)
        _wait_reach_state(page, "ok")
        page.screenshot(path=str(OUT / "host-store-saved.png"))
        assert "edited while blocked" in (project / "cabinet.py").read_text()

        # Reload: what was blocked has landed, so the script on screen and on disk agree,
        # with nothing left for the outbox to still be holding (AC#3). The reach chip reads
        # "ok" the moment `chosenStore()` resolves, before `store.load()` has replaced the
        # editor's text, so this waits for the editor itself rather than the chip.
        page.reload()
        _wait_reach_shown(page)
        editor_lines = (
            "() => Array.from(document.querySelectorAll('.cm-content .cm-line'),"
            " (l) => l.textContent).join('\\n')"
        )
        page.wait_for_function(
            f"() => ({editor_lines})().includes('edited while blocked')", timeout=BOOT_MS
        )
        _wait_reach_state(page, "ok")
        context.close()


def test_several_edits_while_blocked_land_as_one_write(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = tmp_path / "projects"
    project = _seed(root)
    with preview.served(env={VARIABLE: str(root)}) as url:
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        landed: list[Response] = []
        page.on(
            "response",
            lambda r: (
                landed.append(r)
                if r.request.method == "PUT" and "cabinet.py" in r.url and r.ok
                else None
            ),
        )
        page.goto(url)
        _wait_reach_shown(page)
        _wait_reach_state(page, "ok")
        _block_writes(context)

        page.locator(".cm-content").click()
        page.keyboard.press("ControlOrMeta+A")
        page.keyboard.type(SCRIPT)
        for char in "abcde":
            page.keyboard.type(char)
        _wait_reach_state(page, "warn")

        context.unroute(ROUTE)
        _wait_reach_state(page, "ok")
        assert (project / "cabinet.py").read_text() == f"{SCRIPT}abcde"
        assert len(landed) == 1, f"expected one landed write for cabinet.py, saw {len(landed)}"
        context.close()


def test_a_write_the_host_refuses_as_moved_is_reported_and_not_retried(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = tmp_path / "projects"
    project = _seed(root)
    with preview.served(env={VARIABLE: str(root)}) as url:
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(url)
        _wait_reach_shown(page)
        _wait_reach_state(page, "ok")
        # The boot's own read has to have happened first, or the change below is simply what
        # the boot reads - the race that made this check fail now and then on main.
        _wait_editor(page, "part('plate'")

        # Somebody else's editor moves the file from under the browser, between the boot's
        # own read and the edit below.
        (project / "cabinet.py").write_text(SCRIPT + "# changed on the host\n")

        # Waited for the PUT itself (a real network round trip) rather than only polling the
        # chip: under a full e2e run's CPU load the outbox's own `setTimeout`-driven debounce
        # can lag well behind wall-clock time, and this is the one event that proves the
        # refused write was actually attempted rather than still waiting to be sent.
        with page.expect_response(
            lambda r: r.request.method == "PUT" and "cabinet.py" in r.url, timeout=90_000
        ) as response_info:
            _type(page, SCRIPT + "# changed in the browser\n")
        assert response_info.value.status == 409
        _wait_reach_state(page, "error", timeout=15_000)
        assert "cabinet.py" in _reach_text(page)
        OUT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(OUT / "host-store-refused.png"))

        # Never retried until it wins: waited well past the outbox's own backoff, the disk
        # still says what the host, not the browser, put there.
        page.wait_for_timeout(6000)
        assert (project / "cabinet.py").read_text() == SCRIPT + "# changed on the host\n"
        assert _reach_state(page) == "error"
        context.close()


def test_typing_continuously_against_a_reachable_host_never_conflicts(
    tmp_path: Path, browser: Browser, built_app: Path
) -> None:
    root = tmp_path / "projects"
    project = _seed(root)
    with preview.served(env={VARIABLE: str(root)}) as url:
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(url)
        _wait_reach_shown(page)

        page.locator(".cm-content").click()
        page.keyboard.press("End")
        for char in "# typed one character at a time\n":
            page.keyboard.type(char)
            page.wait_for_timeout(20)

        _wait_reach_state(page, "ok")
        assert _reach_state(page) != "error"
        assert "typed one character at a time" in (project / "cabinet.py").read_text()
        context.close()
