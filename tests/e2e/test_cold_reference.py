"""End to end: task-96 - a project with a large reference runs on a cold page, and the watchdog
times the script alone.

projects/tower's ``coupon.py`` was stopped at 15 s on its first run after a page load and took
8.2 s when run again. What the clock was counting was not warm-up - a cold run and a warm one
measure the same - but whatever the worker was doing when Run was pressed: the survey of the
project's reference, which takes minutes on a quarter of a million triangles and which the run
had to wait behind with its watchdog already running. The run now takes the worker from a
survey, and its watchdog starts when the script does (AC#2, AC#3, AC#5). The same clock used to
count the rest of a run still working when Run was pressed again; and the guarantee it is there
for still holds - a ``while True`` somebody has already typed over dies at the limit from its
own start, and the script after it runs on the fresh worker instead of being blamed (AC#2).

The second half is the other symptom (AC#4): after a runaway, a page opened on the same script -
a reading tab or the writer's own reload - held the script back as it should, but left the
project's reference off the view too, so the first Run there said "no reference". Not a task-88
regression: the early return that skipped it is older than the inspector.

The reference is made here, at test time - a field of round pins, the shape a survey spends
longest on, as many triangles as tower's fixture - rather than committed: it is ten megabytes of
nothing but numbers, and tower's own is Festool's and not ours to ship.
"""

import math
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tools import preview
from tools.projects import VARIABLE

pytestmark = pytest.mark.e2e

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page

try:
    import playwright.sync_api  # ruff: ignore[unused-import]  # the import is the check
except ImportError:
    pytest.skip("playwright is not installed - uv pip install playwright", allow_module_level=True)

if not (preview.WEB / "node_modules").is_dir():
    pytest.skip("web/node_modules missing - run npm ci in web/", allow_module_level=True)
if shutil.which("npx") is None:
    pytest.skip("npx not on PATH", allow_module_level=True)

BOOT_MS = 240_000

RUN_MS = 60_000
"""How long a run of the script may take to come back, boot and all - four times the watchdog,
so a run stopped by it is seen stopped rather than timed out on."""

OUT = preview.WEB / "e2e" / "out"

PROJECT = "heavy"

MESH = "pins.stl"

ACROSS = 36
"""Pins along each side of the field."""

SEGMENTS = 40
"""Sides to each pin: ``ACROSS``² pins of ``4 * SEGMENTS`` triangles is 207 360 of them - tower's
fixture is 208 828."""

SCRIPT = (
    "from bench import *\n"
    "\n"
    "if reference is None:\n"
    '    raise ValueError("no reference: bench.toml\'s [reference] should name pins.stl")\n'
    "print(f'{len(reference.triangles) // 3} triangles')\n"
    "show(part('plate', fill(rect(60, 40)), Stock(3, 'ply')))\n"
)

TABLE = f'[project]\nentry = "fit.py"\n\n[values]\n\n[reference]\nfile = "{MESH}"\n'

SAID = f"{ACROSS * ACROSS * 4 * SEGMENTS} triangles"
"""What the script prints when it was handed the whole reference."""

HANG = "bench.lastHang"
"""``KEYS.hang`` in ``web/src/storage.ts``: the hash of a script that ran away, which a page
opened on the same script does not run again by itself."""

OPEN = "bench.open"
"""``KEYS.open``: which project and script the browser has open."""

BUSY = (
    "import time\n"
    "\n"
    "from bench import *\n"
    "\n"
    "begun = time.monotonic()\n"
    "while time.monotonic() - begun < 10:\n"
    "    pass\n"
    "print('worked')\n"
    "show(part('plate', fill(rect(60, 40)), Stock(3, 'ply')))\n"
)
"""Ten seconds of work and then a plate: two of it back to back take longer than the watchdog,
one alone does not."""

QUICK = "from bench import *\n\nshow(part('plate', fill(rect(30, 20)), Stock(3, 'ply')))\n"

RUNAWAY = "while True:\n    pass\n"


