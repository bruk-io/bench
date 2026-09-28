"""End to end: task-89 - the view's three ways of looking, Assembled, On bed and Section.

decision-12's view modes, in the built app with the browser's own modeller: a control in the
view's bar switches between them and the view says which it is in (AC#1); *On bed* lays each
printed part on the printer's bed with the placement Python sent, marks what does not fit and
paints what the overhang findings name (AC#2, AC#3); and *Section* cuts the parts, a context
body and a dropped reference alike, each with its cut face filled (AC#4). Where the parts land
on the bed, to the corner, is ``tests/adapter/test_on_bed.py``'s; this asks what a person sees.

Whether a cut face is filled is read off the picture itself: every cut face is painted unlit in
its own colour - a part's red, a context body's sand, a reference's charcoal - so counting the
pixels of that colour in a screenshot of the view says whether it is there, with nothing about
the view's own workings taken on trust.
"""

import base64
import shutil
import struct
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

try:
    import playwright.sync_api  # ruff: ignore[unused-import]  # the import is the check
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

CUT = (0xB2, 0x3A, 0x2E)
"""A part's cut face - ``CUT`` in ``web/src/viewer3d.ts``."""

CONTEXT_CUT = (0xA9, 0x80, 0x3D)
"""A context body's cut face."""

REFERENCE_CUT = (0x27, 0x30, 0x3A)
"""A reference's cut face."""

ENOUGH = 50
"""How many pixels of a cut face's colour count as the face being there: a few stray ones
can land on an antialiased edge, a filled face is hundreds."""

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
"""Drop a file on the view the way a drag from the desktop lands - ``test_app.py``'s own."""


# ---- reading the view -------------------------------------------------------------------


def _data(page: Page, name: str) -> str:
    return page.locator("#canvas3d").get_attribute(f"data-{name}") or ""


def _mode(page: Page, mode: str) -> None:
    """Pick a way of looking in the view's bar, and wait for the view to be in it."""
    page.locator(f"#view-modes [data-mode='{mode}']").click()
    page.wait_for_function(
        "(want) => document.querySelector('#canvas3d')?.dataset.mode === want",
        arg=mode,
        timeout=10_000,
    )
    page.wait_for_timeout(300)


def _cut_at(page: Page, axis: str, position: float) -> None:
    """Put *Section*'s plane at ``position`` along ``axis`` - by hand, since ``fill`` refuses a
    range input."""
    page.select_option("#section-axis", axis)
    page.eval_on_selector(
        "#section-position",
        "(el, value) => {"
        " el.value = value;"
        " el.dispatchEvent(new Event('input', { bubbles: true }));"
        "}",
        str(position),
    )
    page.wait_for_timeout(300)


def _span(page: Page) -> tuple[float, float]:
    """Where the stage runs along the axis chosen - the slider's own range."""
    slider = page.locator("#section-position")
    return float(slider.get_attribute("min") or 0), float(slider.get_attribute("max") or 0)


