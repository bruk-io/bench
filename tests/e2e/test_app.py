"""End to end: the built app in a browser, doing what the product promises.

One chromium page walks the whole product in file order, as a person would: it waits for
Python to boot and draw the cabinet's plates, edits a parameter and watches the geometry
change, clicks a plate and inserts its ref, puts the cursor in a ref string and watches what
it names light up, downloads a sheet and the zip and opens both, then types a syntax error
and checks the editor marks the line. The dark and narrow layouts get a clean page of their own.
Screenshots land in ``web/e2e/out/``.

The app is a workbench: a rail whose icons switch what the sidebar is, a centre holding the
script beside the 3D view, a panel across the bottom and a status bar under everything. So the
walks below go through that furniture - the rail to reach the parameters, the panel's tabs to
read what a run said - and the checks that are about the furniture itself are under "the shell"
and "the refs tree".

Run it with ``uv run pytest -m e2e``; the default run leaves it out.
"""

import base64
import shutil
import time
import tomllib
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

try:
    from playwright.sync_api import FloatRect, Page
except ImportError:  # pragma: no cover - the import is the check
    pytest.skip("playwright is not installed - uv pip install playwright", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"

if not (WEB / "node_modules").is_dir():
    pytest.skip("web/node_modules missing - run npm install in web/", allow_module_level=True)
if shutil.which("npx") is None:
    pytest.skip("npx not on PATH", allow_module_level=True)

BOOT_MS = 240_000
"""How long the app may take to run a script, in milliseconds."""

PULL = "drawer-front-1/pull"
"""The ref that gets clicked, inserted and highlighted."""

EDITOR_TEXT = """() => {
    const lines = document.querySelectorAll('.cm-content .cm-line');
    return Array.from(lines, (line) => line.textContent).join('\\n');
}"""

CHANGED = """(before) => {
    const pane = document.querySelector('#canvas3d');
    return `${pane?.dataset.triangles}|${pane?.dataset.bounds}` !== before;
}"""
"""Whether the view drew something other than ``before``, a :func:`_drawn` fingerprint."""

INSERTED = """(wanted) => {
    const lines = document.querySelectorAll('.cm-content .cm-line');
    const text = Array.from(lines, (line) => line.textContent).join('\\n');
    return text.includes(wanted);
}"""

GUTTER_MARKED = """() => {
    const cells = document.querySelectorAll('.cm-errorGutter .cm-gutterElement');
    return Array.from(cells).some(
        (cell) => cell.style.visibility !== 'hidden' && cell.textContent.trim() !== ''
    );
}"""

ONE_COLUMN = """() => {
    const groups = document.querySelector('#groups');
    if (groups === null) return false;
    return getComputedStyle(groups).gridTemplateColumns.split(' ').length === 1;
}"""
"""Whether the script and the view have stopped sharing a row - the narrow layout."""

CURSOR_LINE = """() => {
    const marked = document.querySelector('.cm-activeLineGutter');
    return marked === null ? 0 : Number(marked.textContent.trim());
}"""
"""Which line the editor's cursor is on, as its gutter number says."""

OVERRIDES = """() => {
    try {
        const kept = JSON.parse(window.localStorage.getItem('bench.files') ?? 'null');
        const open = kept?.files?.find((file) => file.name === kept.current);
        return open === undefined ? null : open.values;
    } catch { return null; }
}"""
"""The open project's values as the browser keeps them: the TOML document itself."""

DRAWN = "#canvas3d[data-bodies]:not([data-bodies='0'])"
"""The view once it has drawn a scene with something in it."""

BODIES = "() => Number(document.querySelector('#canvas3d')?.dataset.bodies ?? 0)"

HOW_TO_SELECT = "click any face to get its ref"
"""What the selection bar says with nothing selected - ``status.ts``' own words."""

# A press the browser takes away mid-gesture: without a `pointercancel` handler the view
# would still be holding the press, and the pointer coming up afterwards would land as a
# click. The mouse's own pointer id, so the orbit control's pointer capture has a real one.
CANCELLED_CLICK = """() => {
    const canvas = document.querySelector('#canvas3d canvas');
    const box = canvas.getBoundingClientRect();
    const at = (type) => canvas.dispatchEvent(new PointerEvent(type, {
        pointerId: 1, pointerType: 'mouse', isPrimary: true,
        clientX: box.left + box.width / 2, clientY: box.top + box.height / 2,
        button: 0, buttons: type === 'pointerup' ? 0 : 1, bubbles: true, cancelable: true,
    }));
    at('pointerdown');
    at('pointercancel');
    at('pointerup');
    return document.querySelector('#selection').textContent.trim();
}"""

# How much red a sheet's thumbnail puts on the screen: the image drawn at the size it is shown
# into a canvas, and its cut-line pixels counted. A white box counts none.
THUMBNAIL_INK = """async () => {
    const list = document.querySelector('bench-sheets');
    const picture = list?.shadowRoot?.querySelector('img');
    if (!picture) return -1;
    await picture.decode();
    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    const pen = canvas.getContext('2d');
    pen.drawImage(picture, 0, 0, 64, 64);
    const data = pen.getImageData(0, 0, 64, 64).data;
    let red = 0;
    for (let at = 0; at < data.length; at += 4) {
        const [r, g, b, a] = [data[at], data[at + 1], data[at + 2], data[at + 3]];
        if (a > 0 && r > 150 && g < 140 && b < 140) red += 1;
    }
    return red;
}"""

RUNAWAY = "while True:\n    pass\n"
"""The script the watchdog exists for: nothing outside the loop can interrupt it."""

SLOWDOWN = "\nimport time; time.sleep(1.0)\n"
"""Appended to a script to make one run take a known, measurable second."""

DEBOUNCE_MS = 300
"""How long the app waits after a keystroke before it runs - ``main.ts``' own constant."""

WATCHDOG_MS = 40_000
"""How long a check may wait for the 15 s watchdog to fire and the panel to say so."""


def _overrides(page: Page) -> dict[str, object]:
    """The open project's values as the browser remembers them - read with :mod:`tomllib`,
    which is what makes them a document rather than a blob: the same reader
    ``tools/build.py`` uses on a file beside a script."""
    said = page.evaluate(OVERRIDES)
    return {} if said is None else dict(tomllib.loads(str(said)).get("values", {}))


def _ran(page: Page, settle: Callable[[Page], None]) -> None:
    """Wait out a 300 ms debounce and then the run it starts."""
    page.wait_for_timeout(500)
    settle(page)


def _editor_text(page: Page) -> str:
    return str(page.evaluate(EDITOR_TEXT))


def _container(page: Page, name: str) -> None:
    """Put one container in the sidebar - ``files``, ``refs``, ``parameters``, ``sheets`` -
    the way the rail does. The sidebar shows one at a time, and Playwright will not act on
    what cannot be seen."""
    page.click(f"#rail-{name}")


def _script(page: Page) -> None:
    """Bring the script to the front of the editor group, past any sheet opened beside it."""
    page.click("#tab-script")


def _panel(page: Page, tab: str) -> None:
    """Bring one tab of the bottom panel forward - ``problems``, ``output``, ``stderr``,
    ``files``.

    Only clicks when it has to: a click on the tab already in front is how the panel is put
    away, so asking twice for the tab you are already on would hide what you came to read.
    A collapsed panel reads as ``aria-selected="false"`` on every tab, so this opens one.
    """
    button = page.locator(f"#panel-tab-{tab}")
    if button.get_attribute("aria-selected") != "true":
        button.click()


def _typed(page: Page, text: str) -> None:
    """Type at the end of the script, with the script in front to receive it."""
    _script(page)
    page.locator(".cm-content").click()
    page.keyboard.press("ControlOrMeta+End")
    page.keyboard.type(text)


def _drawn(page: Page) -> str:
    """What the view drew, as a fingerprint: its triangle count and the box the stage filled.
    Two runs of the same settings draw the same; a setting that moves a panel does not."""
    pane = page.locator("#canvas3d")
    return f"{pane.get_attribute('data-triangles')}|{pane.get_attribute('data-bounds')}"


def _bodies(page: Page) -> int:
    """How many parts the view drew."""
    return int(page.locator("#canvas3d").get_attribute("data-bodies") or "0")


def _lit(page: Page) -> int:
    """How many triangles the view has painted as selected."""
    return int(page.locator("#canvas3d").get_attribute("data-lit") or "0")


def _distance(page: Page) -> float:
    """How far the view's camera stands from what it looks at, in millimetres."""
    return float(page.locator("#canvas3d").get_attribute("data-distance") or "0")


def _state(page: Page) -> str | None:
    return page.locator("#state").get_attribute("data-state")


def _status(page: Page) -> str:
    return page.locator("#status").inner_text()


def _reported(page: Page, state: str, shown: str, saying: str | None = None) -> None:
    """Wait for a run to end in ``state`` with ``shown`` - a part of the panel - on screen,
    and saying ``saying`` when that is given.

    The panel is a component, and what it shows is in its shadow root: out of reach of
    ``document.querySelector``, in reach of a locator. So this waits on locators, one after
    the other - each condition holds once it is met, so the order costs nothing.
    """
    page.wait_for_selector(f'#state[data-state="{state}"]', timeout=BOOT_MS)
    part = page.locator(shown) if saying is None else page.locator(shown, has_text=saying)
    part.first.wait_for(timeout=BOOT_MS)


# ---- the first run --------------------------------------------------------------------


@pytest.mark.e2e
def test_the_first_run_draws_the_whole_cabinet(page: Page) -> None:
    bodies = _bodies(page)
    assert bodies > 0, "the viewer drew nothing"
    assert bodies > 5, f"the cabinet is more than five panels; {bodies} were drawn"


@pytest.mark.e2e
def test_the_first_run_reports_ok(page: Page) -> None:
    assert _state(page) == "ok", _status(page)


@pytest.mark.e2e
def test_the_first_run_lists_its_sheets(page: Page) -> None:
    _panel(page, "files")
    assert page.locator("bench-file-row").count() > 0, "no sheet was offered for download"


@pytest.mark.e2e
def test_the_status_bar_says_what_the_run_amounts_to(page: Page) -> None:
    """The count and the timing live under everything now, not in the header."""
    assert "part" in _status(page), _status(page)
    assert page.locator("#made").inner_text().strip() != "", "the title bar names no count"
    assert page.locator("#timing").inner_text().strip().endswith("s"), "the run was not timed"


# ---- the shell: the rail and its containers --------------------------------------------


@pytest.mark.e2e
def test_the_rail_switches_what_the_sidebar_is(clean_page: Page) -> None:
    """VS Code's model: an icon changes the sidebar's contents rather than firing a command.
    One container is showing at a time, and the rail marks which."""
    page = clean_page
    _container(page, "parameters")
    assert page.locator("#container-parameters").is_visible()
    assert page.locator("#container-refs").is_hidden()
    assert page.locator("#rail-parameters").get_attribute("aria-pressed") == "true"
    assert page.locator("#rail-refs").get_attribute("aria-pressed") == "false"

    _container(page, "files")
    assert page.locator("#container-files").is_visible()
    assert page.locator("#container-parameters").is_hidden()
    assert page.locator("#rail-files").get_attribute("aria-pressed") == "true"


@pytest.mark.e2e
def test_which_container_was_open_survives_a_reload(
    clean_page: Page, settle: Callable[[Page], None]
) -> None:
    page = clean_page
    _container(page, "sheets")
    assert page.locator("#container-sheets").is_visible()
    page.reload()
    page.wait_for_selector(DRAWN, timeout=BOOT_MS)
    settle(page)
    assert page.locator("#container-sheets").is_visible(), "a reload forgot the container"


@pytest.mark.e2e
def test_the_rail_counts_what_is_waiting_in_a_container(page: Page) -> None:
    """The badge is what the rail is for: a count worth seeing while its container is shut."""
    _container(page, "refs")
    assert page.locator("#refs-count").inner_text().strip() != ""
    assert page.locator("#rail-param-count").inner_text().strip() == "11"


@pytest.mark.e2e
def test_the_parameters_live_in_the_sidebar_now(clean_page: Page) -> None:
    """The panel generated from the script moved out of the centre and into the rail's own
    container: it is not on screen until the rail is asked for it."""
    page = clean_page
    assert page.locator("#params").is_hidden()
    assert page.locator("#reset").is_hidden() or page.locator("#reset").is_disabled()
    _container(page, "parameters")
    assert page.locator("#params").is_visible()
    assert page.locator("#param-count").inner_text().strip() == "11"


# ---- the parameters panel -------------------------------------------------------------


@pytest.mark.e2e
def test_a_parameter_edit_regrows_the_geometry(page: Page, settle: Callable[[Page], None]) -> None:
    """A panel edit re-runs the script with overrides, without touching its text."""
    before = _drawn(page)
    source = _editor_text(page)
    _container(page, "parameters")
    page.fill("#param-units_x", "6")
    page.wait_for_function(CHANGED, arg=before, timeout=BOOT_MS)
    settle(page)
    after = _drawn(page)
    assert after != before, f"{before} -> {after}"
    assert _editor_text(page) == source, "the override rewrote the script"


@pytest.mark.e2e
def test_inserting_a_ref_from_the_parameters_container_brings_the_script_forward(
    clean_page: Page,
) -> None:
    """The ref lands in the script, so the script is what has to be in front to see it."""
    page = clean_page
    _container(page, "parameters")
    ref = _click_a_face(page, "")
    page.keyboard.press("Control+i")
    page.wait_for_function(INSERTED, arg=f'ref("{ref}")', timeout=30_000)
    assert page.locator("#editor").is_visible()
    assert page.locator("#tab-script").get_attribute("aria-selected") == "true"


# ---- the refs tree: bench's one round-trip ---------------------------------------------


@pytest.mark.e2e
def test_clicking_a_face_reveals_that_ref_in_the_tree(page: Page, screenshots: Path) -> None:
    """Half the round-trip: the drawing is clicked, and the tree opens whatever was shut above
    the row and marks it."""
    _container(page, "refs")
    ref = _click_a_face(page, "")
    row = page.locator(f'bench-refs-tree [data-ref="{ref}"]')
    row.wait_for(timeout=30_000)
    assert row.get_attribute("aria-current") == "true", f"{ref} was not revealed in the tree"
    page.screenshot(path=str(screenshots / "17-tree-reveals.png"))


@pytest.mark.e2e
def test_clicking_the_tree_lights_up_what_it_names(page: Page) -> None:
    """And the other half: a click in the tree selects exactly as a click on a face does, so
    the bar says the ref and the geometry is painted.

    The ref is taken off the drawing first and then cleared, so the row this clicks is one the
    view can certainly light: a name picked blind off the top of the tree could be a branch
    with no geometry under it, and proving nothing lit would prove nothing.
    """
    _container(page, "refs")
    ref = _click_a_face(page, "")
    page.keyboard.press("Escape")
    assert _lit(page) == 0, "Escape did not put the selection down"

    page.locator(f'bench-refs-tree [data-ref="{ref}"]').click()
    page.wait_for_timeout(150)
    assert page.locator("#selection").inner_text().strip() == ref
    assert _lit(page) > 0, f"{ref} was picked in the tree and nothing on screen is coloured"
    assert page.locator("#insert").is_enabled(), "Insert ref is not offered for a picked ref"


RETIRED_BY_FEWER_DRAWERS = "drawer-front-6"
"""A part the cabinet stops making when `drawers` comes down to two.

Part-level on purpose: it certainly has geometry to light when it is picked, and it
certainly ceases to exist afterwards. Dropping the cabinet from six drawers to two retires
300 of its 770 refs, `drawer-front-3` through `drawer-front-6` among them.
"""


@pytest.mark.e2e
def test_a_ref_the_newest_run_no_longer_names_stops_being_selected(
    page: Page, settle: Callable[[Page], None]
) -> None:
    """A ref survives a run, because a name is the same name after a rebuild - but only while
    the run still makes the thing. Pick a part, then change a number so that part is not made
    at all, and the selection has to be put down rather than left naming something gone.

    The view is what notices: it is handed the new scene, finds the chosen ref is in none of
    it, and tells the page, which clears the bar and the tree.
    """
    _container(page, "refs")
    page.locator(f'bench-refs-tree [data-ref="{RETIRED_BY_FEWER_DRAWERS}"]').click()
    page.wait_for_timeout(150)
    assert page.locator("#selection").inner_text().strip() == RETIRED_BY_FEWER_DRAWERS

    before = _drawn(page)
    _container(page, "parameters")
    page.fill("#param-drawers", "2")
    page.wait_for_function(CHANGED, arg=before, timeout=BOOT_MS)
    settle(page)

    said = page.locator("#selection").inner_text().strip()
    assert said == HOW_TO_SELECT, f"a run that stopped making it left {said!r} selected"
    assert not page.locator("#insert").is_enabled(), "Insert ref is offered for a ref nothing names"
    _container(page, "refs")
    assert page.locator(f'bench-refs-tree [data-ref="{RETIRED_BY_FEWER_DRAWERS}"]').count() == 0, (
        "the tree still holds a row the newest run does not name"
    )

    # Put the cabinet back. `page` is module-scoped - one browser page walks every check in
    # this file in order - so a check that changes a number and leaves it changed hands the
    # next one a scene it did not ask for. Nothing after this happens to care about the
    # drawer count today, and that is luck rather than a promise worth resting on.
    back = _drawn(page)
    _container(page, "parameters")
    page.fill("#param-drawers", "6")
    page.wait_for_function(CHANGED, arg=back, timeout=BOOT_MS)
    settle(page)


# ---- refs: click, insert, highlight ---------------------------------------------------


@pytest.mark.e2e
def test_clicking_a_plate_selects_its_ref_and_colours_it(page: Page) -> None:
    """The bar used to say what was clicked while the plate stayed grey: the top of a plate
    with no name of its own answers to its part, and only the click knew that."""
    ref = _click_a_face(page, "")
    assert page.locator("#selection").inner_text().strip() == ref
    assert page.locator("#insert").is_enabled(), "Insert ref is not offered for a plate"
    assert _lit(page) > 0, f"{ref} is selected and nothing on screen is coloured"


@pytest.mark.e2e
def test_the_insert_shortcut_writes_the_ref_once(
    page: Page, settle: Callable[[Page], None]
) -> None:
    """``Ctrl+I`` puts ``ref("…")`` at the cursor - on a fresh last line, so the insert
    lands somewhere legal and the script still runs afterwards.

    ``Ctrl+Shift+I``, which this used to be, is DevTools in every browser but this one.
    """
    ref = page.locator("#selection").inner_text().strip()
    _script(page)
    page.locator(".cm-content").click()
    page.keyboard.press("ControlOrMeta+End")
    page.keyboard.press("Enter")
    page.keyboard.press("Control+i")
    page.wait_for_function(INSERTED, arg=f'ref("{ref}")', timeout=30_000)
    assert _editor_text(page).count(f'ref("{ref}")') == 1
    settle(page)
    assert _state(page) == "ok", _status(page)


@pytest.mark.e2e
def test_a_cursor_inside_a_ref_string_lights_up_what_it_names(
    page: Page, settle: Callable[[Page], None], screenshots: Path
) -> None:
    """The pull is a hole in the drawer front, and on its plate it is that hole's wall - named
    with the same ref its cut path carries in the SVG, which is what a script already says."""
    _script(page)
    page.locator(".cm-content").click()
    page.keyboard.press("ControlOrMeta+End")
    page.keyboard.press("Enter")
    page.keyboard.type(f'ref("{PULL}")')
    for _ in range(3):
        page.keyboard.press("ArrowLeft")
    page.wait_for_selector(f'#canvas3d[data-pointed="{PULL}"]', timeout=30_000)
    settle(page)
    page.screenshot(path=str(screenshots / "01-light.png"))


# ---- the bottom panel ------------------------------------------------------------------


@pytest.mark.e2e
def test_the_panel_keeps_the_two_streams_on_tabs_of_their_own(
    clean_page: Page, settle: Callable[[Page], None], screenshots: Path
) -> None:
    """A script's stderr is shown, not swallowed, and not run together with what it meant to
    print: that is how a warning goes unread. The run is still `ok` - saying something on
    stderr is not failing."""
    page = clean_page
    _typed(page, SAYS_BOTH)
    # The count beside the tab, not the tab: every tab is always there, so waiting on one
    # would wait for nothing and let the assertions below read the run before this one.
    _reported(page, "ok", "#panel-tab-stderr .count")
    settle(page)
    assert _state(page) == "ok", _status(page)

    _panel(page, "stderr")
    said = page.locator("#stderr").inner_text()
    assert "written on stderr" in said
    assert "a warning nobody would have seen" in said
    assert page.locator("#stdout").count() == 0, "the two streams were run together"
    page.screenshot(path=str(screenshots / "15-stderr.png"))

    _panel(page, "output")
    printed = page.locator("#stdout").inner_text()
    assert "printed on stdout" in printed
    assert "written on stderr" not in printed
    assert page.locator("#error").is_hidden(), "stderr was reported as a failed run"


@pytest.mark.e2e
def test_the_panel_can_be_put_away_and_brought_back(clean_page: Page) -> None:
    """The drawing is the thing worth looking at, so the panel gets out of the way on a click
    of the tab already in front - and the rail keeps saying what is waiting.

    The clicks are made here rather than through :func:`_panel`, which exists to bring a tab
    forward and deliberately will not toggle: the toggle is the thing under test.
    """
    page = clean_page
    assert page.locator("#panel-body").is_visible()
    page.click("#panel-tab-problems")
    assert page.locator("#panel-body").is_hidden(), "the panel did not put itself away"
    page.click("#panel-tab-problems")
    assert page.locator("#panel-body").is_visible()


@pytest.mark.e2e
def test_a_clean_run_says_so_rather_than_showing_an_empty_panel(clean_page: Page) -> None:
    """Problems is the tab in front to begin with, so this reads it where it already is: a
    click on the tab already in front is how the panel is put away, not how it is opened."""
    page = clean_page
    assert page.locator("#panel-tab-problems").get_attribute("aria-selected") == "true"
    assert page.locator("#no-problems").is_visible()
    assert page.locator("#rail-problem-count").is_hidden(), "a clean run badged the rail"


# ---- downloads ------------------------------------------------------------------------


@pytest.mark.e2e
def test_a_sheet_thumbnail_shows_its_cut_lines(page: Page) -> None:
    """The nest is only seen here now, and the first thumbnails were blank: a cutter's
    hairline shrunk sixty times over draws no pixel at all."""
    _container(page, "sheets")
    ink = int(page.evaluate(THUMBNAIL_INK))
    assert ink > 20, f"the thumbnail put {ink} red pixels on the screen"


@pytest.mark.e2e
def test_a_sheet_downloads_as_svg(page: Page, screenshots: Path) -> None:
    _panel(page, "files")
    sheet_row = page.locator("bench-file-row", has_text="sheet-3mm-01")
    with page.expect_download() as caught:
        sheet_row.locator("button", has_text="SVG").click()
    sheet = caught.value
    assert sheet.suggested_filename == "sheet-3mm-01.svg"
    saved = screenshots / "sheet-3mm-01.svg"
    sheet.save_as(str(saved))
    assert "<svg" in saved.read_text()[:400]


@pytest.mark.e2e
def test_the_zip_holds_every_file_and_opens(page: Page, screenshots: Path) -> None:
    """The zip is written by hand, so it is opened with :mod:`zipfile` to prove the writer
    is honest about what it claims."""
    _panel(page, "files")
    with page.expect_download() as caught:
        page.locator("#zip").click()
    archive = caught.value
    saved = screenshots / "bench-cut-files.zip"
    archive.save_as(str(saved))
    with zipfile.ZipFile(saved) as bundle:
        assert bundle.testzip() is None, "the archive is corrupt"
        assert "baseplate.scad" in bundle.namelist()
        sheet = bundle.read("sheet-3mm-01.svg").decode()
    assert sheet.startswith("<?xml") or sheet.lstrip().startswith("<svg")


@pytest.mark.e2e
def test_the_downloads_wait_on_a_tab_of_the_panel(clean_page: Page) -> None:
    """The files a run made are a tab away, not a third of the screen and not a popover:
    the Files tab says how many there are before it is opened."""
    page = clean_page
    assert page.locator("#outputs").is_hidden(), "the files are shown before they are asked for"
    assert page.locator("#panel-tab-files .count").inner_text().strip() != ""
    _panel(page, "files")
    assert page.locator("bench-file-row", has_text="sheet-3mm-01").is_visible()
    assert page.locator("#zip").is_visible()


# ---- a cut sheet, opened beside the script ---------------------------------------------


@pytest.mark.e2e
def test_a_sheet_opens_as_a_tab_beside_the_script(clean_page: Page, screenshots: Path) -> None:
    """A nest used to be a 64 px thumbnail in a menu. It opens in the editor group now, big
    enough to read before cutting - and the view is not what gets covered to do it."""
    page = clean_page
    _container(page, "sheets")
    page.locator("bench-sheets .sheet").first.click()
    page.wait_for_selector("#panel-sheet:not([hidden])", timeout=30_000)
    assert page.locator("#sheet-drawing").is_visible()
    assert page.locator("#editor").is_hidden(), "the sheet did not come to the front"
    # The whole point of the ruling: the view is still there.
    assert page.locator("#canvas3d").is_visible(), "opening a sheet covered the view"
    page.screenshot(path=str(screenshots / "18-sheet-tab.png"))


@pytest.mark.e2e
def test_a_sheet_tab_closes_and_the_script_cannot(clean_page: Page) -> None:
    page = clean_page
    _container(page, "sheets")
    page.locator("bench-sheets .sheet").first.click()
    page.wait_for_selector("#panel-sheet:not([hidden])", timeout=30_000)
    assert page.locator("#tab-script .tab-close").count() == 0, "the script offers a close button"
    page.locator(".tab .tab-close").first.click()
    assert page.locator("#editor").is_visible(), "closing the sheet left nothing in front"
    assert page.locator("#panel-sheet").is_hidden()


# ---- a failed run ---------------------------------------------------------------------


@pytest.mark.e2e
def test_a_syntax_error_is_reported_on_its_own_line(
    page: Page, settle: Callable[[Page], None], screenshots: Path
) -> None:
    """A broken line is named, marked in the text and in the gutter, and the geometry from
    the last good run stays on screen."""
    _typed(page, "\nif :")
    _reported(page, "error", "#error", "SyntaxError")
    settle(page)
    marked = page.locator(".cm-errorLine")
    assert marked.count() > 0, "no line was marked"
    assert "if :" in marked.first.inner_text()
    assert page.evaluate(GUTTER_MARKED) is True, "the error gutter is blank"
    assert _state(page) == "error", _status(page)
    assert "SyntaxError" in page.locator("#error").inner_text()
    assert _bodies(page) > 5, "a failed run threw the geometry away"
    page.screenshot(path=str(screenshots / "02-error-light.png"))


@pytest.mark.e2e
def test_a_failed_run_brings_the_panel_forward_by_itself(clean_page: Page) -> None:
    """The one state that opens the panel without being asked: something went wrong and the
    reason is the most useful thing on screen.

    The panel is put away with a direct click rather than through :func:`_panel`, which brings
    a tab forward and deliberately will not toggle.
    """
    page = clean_page
    page.click("#panel-tab-problems")
    assert page.locator("#panel-body").is_hidden(), "the panel was not put away first"
    _typed(page, "\nif :")
    _reported(page, "error", "#error", "SyntaxError")
    assert page.locator("#panel-body").is_visible(), "a failed run left the panel shut"


SAYS_BOTH = (
    "\nimport sys, warnings"
    "\nprint('printed on stdout')"
    "\nprint('written on stderr', file=sys.stderr)"
    "\nwarnings.warn('a warning nobody would have seen')\n"
)
"""Appended to the example after its `show`, so the run is an ordinary good one that
happens to have said something on both streams."""


SAYS_THEN_FALLS_OVER = "\nprint('got this far')\nraise ValueError('boom')\n"
"""Appended after the example's `show`, so the run has printed something real by the time
it raises."""


@pytest.mark.e2e
def test_a_run_that_fell_over_still_shows_what_it_printed(
    clean_page: Page, settle: Callable[[Page], None], screenshots: Path
) -> None:
    """A failed run used to throw its output away with everything else, which is backwards:
    a script prints its way to the line that breaks, so that is the output worth keeping."""
    page = clean_page
    _typed(page, SAYS_THEN_FALLS_OVER)
    _reported(page, "error", "#error", "ValueError")
    settle(page)
    assert _state(page) == "error", _status(page)
    assert "ValueError: boom" in page.locator("#error").inner_text()
    _panel(page, "output")
    assert "got this far" in page.locator("#stdout").inner_text()
    page.screenshot(path=str(screenshots / "16-failed-with-output.png"))


# ---- one owner for the overrides ------------------------------------------------------


@pytest.mark.e2e
def test_an_override_survives_a_scene_that_lands_mid_debounce(
    clean_page: Page, settle: Callable[[Page], None]
) -> None:
    """A scene that arrives while a parameter edit is still waiting out its debounce must
    not put the old override table back.

    The reviewer's scenario: edit the script, wait for its run to be in flight, set
    ``units_x`` to 7, and watch the widget say 7 while the geometry and the cut files stay at
    4 with nothing reporting it. The panel and the host each kept a copy of the override
    table, and a scene from a run that started before the edit handed the host's stale copy
    back to the panel on its way in, wiping the edit that was still waiting out its 300 ms.

    The window is narrow - a scene has to land inside one debounce - so the script is first
    given a one-second sleep and one run of it is timed. That turns "wait about 350 ms" into
    "put the edit a known 250, 150 and 50 ms before the scene is due", which is the same
    scenario with the machine's speed taken out of it.
    """
    page = clean_page
    at_four = _drawn(page)
    _container(page, "parameters")
    page.fill("#param-units_x", "7")
    _ran(page, settle)
    at_seven = _drawn(page)
    assert at_seven != at_four, f"units_x did not change the drawing: {at_four} -> {at_seven}"

    _typed(page, SLOWDOWN)
    _ran(page, settle)

    started = time.monotonic()
    page.keyboard.press("Control+Enter")
    page.wait_for_function(
        "() => document.querySelector('#state')?.dataset.state === 'running'", timeout=BOOT_MS
    )
    settle(page)
    round_trip = (time.monotonic() - started) * 1000
    assert round_trip > 900, f"the sleep did not slow the run down: {round_trip:.0f} ms"

    for early in (250, 150, 50):
        _container(page, "parameters")
        page.click("#reset")
        _ran(page, settle)
        assert _drawn(page) == at_four, f"reset, {early} ms"

        # An edit to the script: 300 ms of debounce, then a run that answers in `round_trip`.
        _typed(page, f"\n# mid-debounce, {early} ms early")
        page.wait_for_timeout(max(DEBOUNCE_MS + round_trip - early, 0))
        _container(page, "parameters")
        page.fill("#param-units_x", "7")
        _ran(page, settle)

        assert _state(page) == "ok", _status(page)
        assert _drawn(page) == at_seven, (
            f"the drawing is not the one for units_x=7, with the edit {early} ms early"
        )
        assert _overrides(page) == {"units_x": 7}, f"localStorage lost the edit, {early} ms early"


# ---- a runaway script -----------------------------------------------------------------


@pytest.mark.e2e
def test_a_runaway_script_is_stopped_by_the_watchdog(runaway_page: Page, screenshots: Path) -> None:
    """``while True: pass`` cannot be interrupted from outside the loop, so the watchdog
    kills the worker, says so in the panel, and offers the Stop button meanwhile."""
    page = runaway_page
    _script(page)
    page.locator(".cm-content").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type(RUNAWAY)

    page.wait_for_selector("#stop:not([disabled])", timeout=30_000)
    page.screenshot(path=str(screenshots / "05-running-stop.png"))

    page.locator("#error", has_text="was stopped").wait_for(timeout=WATCHDOG_MS)
    reported = page.locator("#error").inner_text()
    assert "the script did not finish in 15 s and was stopped" in reported, reported
    assert _state(page) == "error", _status(page)
    assert page.locator("#stop").is_disabled(), "Stop is still offered with nothing running"
    page.screenshot(path=str(screenshots / "06-stopped.png"))


@pytest.mark.e2e
def test_a_reload_does_not_replay_a_runaway(runaway_page: Page) -> None:
    """The runaway is still the remembered script, and a reload used to run it again and
    read as "booting" for ever. The app now says what happened and waits to be asked."""
    page = runaway_page
    page.reload()
    page.locator("#error", has_text="did not finish").wait_for(timeout=60_000)
    assert "Press Run" in page.locator("#error").inner_text()
    # Nothing was started, so nothing can be stopped - and the editor still has the script.
    assert page.locator("#stop").is_disabled()
    assert "while True" in _editor_text(page)
    page.wait_for_timeout(2_000)
    assert _state(page) == "error", _status(page)


@pytest.mark.e2e
def test_the_app_still_works_after_a_runaway(runaway_page: Page, screenshots: Path) -> None:
    """A fresh worker took the dead one's place, so picking an example draws it again."""
    page = runaway_page
    page.click("#examples-button")
    page.locator("#examples button", has_text="gridfinity_cabinet.py").click()
    page.wait_for_selector(DRAWN, timeout=BOOT_MS)
    page.wait_for_function(
        "() => document.querySelector('#state')?.dataset.state === 'ok'", timeout=BOOT_MS
    )
    assert _bodies(page) > 5, "the app did not come back"
    page.screenshot(path=str(screenshots / "07-after-runaway.png"))


@pytest.mark.e2e
def test_the_stop_button_stops_a_running_script(clean_page: Page) -> None:
    """The Stop button does by hand what the watchdog does on a timer."""
    page = clean_page
    _script(page)
    page.locator(".cm-content").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type(RUNAWAY)
    page.wait_for_selector("#stop:not([disabled])", timeout=30_000)
    page.click("#stop")
    page.locator("#error", has_text="was stopped").wait_for(timeout=30_000)
    assert "reload the page" in page.locator("#error").inner_text()
    assert page.locator("#stop").is_disabled()


# ---- files -----------------------------------------------------------------------------


CABINET_FIRST_LINE = (ROOT / "examples" / "gridfinity_cabinet.py").read_text().splitlines()[0]


def _files(page: Page) -> None:
    """Put the scripts container in the sidebar."""
    _container(page, "files")


def _file_names(page: Page) -> list[str]:
    """Every script the explorer lists, in its order."""
    _files(page)
    return [one.strip() for one in page.locator("bench-explorer .file").all_inner_texts()]


def _open_file(page: Page, name: str, settle: Callable[[Page], None]) -> None:
    _files(page)
    page.locator("bench-explorer .file", has_text=name).click()
    _ran(page, settle)


def _open_name(page: Page) -> str:
    """Which script the title bar says is open."""
    return page.locator("#open-name").inner_text().strip()


@pytest.mark.e2e
def test_a_new_file_starts_from_the_template_and_draws_it(
    files_page: Page, settle: Callable[[Page], None], screenshots: Path
) -> None:
    page = files_page
    _files(page)
    page.click("#file-new")
    page.wait_for_function(f"() => ({BODIES})() === 1", timeout=BOOT_MS)
    settle(page)
    assert _state(page) == "ok", _status(page)
    assert _open_name(page) == "untitled.py"
    assert "class Settings" in _editor_text(page)
    page.screenshot(path=str(screenshots / "09-new-file.png"))


@pytest.mark.e2e
def test_a_new_file_does_not_cost_the_script_before_it(
    files_page: Page, settle: Callable[[Page], None]
) -> None:
    page = files_page
    assert _file_names(page) == ["gridfinity_cabinet.py", "untitled.py"]
    _open_file(page, "gridfinity_cabinet.py", settle)
    page.wait_for_function(f"() => ({BODIES})() > 5", timeout=BOOT_MS)
    assert CABINET_FIRST_LINE in _editor_text(page)


@pytest.mark.e2e
def test_an_example_opens_as_a_file_of_its_own(
    files_page: Page, settle: Callable[[Page], None]
) -> None:
    """Picking an example used to replace the script in the editor, whatever was in it."""
    page = files_page
    _open_file(page, "untitled.py", settle)
    _typed(page, "\n# mine")
    _ran(page, settle)

    page.click("#examples-button")
    page.locator("#examples button", has_text="box_with_hole.py").click()
    _ran(page, settle)
    assert _open_name(page) == "box_with_hole.py"
    assert _file_names(page) == ["gridfinity_cabinet.py", "untitled.py", "box_with_hole.py"]

    _open_file(page, "untitled.py", settle)
    assert "# mine" in _editor_text(page)


@pytest.mark.e2e
def test_a_rename_and_a_delete_outlast_a_reload(
    files_page: Page, settle: Callable[[Page], None]
) -> None:
    page = files_page
    _files(page)
    page.click("#file-rename")
    page.fill("#file-name", "shelf")
    page.click("#file-rename-confirm")
    assert _open_name(page) == "shelf.py"
    # The values file is named for its script, so it was renamed too.
    assert page.locator("#tab-values").inner_text().strip() == "shelf.toml"

    _open_file(page, "box_with_hole.py", settle)
    _files(page)
    page.click("#file-delete")
    page.click("#file-delete-confirm")
    _ran(page, settle)
    assert _open_name(page) == "shelf.py", "deleting the open file opens its neighbour"

    page.reload()
    page.wait_for_selector(DRAWN, timeout=BOOT_MS)
    settle(page)
    assert _file_names(page) == ["gridfinity_cabinet.py", "shelf.py"]
    assert _open_name(page) == "shelf.py"
    assert "# mine" in _editor_text(page)
    assert _state(page) == "ok", _status(page)


# ---- a project: the script and its values, kept and carried together -------------------
#
# The files story goes on with `shelf.py`, the starter template, open: a panel edit becomes a
# line in a values file, the file is read as a document, a copy takes it along, a download
# is run by the command-line host with no browser in sight, and a project opened from disk
# arrives with its values - held to the script's range by the run and written back that way.

STARTER_TEXT = (ROOT / "templates" / "untitled.py").read_text()
"""What a new script starts as - the same text a project opened from disk is given here."""


def _pick(page: Page, *paths: Path) -> None:
    """Open the files at ``paths`` through the explorer's picker, the way Open… does."""
    _files(page)
    page.locator("bench-explorer #file-pick").set_input_files([str(one) for one in paths])


@pytest.mark.e2e
def test_a_panel_edit_is_a_line_in_the_values_file(
    files_page: Page, settle: Callable[[Page], None], screenshots: Path
) -> None:
    """The knob turned is a line somebody can read: the values are kept as TOML, and the
    same TOML opens as a tab beside the script - a document, not a widget."""
    page = files_page
    _container(page, "parameters")
    page.fill("#param-w", "150")
    _ran(page, settle)
    assert _state(page) == "ok", _status(page)
    assert _overrides(page) == {"w": 150}

    page.click("#tab-values")
    assert page.locator("#values-text").is_visible()
    assert page.locator("#editor").is_hidden(), "the values did not come to the front"
    assert page.locator("#canvas3d").is_visible(), "opening the values covered the view"
    assert page.locator("#tab-values").inner_text().strip() == "shelf.toml"
    assert page.locator("#tab-values .tab-close").count() == 0, "the values offer a close button"
    text = page.locator("#values-text").inner_text()
    assert "[values]" in text
    assert "w = 150" in text
    assert tomllib.loads(text)["values"] == {"w": 150}, text
    page.screenshot(path=str(screenshots / "19-values-tab.png"))
    _script(page)


@pytest.mark.e2e
def test_duplicating_a_project_copies_its_values_with_it(
    files_page: Page, settle: Callable[[Page], None]
) -> None:
    page = files_page
    _files(page)
    page.click("#file-duplicate")
    _ran(page, settle)
    assert _open_name(page) == "shelf-2.py"
    assert _file_names(page) == ["gridfinity_cabinet.py", "shelf.py", "shelf-2.py"]
    assert "# mine" in _editor_text(page)
    assert _overrides(page) == {"w": 150}, "the copy lost the values"
    assert page.locator("#tab-values").inner_text().strip() == "shelf-2.toml"


@pytest.mark.e2e
def test_a_downloaded_project_runs_outside_the_browser(
    files_page: Page, screenshots: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The point of the whole step: what one browser kept is two files another host can
    run. The download is opened with :mod:`zipfile`, and the script is run with its values
    beside it by ``tools/build.py`` - the same values the panel edited, used by a run that
    never saw the browser."""
    page = files_page
    _files(page)
    with page.expect_download() as caught:
        page.click("#file-download")
    archive = caught.value
    assert archive.suggested_filename == "shelf-2.zip"
    saved = screenshots / "shelf-2.zip"
    archive.save_as(str(saved))
    into = screenshots / "shelf-2"
    shutil.rmtree(into, ignore_errors=True)
    with zipfile.ZipFile(saved) as bundle:
        assert bundle.testzip() is None, "the archive is corrupt"
        assert sorted(bundle.namelist()) == ["shelf-2.py", "shelf-2.toml"]
        bundle.extractall(into)
    assert tomllib.loads((into / "shelf-2.toml").read_text())["values"] == {"w": 150}
    assert "# mine" in (into / "shelf-2.py").read_text()

    from tools import build

    code = build.main((str(into / "shelf-2.py"), "--out", str(into / "out")))
    said = capsys.readouterr().out
    assert code == 0, said
    assert "shelf-2.toml: w=150" in said, said
    assert "ok: 1 parts" in said, said
    assert list((into / "out").glob("*.svg")), "the run wrote no cut sheet"


@pytest.mark.e2e
def test_a_project_opened_from_disk_arrives_with_its_values(
    files_page: Page, settle: Callable[[Page], None], tmp_path: Path
) -> None:
    """A script and the `.toml` beside it, picked together, open as one project - and a
    value the file holds past the script's range is held at that end by the run and written
    back as built, so the file never says something the run did not do."""
    page = files_page
    (tmp_path / "plate.py").write_text(STARTER_TEXT)
    (tmp_path / "plate.toml").write_text("[values]\nw = 40\nhole_r = 99\n")
    _pick(page, tmp_path / "plate.py", tmp_path / "plate.toml")
    _ran(page, settle)
    assert _state(page) == "ok", _status(page)
    assert _open_name(page) == "plate.py"
    assert "class Settings" in _editor_text(page)
    # `hole_r` is `knob(8.0, min=2.0, max=20.0)`: 99 was sent, 20 was built, 20 is kept.
    assert _overrides(page) == {"w": 40, "hole_r": 20}
    _container(page, "parameters")
    assert page.locator("#param-hole_r").input_value() == "20"
    assert page.locator("#param-w").input_value() == "40"


@pytest.mark.e2e
def test_a_script_opened_with_no_values_file_runs_on_its_defaults(
    files_page: Page, settle: Callable[[Page], None], tmp_path: Path
) -> None:
    page = files_page
    (tmp_path / "bare.py").write_text(STARTER_TEXT)
    _pick(page, tmp_path / "bare.py")
    _ran(page, settle)
    assert _state(page) == "ok", _status(page)
    assert _open_name(page) == "bare.py"
    assert _overrides(page) == {}
    page.click("#tab-values")
    text = page.locator("#values-text").inner_text()
    assert tomllib.loads(text) == {"values": {}}, text
    _script(page)


@pytest.mark.e2e
def test_a_values_file_that_cannot_be_read_opens_nothing_and_says_why(
    files_page: Page, tmp_path: Path
) -> None:
    """One rule for the pick, as ``tools/build.py`` has for a file it cannot read: nothing
    is opened, and the line is named."""
    page = files_page
    before = _file_names(page)
    (tmp_path / "bad.py").write_text(STARTER_TEXT)
    (tmp_path / "bad.toml").write_text("[values]\nw = [1, 2]\n")
    _pick(page, tmp_path / "bad.py", tmp_path / "bad.toml")
    page.locator("#error", has_text="bad.toml").wait_for(timeout=10_000)
    assert "line 2" in page.locator("#error").inner_text()
    assert _file_names(page) == before, "a project was opened from an unreadable pick"


# ---- booting ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_the_boot_says_what_it_is_loading(booting_page: Page, screenshots: Path) -> None:
    """Thirteen megabytes the first time and a compile every time is a long quiet wait; the
    status bar names it while it happens, without claiming a download that may not be one."""
    page = booting_page
    page.wait_for_function(
        "() => (document.querySelector('#status')?.textContent ?? '')"
        ".includes('loading Python runtime')",
        timeout=60_000,
    )
    assert page.locator("#state").get_attribute("data-state") == "boot"
    page.screenshot(path=str(screenshots / "08-booting.png"))


# ---- the viewer on a phone, and its captions -------------------------------------------


@pytest.mark.e2e
def test_with_nothing_selected_the_bar_says_how_to_select_something(clean_page: Page) -> None:
    """The bar used to say "nothing selected", which tells a first-time maker nothing at
    all about where a ref comes from."""
    page = clean_page
    assert page.locator("#selection").inner_text().strip() == HOW_TO_SELECT
    assert page.locator("#insert").is_disabled(), "Insert ref is offered with nothing to insert"


@pytest.mark.e2e
def test_a_printed_scene_says_to_click_a_face(printed_page: Page) -> None:
    """One hint for every scene, since every part is drawn the same way now."""
    page = printed_page
    assert page.locator("#selection").inner_text().strip() == HOW_TO_SELECT


@pytest.mark.e2e
def test_the_zoom_buttons_move_the_camera(page: Page) -> None:
    page.click("#fit")
    page.wait_for_timeout(100)
    fitted = _distance(page)
    page.click("#zoom-in")
    assert _distance(page) < fitted
    page.click("#zoom-out")
    page.click("#zoom-out")
    assert _distance(page) > fitted
    page.click("#fit")


@pytest.mark.e2e
def test_hovering_a_plate_names_its_part_its_stock_and_its_sheet(page: Page) -> None:
    """What a maker needs off the view: which part, what it is cut from and which sheet to
    look for it on - said by the pointer, since a canvas has no captions of its own."""
    page.click("#fit")
    page.wait_for_timeout(100)
    said = _hover_a_part(page)
    assert " mm " in said, said
    assert "sheet-" in said, said


@pytest.mark.e2e
def test_a_cancelled_press_does_not_land_as_a_click(page: Page) -> None:
    page.keyboard.press("Escape")
    assert page.evaluate(CANCELLED_CLICK) == HOW_TO_SELECT, "the cancelled press selected"


@pytest.mark.e2e
def test_nothing_went_wrong_in_the_page(page: Page, page_errors: list[str]) -> None:
    """Every check that shared this page ran before this one, so this is the whole
    session's console."""
    assert page_errors == [], "; ".join(page_errors[:3])


# ---- the other layouts ----------------------------------------------------------------


@pytest.mark.e2e
def test_the_dark_theme_renders(dark_page: Page, screenshots: Path) -> None:
    dark_page.screenshot(path=str(screenshots / "03-dark.png"))
    assert _bodies(dark_page) > 5


@pytest.mark.e2e
def test_a_narrow_window_stacks_the_layout(dark_page: Page, screenshots: Path) -> None:
    """Four edges of chrome is what the shell costs, and a narrow window cannot pay it: the
    sidebar stops sharing the row, and the script and the view stop sharing one too."""
    dark_page.set_viewport_size({"width": 420, "height": 900})
    dark_page.wait_for_function(ONE_COLUMN, timeout=5_000)
    dark_page.screenshot(path=str(screenshots / "04-narrow-dark.png"))
    assert dark_page.evaluate(ONE_COLUMN) is True, "the script and the view still share a row"
    assert dark_page.locator("#sidebar").is_hidden(), "the sidebar is still taking room"
    assert dark_page.locator("#canvas3d").is_visible(), "the view went away"


# ---- a printed part: the 3D pane, its refs, and what a printer reads --------------------
#
# One page in file order again, as a maker would walk it: the bin is drawn, a face on it
# answers to a ref, the ref goes into the script, the STL and the 3MF come down, a laser
# example is drawn as plates beside nothing printed, and a check that fails is reported
# where it happened.

BIN = "gridfinity_bin.py"
"""The printed example: hulled feet, a scoop, a stacking lip - the real object."""

LASER = "box_with_hole.py"
"""And a flat one: five panels, each a plate."""

CHECKED = "enclosure_lid.py"
"""The example with a `check_wall` in it, at a line the editor can be asked to mark."""

THIN_WALL = "1.2"
"""What the enclosure's wall has to come down to before PLA's 0.86 mm is not met."""

CHECKED_PART = "box"
"""The part the enclosure's wall check is about: `check_wall(box, ...)` runs on the bare
solid that `part("box", box, ...)` then becomes, and the run ties the two together by
identity, so the finding reaches the page as `box/...` - a ref the tree holds."""

UNCHECKED_PART = "lid"
"""The enclosure's other part, which the wall check never measured."""

CANVAS_3D = "#canvas3d canvas"

STL_HEADER = 84
"""Eighty bytes of header and a four-byte triangle count, before any triangle."""

STL_FACET = 50
"""Twelve floats and a two-byte attribute count, per triangle."""

DREW_A_MESH = """() => {
    const pane = document.querySelector('#canvas3d');
    const canvas = pane?.querySelector('canvas');
    if (!pane || !canvas) return false;
    return Number(pane.dataset.triangles ?? 0) > 0 && canvas.clientWidth > 0;
}"""

ERROR_ROW = 'bench-violation[severity="error"]'
"""A check's finding that will not work. Playwright's CSS reaches into the shadow roots the
rows live in; ``document.querySelector`` would not, which is why this is a locator."""

UNCHECKED_ROW = 'bench-violation[severity="unchecked"]'

TOTE = "systainer_tote.py"
"""The printed example whose `check_overhangs(tub, ...)` leaves one warning standing on
purpose - its own docstring says why - which is what `task-53`'s status bar counted."""


def _canvas3d(page: Page) -> FloatRect:
    """Where the 3D canvas is on screen; it fails the test that asked if it is not there."""
    box = page.locator(CANVAS_3D).bounding_box()
    assert box is not None, "the 3D canvas has no box on screen"
    return box


_SPOTS = ((0.5, 0.55), (0.42, 0.6), (0.58, 0.5), (0.5, 0.42), (0.62, 0.62), (0.35, 0.45))
"""Where on the view to try: where a part lands under the camera is the camera's business, so
a handful of points rather than insisting the middle is over material - a bin is mostly a hole
seen from above, and a row of plates has gaps between them."""


def _click_a_face(page: Page, prefix: str = "bin/") -> str:
    """Click the view until something answers with a ref starting ``prefix``, and give back
    the ref it answered with.

    Raises:
        AssertionError: if nothing on screen answers to such a ref.
    """
    box = _canvas3d(page)
    for across, down in _SPOTS:
        page.mouse.click(box["x"] + box["width"] * across, box["y"] + box["height"] * down)
        page.wait_for_timeout(150)
        said = page.locator("#selection").inner_text().strip()
        if said != HOW_TO_SELECT and said.startswith(prefix):
            return said
    raise AssertionError(f"no face answered: {page.locator('#selection').inner_text()}")


def _hover_a_part(page: Page) -> str:
    """Move over the view until the tip names a part, and give back what the part line says.

    Raises:
        AssertionError: if the pointer finds nothing to name.
    """
    box = _canvas3d(page)
    for across, down in _SPOTS:
        page.mouse.move(box["x"] + box["width"] * across, box["y"] + box["height"] * down)
        page.wait_for_timeout(150)
        if page.locator(".canvas-tip").is_visible():
            return page.locator(".canvas-tip-part").inner_text()
    raise AssertionError("the pointer found no part to name")


@pytest.mark.e2e
def test_a_printed_part_is_drawn_as_a_solid(printed_page: Page, screenshots: Path) -> None:
    """The whole point of the step: a script that prints something shows the thing, built in
    the browser by the same Manifold the command line uses."""
    page = printed_page
    page.wait_for_function(DREW_A_MESH, timeout=BOOT_MS)
    triangles = int(page.locator("#canvas3d").get_attribute("data-triangles") or "0")
    assert triangles > 100, f"the solid is {triangles} triangles, which is not a bin"
    assert page.locator("#canvas3d").get_attribute("data-bodies") == "1"
    page.screenshot(path=str(screenshots / "10-printed.png"))


@pytest.mark.e2e
def test_clicking_a_face_of_the_solid_gives_its_ref(printed_page: Page, screenshots: Path) -> None:
    """The same contract the drawing has had all along, now on a face of a body."""
    page = printed_page
    ref = _click_a_face(page)
    assert page.locator("#selection").inner_text().strip() == ref
    assert page.locator("#insert").is_enabled(), "Insert ref is not offered for a face"
    assert _lit(page) > 0, f"{ref} is selected and nothing on screen is coloured"
    page.screenshot(path=str(screenshots / "11-face-selected.png"))


@pytest.mark.e2e
def test_hovering_a_face_names_it(printed_page: Page) -> None:
    """A canvas has no tooltip of its own, so the pointer carries the ref with it."""
    page = printed_page
    box = _canvas3d(page)
    page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.55)
    page.wait_for_selector(".canvas-tip:not([hidden])", timeout=10_000)
    assert page.locator(".canvas-tip").inner_text().startswith("bin/")


@pytest.mark.e2e
def test_the_stl_is_a_binary_stl(printed_page: Page, screenshots: Path) -> None:
    """Written by `bench.export.stl`, carried through the scene as base64 and decoded on the
    way out - so the bytes are checked, not the string."""
    page = printed_page
    _panel(page, "files")
    stl_row = page.locator("bench-file-row", has_text="bin.stl")
    with page.expect_download() as caught:
        stl_row.locator("button", has_text="STL").click()
    saved = screenshots / "bin.stl"
    caught.value.save_as(str(saved))
    data = saved.read_bytes()
    assert len(data) > STL_HEADER, "the STL is nothing but a header"
    count = int.from_bytes(data[80:STL_HEADER], "little")
    assert count > 100, f"{count} triangles is not a bin"
    assert len(data) == STL_HEADER + STL_FACET * count, (
        f"{len(data)} bytes is not {STL_HEADER} + {STL_FACET} x {count}"
    )


@pytest.mark.e2e
def test_the_3mf_is_a_package_with_the_model_in_it(printed_page: Page, screenshots: Path) -> None:
    page = printed_page
    _panel(page, "files")
    label = page.locator("#outputs bench-file-row .name", has_text=".3mf").first
    name = label.inner_text().strip()
    with page.expect_download() as caught:
        page.locator("bench-file-row", has_text=name).locator("button", has_text="3MF").click()
    saved = screenshots / name
    caught.value.save_as(str(saved))
    with zipfile.ZipFile(saved) as package:
        assert package.testzip() is None, "the 3MF is corrupt"
        model = package.read("3D/3dmodel.model").decode()
    assert 'unit="millimeter"' in model
    assert "<triangle " in model


@pytest.mark.e2e
def test_the_zip_carries_the_stl_as_bytes(printed_page: Page, screenshots: Path) -> None:
    """The archive is written by hand and its entries are encoded there, not by `save` - so
    a base64 STL that decodes on its own can still go into the zip as a wall of letters."""
    page = printed_page
    _panel(page, "files")
    with page.expect_download() as caught:
        page.click("#zip")
    saved = screenshots / "printed.zip"
    caught.value.save_as(str(saved))
    with zipfile.ZipFile(saved) as bundle:
        assert bundle.testzip() is None, "the archive is corrupt"
        data = bundle.read("bin.stl")
    count = int.from_bytes(data[80:STL_HEADER], "little")
    assert len(data) == STL_HEADER + STL_FACET * count, "the STL went in as base64 text"


@pytest.mark.e2e
def test_the_insert_shortcut_writes_a_ref_picked_off_the_solid(
    printed_page: Page, settle: Callable[[Page], None]
) -> None:
    """A face picked off a printed body goes into the script the way a plate's wall does."""
    page = printed_page
    ref = _click_a_face(page)
    _script(page)
    page.locator(".cm-content").click()
    page.keyboard.press("ControlOrMeta+End")
    page.keyboard.press("Enter")
    page.keyboard.press("Control+i")
    page.wait_for_function(INSERTED, arg=f'ref("{ref}")', timeout=30_000)
    assert _editor_text(page).count(f'ref("{ref}")') == 1
    settle(page)
    assert _state(page) == "ok", _status(page)


@pytest.mark.e2e
def test_a_laser_example_is_drawn_as_plates(
    printed_page: Page, example: Callable[[Page, str], None], screenshots: Path
) -> None:
    """A flat part is the plate it is cut from, in the same view the bin was just in, and a
    click on one gives a ref of the box."""
    page = printed_page
    example(page, LASER)
    page.wait_for_function(f"() => ({BODIES})() === 5", timeout=BOOT_MS)
    assert _click_a_face(page, "")
    page.screenshot(path=str(screenshots / "12-plates.png"))


@pytest.mark.e2e
def test_a_failed_check_is_reported_and_its_line_is_marked(
    printed_page: Page,
    example: Callable[[Page, str], None],
    settle: Callable[[Page], None],
    screenshots: Path,
) -> None:
    """A run can succeed and still be wrong. The enclosure's wall check fails once the wall
    is thin enough, and it reads as an error with the face it measured and the line that
    asked - marked in the editor exactly as a raised exception would be."""
    page = printed_page
    example(page, CHECKED)
    _container(page, "parameters")
    page.fill("#param-wall", THIN_WALL)
    # A finding lives on the Problems tab, and the panel draws one tab at a time - the checks
    # before this one left Files in front. A violation does not steal the tab back (the run
    # is `ok`; the badge and the red count say so instead), so ask for it the way a person would.
    _panel(page, "problems")
    found = page.locator(ERROR_ROW, has_text="thinnest wall").first
    found.wait_for(timeout=BOOT_MS)
    settle(page)

    # Read the parts, not the row: `inner_text` on a shadow host is the host's own light DOM,
    # which is empty. The label is upper-cased in CSS, which is what `inner_text` reports.
    head = found.locator(".head").inner_text()
    said = found.locator(".message").inner_text()
    assert "error" in head.lower(), head
    assert "mm" in said, said
    assert found.get_attribute("check") == "wall"
    where = found.locator(".where").inner_text()
    assert "line " in where, where
    assert f"{CHECKED_PART}/" in where, where

    # And the tree marks the row the finding is about. The face itself sits under a shut
    # branch, so the mark is read off the part's row, which carries it for everything under
    # it - and not off the lid's, which no check found anything on.
    _container(page, "refs")
    box_row = page.locator(f'bench-refs-tree [data-ref="{CHECKED_PART}"]')
    box_row.wait_for(timeout=BOOT_MS)
    assert box_row.locator(".flag").count() == 1, f"{CHECKED_PART}'s row is not marked"
    lid_row = page.locator(f'bench-refs-tree [data-ref="{UNCHECKED_PART}"]')
    assert lid_row.count() == 1, f"{UNCHECKED_PART} is not in the tree"
    assert lid_row.locator(".flag").count() == 0, f"{UNCHECKED_PART}'s row is marked"

    # The geometry is still drawn: a violation is a report, not a failure.
    assert int(page.locator("#canvas3d").get_attribute("data-triangles") or "0") > 0
    assert _state(page) == "ok", _status(page)
    # The mark is in the editor, and the edit was made from the sidebar.
    _script(page)
    assert page.evaluate(GUTTER_MARKED) is True, "the failing check marked no line"
    assert page.locator(".cm-errorLine").count() == 1
    page.screenshot(path=str(screenshots / "13-violation.png"))


@pytest.mark.e2e
def test_a_findings_line_number_takes_you_to_it(
    printed_page: Page,
    example: Callable[[Page, str], None],
    settle: Callable[[Page], None],
) -> None:
    """A finding carries the line of the script that asked for the check, and that line is a
    way back to it rather than a number to read out."""
    page = printed_page
    example(page, CHECKED)
    _container(page, "parameters")
    page.fill("#param-wall", THIN_WALL)
    _panel(page, "problems")
    found = page.locator(ERROR_ROW, has_text="thinnest wall").first
    found.wait_for(timeout=BOOT_MS)
    settle(page)

    wanted = int(found.locator(".where .jump").inner_text().strip().removeprefix("line "))
    found.locator(".where .jump").click()
    page.wait_for_timeout(200)
    assert page.locator("#editor").is_visible(), "the script did not come forward"
    assert int(page.evaluate(CURSOR_LINE)) == wanted, "the cursor did not land on the line"


@pytest.mark.e2e
def test_an_example_whose_name_is_another_examples_prefix_still_picks_cleanly(
    printed_page: Page, example: Callable[[Page, str], None]
) -> None:
    """`hinge.py` is a prefix of `fulcrum_hinge.py`'s own name, so a locator matching the
    examples menu by substring resolves both and Playwright refuses the click as a strict
    mode violation - the crash `tools.qa`'s default walk hit on its third stop. The shared
    `example` fixture has to pick the button named exactly `hinge.py`, not one that merely
    contains it."""
    page = printed_page
    example(page, "hinge.py")
    assert _open_name(page) == "hinge.py", _open_name(page)


@pytest.mark.e2e
def test_a_warning_the_status_bar_counts_is_in_the_problems_panel(
    printed_page: Page, example: Callable[[Page, str], None]
) -> None:
    """`task-53`: a run whose status bar says "1 warning" has to show that warning in the
    Problems panel too, not only in the count - `systainer_tote.py`'s own `check_overhangs`
    finding, read off the tab a person actually opens."""
    page = printed_page
    example(page, TOTE)
    assert "1 warning" in _status(page), _status(page)
    _panel(page, "problems")
    # `check` is a host attribute for anything that needs to find a row by it, not text a
    # person reads - the visible head says the severity, and the message is where "socket-1"
    # is put in words, so the row is found by the attribute rather than its own text.
    found = page.locator('bench-violation[severity="warning"][check="overhangs"]').first
    found.wait_for(timeout=BOOT_MS)
    where = found.locator(".where").inner_text()
    assert "socket-1" in where, where


@pytest.mark.e2e
def test_nothing_went_wrong_on_the_printed_page(
    printed_page: Page, printed_errors: list[str]
) -> None:
    """Every printed check shared this page and ran before this one."""
    assert printed_page is not None
    assert printed_errors == [], "; ".join(printed_errors[:3])


# ---- the modeller not arriving ----------------------------------------------------------


@pytest.mark.e2e
def test_without_the_modeller_a_laser_part_is_unaffected(
    no_modeller_page: Page, example: Callable[[Page, str], None]
) -> None:
    """Half a megabyte that does not arrive must not cost a person cutting a box anything at
    all: the run is given no kernel, and a plate is swept without one."""
    page = no_modeller_page
    example(page, LASER)
    page.wait_for_function(f"() => ({BODIES})() === 5", timeout=BOOT_MS)
    assert _state(page) == "ok", _status(page)
    _panel(page, "files")
    assert page.locator("bench-file-row", has_text=".svg").count() > 0


@pytest.mark.e2e
def test_without_the_modeller_a_printed_part_still_has_every_ref(
    no_modeller_page: Page, example: Callable[[Page, str], None], screenshots: Path
) -> None:
    """And a printed one comes back named but unbuilt, saying so: no triangles, nothing for
    the printer, and a check that needed a measurement reading **not checked** - which is not
    a pass, and is the whole reason there is a third severity."""
    page = no_modeller_page
    example(page, BIN)
    assert _state(page) == "ok", _status(page)
    assert page.locator("#canvas3d").get_attribute("data-triangles") in (None, "0")
    # The pane's own note, not the stand-in the deferred three.js import leaves while it
    # downloads - which reads much the same and says nothing about the modeller.
    note = page.locator("#canvas3d .canvas-note:not(.is-waiting)")
    note.wait_for(timeout=30_000)
    assert "built no body" in note.inner_text()

    # The findings first, on their own tab - the panel draws one at a time, so reading them
    # after the Files tab is asked for would be reading a tab that is not there.
    _panel(page, "problems")
    unchecked = page.locator(UNCHECKED_ROW).first
    head = unchecked.locator(".head").inner_text()
    said = unchecked.locator(".message").inner_text()
    assert "not checked" in head.lower(), head
    assert "no kernel" in said, said

    _panel(page, "files")
    assert page.locator("bench-file-row", has_text=".stl").count() == 0, "an STL with nothing in it"
    # Not marked as an error in the editor: nobody said this part is wrong.
    assert page.locator(".cm-errorLine").count() == 0
    page.screenshot(path=str(screenshots / "14-no-modeller.png"))


# ---- a body dropped on the view, and what it measures ----------------------------------
#
# The same page, because a survey needs no modeller: a mesh is already triangles, which is
# the reason `bench.survey` is worth having, and a maker whose modeller did not load can
# still read what a downloaded part measures. The body is a bracket bench itself swept as a
# plate - a rectangle with a bore - written out by bench's own STL exporter, so the walk
# hands the page exactly the bytes a download would.

REFERENCE = "bracket.stl"
"""What the dropped file is called, which is what its report's tab is called."""

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
"""Drop a file on the view the way a drag from the desktop lands: the two events that have
to be answered before the third is delivered, then the drop itself."""

SURVEYS_TIMED = (
    "() => performance.getEntriesByType('measure')"
    ".filter((one) => one.name === 'bench.worker.survey').length"
)
"""How many times the worker has measured a body, read off the page's own timeline."""


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


@pytest.mark.e2e
def test_a_dropped_body_is_surveyed_and_its_report_opens_beside_the_script(
    no_modeller_page: Page, screenshots: Path
) -> None:
    """The whole of task-19: a maker drops a body and reads what it measures, without typing
    a call or knowing that `survey` and `report` exist - and reads it on a tab of the editor
    group, a document beside the script, with the view still on screen."""
    page = no_modeller_page
    _drop(page, REFERENCE, _bracket())
    page.wait_for_selector("#panel-report:not([hidden])", timeout=BOOT_MS)

    text = page.locator("#report-text").inner_text()
    assert text.startswith("SURVEY of "), text[:80]
    assert "WALLS" in text and "3.000 mm" in text, "the plate's thickness was not measured"
    assert "6.000 mm" in text, "the bore was not measured"
    assert page.locator("#tab-report .name").inner_text().strip() == REFERENCE
    assert page.locator("#tab-report").get_attribute("aria-selected") == "true"
    assert page.locator("#editor").is_hidden(), "the report did not come to the front"
    assert page.locator("#canvas3d").is_visible(), "opening the report covered the view"
    # The chip says the body is held and the report is a click away.
    assert page.locator("#reference").is_visible()
    assert page.locator("#reference-name").inner_text().strip() == REFERENCE
    assert page.locator("#reference-report").is_enabled()
    # A real part's report is hundreds of lines: the tab is what scrolls, not the page.
    assert (
        page.locator("#panel-report").evaluate("(el) => getComputedStyle(el).overflowY") == "auto"
    )
    assert page.evaluate(SURVEYS_TIMED) == 1
    page.screenshot(path=str(screenshots / "20-report-tab.png"))


@pytest.mark.e2e
def test_the_report_tab_shuts_and_the_chip_brings_it_back_without_measuring_again(
    no_modeller_page: Page,
) -> None:
    page = no_modeller_page
    page.locator("#tab-report .tab-close").click()
    assert page.locator("#tab-report").count() == 0
    assert page.locator("#panel-report").is_hidden()
    assert page.locator("#editor").is_visible(), "shutting the report left nothing in front"

    page.click("#reference-report")
    page.wait_for_selector("#panel-report:not([hidden])", timeout=10_000)
    assert page.locator("#report-text").inner_text().startswith("SURVEY of ")
    assert page.evaluate(SURVEYS_TIMED) == 1, "reopening the tab measured the body again"


@pytest.mark.e2e
def test_forgetting_the_body_takes_its_report_with_it(
    no_modeller_page: Page, settle: Callable[[Page], None]
) -> None:
    page = no_modeller_page
    page.click("#reference-clear")
    settle(page)
    assert page.locator("#reference").is_hidden()
    assert page.locator("#tab-report").count() == 0, "the report outlived the body"
    assert page.locator("#panel-report").is_hidden()
    assert page.locator("#editor").is_visible()
    assert _state(page) == "ok", _status(page)


def _far_body() -> bytes:
    """A small plate landed hundreds of millimetres from the origin, the way a real export's
    own coordinates would - task-24's own example, the systainer foot's extent from
    (606.795, -116.868, 0.000) to (651.795, -78.868, 6.800)."""
    from bench import Point, Stock, fill, part, rect, stl
    from bench.plates import plate

    face = fill(rect(45, 38, Point(606.795, -116.868)))
    swept = plate(part("foot", face, Stock(6.8, "ply")))
    assert swept is not None, "the foot did not sweep as a plate"
    return stl(swept.mesh)


def _far_body_2() -> bytes:
    """A different body at a different distant spot - a different file dropped over the
    first, not the same one again, which content-comparison could mistake for a redraw."""
    from bench import Point, Stock, fill, part, rect, stl
    from bench.plates import plate

    face = fill(rect(30, 25, Point(-520.0, 410.0)))
    swept = plate(part("other-foot", face, Stock(4.0, "ply")))
    assert swept is not None, "the second body did not sweep as a plate"
    return stl(swept.mesh)


def _orbit(page: Page) -> None:
    """Drag the view rather than click it, so OrbitControls treats the camera as hand-moved -
    past the click slop, the same way a maker orbiting to look at something would."""
    box = _canvas3d(page)
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(cx, cy)
    page.mouse.down()
    page.mouse.move(cx + 140, cy + 70, steps=12)
    page.mouse.up()
    page.wait_for_timeout(100)


def _clear_reference(page: Page) -> None:
    """Forget whatever reference is held, if any - the chip is inside a hidden container once
    there is none, so a plain click times out waiting for it to become visible."""
    if page.locator("#reference").is_visible():
        page.click("#reference-clear")
        page.wait_for_timeout(300)


SMALL_PLATE_SCRIPT = (
    "from bench import *\n\nshow((part('plate', face(rect(60, 40)), Stock(3, 'ply')),))\n"
)
"""One 60 x 40 mm plate at the origin - unlike the laser examples, which lay several panels
out in a row up to 600 mm wide, this stays a fraction of the size of a body dropped hundreds
of millimetres away, which is the whole point of comparing sizes against one in task-25."""


def _load_small_plate(page: Page, settle: Callable[[Page], None]) -> None:
    """Replace the whole script with :data:`SMALL_PLATE_SCRIPT` and wait for the run it starts."""
    _script(page)
    page.locator(".cm-content").click()
    page.keyboard.press("ControlOrMeta+A")
    page.keyboard.type(SMALL_PLATE_SCRIPT)
    _ran(page, settle)


@pytest.mark.e2e
def test_a_dropped_body_is_a_row_in_the_refs_container(
    no_modeller_page: Page, screenshots: Path
) -> None:
    """task-44: a body somebody else made is listed where everything else selectable is
    listed, and selecting it lights it up - but it is not a ref, so there is nothing to
    insert and the button says so."""
    page = no_modeller_page
    _drop(page, REFERENCE, _bracket())
    page.wait_for_selector("#panel-report:not([hidden])", timeout=BOOT_MS)
    _container(page, "refs")

    row = page.locator(f'bench-refs-tree [data-reference="{REFERENCE}"]')
    row.wait_for(timeout=30_000)
    assert row.count() == 1, "the dropped body is not listed in the refs container"
    # A dropped body was named by no run, so it is not among what the run named.
    assert page.locator(f'bench-refs-tree [data-ref="{REFERENCE}"]').count() == 0, (
        "the dropped body was put in the run's own tree"
    )

    row.click()
    page.wait_for_timeout(150)
    assert row.get_attribute("aria-current") == "true", "the row did not take the selection"
    assert page.locator("#canvas3d").get_attribute("data-reference") == "marked", (
        "selecting the dropped body did not light it up in the view"
    )
    said = page.locator("#selection").inner_text().strip()
    assert REFERENCE in said, f"the bar does not name the dropped body: {said!r}"
    assert page.locator("#insert").is_disabled(), (
        "Insert ref is offered for a dropped body, which ref() cannot name"
    )
    page.screenshot(path=str(screenshots / "31-reference-in-refs.png"))


@pytest.mark.e2e
def test_a_ref_and_a_dropped_body_do_not_hold_the_selection_at_once(
    no_modeller_page: Page,
) -> None:
    """Two kinds of thing, one selection: picking either puts the other down, so the bar and
    Insert ref never describe something that is no longer chosen."""
    page = no_modeller_page
    _drop(page, REFERENCE, _bracket())
    page.wait_for_selector("#panel-report:not([hidden])", timeout=BOOT_MS)
    _container(page, "refs")

    # The ref is taken off the tree rather than off the drawing: what is under any given
    # spot in the view depends on where the camera ended up after the drop framed the body,
    # and this check is about the selection, not about picking.
    first = page.locator("bench-refs-tree [data-ref]").first
    first.wait_for(timeout=30_000)
    ref = first.get_attribute("data-ref") or ""
    assert ref != "", "the run named nothing to select"
    first.click()
    page.wait_for_timeout(150)
    assert page.locator("#insert").is_enabled(), "a picked ref did not offer itself"

    page.locator(f'bench-refs-tree [data-reference="{REFERENCE}"]').click()
    page.wait_for_timeout(150)
    assert page.locator(f'bench-refs-tree [data-ref="{ref}"]').get_attribute("aria-current") == (
        "false"
    ), "the ref kept the selection after a dropped body took it"
    assert page.locator("#insert").is_disabled()

    page.locator(f'bench-refs-tree [data-ref="{ref}"]').click()
    page.wait_for_timeout(150)
    assert (
        page.locator(f'bench-refs-tree [data-reference="{REFERENCE}"]').get_attribute(
            "aria-current"
        )
        == "false"
    ), "the dropped body kept the selection"
    assert page.locator("#canvas3d").get_attribute("data-reference") == "", (
        "the dropped body stayed lit after a ref took the selection"
    )
    assert page.locator("#insert").is_enabled(), "Insert ref did not come back for a ref"


@pytest.mark.e2e
def test_a_dropped_body_is_framed_even_after_the_camera_has_moved(
    no_modeller_page: Page, settle: Callable[[Page], None], screenshots: Path
) -> None:
    """task-24: `touched` used to survive a drop exactly as it survives a run, so a body
    landing hundreds of millimetres from the work stayed off camera until somebody found the
    Fit button. Orbiting first is the walk that would have let that guard come back unnoticed -
    without it, a fix that only worked because nobody had touched the camera yet would pass."""
    page = no_modeller_page
    _load_small_plate(page, settle)  # small, so a body 600 mm away is unmistakably framed
    page.click("#fit")
    page.wait_for_timeout(100)
    _orbit(page)
    orbited = _distance(page)

    _drop(page, "systainer-foot.stl", _far_body())
    page.wait_for_selector("#panel-report:not([hidden])", timeout=BOOT_MS)
    framed = _distance(page)
    assert framed > orbited * 3, (
        f"the camera stood at {framed:.0f} mm after the drop, {orbited:.0f} mm before it - "
        "a body several hundred mm away was not framed"
    )
    page.screenshot(path=str(screenshots / "21-framed-after-orbit.png"))

    # Criterion #3: framing moved the camera, not the mesh - the survey reads the same
    # coordinates the body was dropped with, the exact numbers task-24's own brief quotes.
    text = page.locator("#report-text").inner_text()
    assert "from (606.795, -116.868, 0.000) to (651.795, -78.868, 6.800)" in text, text[:200]

    # Dropping a different file over an existing reference is the same deliberate act, and
    # frames again - even though the camera has since been zoomed well away from what fitting
    # would show, which a same-content re-fit could not be mistaken for.
    page.click("#zoom-in")
    page.click("#zoom-in")
    page.click("#zoom-in")
    zoomed = _distance(page)
    assert zoomed < framed / 2, "zooming in did not actually move the camera"
    _drop(page, "other-foot.stl", _far_body_2())
    # The report panel is already open from the first drop, so waiting for it to appear would
    # pass at once - wait for the second body's own numbers instead, so the assertion below
    # measures the camera after the second survey has actually landed.
    page.wait_for_function(
        "() => (document.querySelector('#report-text')?.textContent ?? '')"
        ".includes('(-520.000, 410.000, 0.000)')",
        timeout=BOOT_MS,
    )
    assert _distance(page) > zoomed * 1.5, (
        "dropping a different file over an existing reference did not frame again"
    )

    # Clearing the reference frames back to the work: the far body leaves and the camera comes
    # back down to something near it, not left standing out at a distant body's own distance.
    after_second = _distance(page)
    page.click("#reference-clear")
    page.wait_for_timeout(500)
    assert _distance(page) < after_second / 2, (
        "clearing the reference did not frame back to the work"
    )


@pytest.mark.e2e
def test_a_run_after_a_drop_does_not_yank_a_moved_camera(no_modeller_page: Page) -> None:
    """task-24 criterion #2: a drop is a deliberate act and a run is not - typing must not
    re-frame a camera the maker has since aimed, even though the same reference is still being
    resent with every run."""
    page = no_modeller_page
    _drop(page, "systainer-foot.stl", _far_body())
    page.wait_for_selector("#panel-report:not([hidden])", timeout=BOOT_MS)
    _script(page)
    _orbit(page)
    moved = _distance(page)
    _typed(page, "\n# a comment, to force a run with nothing else changed\n")
    page.wait_for_timeout(500)
    assert _distance(page) == pytest.approx(moved, rel=0.01), (
        "a run re-framed a camera the maker had just moved"
    )
    _clear_reference(page)


# ---- the pick (decision-7, task-42) -----------------------------------------------------


@pytest.mark.e2e
def test_the_pick_panel_comes_and_goes_with_the_mode_that_makes_a_click_mean_anything(
    no_modeller_page: Page,
) -> None:
    """decision-7 asked for the pick to be gated behind an explicit mode, and task-40 already
    built one: detection is the only thing that makes the backdrop answer a click, so the panel
    lives and dies with it. And with nothing dropped there is no mode and no panel - the chip
    itself is hidden - which is that open question answered by construction."""
    page = no_modeller_page
    _clear_reference(page)
    assert page.locator("#pick").is_hidden(), "the pick panel outlived the body"

    _drop(page, REFERENCE, _bracket())
    page.wait_for_selector("#panel-report:not([hidden])", timeout=BOOT_MS)
    assert page.locator("#pick").is_hidden(), "the panel was up before the mode was on"

    page.click("#reference-detect")
    page.wait_for_selector("#pick:not([hidden])", timeout=BOOT_MS)
    # Nothing picked yet: the assign buttons are dead rather than lying about having numbers.
    assert page.locator("#pick-as-origin").is_disabled()
    assert page.locator("#pick-as-up").is_disabled()

    page.click("#reference-detect")
    assert page.locator("#pick").is_hidden(), "turning detection off left the panel up"


@pytest.mark.e2e
def test_a_placement_is_written_in_one_act_and_can_be_cleared_again(
    no_modeller_page: Page, settle: Callable[[Page], None]
) -> None:
    """decision-7's own open question, answered: the numbers are committed once, together.

    A partial `[reference]` is not a smaller version of a whole one - `bench.placement`
    *raises* on a table missing any of the three, and the app applies a table the moment its
    `file` names the dropped body, so a write per pick would break every run in between. The
    panel refuses one for that reason, in those terms, and one write does all three.
    """
    page = no_modeller_page
    page.click("#reference-detect")
    page.wait_for_selector("#pick:not([hidden])", timeout=BOOT_MS)

    # Two thirds of a placement is refused, naming what is still to say.
    page.fill("#pick-origin", "low")
    page.fill("#pick-up", "+Z")
    page.click("#pick-write")
    refused = page.locator("#pick-why").inner_text()
    assert "along" in refused, refused
    assert "reference" not in page.locator("#values-text").inner_text()

    page.fill("#pick-along", "+X")
    page.click("#pick-write")
    page.wait_for_selector("#pick-unplace:not([hidden])", timeout=BOOT_MS)
    settle(page)

    # It is the project's values file now, and the chip says the body is placed by it.
    written = page.locator("#values-text").inner_text()
    assert "[reference]" in written, written
    assert f'file = "{REFERENCE}"' in written
    assert 'origin = "low"' in written and 'up = "+Z"' in written and 'along = "+X"' in written
    assert "placed" in page.locator("#reference-name").inner_text()

    # And from inside the placed frame the panel refuses to pick again rather than write a
    # number measured in one frame into a table read in another.
    page.wait_for_selector("#pick:not([hidden])", timeout=BOOT_MS)
    assert page.locator("#pick-write").is_disabled()
    assert "placed frame" in page.locator("#pick-frame").inner_text()

    page.click("#pick-unplace")
    settle(page)
    assert "[reference]" not in page.locator("#values-text").inner_text()
    assert "placed" not in page.locator("#reference-name").inner_text()
    _clear_reference(page)
    assert _state(page) == "ok", _status(page)


# ---- the origin and its axes ------------------------------------------------------------


@pytest.mark.e2e
def test_the_origin_and_its_axes_scale_with_what_is_in_view(
    no_modeller_page: Page, settle: Callable[[Page], None], screenshots: Path
) -> None:
    """task-25: the datum is drawn at the origin and its arms are sized off the same box the
    camera frames from, so it neither vanishes beside a small part nor swallows the screen
    beside a large one - `data-datum` is the length those arms are drawn at, in millimetres."""
    page = no_modeller_page
    _clear_reference(page)
    _load_small_plate(page, settle)
    small = float(page.locator("#canvas3d").get_attribute("data-datum") or "0")
    assert small > 0, "no datum was drawn over the work"

    # Criterion #3: it never gets in the way of picking the work itself - a click still
    # reaches the face behind the axes, while the work still fills most of the frame.
    ref = _click_a_face(page, "")
    assert page.locator("#selection").inner_text().strip() == ref

    _drop(page, "systainer-foot.stl", _far_body())
    page.wait_for_selector("#panel-report:not([hidden])", timeout=BOOT_MS)
    large = float(page.locator("#canvas3d").get_attribute("data-datum") or "0")
    assert large > small * 2, "the datum did not grow to match a scene hundreds of mm across"
    page.screenshot(path=str(screenshots / "22-origin-datum.png"))
    _clear_reference(page)


@pytest.mark.e2e
def test_the_origin_and_its_axes_render_in_the_dark_theme(
    dark_page: Page, screenshots: Path
) -> None:
    """task-25: the pane's own background switches for the dark theme (`styles.css`,
    `.canvas-3d`), so a datum drawn to read against the light gradient is worth checking
    against the dark one too."""
    page = dark_page
    datum = float(page.locator("#canvas3d").get_attribute("data-datum") or "0")
    assert datum > 0, "no datum was drawn in the dark theme"
    page.screenshot(path=str(screenshots / "23-origin-datum-dark.png"))


@pytest.mark.e2e
def test_every_side_of_a_run_is_timed_on_the_pages_timeline(printed_page: Page) -> None:
    """The boot, the Python inside the worker, the kernel it drove and the draw on the page
    all arrive as User Timing measures on the page's own timeline - the one the Performance
    panel draws and a collector reads - so nothing about where a run's time went is left in
    a thread nobody is watching."""
    page = printed_page
    page.wait_for_function(DREW_A_MESH, timeout=BOOT_MS)
    names = set(
        page.evaluate("() => performance.getEntriesByType('measure').map((one) => one.name)")
    )
    expected = {
        "bench.boot.python",
        "bench.run.roundtrip",
        "bench.run",
        "bench.script.exec",
        "bench.kernel.mesh",
        "bench.worker.run",
        "bench.view.geometry",
    }
    assert expected <= names, f"missing {sorted(expected - names)}"
