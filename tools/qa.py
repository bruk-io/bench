"""Look at the app: ``uv run python -m tools.qa [example.py ...]``, or a host project's
scripts with ``uv run python -m tools.qa --project NAME [entry.py ...]``.

The ``e2e`` layer already drives the built app and asserts about it; this drives the same
app - :mod:`tools.preview`, the same build and the same server - and asserts nothing. It
walks the examples given (or :data:`STOPS` when none are), shoots each one, and writes down
everything the app said on the way: the browser's console, anything the page threw, any
request that failed, and what a person reads - what was built, what the script printed on
either stream, what was violated and what went wrong. Each stop is shot in every state the
inspector has (decision-12): the project with its knobs, the part the status bar's count
goes to, a face of that part, the project's export, and - when the project holds one - its
reference mesh. Then in the view's other two ways of looking (task-89): *On bed*, and
*Section* - through the middle of the work along X, or wherever ``--section AXIS:MM`` says,
``--section x:-165`` for a plane at x = -165 mm.

That last part is the whole reason this is not a test. A check knows in advance what it
wants to be true; a look round does not, which is why nothing here fails - it collects, and
the answer is the screenshots and :data:`LOG` for someone to read.

One thing worth knowing about the log: Chromium surfaces a worker's console on the page as
well, and ``web/src/worker.ts`` sends the script's stderr to ``console.warn`` inside the
worker, so ``page.on("console")`` is the whole story - a script's stderr arrives here with
nothing wrapped round the worker to fetch it.

The app keeps its projects on the host it is served from (decision-9), so every example a look
round opens is a project written to disk. It is served over a projects root of its own, made
for the walk and removed after it, so a look round never leaves anything in the repository's
own ``projects/`` or anyone's ``$BENCH_PROJECTS``.

**A host project (task-79).** ``--project NAME`` looks at a project instead of the examples:
the directory ``NAME`` names under the projects root - ``$BENCH_PROJECTS``, by
:mod:`tools.projects`, exactly as :mod:`tools.build` resolves it - is *copied* onto the walk's
own root and the app served over that, so the project is opened the way a maker opens it (its
own ``bench.toml``, its sibling modules, its meshes) and nothing the app does on the way can
touch the original. Each script named - the project's entry, by the app's own rule, when none
is - is opened as the app reopens a project, through the ``{project, script}`` the browser
remembers, and shot as an example is: the view with the project in the inspector, the part the
findings go to, the knobs, the export, a face and the reference mesh when there is one. The
browser's modeller builds every body, so a kernel check reports what it measured rather than
reading ``unchecked``.
"""

import json
import shutil
import sys
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from tools import preview
from tools.build import entry_in
from tools.projects import VARIABLE, project_dir, project_file

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
"""How long a selection takes to settle - the inspector redrawing, a 0.12 s transition on a
row - before a shot, which would otherwise catch it half-drawn."""

REPORT = """() => {
    const panel = document.querySelector('#run-panel');
    const inspector = document.querySelector('#inspector');
    if (panel === null || inspector === null) return [];
    const where = (one) => [...one.refs, ...(one.line === null ? [] : [`line ${one.line}`])];
    const found = inspector.violations.map(
        (one) => `${one.severity} ${one.check}: ${one.message} (${where(one).join(', ')})`
    );
    return [
        ['script stdout', panel.stdout],
        ['script stderr', panel.stderr],
        ['violations', found.join(' | ')],
        ['warnings', inspector.warnings.join(' | ')],
        ['error', inspector.error],
    ];
}"""
"""What a person reads off the app after a run, in the order they read it, as ``[name, text]``
pairs.

Read off the components' own properties rather than off the page: the Output panel starts
folded, the inspector draws only what its subject is about, and what either does draw is in a
shadow root; the properties are the whole of what they were given, either way."""

FACE = "bench-refs-tree .row[data-ref*='/']"
"""A face's row in the inspector's faces tree - any row whose ref is a path under a part."""