def _pins() -> bytes:
    """A field of round pins as a binary STL: ``ACROSS`` x ``ACROSS`` of them, each a closed
    cylinder of ``SEGMENTS`` sides, radii a little different so no two are alike."""
    from bench import stl
    from bench.kernel import Mesh

    points: list[float] = []
    corners: list[int] = []
    for i in range(ACROSS):
        for j in range(ACROSS):
            x0, y0, r, h = 10.0 * i, 10.0 * j, 3.0 + 0.01 * ((7 * i + j) % 13), 8.0
            ring = len(points) // 3
            for k in range(SEGMENTS):
                a = 2 * math.pi * k / SEGMENTS
                x, y = x0 + r * math.cos(a), y0 + r * math.sin(a)
                points += [x, y, 0.0, x, y, h]
            bottom, top = len(points) // 3, len(points) // 3 + 1
            points += [x0, y0, 0.0, x0, y0, h]
            for k in range(SEGMENTS):
                a0, b0 = ring + 2 * k, ring + 2 * ((k + 1) % SEGMENTS)
                corners += [a0, b0, b0 + 1, a0, b0 + 1, a0 + 1, bottom, b0, a0, top, a0 + 1, b0 + 1]
    return stl(Mesh(tuple(points), tuple(corners), (None,) * (len(corners) // 3)))


@pytest.fixture(scope="module")
def hosted(tmp_path_factory: pytest.TempPathFactory, built_app: Path) -> Iterator[str]:
    """The app over a root holding one project, ``heavy``: its script, and the large reference
    its ``bench.toml`` names."""
    root = tmp_path_factory.mktemp("projects")
    project = root / PROJECT
    project.mkdir()
    (project / "fit.py").write_text(SCRIPT)
    (project / "bench.toml").write_text(TABLE)
    (project / MESH).write_bytes(_pins())
    for name, entry, text in (("busy", "work.py", BUSY), ("loop", "quick.py", QUICK)):
        (root / name).mkdir()
        (root / name / entry).write_text(text)
        (root / name / "bench.toml").write_text(f'[project]\nentry = "{entry}"\n')
    with preview.served(env={VARIABLE: str(root)}) as url:
        yield url


def _context(browser: Browser, project: str = PROJECT, script: str = "fit.py") -> BrowserContext:
    """A browser of its own - its own storage, so nothing one check remembered reaches the
    next - that opens ``project`` at ``script`` the way the app reopens where it was left."""
    context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    context.add_init_script(
        f"localStorage.setItem('{OPEN}',"
        f" JSON.stringify({{project: '{project}', script: '{script}'}}));"
    )
    return context


def _state(page: Page) -> str:
    return str(page.evaluate("() => document.querySelector('#state')?.dataset.state"))


def _said(page: Page) -> str:
    """What the last run printed, and what went wrong with it, if anything did."""
    return str(
        page.evaluate(
            "() => `${document.querySelector('#run-panel')?.stdout ?? ''}"
            "${document.querySelector('#inspector')?.error ?? ''}`"
        )
    )


def _ran(page: Page) -> None:
    """Wait for a run to come back, whichever way it ends - a watchdog's stop, which times
    nothing, included."""
    page.wait_for_function(
        """() => {
            const state = document.querySelector('#state')?.dataset.state;
            const timed = (document.querySelector('#timing')?.textContent ?? '') !== '';
            const error = document.querySelector('#inspector')?.error ?? '';
            const stopped = error.includes('did not finish in');
            return !['running', 'boot'].includes(state) && (timed || stopped);
        }""",
        timeout=RUN_MS,
    )


def _run(page: Page) -> None:
    """Press Run and wait for what it answers."""
    page.evaluate("() => { document.querySelector('#timing').textContent = ''; }")
    page.click("#run")
    _ran(page)


def _fnv(text: str) -> str:
    """``hashOf`` in ``web/src/storage.ts``: FNV-1a over the text's UTF-16 code units."""
    found = 0x811C9DC5
    for unit in memoryview(text.encode("utf-16-le")).cast("H"):
        found = ((found ^ unit) * 0x01000193) & 0xFFFFFFFF
    return f"{found:08x}"


def _held_back(page: Page) -> None:
    page.locator("#error", has_text="did not finish").wait_for(timeout=BOOT_MS)


def _active_is(page: Page, name: str) -> None:
    page.wait_for_function(
        "(name) => document.querySelector('#inspector')?.activeReference === name",
        arg=name,
        timeout=RUN_MS,
    )


# ---- AC#3, AC#5: a cold first run, and a run pressed while the reference is surveyed -------


def test_a_cold_run_with_a_large_reference_completes_and_so_does_one_pressed_during_its_survey(
    hosted: str, browser: Browser
) -> None:
    context = _context(browser)
    page = context.new_page()
    said: list[str] = []
    page.on("console", lambda message: said.append(message.text))
    page.goto(hosted)

    # The page's own first run, on a cold worker, with the reference read, sent and placed.
    page.wait_for_function(
        "() => (document.querySelector('#run-panel')?.stdout ?? '').includes('triangles')",
        timeout=BOOT_MS,
    )
    _ran(page)
    assert _state(page) == "ok", _said(page)
    assert SAID in _said(page)

    # The survey of the reference starts behind it, and runs for minutes: Run now used to wait
    # behind it on a clock that was already counting, and be stopped at 15 s.
    survey_done = "() => performance.getEntriesByName('bench.worker.survey').length > 0"
    assert not page.evaluate(survey_done), "the survey finished too soon to be in the way"
    _run(page)
    assert _state(page) == "ok", _said(page)
    assert "did not finish" not in _said(page)
    assert SAID in _said(page)
    assert any("a run took the worker from a survey" in one for one in said), said
    page.screenshot(path=str(OUT / "cold-reference-run-during-survey.png"))
    context.close()


# ---- AC#4: a page that holds a script back after a runaway still has its reference ----------


def test_after_a_runaway_a_reading_tab_and_the_writers_reload_both_hold_the_named_reference(
    hosted: str, browser: Browser
) -> None:
    context = _context(browser)
    writer = context.new_page()
    writer.goto(hosted)
    writer.wait_for_function(
        "() => (document.querySelector('#run-panel')?.stdout ?? '').includes('triangles')",
        timeout=BOOT_MS,
    )
    _ran(writer)
    # What the watchdog leaves behind when this script runs away: remembered for the browser,
    # so every tab of it opens the script held back rather than running it again.
    writer.evaluate(f"() => localStorage.setItem('{HANG}', '{_fnv(SCRIPT)}')")

    reader = context.new_page()
    reader.goto(hosted)
    _held_back(reader)
    assert reader.evaluate("() => document.querySelector('#inspector')?.reading") is True
    _active_is(reader, MESH)
    _run(reader)
    assert _state(reader) == "ok", _said(reader)
    assert SAID in _said(reader)
    reader.screenshot(path=str(OUT / "cold-reference-reader-after-runaway.png"))
    reader.close()

    writer.evaluate(f"() => localStorage.setItem('{HANG}', '{_fnv(SCRIPT)}')")
    writer.reload()
    _held_back(writer)
    _active_is(writer, MESH)
    _run(writer)
    assert _state(writer) == "ok", _said(writer)
    assert SAID in _said(writer)
    context.close()


# ---- AC#2: the clock is the script's own, and a runaway still dies at the limit -------------

_BOOTED = "() => performance.getEntriesByName('bench.boot.bench').length > 0"
"""Python is up - and so the page's own first run, asked for before it was, has begun."""


def _replaced(page: Page, text: str) -> None:
    """Put ``text`` in the editor in place of the script, as one change."""
    page.click("#tab-script")
    page.locator(".cm-content").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.insert_text(text)


def test_a_run_pressed_while_another_is_working_is_timed_from_its_own_start(
    hosted: str, browser: Browser
) -> None:
    """Ten seconds of script, pressed again a second into it: the second run waits out the
    first and then takes ten seconds of its own. Twenty from the press, but fifteen of them
    the second run's clock used to count."""
    context = _context(browser, "busy", "work.py")
    page = context.new_page()
    page.goto(hosted)
    page.wait_for_function(_BOOTED, timeout=BOOT_MS)
    page.wait_for_timeout(1_000)

    _run(page)

    assert _state(page) == "ok", _said(page)
    assert "worked" in _said(page)
    context.close()


def test_a_runaway_that_was_superseded_still_dies_and_the_script_after_it_runs(
    hosted: str, browser: Browser
) -> None:
    """``while True`` started, then replaced by a script that finishes: the loop is the
    runaway and is stopped at the limit from its own start, and the script after it - the one
    somebody is waiting on - is handed to the fresh worker and runs, and is not remembered as
    the runaway."""
    context = _context(browser, "loop", "quick.py")
    page = context.new_page()
    said: list[str] = []
    page.on("console", lambda message: said.append(message.text))
    page.goto(hosted)
    _ran(page)
    assert _state(page) == "ok", _said(page)

    _replaced(page, RUNAWAY)
    page.wait_for_selector("#stop:not([disabled])", timeout=RUN_MS)
    page.wait_for_timeout(2_000)
    page.evaluate("() => { document.querySelector('#timing').textContent = ''; }")
    _replaced(page, QUICK + "# after the loop\n")
    _ran(page)

    assert _state(page) == "ok", _said(page)
    assert "did not finish" not in _said(page)
    assert any("a superseded run passed the watchdog" in one for one in said), said
    assert page.evaluate(f"() => localStorage.getItem('{HANG}')") is None
    context.close()
