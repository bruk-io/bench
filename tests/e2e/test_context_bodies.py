"""End to end: task-90 - a body shown for context, drawn and never made.

``examples/pipe_bracket.py`` shows the pipe it holds with ``context(pipe, label="pipe")``. In
the built app, with the browser's own modeller, the bracket is the one part drawn and the pipe
is drawn beside it as context: counted apart from the parts, its faces answering a click as
``pipe/...`` wherever no part is under the pointer, and the bracket's answering wherever one
is. What it looks like - translucent, in a colour no part wears - is the screenshot's claim,
in the PR, not this file's.
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

_ACROSS = tuple(0.2 + 0.05 * step for step in range(13))
_DOWN = tuple(0.2 + 0.05 * step for step in range(13))
"""A grid of spots over the middle of the view, tried in turn: where the bracket and the pipe
land on screen is the camera's business, so the test asks what each spot answers rather than
knowing in advance which one is which."""


def _canvas3d(page: Page) -> FloatRect:
    box = page.locator("#canvas3d").bounding_box()
    assert box is not None, "the 3D canvas has no box on screen"
    return box


def _data(page: Page, name: str) -> str:
    return page.locator("#canvas3d").get_attribute(f"data-{name}") or ""


@pytest.fixture(scope="module")
def bracket_page(printed_page: Page, example: Callable[[Page, str], None]) -> Page:
    """``printed_page`` showing the pipe bracket, once for the module."""
    example(printed_page, "pipe_bracket.py")
    printed_page.wait_for_function(
        "() => document.querySelector('#canvas3d')?.dataset.context === '1'", timeout=BOOT_MS
    )
    return printed_page


@pytest.mark.e2e
def test_the_pipe_is_drawn_as_context_beside_the_one_part(bracket_page: Page) -> None:
    assert _data(bracket_page, "bodies") == "1", "the bracket is the only part"
    assert _data(bracket_page, "context") == "1", "the pipe is drawn, apart from the parts"
    assert int(_data(bracket_page, "context-triangles")) > 0


@pytest.mark.e2e
def test_a_click_names_the_pipes_face_where_no_part_is_under_it_and_the_part_where_one_is(
    bracket_page: Page, screenshots: Path
) -> None:
    """Every spot of the grid clicked, and what the status bar said kept: the pipe answers by
    its faces' own names, the bracket still answers where it is, and nothing answers as the
    pipe's bare label - a triangle with no name of its own is not a thing to pick. The view is
    left with a face of the pipe picked, and a picture of it taken."""
    box = _canvas3d(bracket_page)
    said: dict[str, tuple[float, float]] = {}
    for across in _ACROSS:
        for down in _DOWN:
            spot = (box["x"] + box["width"] * across, box["y"] + box["height"] * down)
            bracket_page.mouse.click(*spot)
            bracket_page.wait_for_timeout(60)
            said.setdefault(bracket_page.locator("#selection").inner_text().strip(), spot)
    piped = sorted(one for one in said if one.startswith("pipe/"))
    assert piped, sorted(said)
    assert any(one.startswith("bracket") for one in said), sorted(said)
    assert "pipe" not in said
    bracket_page.mouse.click(*said[piped[0]])
    bracket_page.wait_for_timeout(150)
    assert _data(bracket_page, "selected") == piped[0]
    bracket_page.screenshot(path=str(screenshots / "context-pipe-picked.png"))
