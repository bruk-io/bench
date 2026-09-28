"""End to end: task-91 - the centre is Code, Split or View, and this browser remembers which;
and task-94 - View folds the project's files away too, and the header's files button shows or
folds them at any width.

decision-12: "Centre: editor and view, with a Code | Split | View control: Code for writing,
View for checking and printing, Split as today." A browser that never chose sees Split; the
control in the header gives the editor or the view the whole centre, the inspector staying on
the right in every one of them; ``Ctrl/Cmd+\\`` steps through the three from anywhere, the
editor included; and the choice outlives a reload - or, where the browser will not keep
anything, lasts as long as the page and breaks nothing (AC#1). The lease chip that took the
banner's place is driven in ``test_write_lease.py``, with the two browsers it needs.

Each check has a browser context and a server of its own: what is remembered is the subject.
"""

import contextlib
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tools import preview
from tools.projects import VARIABLE

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

pytestmark = pytest.mark.e2e

BOOT_MS = 240_000

OUT = preview.WEB / "e2e" / "out"

BLOCKED = """
Object.defineProperty(window, 'localStorage', {
    configurable: true,
    get() { throw new DOMException('blocked for the test', 'SecurityError'); },
});
"""
"""A browser that keeps nothing: every touch of ``localStorage`` throws, as a blocked origin's
does - before the app's own code runs."""

EDITOR_TEXT = (
    "() => Array.from(document.querySelectorAll('.cm-content .cm-line'),"
    " (line) => line.textContent).join('\\n')"
)


@contextlib.contextmanager
def _opened(browser: Browser, tmp_path: Path, blocked: bool = False) -> Iterator[Page]:
    """The app over an empty projects root of its own, in a fresh browser, booted and showing
    its first scene."""
    root = tmp_path / "projects"
    root.mkdir()
    with preview.served(env={VARIABLE: str(root)}) as url:
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        if blocked:
            context.add_init_script(BLOCKED)
        page = context.new_page()
        page.goto(url)
        _rendered(page)
        try:
            yield page
        finally:
            context.close()


def _rendered(page: Page) -> None:
    # Attached, not visible: in the Code layout the view is drawn to while it is put away.
    page.wait_for_selector(
        "#canvas3d[data-bodies]:not([data-bodies='0'])", state="attached", timeout=BOOT_MS
    )
    page.wait_for_function(
        "() => document.querySelector('#state')?.dataset.state !== 'running'", timeout=BOOT_MS
    )


def _layout(page: Page) -> str:
    return page.locator("#groups").get_attribute("data-layout") or ""


def _pressed(page: Page) -> list[str]:
    return [
        one.strip()
        for one in page.locator('bench-layout-switch button[aria-pressed="true"]').all_inner_texts()
    ]


def _width(page: Page, selector: str) -> float:
    box = page.locator(selector).bounding_box()
    assert box is not None, f"{selector} is not on screen"
    return box["width"]


