"""Look at the app: ``uv run python -m tools.qa [example.py ...]``.

The ``e2e`` layer already drives the built app and asserts about it; this drives the same
app - :mod:`tools.preview`, the same build and the same server - and asserts nothing. It
walks the examples given (or :data:`STOPS` when none are), shoots each one, and writes down
everything the app said on the way: the browser's console, anything the page threw, any
request that failed, and what a person reads - what was built, what the script printed on
either stream, what was violated and what went wrong. Where a run made files, the Export
menu is shot open as well.

That last part is the whole reason this is not a test. A check knows in advance what it
wants to be true; a look round does not, which is why nothing here fails - it collects, and
the answer is the screenshots and :data:`LOG` for someone to read.

One thing worth knowing about the log: Chromium surfaces a worker's console on the page as
well, and ``web/src/worker.ts`` sends the script's stderr to ``console.warn`` inside the
worker, so ``page.on("console")`` is the whole story - a script's stderr arrives here with
nothing wrapped round the worker to fetch it.
"""

import sys
import time
from typing import TYPE_CHECKING

from tools import preview

if TYPE_CHECKING:
    from playwright.sync_api import Page

OUT = preview.WEB / "qa" / "out"
"""Where the screenshots and the log land - gitignored, like the e2e layer's own."""

LOG = "qa-log.txt"
"""The one file everything said ends up in, under :data:`OUT`."""

STOPS = ("gridfinity_cabinet.py", "gridfinity_bin.py", "hinge.py")
"""What a look round visits when the caller names nothing: the biggest laser script, a
printed part the browser's own modeller has to build, and an assembly of three bodies."""

BOOT_MS = 240_000
"""How long the app may take to boot Python and draw the first scene, in milliseconds."""

SETTLE_MS = 1500
"""How long to let the 3D pane finish drawing before a screenshot - the scene is up before
the first frame is, and a shot taken between the two is of an empty pane."""

TAB_MS = 250
"""How long a tab's underline and colour take to move - a 0.12 s transition - before a shot,
which would otherwise catch both tabs half-selected."""

HOME = "refs"
"""The sidebar container a look round leaves open: the refs tree, which is the one surface
that is about the thing on screen rather than about the file."""

REPORT = """() => {
    const report = document.querySelector('#run-panel');
    if (report === null) return [];
    const where = (one) => [...one.refs, ...(one.line === null ? [] : [`line ${one.line}`])];
    const found = report.violations.map(
        (one) => `${one.severity} ${one.check}: ${one.message} (${where(one).join(', ')})`
    );
    return [
        ['script stdout', report.stdout],
        ['script stderr', report.stderr],
        ['violations', found.join(' | ')],
        ['warnings', report.warnings.join(' | ')],
        ['error', report.error],
    ];
}"""
"""What a person reads off the report after a run, in the order they read it, as ``[name,
text]`` pairs.

Read off ``<bench-panel>``'s own properties rather than off the page. The panel draws one tab
at a time - a clean run's stdout is behind the Output tab, not drawn at all - and what it does
draw is in a shadow root; the properties are the whole of what it was given, either way."""


def _line(kind: str, text: str) -> str:
    return f"[{time.strftime('%H:%M:%S')}] {kind:<14} {text}"


def _said(spoken: list[str], kind: str, text: str) -> None:
    """Write one thing down, and say it as it happens - a look round is watched, not
    awaited."""
    line = _line(kind, " ".join(text.split())[:500])
    spoken.append(line)
    print(line, flush=True)


def _watch(page: Page, spoken: list[str]) -> None:
    """Listen to everything the page can say, including the worker's console."""
    page.on("console", lambda said: _said(spoken, f"console.{said.type}", said.text))
    page.on("pageerror", lambda thrown: _said(spoken, "pageerror", str(thrown)))
    page.on("requestfailed", lambda asked: _said(spoken, "netfail", f"{asked.url} {asked.failure}"))


def _settled(page: Page) -> None:
    """Wait until the app is not mid-run."""
    page.wait_for_function(
        "() => document.querySelector('#state')?.dataset.state !== 'running'", timeout=BOOT_MS
    )


