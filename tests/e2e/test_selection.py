"""End to end: a selection is by ref (decision-12, task-92).

It survives a re-run - a script edit, a knob - while the run still names what is selected and
falls back to the project when it does not; the status bar's count selects the part worst off
and lights the first place of its worst finding; and the selection is in the URL hash, so a
reload, or a link opened somewhere else, lands on the same subject once the scene arrives.

One page walks the cabinet, the default project, in file order; a link is opened in a second
browser context on the same host - a desktop and a tablet, sharing the project - and the
status bar's count is last, on the tote example, since picking an example opens a project of
its own.

Run it with ``uv run pytest -m e2e``; the default run leaves it out.
"""

import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Browser

    from tests.e2e.conftest import Hosted, Serve

try:
    from playwright.sync_api import Page
except ImportError:  # pragma: no cover - the import is the check
    pytest.skip("playwright is not installed - uv pip install playwright", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"

if not (WEB / "node_modules").is_dir():
    pytest.skip("web/node_modules missing - run npm install in web/", allow_module_level=True)
if shutil.which("npx") is None:
    pytest.skip("npx not on PATH", allow_module_level=True)

BOOT_MS = 240_000
"""How long the app may take to boot Python and run a script, in milliseconds."""

KEPT = "drawer-front-1"
"""A part the cabinet makes whatever its drawer count."""

KEPT_FACE = f"{KEPT}/pull"
"""A face on it - the pull the default cabinet's e2e clicks."""

RETIRED = "drawer-front-6"
"""A part the cabinet stops making when ``drawers`` comes down to two."""

RETIRED_FACE = f"{RETIRED}/pull"
"""A face on it, which goes with it."""

TOTE = "systainer_tote.py"
"""The printed example that leaves one overhang warning on its ``tote`` on purpose."""

HOW_TO_SELECT = "click any face to get its ref"
"""What the selection bar says with nothing selected - ``status.ts``' own words."""

CHANGED = """(before) => {
    const pane = document.querySelector('#canvas3d');
    return `${pane?.dataset.triangles}|${pane?.dataset.bounds}` !== before;
}"""
"""Whether the view drew something other than ``before``, a :func:`_drawn` fingerprint."""

DRAWS = "() => performance.getEntriesByName('bench.view.geometry').length"
"""How many scenes the view has drawn - one ``bench.view.geometry`` span per run that worked."""

TURN_A_KNOB = """([name, value]) => {
    document.querySelector('#inspector').dispatchEvent(new CustomEvent('param-change', {
        bubbles: true, composed: true, detail: { name, value },
    }));
}"""
"""A knob turned, as the knob itself says so: its own ``param-change``, from the inspector.

The knobs are the project's in the inspector today (task-88), so a person cannot turn one with a
part selected - reaching them from a part is task-94's. The event is the one a knob sends, and
it goes through the page's own handler, override table and debounced run; only the click on a
knob that is not on screen is skipped."""


# ---- the page -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def host(serve: Serve) -> Iterator[Hosted]:
    """One server and projects root for the module, so a second context can open a link to
    the project the first one is on."""
    with serve() as served:
        yield served


@pytest.fixture(scope="module")
def page(browser: Browser, host: Hosted) -> Iterator[Page]:
    """The app on the cabinet, booted and showing its first scene."""
    context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    found = context.new_page()
    found.goto(host.url)
    _rendered(found)
    try:
        yield found
    finally:
        context.close()


def _settled(page: Page) -> None:
    page.wait_for_function(
        "() => document.querySelector('#state')?.dataset.state !== 'running'", timeout=BOOT_MS
    )


def _rendered(page: Page) -> None:
    page.wait_for_selector("#canvas3d[data-bodies]:not([data-bodies='0'])", timeout=BOOT_MS)
    _settled(page)


def _opened(browser: Browser, url: str) -> Page:
    """A page of a context of its own, opened on ``url`` and booted to its first scene."""
    context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    found = context.new_page()
    found.goto(url)
    _rendered(found)
    return found


# ---- reading and acting ---------------------------------------------------------------


def _drawn(page: Page) -> str:
    pane = page.locator("#canvas3d")
    return f"{pane.get_attribute('data-triangles')}|{pane.get_attribute('data-bounds')}"


def _selected(page: Page) -> str:
    """The ref the view has lit."""
    return page.locator("#canvas3d").get_attribute("data-selected") or ""


def _said(page: Page) -> str:
    """What the inspector's selection bar says."""
    return page.locator("#selection").inner_text().strip()


def _on_project(page: Page) -> bool:
    return page.locator("#crumb-project").get_attribute("aria-current") == "page"


def _part_crumb(page: Page) -> str:
    return page.locator("#crumb-part").inner_text().strip()


def _hash(page: Page) -> str:
    return str(page.evaluate("() => location.hash"))


def _project(page: Page) -> None:
    page.click("#crumb-project")


def _part(page: Page, ref: str) -> None:
    """Make a part the subject from the project's list of parts."""
    _project(page)
    page.locator(f'#parts .part[data-part="{ref}"]').click()


def _face(page: Page, ref: str) -> None:
    """Make a face the subject from its part's tree, opening the part's row to reach it."""
    part = ref.split("/")[0]
    _part(page, part)
    row = page.locator(f'bench-refs-tree [data-ref="{ref}"]')
    if row.count() == 0:
        page.locator(f'bench-refs-tree [data-ref="{part}"] .twist').click()
    row.click()
    page.wait_for_timeout(150)
    assert _said(page) == ref, f"{ref} was clicked in the tree and {_said(page)!r} is selected"


def _script_drawers(page: Page, was: str, now: str) -> None:
    """Change what the cabinet's script passes as ``drawers=`` by hand in the editor, and wait
    for the run that makes something else."""
    before = _drawn(page)
    page.click("#tab-script")
    page.locator(".cm-line", has_text=f"drawers={was}").click()
    page.keyboard.press("End")
    for _ in was:
        page.keyboard.press("Backspace")
    page.keyboard.type(now)
    page.wait_for_function(CHANGED, arg=before, timeout=BOOT_MS)
    _settled(page)


def _knob_drawers(page: Page, value: int) -> None:
    """Turn the cabinet's ``drawers`` knob and wait for the run that makes something else."""
    before = _drawn(page)
    page.evaluate(TURN_A_KNOB, ["drawers", value])
    page.wait_for_function(CHANGED, arg=before, timeout=BOOT_MS)
    _settled(page)


# ---- #1: a selection survives a re-run while its ref does -----------------------------


@pytest.mark.e2e
def test_a_part_stays_selected_across_a_script_edit(page: Page) -> None:
    """A part the edited script still makes is still the subject, and still lit."""
    _part(page, KEPT)
    assert _part_crumb(page) == KEPT
    _script_drawers(page, "p.drawers,", "2,")
    try:
        assert not _on_project(page), "a script edit put the part down"
        assert _part_crumb(page) == KEPT
        assert _selected(page) == KEPT
        assert _said(page) == KEPT
    finally:
        _script_drawers(page, "2,", "p.drawers,")
    assert _part_crumb(page) == KEPT, "putting the script back put the part down"


@pytest.mark.e2e
def test_a_face_stays_selected_while_it_is_made_and_goes_when_it_is_not(
    page: Page, screenshots: Path
) -> None:
    """A face the run still names stays the subject across a script edit; a face on a part the
    run stops making leaves the project as the subject - not the part it was on, which is gone
    too, and not a face nothing answers to."""
    _face(page, KEPT_FACE)
    _script_drawers(page, "p.drawers,", "2,")
    try:
        assert _said(page) == KEPT_FACE, f"{_said(page)!r} is selected after the edit"
        assert _selected(page) == KEPT_FACE
        page.screenshot(path=str(screenshots / "task-92-face-kept.png"))
    finally:
        _script_drawers(page, "2,", "p.drawers,")

    _face(page, RETIRED_FACE)
    _script_drawers(page, "p.drawers,", "2,")
    try:
        assert _on_project(page), "a face on a part no longer made is still the subject"
        assert _said(page) == HOW_TO_SELECT
        assert _selected(page) == ""
        assert _hash(page) == "", f"the hash still names {_hash(page)!r}"
    finally:
        _script_drawers(page, "2,", "p.drawers,")


@pytest.mark.e2e
def test_a_part_stays_selected_across_a_knob_and_goes_when_the_knob_retires_it(
    page: Page,
) -> None:
    """The same rule for a run a knob made: the part stays while it is made, and the project
    is the subject once it is not (see ``TURN_A_KNOB`` on why the knob is not clicked)."""
    _part(page, KEPT)
    _knob_drawers(page, 2)
    try:
        assert _part_crumb(page) == KEPT, "a knob's run put the part down"
        assert not _on_project(page)
        assert _selected(page) == KEPT
    finally:
        _knob_drawers(page, 6)

    _part(page, RETIRED)
    _knob_drawers(page, 2)
    try:
        assert _on_project(page), f"{RETIRED} is not made and is still the subject"
        assert _said(page) == HOW_TO_SELECT
    finally:
        _knob_drawers(page, 6)


# ---- #3: the selection round-trips through the URL ------------------------------------


@pytest.mark.e2e
def test_the_selection_is_written_to_the_hash(page: Page) -> None:
    """Each subject is in the address: a part, a face, and the project as no hash at all."""
    _part(page, KEPT)
    assert _hash(page) == f"#part={KEPT}"
    _face(page, KEPT_FACE)
    assert _hash(page) == f"#face={KEPT_FACE}"
    _project(page)
    assert _hash(page) == ""
    assert "#" not in page.url


@pytest.mark.e2e
def test_a_reload_opens_on_the_same_face(page: Page, screenshots: Path) -> None:
    """Reload with a face selected and the same face is selected once the scene is back."""
    _face(page, KEPT_FACE)
    page.reload()
    _rendered(page)
    page.wait_for_function(
        "(ref) => document.querySelector('#canvas3d')?.dataset.selected === ref",
        arg=KEPT_FACE,
        timeout=BOOT_MS,
    )
    assert _said(page) == KEPT_FACE
    assert _hash(page) == f"#face={KEPT_FACE}"
    page.screenshot(path=str(screenshots / "task-92-reloaded-on-a-face.png"))
    _project(page)


@pytest.mark.e2e
def test_a_link_opened_elsewhere_selects_its_part(
    page: Page, browser: Browser, host: Hosted, screenshots: Path
) -> None:
    """A link to a part, opened in another browser on the same host, opens on that part."""
    assert page is not None  # the cabinet is the host's project by now
    other = _opened(browser, f"{host.url}#part={KEPT}")
    try:
        other.wait_for_function(
            "(ref) => document.querySelector('#canvas3d')?.dataset.selected === ref",
            arg=KEPT,
            timeout=BOOT_MS,
        )
        assert _part_crumb(other) == KEPT
        assert other.locator("#crumb-part").get_attribute("aria-current") == "page"
        assert _hash(other) == f"#part={KEPT}", "following the link rewrote it"
        other.screenshot(path=str(screenshots / "task-92-link-to-a-part.png"))
    finally:
        other.context.close()


@pytest.mark.e2e
def test_a_link_to_something_the_run_does_not_make_opens_on_the_project(
    browser: Browser, host: Hosted, page: Page
) -> None:
    """A link to a ref the run has no such thing as - renamed, retired, mistyped - opens on
    the project, says nothing went wrong, and takes the stale name out of the address."""
    assert page is not None
    other = _opened(browser, f"{host.url}#face={RETIRED}/no-such-face")
    errors: list[str] = []
    other.on("pageerror", lambda problem: errors.append(str(problem)))
    try:
        other.wait_for_function("() => location.hash === ''", timeout=BOOT_MS)
        assert other.locator("#crumb-project").get_attribute("aria-current") == "page"
        assert _said(other) == HOW_TO_SELECT
        assert _selected(other) == ""
        assert errors == []
    finally:
        other.context.close()


@pytest.mark.e2e
def test_a_hash_changed_in_the_tab_selects_what_it_names(page: Page) -> None:
    """A link pasted into the address bar of a tab already open follows it - no reload."""
    _project(page)
    page.evaluate("(ref) => { location.hash = `#part=${ref}`; }", KEPT)
    page.wait_for_function(
        "(ref) => document.querySelector('#canvas3d')?.dataset.selected === ref",
        arg=KEPT,
        timeout=5_000,
    )
    assert _part_crumb(page) == KEPT
    page.evaluate("() => { location.hash = '#part=nothing-by-this-name'; }")
    page.wait_for_function("() => location.hash === ''", timeout=5_000)
    assert _on_project(page)


# ---- #2: the status bar's count goes to the worst part and lights its first place ----


@pytest.mark.e2e
def test_the_count_selects_the_worst_part_and_lights_its_first_place(
    page: Page, example: Callable[[Page, str], None], screenshots: Path
) -> None:
    """The tote's one warning: the count selects the tote, and the first place of the warning
    is lit in the view and marked in the list - the place a person would click first. And the
    selection it made is by ref like any other, so a script edit keeps both."""
    example(page, TOTE)
    count = page.locator("#findings")
    assert count.inner_text().strip() == "1 warning", count.inner_text()
    count.click()

    assert _part_crumb(page) == "tote"
    assert page.locator("#crumb-part").get_attribute("aria-current") == "page"
    found = page.locator('bench-violation[severity="warning"]').first
    found.wait_for(timeout=BOOT_MS)
    first = str(found.locator(".place").first.get_attribute("data-ref"))
    assert first.startswith("tote/"), first
    assert _selected(page) == first, f"the count lit {_selected(page)!r}, not {first!r}"
    assert _said(page) == first
    assert found.locator('.place[aria-current="true"]').inner_text().strip() == first
    assert int(page.locator("#canvas3d").get_attribute("data-lit") or "0") > 0, "nothing is lit"
    assert _hash(page) == "#part=tote"
    page.screenshot(path=str(screenshots / "task-92-count-lights-first-place.png"))

    # A run that changes nothing about the tote keeps the part and the place it lit.
    # The view's own span on the timeline is drawn once per run that worked, so a count past
    # the one before is a run that has landed.
    before = page.evaluate(DRAWS)
    page.click("#tab-script")
    page.locator(".cm-content").click()
    page.keyboard.press("ControlOrMeta+End")
    page.keyboard.type("\n# a re-run\n")
    page.wait_for_function(f"(before) => ({DRAWS})() > before", arg=before, timeout=BOOT_MS)
    _settled(page)
    assert _part_crumb(page) == "tote"
    assert _selected(page) == first, f"a re-run left {_selected(page)!r} lit"


@pytest.mark.e2e
def test_a_lit_place_a_run_takes_away_leaves_its_part_selected(page: Page) -> None:
    """The case the view alone got wrong: a place of the tote's warning is lit, and a script
    edit stops making that place while still making the tote. The view puts the place down,
    as it should - but the part is still made, so it stays the subject, lit whole, rather than
    the page falling back to the project. Follows the count's check above, on the same tote.
    """
    _part(page, "tote")
    page.locator('bench-violation[severity="warning"] .place[data-ref="tote/socket-4"]').click()
    page.wait_for_timeout(150)
    assert _selected(page) == "tote/socket-4"

    # Four sockets become one: `socket-4` is no longer cut, and the tote is still made.
    before = page.evaluate(DRAWS)
    page.click("#tab-script")
    # The editor draws only the lines near its cursor, so the cursor is walked down to the one.
    page.locator(".cm-content").click()
    page.keyboard.press("ControlOrMeta+Home")
    wanted = "grid(socket, (2, 2)"
    for _ in range(600):
        if wanted in (page.locator(".cm-activeLine").text_content() or ""):
            break
        page.keyboard.press("ArrowDown")
    text = page.locator(".cm-activeLine").text_content() or ""
    assert wanted in text, text
    # The cursor came down column 0 from the top, so it is at the start of the line: walked
    # right by characters, which a wrapped line's End and Home would not be.
    for _ in range(text.index("(2, 2)")):
        page.keyboard.press("ArrowRight")
    for _ in "(2, 2)":
        page.keyboard.press("Shift+ArrowRight")
    page.keyboard.type("(1, 1)")
    page.wait_for_function(f"(before) => ({DRAWS})() > before", arg=before, timeout=BOOT_MS)
    _settled(page)

    assert _selected(page) == "tote", f"{_selected(page)!r} is lit"
    assert _part_crumb(page) == "tote", "the part went with the place it lit"
    assert page.locator("#crumb-part").get_attribute("aria-current") == "page"
    assert _said(page) == "tote"
    assert _hash(page) == "#part=tote"