OPEN = "bench.open"
"""The key the app remembers which project and script it has open under - ``KEYS.open`` in
``web/src/storage.ts`` - which is how a look round opens one script of a project: the app
reopens where the browser left it."""

PROJECT = "--project"
"""The flag that names a host project to look at instead of the examples."""

OUTPUT = "--out"
"""The flag that names where the screenshots and the log land, in place of :data:`OUT`."""

SECTION = "--section"
"""The flag that says where *Section* cuts, as ``AXIS:MM`` - ``z:12.5``."""

_AXES = ("x", "y", "z")


class _Cut(NamedTuple):
    """Where a look round's *Section* shot cuts: an axis, and millimetres along it."""

    axis: str
    position: float


def _cut(said: str) -> _Cut:
    """``AXIS:MM`` read as a :class:`_Cut`.

    Raises:
        ValueError: naming what is wrong with it - no colon, an axis not x, y or z, or a
            position that is not a number.
    """
    axis, colon, position = said.partition(":")
    if not colon or axis.lower() not in _AXES:
        msg = f"{SECTION} is AXIS:MM with AXIS one of x, y, z - not {said!r}"
        raise ValueError(msg)
    try:
        return _Cut(axis.lower(), float(position))
    except ValueError:
        msg = f"{SECTION} {said!r}: {position!r} is not a number of millimetres"
        raise ValueError(msg) from None


class _Log(NamedTuple):
    """Where a look round writes, and everything it has written down so far."""

    out: Path
    spoken: list[str]


def _line(kind: str, text: str) -> str:
    return f"[{time.strftime('%H:%M:%S')}] {kind:<14} {text}"


def _reset(out: Path) -> None:
    """Clear what an earlier look round left, before this one writes anything of its own.

    A walk that raises - the browser hangs, a locator does not resolve - never reaches the
    line that (re)writes :data:`LOG`, so without this its predecessor's log stays behind. The
    screenshots this walk does take still land, one crash later they sit next to a log an
    unrelated, earlier walk wrote, which reads as one run and is not - the mismatch this
    module's own bug (`task-53`) turned out to be.
    """
    if not out.exists():
        return
    for one in out.iterdir():
        if one.is_file():
            one.unlink()


def _said(log: _Log, kind: str, text: str) -> None:
    """Write one thing down, and say it as it happens - a look round is watched, not
    awaited.

    Flushed to :data:`LOG` immediately rather than once at the end, so a walk that raises
    partway through still leaves a log of what happened before it did, not the last walk's."""
    line = _line(kind, " ".join(text.split())[:500])
    log.spoken.append(line)
    print(line, flush=True)
    (log.out / LOG).write_text("\n".join(log.spoken) + "\n")


def _watch(page: Page, log: _Log) -> None:
    """Listen to everything the page can say, including the worker's console."""
    page.on("console", lambda said: _said(log, f"console.{said.type}", said.text))
    page.on("pageerror", lambda thrown: _said(log, "pageerror", str(thrown)))
    page.on("requestfailed", lambda asked: _said(log, "netfail", f"{asked.url} {asked.failure}"))


def _settled(page: Page) -> None:
    """Wait until the app is not mid-run."""
    page.wait_for_function(
        "() => document.querySelector('#state')?.dataset.state !== 'running'", timeout=BOOT_MS
    )


def _read(page: Page, log: _Log) -> None:
    """Read the run back - its state, what it built, and what the report was given - skipping
    whatever has nothing in it."""
    state: str = page.evaluate("() => document.querySelector('#state')?.dataset.state ?? '?'")
    _said(log, "state", state)
    _said(log, "built", page.locator("#status").inner_text())
    # The spans since the last stop, off the page's User Timing timeline - the same entries a
    # collector would read - and cleared, so each stop reports its own.
    spans: list[list[str | float]] = page.evaluate(
        "() => { const found = performance.getEntriesByType('measure')"
        ".map((one) => [one.name, one.duration]); performance.clearMeasures(); return found; }"
    )
    for name, duration in spans:
        _said(log, "span", f"{name} {float(duration):.1f} ms")
    panels: list[list[str]] = page.evaluate(REPORT)
    for name, said in panels:
        if said.strip():
            _said(log, name, said)


