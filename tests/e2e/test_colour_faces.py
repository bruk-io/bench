"""End to end: task-63 - colour a built part's faces by name.

task-40's *detect faces* colours a dropped mesh's detected flats; nothing did the same for a
part a script builds, although every face of a built part already has a name (the ref a click
on it reveals). A *colour faces* toggle in the view gives each named face of each built part
its own colour from the same palette, from the per-face triangle membership the scene already
carries for picking - the viewer only colours, nothing is measured here that Python has not
already named.

Off by default (AC#3's first half); a click still reveals the face's ref and a selection still
shows over its own face colour (AC#2); the toggle survives a re-run (AC#3's second half). Which
two faces land on which two pastels, and whether neighbours read apart, is a screenshot's own
claim - see the PR - not this file's.
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


def _click_a_face(page: Page) -> str:
    """Click round the view until something answers with a ref, and give back what it said.

    Raises:
        AssertionError: if nothing in the view answers a click at all.
    """
    box = _canvas3d(page)
    for across, down in _SPOTS:
        page.mouse.click(box["x"] + box["width"] * across, box["y"] + box["height"] * down)
        page.wait_for_timeout(150)
        said = page.locator("#selection").inner_text().strip()
        if said != HOW_TO_SELECT:
            return said
    raise AssertionError(f"no face answered: {page.locator('#selection').inner_text()}")


def _colouring(page: Page) -> str:
    return page.locator("#canvas3d").get_attribute("data-colour-faces") or ""


def _lit(page: Page) -> int:
    return int(page.locator("#canvas3d").get_attribute("data-lit") or "0")


def _toggle_on(page: Page) -> None:
    page.click("#colour-faces-toggle")
    page.wait_for_function(
        "() => document.querySelector('#colour-faces-toggle')"
        "?.getAttribute('aria-pressed') === 'true'",
        timeout=10_000,
    )


def _toggle_off(page: Page) -> None:
    page.click("#colour-faces-toggle")
    page.wait_for_function(
        "() => document.querySelector('#colour-faces-toggle')"
        "?.getAttribute('aria-pressed') === 'false'",
        timeout=10_000,
    )


@pytest.mark.e2e
def test_colour_faces_starts_off(page: Page) -> None:
    assert page.locator("#colour-faces-toggle").get_attribute("aria-pressed") == "false"
    assert _colouring(page) == ""


@pytest.mark.e2e
def test_turning_colour_faces_on_says_so_and_off_puts_it_back(page: Page) -> None:
    _toggle_on(page)
    try:
        assert _colouring(page) == "on"
    finally:
        _toggle_off(page)
    assert _colouring(page) == ""


@pytest.mark.e2e
def test_a_click_still_reveals_the_face_and_a_selection_still_shows(page: Page) -> None:
    """AC#2: colouring every face its own pastel must not cost a click its ref, and a
    selection - `data-lit` triangles painted `SELECTED` - has to read over the face's own
    colour rather than under it."""
    _toggle_on(page)
    try:
        ref = _click_a_face(page)
        assert ref != HOW_TO_SELECT
        assert _lit(page) > 0, "a selected face painted no triangles as selected"
    finally:
        _toggle_off(page)


@pytest.mark.e2e
def test_colour_faces_survives_a_parameter_edit(page: Page, settle: Callable[[Page], None]) -> None:
    _toggle_on(page)
    try:
        before_triangles = page.locator("#canvas3d").get_attribute("data-triangles")
        page.click("#rail-parameters")
        page.fill("#param-units_x", "3")
        page.wait_for_function(
            "(before) => document.querySelector('#canvas3d')?.dataset.triangles !== before",
            arg=before_triangles,
            timeout=BOOT_MS,
        )
        settle(page)
        assert _colouring(page) == "on"
        assert page.locator("#colour-faces-toggle").get_attribute("aria-pressed") == "true"
    finally:
        _toggle_off(page)
        page.click("#rail-parameters")
        page.fill("#param-units_x", "4")
        settle(page)
