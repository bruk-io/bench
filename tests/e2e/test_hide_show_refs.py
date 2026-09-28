"""End to end: task-67 - hide and show parts and faces from the inspector's faces tree.

Asked for while modelling the wall vent (2026-09-23): an assembly of two parts here - the
frame and the attachment that fits over its collar - hides most of itself, and there was no
way to take the attachment off the view to look at the frame's flange behind it. Every part
and named face row in a part's faces tree - in the inspector, since decision-12 - gets an
eye; hiding one hides everything under it -
the viewer filters triangles by the ref membership the scene already carries, nothing
computed here that Python did not already name - and a hidden triangle is not pickable: a
click through it answers with whatever is drawn behind it instead (AC#1, AC#2). The state is
per tab, keyed by ref name, surviving a re-run and a knob change without ever reaching the
script or the host (AC#3). Isolate and show all are one click each (AC#4). A hidden row says
so, in the tree and in the project's list of parts, and a finding on a hidden part still
lists with that part (AC#5) - checked here against
`enclosure_lid.py`'s own proven thin-wall violation (`test_app.py`'s `CHECKED`/`THIN_WALL`),
since the vent builds no violation of its own at any knob this file drives.

The wall vent (AC#7) is screenshots and the hide/isolate/pick story; the violation story
below uses the enclosure instead, on the same reasoning `test_section_view.py` keeps the
vent's own hook out of the shared `page` fixture - a script worth a deterministic finding,
not a search for one.
"""

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page

try:
    from playwright.sync_api import FloatRect