def _stops(named: tuple[str, ...]) -> tuple[str, ...]:
    """What to visit: what was asked for, with ``.py`` supplied where it was left off."""
    return tuple(one if one.endswith(".py") else f"{one}.py" for one in named) or STOPS


def _visited(page: Page, stop: str, log: _Log, number: int, cut: _Cut | None) -> None:
    """Load one example, wait for it, shoot it and read it."""
    page.click("#examples-button")
    page.locator("#examples").get_by_role("button", name=stop, exact=True).click()
    _settled(page)
    page.wait_for_timeout(SETTLE_MS)
    _toured_inspector(page, stop, log, number)
    _toured_modes(page, stop, log, number, cut)


def _mode(page: Page, mode: str) -> None:
    """Pick one of the view's ways of looking, and wait for the view to say it is in it."""
    page.locator(f"bench-view-modes [data-mode='{mode}']").click()
    page.wait_for_function(
        "(want) => document.querySelector('#canvas3d')?.dataset.mode === want", arg=mode
    )


def _toured_modes(page: Page, stop: str, log: _Log, number: int, cut: _Cut | None) -> None:
    """Shoot the stop *On bed* and in *Section* - cut where ``cut`` says, or through the middle
    along X - and put the view back to *Assembled*, the way it opens."""
    _mode(page, "bed")
    page.wait_for_timeout(SETTLE_MS)
    view = page.locator("#canvas3d")
    laid = {
        key: view.get_attribute(f"data-{key}") or ""
        for key in ("bed", "plates", "laid", "unfit", "overhang")
    }
    _said(log, "on bed", ", ".join(f"{key} {value}" for key, value in laid.items()))
    _shot(page, stop, log, number, "-bed")
    _mode(page, "section")
    if cut is not None:
        page.select_option("#section-axis", cut.axis)
        # A range input clamps what it is given to its own span - the stage's, along the axis.
        page.eval_on_selector(
            "#section-position",
            "(el, value) => {"
            " el.value = value;"
            " el.dispatchEvent(new Event('input', { bubbles: true }));"
            "}",
            str(cut.position),
        )
    page.wait_for_timeout(SETTLE_MS)
    _said(log, "section", page.locator("#canvas3d").get_attribute("data-section") or "")
    _shot(page, stop, log, number, "-section")
    _mode(page, "assembled")


def _shot(
    page: Page, stop: str, log: _Log, number: int, suffix: str, *, whole: bool = True
) -> None:
    """Shoot the page - or, with ``whole`` false, the inspector alone - as ``suffix``."""
    page.wait_for_timeout(TAB_MS)
    shot = log.out / f"qa-{number:02d}-{stop.removesuffix('.py')}{suffix}.png"
    if whole:
        page.screenshot(path=str(shot))
    else:
        page.locator("#inspector-pane").screenshot(path=str(shot))
    _said(log, "screenshot", shot.name)


def _project(page: Page) -> None:
    """Nothing selected: the inspector back on the project."""
    page.locator("#crumb-project").click()