def _shot(page: Page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.wait_for_timeout(300)  # past the buttons' own fade, so the picture shows the one pressed
    page.screenshot(path=str(OUT / name))


# ---- AC#1: three layouts, by the control, each giving the centre to what it names ----------


def test_split_first_then_code_and_view_each_take_the_whole_centre_beside_the_inspector(
    browser: Browser, tmp_path: Path, built_app: Path
) -> None:
    with _opened(browser, tmp_path) as page:
        assert _layout(page) == "split"
        assert _pressed(page) == ["Split"]
        assert page.locator("#editor").is_visible()
        assert page.locator("#canvas3d").is_visible()
        split_view = _width(page, "#canvas3d")
        _shot(page, "layout-split.png")

        page.click("#layout-code")
        assert _layout(page) == "code"
        assert _pressed(page) == ["Code"]
        assert page.locator("#editor").is_visible()
        assert page.locator("#canvas3d").is_hidden()
        assert page.locator("#inspector").is_visible()
        # The editor has the centre, all of it, and the inspector keeps its own column.
        assert abs(_width(page, ".group-editor") - _width(page, "#groups")) < 2
        _shot(page, "layout-code.png")

        page.click("#layout-view")
        assert _layout(page) == "view"
        assert _pressed(page) == ["View"]
        assert page.locator("#editor").is_hidden()
        assert page.locator("#canvas3d").is_visible()
        assert page.locator("#inspector").is_visible()
        assert abs(_width(page, ".group-view") - _width(page, "#groups")) < 2
        assert _width(page, "#canvas3d") > split_view * 1.3
        # Still the scene, drawn at the new size, and still answering the view's own controls.
        assert int(page.locator("#canvas3d").get_attribute("data-bodies") or 0) > 0
        page.click("#fit")
        _shot(page, "layout-view.png")

        page.click("#layout-split")
        assert _layout(page) == "split"
        assert page.locator("#editor").is_visible()
        assert page.locator("#canvas3d").is_visible()
        assert abs(_width(page, "#canvas3d") - split_view) < 2


# ---- AC#1: a shortcut, from anywhere - the editor included --------------------------------


def test_the_shortcut_steps_through_the_layouts_even_from_the_editor_and_types_nothing(
    browser: Browser, tmp_path: Path, built_app: Path
) -> None:
    with _opened(browser, tmp_path) as page:
        page.click(".cm-content")
        before = page.evaluate(EDITOR_TEXT)
        page.keyboard.press("Control+Backslash")
        assert _layout(page) == "view"
        page.keyboard.press("Control+Backslash")
        assert _layout(page) == "code"
        assert _pressed(page) == ["Code"]
        page.click(".cm-content")
        page.keyboard.press("Control+Backslash")
        assert _layout(page) == "split"
        assert page.evaluate(EDITOR_TEXT) == before, "the shortcut typed into the script"
        # The editor's own Mod+Shift+\ (the matching bracket) is left to it.
        page.keyboard.press("Control+Shift+Backslash")
        assert _layout(page) == "split"


# ---- AC#1: remembered per browser --------------------------------------------------------


def test_the_layout_chosen_is_the_layout_after_a_reload(
    browser: Browser, tmp_path: Path, built_app: Path
) -> None:
    with _opened(browser, tmp_path) as page:
        page.click("#layout-view")
        assert page.evaluate("() => localStorage.getItem('bench.layout')") == "view"
        page.reload()
        # Laid out before the first scene is drawn, not after: nothing jumps once it is.
        page.wait_for_selector("#groups[data-layout='view']", timeout=BOOT_MS)
        _rendered(page)
        assert _pressed(page) == ["View"]
        assert page.locator("#editor").is_hidden()
        assert page.locator("#canvas3d").is_visible()
        page.click("#layout-code")
        page.reload()
        _rendered(page)
        assert _layout(page) == "code"


def test_a_browser_that_keeps_nothing_still_draws_and_still_switches(
    browser: Browser, tmp_path: Path, built_app: Path
) -> None:
    with _opened(browser, tmp_path, blocked=True) as page:
        assert (
            page.evaluate(
                "() => { try { localStorage; return 'kept'; } catch { return 'blocked'; } }"
            )
            == "blocked"
        )
        assert _layout(page) == "split"
        page.click("#layout-view")
        assert _layout(page) == "view"
        assert page.locator("#canvas3d").is_visible()
        page.keyboard.press("Control+Backslash")
        assert _layout(page) == "code"
        assert page.locator("#editor").is_visible()


# ---- what the editor group has to say is never put away with it ----------------------------


def test_a_notice_in_the_editor_group_is_shown_even_in_the_view_layout(
    browser: Browser, tmp_path: Path, built_app: Path
) -> None:
    """A host whose projects root is missing says so over the editor; a browser that last
    chose View must still be told, so the centre is split again while it is up."""
    with preview.served(env={VARIABLE: str(tmp_path / "not-there")}) as url:
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        context.add_init_script("localStorage.setItem('bench.layout', 'view')")
        page = context.new_page()
        page.goto(url)
        page.wait_for_selector("#no-host:not([hidden])", timeout=BOOT_MS)
        assert _layout(page) == "view"
        assert page.locator("#no-host").is_visible()
        assert page.locator("#canvas3d").is_visible()
        context.close()


# ---- task-94 AC#7: View folds the files too; the header's button shows and folds them ------


def _files_pressed(page: Page) -> str:
    return page.locator("#files-toggle").get_attribute("aria-pressed") or ""


def test_view_folds_the_files_so_the_view_takes_everything_but_the_inspector(
    browser: Browser, tmp_path: Path, built_app: Path
) -> None:
    with _opened(browser, tmp_path) as page:
        assert page.locator("#sidebar").is_visible()
        assert _files_pressed(page) == "true"
        page.click("#layout-view")
        assert page.locator("#sidebar").is_hidden(), "View kept the files beside the view"
        assert _files_pressed(page) == "false"
        # The centre and the inspector share the whole width: nothing else is left in the row.
        shell = _width(page, "#shell")
        assert abs(_width(page, "#centre") + _width(page, "#inspector-pane") - shell) < 2
        folded_view = _width(page, "#canvas3d")
        _shot(page, "layout-view-files-folded.png")

        # Asked for, the files come back beside the view, and go again on a second click.
        page.click("#files-toggle")
        assert page.locator("#sidebar").is_visible()
        assert _files_pressed(page) == "true"
        assert _width(page, "#canvas3d") < folded_view - 100
        page.click("#files-toggle")
        assert page.locator("#sidebar").is_hidden()

        # Split shows them by itself again; the button folds them there too.
        page.click("#layout-split")
        assert page.locator("#sidebar").is_visible()
        split_view = _width(page, "#canvas3d")
        page.click("#files-toggle")
        assert page.locator("#sidebar").is_hidden()
        assert _files_pressed(page) == "false"
        assert _width(page, "#canvas3d") > split_view + 50, "folding gave the view nothing"
        page.click("#files-toggle")
        assert page.locator("#sidebar").is_visible()


def test_a_narrow_window_keeps_the_files_folded_until_they_are_asked_for(
    browser: Browser, tmp_path: Path, built_app: Path
) -> None:
    """Where the files and the work cannot sit side by side, the files take the centre's
    place when asked for and give it back on the next click - the rail's one job, which the
    header's button does now."""
    with _opened(browser, tmp_path) as page:
        page.set_viewport_size({"width": 900, "height": 900})
        # The button follows the width as it changes, and says so as soon as it has.
        page.wait_for_selector("#files-toggle[aria-pressed='false']", timeout=5_000)
        assert page.locator("#sidebar").is_hidden()
        assert page.locator("#canvas3d").is_visible()
        page.click("#files-toggle")
        assert page.locator("#sidebar").is_visible()
        assert page.locator("#centre").is_hidden(), "the files and the work are sharing a row"
        assert page.locator("#inspector").is_visible()
        assert _files_pressed(page) == "true"
        page.click("#files-toggle")
        assert page.locator("#sidebar").is_hidden()
        assert page.locator("#canvas3d").is_visible()
