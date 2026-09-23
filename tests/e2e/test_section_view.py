"""End to end: task-62 - a section view, clipping the whole scene at a plane.

decision-10 is what this is for: the vent's tongue sits under the collar's hook, inside the
attachment, and no pose shows it from outside. A toggle in the view clips every part at a
plane along X, Y or Z, with a slider for where along it - off by default (AC#1), reading as a
gap where two parts meet rather than as one more shaded face (AC#2), left exactly as set
across a re-run or a parameter edit rather than reset by either (AC#3), and taking picking
with it: a face the plane has clipped away must not answer a click (AC#4).

The default page (``page``, from ``conftest.py``) already has the cabinet drawn, which is
enough for the toggle, the persistence and the picking checks; the vent's own hook, sectioned
at two `Fitting` values, is screenshots only - a separate script drives ``tools.preview`` over
a temporary copy of ``projects/frame``, never the checked-out one, and is not a pytest check.
"""

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

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

HOW_TO_SELECT = "click any face to get its ref"

_SPOTS = ((0.5, 0.55), (0.42, 0.6), (0.58, 0.5), (0.5, 0.42), (0.62, 0.62), (0.35, 0.45))


def _canvas3d(page: Page) -> FloatRect:
    box = page.locator("#canvas3d").bounding_box()
    assert box is not None, "the 3D canvas has no box on screen"
    return box


def _click(page: Page) -> str | None:
    """Click round the view until something answers, or give back `None` if nothing did in
    any of the spots tried - the outcome the picking check wants once the section has clipped
    every one of them away."""
    box = _canvas3d(page)
    for across, down in _SPOTS:
        page.mouse.click(box["x"] + box["width"] * across, box["y"] + box["height"] * down)
        page.wait_for_timeout(150)
        said = page.locator("#selection").inner_text().strip()
        if said != HOW_TO_SELECT:
            return said
    return None


def _data_section(page: Page) -> str:
    return page.locator("#canvas3d").get_attribute("data-section") or ""


def _bounds(page: Page) -> tuple[float, ...]:
    raw = page.locator("#canvas3d").get_attribute("data-bounds") or ""
    return tuple(float(one) for one in raw.split(","))


def _toggle_on(page: Page) -> None:
    page.click("#section-toggle")
    page.wait_for_function(
        "() => document.querySelector('#section-toggle')?.getAttribute('aria-pressed') === 'true'",
        timeout=10_000,
    )


def _toggle_off(page: Page) -> None:
    page.click("#section-toggle")
    page.wait_for_function(
        "() => document.querySelector('#section-toggle')?.getAttribute('aria-pressed') === 'false'",
        timeout=10_000,
    )


@pytest.mark.e2e
def test_the_section_toggle_starts_off(page: Page) -> None:
    assert page.locator("#section-toggle").get_attribute("aria-pressed") == "false"
    assert _data_section(page) == ""
    assert page.locator("#section-axis").is_disabled()
    assert page.locator("#section-position").is_disabled()


@pytest.mark.e2e
def test_turning_the_section_on_clips_the_view_and_says_so(page: Page) -> None:
    _toggle_on(page)
    try:
        assert page.locator("#section-toggle").get_attribute("aria-pressed") == "true"
        assert not page.locator("#section-axis").is_disabled()
        assert not page.locator("#section-position").is_disabled()
        said = _data_section(page)
        assert said.startswith("x:"), said
    finally:
        _toggle_off(page)
    assert _data_section(page) == ""


@pytest.mark.e2e
def test_the_section_stays_exactly_as_set_across_a_parameter_edit(
    page: Page, settle: Callable[[Page], None]
) -> None:
    """A pose knob moving the geometry through a still plane is the whole point (decision-10):
    the axis and the position the section is set to must not move on their own when a run
    redraws the scene."""
    _toggle_on(page)
    try:
        page.select_option("#section-axis", "z")
        before = _data_section(page)
        assert before.startswith("z:"), before
        before_triangles = page.locator("#canvas3d").get_attribute("data-triangles")

        page.click("#rail-parameters")
        page.fill("#param-units_x", "3")
        page.wait_for_function(
            "(before) => document.querySelector('#canvas3d')?.dataset.triangles !== before",
            arg=before_triangles,
            timeout=BOOT_MS,
        )
        settle(page)

        after = _data_section(page)
        assert after == before, f"the section moved on a re-run: {before} -> {after}"
        assert page.locator("#section-toggle").get_attribute("aria-pressed") == "true"
    finally:
        _toggle_off(page)
        page.click("#rail-parameters")
        page.fill("#param-units_x", "4")
        settle(page)


@pytest.mark.e2e
def test_a_face_the_section_has_clipped_away_cannot_be_picked(page: Page) -> None:
    """Picking a face that is still drawn works exactly as it does off; a face the plane has
    clipped away must answer no click at all, not the nearest thing still standing."""
    picked_before = _click(page)
    assert picked_before is not None, "nothing in the default scene answered a click at all"

    _toggle_on(page)
    try:
        page.select_option(
            "#section-axis", "x"
        )  # not left to the default: another check may have changed it
        low, _y0, _z0, _high, _y1, _z1 = _bounds(page)
        # `fill` refuses a `range` input, so the value and its `input` event are set by hand -
        # to the axis' own low bound, which clips the whole scene away (AC#4's own worst case).
        page.eval_on_selector(
            "#section-position",
            "(el, value) => {"
            " el.value = value;"
            " el.dispatchEvent(new Event('input', { bubbles: true }));"
            "}",
            str(low),
        )
        page.wait_for_function(
            "(want) => (document.querySelector('#canvas3d')?.dataset.section ?? '')"
            ".startsWith(want)",
            arg=f"x:{low:.2f}",
            timeout=10_000,
        )
        picked_after = _click(page)
        assert picked_after is None, f"a clipped-away face still answered: {picked_after!r}"
    finally:
        _toggle_off(page)