def _read(page: Page, spoken: list[str]) -> None:
    """Read the run back - its state, what it built, and what the report was given - skipping
    whatever has nothing in it."""
    state: str = page.evaluate("() => document.querySelector('#state')?.dataset.state ?? '?'")
    _said(spoken, "state", state)
    _said(spoken, "built", page.locator("#status").inner_text())
    # The spans since the last stop, off the page's User Timing timeline - the same entries a
    # collector would read - and cleared, so each stop reports its own.
    spans: list[list[str | float]] = page.evaluate(
        "() => { const found = performance.getEntriesByType('measure')"
        ".map((one) => [one.name, one.duration]); performance.clearMeasures(); return found; }"
    )
    for name, duration in spans:
        _said(spoken, "span", f"{name} {float(duration):.1f} ms")
    panels: list[list[str]] = page.evaluate(REPORT)
    for name, said in panels:
        if said.strip():
            _said(spoken, name, said)


def _stops(named: tuple[str, ...]) -> tuple[str, ...]:
    """What to visit: what was asked for, with ``.py`` supplied where it was left off."""
    return tuple(one if one.endswith(".py") else f"{one}.py" for one in named) or STOPS


def _visited(page: Page, stop: str, spoken: list[str], number: int) -> None:
    """Load one example, wait for it, shoot it and read it."""
    page.click("#examples-button")
    page.locator("#examples").get_by_role("button", name=stop, exact=True).click()
    _settled(page)
    page.wait_for_timeout(SETTLE_MS)
    shot = OUT / f"qa-{number:02d}-{stop.removesuffix('.py')}.png"
    page.screenshot(path=str(shot))
    _said(spoken, "screenshot", shot.name)
    _read(page, spoken)
    _parameters(page, stop, spoken, number)
    _exported(page, stop, spoken, number)


def _parameters(page: Page, stop: str, spoken: list[str], number: int) -> None:
    """Shoot the parameters container - the panel generated from what the script declares -
    and put the refs back in the sidebar."""
    page.click("#rail-parameters")
    page.wait_for_timeout(TAB_MS)
    shot = OUT / f"qa-{number:02d}-{stop.removesuffix('.py')}-parameters.png"
    page.screenshot(path=str(shot))
    _said(spoken, "screenshot", shot.name)
    page.click(f"#rail-{HOME}")


def _exported(page: Page, stop: str, spoken: list[str], number: int) -> None:
    """Shoot the panel's Files tab - what a run made, as a person picks from it - and leave
    Problems in front again."""
    page.click("#panel-tab-files")
    page.wait_for_timeout(TAB_MS)
    shot = OUT / f"qa-{number:02d}-{stop.removesuffix('.py')}-export.png"
    page.screenshot(path=str(shot))
    _said(spoken, "screenshot", shot.name)
    page.click("#panel-tab-problems")


def _walk(url: str, stops: tuple[str, ...], spoken: list[str]) -> None:
    """Open the app once and visit every stop in it, the way a person would."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as play:
        browser = play.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        page = context.new_page()
        _watch(page, spoken)
        page.goto(url)
        page.wait_for_selector("#canvas3d[data-bodies]:not([data-bodies='0'])", timeout=BOOT_MS)
        _settled(page)
        _said(spoken, "boot", "the first scene is up")
        page.click("#examples-button")
        shot = OUT / "qa-00-examples.png"
        page.screenshot(path=str(shot))
        _said(spoken, "screenshot", shot.name)
        page.keyboard.press("Escape")
        for number, stop in enumerate(stops, start=1):
            _visited(page, stop, spoken, number)
        context.close()
        browser.close()


def main(argv: tuple[str, ...] | None = None) -> int:
    """Build the app if it is stale, serve it, walk it, and write down what it said.

    Returns:
        ``0``, always - a look round has no verdict to give.
    """
    stops = _stops(tuple(sys.argv[1:] if argv is None else argv))
    OUT.mkdir(parents=True, exist_ok=True)
    spoken: list[str] = []
    _said(spoken, "build", "building the app if anything it is made from has changed")
    preview.built()
    with preview.served() as url:
        _said(spoken, "server", f"vite preview at {url}")
        _walk(url, stops, spoken)
    written = OUT / LOG
    written.write_text("\n".join(spoken) + "\n")
    shots = sum(1 for line in spoken if " screenshot " in line)
    print(f"\n{shots} screenshots and {written} - have a look", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