def _rows(png: bytes) -> tuple[int, int, int, list[bytes]]:
    """A PNG's width, height, bytes per pixel and unfiltered rows: 8-bit RGB or RGBA, not
    interlaced - what a browser screenshot is."""
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    at, packed, width, height, kind = 8, b"", 0, 0, 0
    while at < len(png):
        (size,) = struct.unpack(">I", png[at : at + 4])
        name, body = png[at + 4 : at + 8], png[at + 8 : at + 8 + size]
        if name == b"IHDR":
            width, height, depth, kind, _, _, laced = struct.unpack(">IIBBBBB", body)
            assert (depth, laced) == (8, 0) and kind in (2, 6), (depth, kind, laced)
        elif name == b"IDAT":
            packed += body
        at += 12 + size
    per = 3 if kind == 2 else 4
    raw = zlib.decompress(packed)
    stride = width * per
    rows: list[bytes] = []
    previous = bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        kind_of, line = raw[start], bytearray(raw[start + 1 : start + 1 + stride])
        for x in range(stride):
            a = line[x - per] if x >= per else 0
            b = previous[x]
            c = previous[x - per] if x >= per else 0
            if kind_of == 1:
                line[x] = (line[x] + a) & 0xFF
            elif kind_of == 2:
                line[x] = (line[x] + b) & 0xFF
            elif kind_of == 3:
                line[x] = (line[x] + (a + b) // 2) & 0xFF
            elif kind_of == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
        rows.append(bytes(line))
        previous = line
    return width, height, per, rows


def _counted(page: Page, colour: tuple[int, int, int], slack: int = 6) -> int:
    """How many pixels of the view are ``colour``, give or take ``slack`` a channel."""
    width, _height, per, rows = _rows(page.locator("#canvas3d").screenshot())
    found = 0
    for row in rows:
        for x in range(width):
            r, g, b = row[x * per], row[x * per + 1], row[x * per + 2]
            if (
                abs(r - colour[0]) <= slack
                and abs(g - colour[1]) <= slack
                and abs(b - colour[2]) <= slack
            ):
                found += 1
    return found


def _settled(page: Page) -> None:
    page.wait_for_function(
        "() => document.querySelector('#state')?.dataset.state !== 'running'", timeout=BOOT_MS
    )
    page.wait_for_timeout(300)


# ---- the control, and Assembled ----------------------------------------------------------


@pytest.mark.e2e
def test_the_view_opens_assembled_with_no_bed_and_no_section(printed_page: Page) -> None:
    """AC#1: *Assembled* is where the view starts, marked in the control; nothing is clipped,
    the section's own controls are not offered, and no bed is drawn."""
    page = printed_page
    assert _data(page, "mode") == "assembled"
    assert page.locator("#mode-assembled").get_attribute("aria-checked") == "true"
    assert _data(page, "section") == ""
    assert page.locator("#section-bar").is_hidden()
    assert _counted(page, CUT) == 0


# ---- On bed ------------------------------------------------------------------------------


@pytest.mark.e2e
def test_on_bed_lays_the_printed_part_on_the_printers_bed(
    printed_page: Page, screenshots: Path
) -> None:
    """AC#1 and AC#2: the bin is printed and fits the H2D - the printer every shipped example
    asks ``check_fits`` about - so it is laid on the one plate and nothing is marked."""
    page = printed_page
    _mode(page, "bed")
    try:
        assert page.locator("#mode-bed").get_attribute("aria-checked") == "true"
        assert (_data(page, "bed"), _data(page, "plates"), _data(page, "laid")) == ("H2D", "1", "1")
        assert _data(page, "unfit") == "0"
        assert _data(page, "section") == ""
        page.screenshot(path=str(screenshots / "89-on-bed-bin.png"))
    finally:
        _mode(page, "assembled")


@pytest.mark.e2e
def test_the_way_of_looking_survives_a_re_run(printed_page: Page) -> None:
    """The mode is the view's, like the section: a run redraws the scene and leaves it as set."""
    page = printed_page
    _mode(page, "bed")
    try:
        before = page.evaluate("() => performance.getEntriesByType('measure').length")
        page.click("#run")
        page.wait_for_function(
            "(before) => performance.getEntriesByType('measure').length > before",
            arg=before,
            timeout=BOOT_MS,
        )
        _settled(page)
        assert _data(page, "mode") == "bed"
        assert _data(page, "laid") == "1"
    finally:
        _mode(page, "assembled")


@pytest.mark.e2e
def test_on_bed_paints_the_places_the_overhang_findings_name(
    printed_page: Page, example: Callable[[Page, str], None], screenshots: Path
) -> None:
    """AC#3: the tote's overhang finding names six places; *On bed* paints the triangles of
    them, and *Assembled* paints none."""
    page = printed_page
    example(page, "systainer_tote.py")
    assert _data(page, "overhang") == "0"
    _mode(page, "bed")
    try:
        assert int(_data(page, "overhang")) > 0
        assert _data(page, "unfit") == "0"
        page.screenshot(path=str(screenshots / "89-on-bed-tote.png"))
    finally:
        _mode(page, "assembled")
    assert _data(page, "overhang") == "0"


@pytest.mark.e2e
def test_on_bed_says_so_when_nothing_is_printed(
    printed_page: Page, example: Callable[[Page, str], None]
) -> None:
    """A laser-only project has nothing to lay: the view says why rather than showing an empty
    bed, and says nothing of the kind once it is back to *Assembled*."""
    page = printed_page
    example(page, "gridfinity_cabinet.py")
    _mode(page, "bed")
    try:
        assert _data(page, "laid") == "0"
        assert "nothing here is printed" in page.locator(".canvas-note").inner_text()
    finally:
        _mode(page, "assembled")
    assert "nothing here is printed" not in page.locator(".canvas-note").inner_text()


# ---- Section -----------------------------------------------------------------------------


@pytest.mark.e2e
def test_section_cuts_a_context_body_as_well_as_the_part_and_fills_both(
    printed_page: Page, example: Callable[[Page, str], None], screenshots: Path
) -> None:
    """AC#4: through the middle of the pipe bracket along the pipe, the bracket's cut face is
    filled in a part's red and the pipe's - a body shown for context - in its own sand."""
    page = printed_page
    example(page, "pipe_bracket.py")
    page.wait_for_function(
        "() => document.querySelector('#canvas3d')?.dataset.context === '1'", timeout=BOOT_MS
    )
    _mode(page, "section")
    try:
        assert page.locator("#section-bar").is_visible()
        page.select_option("#section-axis", "y")
        low, high = _span(page)
        _cut_at(page, "y", (low + high) / 2)
        assert _data(page, "section").startswith("y:")
        assert _counted(page, CUT) > ENOUGH, "the bracket's cut face is not filled"
        assert _counted(page, CONTEXT_CUT) > ENOUGH, "the pipe's cut face is not filled"
        page.screenshot(path=str(screenshots / "89-section-pipe-bracket.png"))
    finally:
        _mode(page, "assembled")
    assert _counted(page, CUT) == 0


@pytest.mark.e2e
def test_section_cuts_a_dropped_reference_and_fills_its_cut_face(printed_page: Page) -> None:
    """AC#4: a plate dropped on the view as the reference is cut too - level through its
    thickness, its cut face filled in the reference's own colour. Last in the module, since a
    drop leaves the reference with the project."""
    from bench import Stock, fill, part, rect, stl
    from bench.plates import plate

    page = printed_page
    swept = plate(part("plate", fill(rect(120, 120)), Stock(3, "ply")))
    assert swept is not None
    page.evaluate(DROPPED, ["plate.stl", base64.b64encode(stl(swept.mesh)).decode()])
    page.wait_for_selector("#panel-report:not([hidden])", timeout=BOOT_MS)
    _settled(page)
    _mode(page, "section")
    try:
        before = _counted(page, REFERENCE_CUT)
        page.select_option("#section-axis", "z")
        _cut_at(page, "z", 1.5)
        # The slider steps in two-hundredths of the stage, so the plane lands near 1.5, not on
        # it - inside the plate's 3 mm either way.
        axis, _, at = _data(page, "section").partition(":")
        assert axis == "z" and 0.0 < float(at) < 3.0, at
        assert _counted(page, REFERENCE_CUT) > before + ENOUGH, "the reference's cut is not filled"
    finally:
        _mode(page, "assembled")