except ImportError:  # pragma: no cover - the import is the check
    pytest.skip("playwright is not installed - uv pip install playwright", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"

if not (WEB / "node_modules").is_dir():
    pytest.skip("web/node_modules missing - run npm install in web/", allow_module_level=True)
if shutil.which("npx") is None:
    pytest.skip("npx not on PATH", allow_module_level=True)

pytestmark = pytest.mark.e2e

BOOT_MS = 240_000

VENT = "wall_vent.py"
"""The mated pair task-62/task-63's own e2e checks already draw: a frame and the attachment
that hides most of it - exactly what this task was asked for while modelling."""

BODIES = "() => Number(document.querySelector('#canvas3d')?.dataset.bodies ?? 0)"

HOW_TO_SELECT = "click any face to get its ref"

# The attachment's own flat base, framed in the default view - the same spots
# `test_app.py`'s `_VENT_ATTACHMENT_FLAT_SPOTS` answers "attachment/" from, kept here rather
# than imported since every other file in this suite keeps its own view-reading constants
# beside the check that reads them.
_ATTACHMENT_SPOTS = ((0.7, 0.5), (0.7, 0.6), (0.5, 0.7), (0.6, 0.7))

CHECKED = "enclosure_lid.py"
THIN_WALL = "1.2"
CHECKED_PART = "box"
ERROR_ROW = 'bench-violation[severity="error"]'


def _canvas3d(page: Page) -> FloatRect:
    box = page.locator("#canvas3d").bounding_box()
    assert box is not None, "the 3D canvas has no box on screen"
    return box


def _click_at(page: Page, spots: tuple[tuple[float, float], ...]) -> str:
    """Click round `spots` and give back what `#selection` says, or the "click any face" hint
    itself if none of them answered anything - the caller decides what that means."""
    box = _canvas3d(page)
    said = HOW_TO_SELECT
    for across, down in spots:
        page.mouse.click(box["x"] + box["width"] * across, box["y"] + box["height"] * down)
        page.wait_for_timeout(150)
        said = page.locator("#selection").inner_text().strip()
        if said != HOW_TO_SELECT:
            return said
    return said


def _project(page: Page) -> None:
    """The inspector back on the project - its knobs, and its list of parts."""
    page.click("#crumb-project")


def _part(page: Page, ref: str) -> None:
    """Make ``ref`` - a part - the inspector's subject, which puts its faces tree up."""
    _project(page)
    page.locator(f'#parts .part[data-part="{ref}"]').click()


def _row(page: Page, ref: str) -> Locator:
    """``ref``'s row in its part's faces tree - making that part the subject first when the
    inspector is on anything else, since a tree holds one part's rows."""
    part = ref.split("/")[0]
    crumb = page.locator("#crumb-part")
    if crumb.count() == 0 or crumb.inner_text().strip() != part:
        _part(page, part)
    return page.locator(f'bench-refs-tree [data-ref="{ref}"]')


def _listed_hidden(page: Page, part: str) -> str | None:
    """Whether the project's list of parts says ``part`` is hidden."""
    _project(page)
    return page.locator(f'#parts .part[data-part="{part}"]').get_attribute("data-hidden")


def _eye(page: Page, ref: str) -> Locator:
    return _row(page, ref).locator(".eye")


def _isolate(page: Page, ref: str) -> Locator:
    """ "Only" reads the same way the eye does: at full opacity on `.row:hover`, so this
    hovers the row before handing back the button - see `_hide`'s own note."""
    row = _row(page, ref)
    row.hover()
    return row.locator(".isolate")


def _hidden_triangles(page: Page) -> int:
    return int(page.locator("#canvas3d").get_attribute("data-hidden") or "0")


def _hide(page: Page, ref: str) -> None:
    """Click `ref`'s eye and wait for its row to say it is hidden.

    The row is waited for through a locator, whose CSS reaches into the inspector's and the
    tree's shadow roots, where `document.querySelector` would not.

    The eye only reads at full opacity on `.row:hover` - the tree's own answer to a hundred
    rows each wearing one, from `refs-tree.ts`'s own scale check - so this hovers the row
    first: a real click starts with the pointer arriving, and `:hover` is what makes the eye
    actionable at all.
    """
    _row(page, ref).hover()
    _eye(page, ref).click()
    page.locator(f'bench-refs-tree [data-ref="{ref}"][data-hidden="true"]').wait_for(timeout=10_000)


def _show_all(page: Page) -> None:
    """Show everything again, from the project - a face's inspector has no show all."""
    _project(page)
    page.click("#refs-show-all")
    page.wait_for_function(
        "() => (document.querySelector('#canvas3d')?.dataset.hidden ?? '0') === '0'",
        timeout=10_000,
    )


@pytest.fixture(scope="module")
def vent_page(printed_page: Page, example: Callable[[Page, str], None]) -> Page:
    """`printed_page` showing the vent - the frame and the attachment mated over its collar,
    two bodies, both with named faces to hide.

    Loaded once for the whole module, the same reason `printed_page` itself is one page for
    the whole printed story: reselecting an example already open is a second run for nothing,
    and it raced the very check this file is making - `_settled` returning before the new run
    it was meant to wait for had even started. Every test below hides only what it asked to
    and puts it back in a `finally`, so the module's tests can share this one load.
    """
    example(printed_page, VENT)
    printed_page.wait_for_function(f"() => ({BODIES})() === 2", timeout=BOOT_MS)
    return printed_page


@pytest.mark.e2e
def test_every_row_starts_shown(vent_page: Page) -> None:
    page = vent_page
    assert _row(page, "frame").get_attribute("data-hidden") == "false"
    assert _row(page, "attachment").get_attribute("data-hidden") == "false"
    assert _eye(page, "attachment").get_attribute("aria-pressed") == "false"
    assert _hidden_triangles(page) == 0


@pytest.mark.e2e
def test_hiding_the_attachment_hides_its_triangles_and_it_is_no_longer_pickable(
    vent_page: Page, screenshots: Path
) -> None:
    """AC#1, AC#2: the eye hides the row and everything under it, and a face it used to cover
    stops answering a click - it either answers nothing or answers whatever the attachment
    was standing in front of."""
    page = vent_page
    before = _click_at(page, _ATTACHMENT_SPOTS)
    assert before.startswith("attachment/"), (
        f"the default scene did not pick the attachment: {before}"
    )

    _hide(page, "attachment")
    try:
        assert _eye(page, "attachment").get_attribute("aria-pressed") == "true"
        assert _row(page, "attachment").get_attribute("data-hidden") == "true"
        assert _hidden_triangles(page) > 0

        after = _click_at(page, _ATTACHMENT_SPOTS)
        assert not after.startswith("attachment/"), f"a hidden face still answered a click: {after}"

        page.screenshot(path=str(screenshots / "task-67-attachment-hidden.png"))
    finally:
        _show_all(page)


@pytest.mark.e2e
def test_hiding_survives_a_parameter_edit(vent_page: Page, settle: Callable[[Page], None]) -> None:
    """AC#3: view state, kept across a re-run and a knob change - never reset by either."""
    page = vent_page
    _hide(page, "attachment")
    try:
        before_triangles = page.locator("#canvas3d").get_attribute("data-triangles")
        _project(page)
        page.fill("#param-duct", "60")
        page.wait_for_function(
            "(before) => document.querySelector('#canvas3d')?.dataset.triangles !== before",
            arg=before_triangles,
            timeout=BOOT_MS,
        )
        settle(page)

        assert _eye(page, "attachment").get_attribute("aria-pressed") == "true"
        assert _row(page, "attachment").get_attribute("data-hidden") == "true"
        assert _hidden_triangles(page) > 0
    finally:
        _show_all(page)
        _project(page)
        page.fill("#param-duct", "50")
        settle(page)


@pytest.mark.e2e
def test_isolate_the_frame_hides_everything_else_and_show_all_restores_it(
    vent_page: Page, screenshots: Path
) -> None:
    """AC#4: isolate and show all, one click each."""
    page = vent_page
    assert page.locator("#refs-show-all").is_disabled()

    _isolate(page, "frame").click()
    page.locator('#canvas3d[data-hidden]:not([data-hidden="0"])').wait_for(timeout=10_000)
    try:
        assert _row(page, "frame").get_attribute("data-hidden") == "false"
        assert not page.locator("#refs-show-all").is_disabled()
        # The attachment's own row is in its own tree: the project's list says it too.
        assert _listed_hidden(page, "attachment") == "true"
        assert _listed_hidden(page, "frame") == "false"
        assert _row(page, "attachment").get_attribute("data-hidden") == "true"
        page.screenshot(path=str(screenshots / "task-67-frame-isolated.png"))
    finally:
        _show_all(page)
    assert _row(page, "attachment").get_attribute("data-hidden") == "false"
    assert page.locator("#refs-show-all").is_disabled()
    assert _hidden_triangles(page) == 0


@pytest.mark.e2e
def test_a_finding_on_a_hidden_part_still_lists_with_it(
    printed_page: Page, example: Callable[[Page, str], None], settle: Callable[[Page], None]
) -> None:
    """AC#5: hiding a part is a viewer thing, and the inspector is not the viewer - a check
    that found something on a part nobody can currently see must still say so, on that part,
    and the project's list must still badge it."""
    page = printed_page
    example(page, CHECKED)
    _project(page)
    page.fill("#param-wall", THIN_WALL)
    page.locator("#findings", has_text="error").click(timeout=BOOT_MS)
    found = page.locator(ERROR_ROW, has_text="thinnest wall").first
    found.wait_for(timeout=BOOT_MS)
    settle(page)

    _hide(page, CHECKED_PART)
    try:
        assert _row(page, CHECKED_PART).get_attribute("data-hidden") == "true"
        assert _row(page, CHECKED_PART).locator(".flag").count() == 1, (
            "a hidden part's finding mark is gone"
        )
        assert found.is_visible(), "a hidden part's finding no longer lists with it"
        _project(page)
        badge = page.locator(f'#parts .part[data-part="{CHECKED_PART}"] .badge')
        assert badge.get_attribute("data-standing") == "error", "a hidden part lost its badge"
    finally:
        _show_all(page)
        _project(page)
        page.fill("#param-wall", "3")
        settle(page)