def _toured_inspector(page: Page, stop: str, log: _Log, number: int) -> None:
    """Shoot one stop in every state the inspector has, and read it.

    The project as it opens; the part the status bar's count goes to - or, with nothing found,
    the first part - with the place it was found lit when there is one; one face of that part;
    the knobs and the export, the project's own; and the reference mesh when the project holds
    one. The inspector is left on the project."""
    _project(page)
    _shot(page, stop, log, number, "")
    _read(page, log)
    findings = page.locator("#findings")
    if findings.is_visible():
        findings.click()
        place = page.locator("#part-findings .place").first
        if place.count() > 0:
            place.click()
    elif page.locator("#parts .part").count() > 0:
        page.locator("#parts .part").first.click()
    _shot(page, stop, log, number, "-problems")
    tree = page.locator("bench-refs-tree .row[aria-expanded='false'] .twist").first
    if tree.count() > 0:
        tree.click()
    face = page.locator(FACE).first
    if face.count() > 0:
        face.click()
        _shot(page, stop, log, number, "-face")
    _project(page)
    _shot(page, stop, log, number, "-parameters", whole=False)
    page.locator("#export").scroll_into_view_if_needed()
    _shot(page, stop, log, number, "-export", whole=False)
    reference = page.locator("bench-reference-list .row").first
    if reference.count() > 0:
        reference.click()
        _shot(page, stop, log, number, "-reference")
        _project(page)


def _walk(url: str, stops: tuple[str, ...], log: _Log, cut: _Cut | None) -> None:
    """Open the app once and visit every stop in it, the way a person would."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as play:
        browser = play.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        page = context.new_page()
        _watch(page, log)
        page.goto(url)
        page.wait_for_selector("#canvas3d[data-bodies]:not([data-bodies='0'])", timeout=BOOT_MS)
        _settled(page)
        _said(log, "boot", "the first scene is up")
        page.click("#examples-button")
        shot = log.out / "qa-00-examples.png"
        page.screenshot(path=str(shot))
        _said(log, "screenshot", shot.name)
        page.keyboard.press("Escape")
        for number, stop in enumerate(stops, start=1):
            _visited(page, stop, log, number, cut)
        context.close()
        browser.close()


RAN = """() => {
    const state = document.querySelector('#state')?.dataset.state;
    const status = document.querySelector('#status')?.textContent ?? '';
    return state === 'error' || (state === 'ok' && status !== 'ready');
}"""
"""Whether the script a page opened has run: it failed, or it came back with a tally. A
project's stop cannot wait for a body on the view the way the examples' first stop does - a
script that fails, or cuts only sheets, never draws one - and ``ok`` alone is not enough
either, since the app says ``ok ready`` once Python is up and before the first run is back."""


def _opened(page: Page, url: str, project: str, script: str) -> None:
    """Open ``script`` of ``project`` the way the app reopens where a browser left it - the
    ``{project, script}`` it remembers under :data:`OPEN` - and wait for its run.

    Said before the page's own scripts run, on every load, rather than written into an open
    page and reloaded: the app would already be booting Python for whatever it opened first.
    Scripts added this way run in the order they were added, so the latest stop is the one
    the app reads."""
    remembered = json.dumps({"project": project, "script": script})
    page.add_init_script(f"localStorage.setItem({json.dumps(OPEN)}, {json.dumps(remembered)});")
    page.goto(url)
    page.wait_for_function(RAN, timeout=BOOT_MS)


def _looked(
    page: Page, url: str, project: str, stop: str, log: _Log, number: int, cut: _Cut | None
) -> None:
    """Open one script of a project, wait for it, and shoot and read it as :func:`_visited`
    does an example."""
    _opened(page, url, project, stop)
    page.wait_for_timeout(SETTLE_MS)
    _toured_inspector(page, stop, log, number)
    _toured_modes(page, stop, log, number, cut)


def _toured(url: str, project: str, stops: tuple[str, ...], log: _Log, cut: _Cut | None) -> None:
    """Open the app once and visit every named script of ``project`` in it."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as play:
        browser = play.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        page = context.new_page()
        _watch(page, log)
        for number, stop in enumerate(stops, start=1):
            _looked(page, url, project, stop, log, number, cut)
        context.close()
        browser.close()


def _copied(source: Path, root: Path) -> None:
    """``source`` copied under ``root`` by its own name - the whole directory, meshes and
    all, less what Python caches and the app's own trash, which a maker never opens."""
    shutil.copytree(
        source, root / source.name, ignore=shutil.ignore_patterns("__pycache__", ".trash")
    )


def _project_stops(
    project: str, named: tuple[str, ...], environ: Mapping[str, str] | None
) -> tuple[Path, tuple[str, ...]]:
    """The project's directory and the scripts of it to visit: those named, with ``.py``
    supplied where it was left off, or its entry by :func:`tools.build.entry_in` - the app's
    own rule - when none are.

    Raises:
        ValueError: the project is not there, or a script named is not one of its files - as
            well as :func:`tools.projects.project_file`'s own, for a name that is not plain.
    """
    directory = project_dir(project, environ)
    if not directory.is_dir():
        msg = f"there is no project at {directory}"
        raise ValueError(msg)
    scripts = tuple(one if one.endswith(".py") else f"{one}.py" for one in named)
    for one in scripts:
        if not project_file(project, one, environ).is_file():
            msg = f"{project} has no {one}"
            raise ValueError(msg)
    return directory, scripts or (entry_in(directory).name,)


def _taken(args: tuple[str, ...], flag: str) -> tuple[str | None, tuple[str, ...]] | None:
    """``flag``'s value among ``args`` and the rest of them without the two - ``None`` for the
    value when ``flag`` is not there - or ``None`` altogether when it is there with nothing
    after it."""
    if flag not in args:
        return None, args
    at = args.index(flag)
    if at + 1 >= len(args):
        return None
    return args[at + 1], args[:at] + args[at + 2 :]


def main(argv: tuple[str, ...] | None = None, environ: Mapping[str, str] | None = None) -> int:
    """Build the app if it is stale, serve it, walk it, and write down what it said.

    ``--project NAME`` walks that host project's scripts instead of the examples, off a copy
    of it (:func:`_copied`); ``environ`` is where its projects root is read from, as
    :mod:`tools.build` reads it - :data:`os.environ` when it is not given. ``--out DIR`` puts
    the screenshots and the log in ``DIR`` rather than :data:`OUT`, which a check that drives
    this uses so it never clears a person's own look round. ``--section AXIS:MM`` is where
    every stop's *Section* shot cuts.

    Returns:
        ``0`` - a look round has no verdict to give - unless a flag is left without its value,
        ``--section`` is not ``AXIS:MM``, or ``--project`` names a project or script that is
        not there, which is said and answered ``1`` before anything is built.
    """
    args = tuple(sys.argv[1:] if argv is None else argv)
    for flag in (PROJECT, OUTPUT, SECTION):
        if _taken(args, flag) is None:
            print(f"{flag} names nothing", file=sys.stderr)
            return 1
    project, args = _taken(args, PROJECT) or (None, args)
    written, args = _taken(args, OUTPUT) or (None, args)
    section, args = _taken(args, SECTION) or (None, args)
    try:
        cut = None if section is None else _cut(section)
    except ValueError as exc:
        print(f"failed: {exc}", file=sys.stderr)
        return 1
    out = OUT if written is None else Path(written)
    if project is not None:
        try:
            source, stops = _project_stops(project, args, environ)
        except ValueError as exc:
            print(f"failed: {exc}", file=sys.stderr)
            return 1
    else:
        stops = _stops(args)
    out.mkdir(parents=True, exist_ok=True)
    _reset(out)
    log = _Log(out, [])
    _said(log, "build", "building the app if anything it is made from has changed")
    preview.built()
    with tempfile.TemporaryDirectory(prefix="bench-qa-") as root:
        if project is not None:
            _copied(source, Path(root))
            _said(log, "project", f"{source} copied to {root}")
        with preview.served(env={VARIABLE: root}) as url:
            _said(log, "server", f"vite preview at {url}")
            if project is None:
                _walk(url, stops, log, cut)
            else:
                _toured(url, project, stops, log, cut)
    shots = sum(1 for line in log.spoken if " screenshot " in line)
    print(f"\n{shots} screenshots and {out / LOG} - have a look", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
