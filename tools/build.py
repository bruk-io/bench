"""Run a script or a project directory and keep what it made:
``uv run python -m tools.build <script.py | project-dir> [--out DIR]``.

Decision-9's own shape: a project is a directory with one ``bench.toml`` - ``[project] entry``
says which script runs, ``[values]`` and ``[reference]`` are what it builds with and what it is
placed against. Handed a directory, this runs its entry; handed a bare script, it runs that
script and reads ``bench.toml`` beside it, or the older ``<script>.toml`` (decision-3) where
there is no ``bench.toml`` - one rule for both, so the app's file and this tool's never
disagree. Either way the directory the script came from goes on the import path, so an entry
that says ``import parts`` reaches a ``parts.py`` beside it - the same directory
``web/src/worker.py`` mounts for the browser. An import naming a file the project does not
have fails in the project's own terms (task-56): :func:`_modules_of` hands the project's other
files to :func:`bench.script.run`, the same list :mod:`bench.missing` reads.

``--project NAME`` resolves that directory under the host's projects root - ``$BENCH_PROJECTS``,
by :mod:`tools.projects`, exactly as the app's route resolves it - and runs its entry;
``--project NAME script.py`` runs that one script of the project instead, the way opening a
tab that is not the entry runs that tab (decision-9: "the script you have open runs"). So
``tools.build --project cabinet`` runs what a fresh open of the app would, and
``tools.build --project cabinet parts.py`` runs the file the app is showing when ``parts.py``
is the open tab.

The repository had no way to run a script without a browser. Every other host of
:func:`bench.script.run` is either the app - :mod:`bench.worker`, inside Pyodide - or a test.
So a maker with a script and a cutting machine had to open a browser to get an SVG out of it,
and a values file had nowhere to be read.

This is that host, and it is deliberately the smallest one that is useful: a path in, a scene
out, and the files written down if you ask for them. It asserts nothing and has no verdict of
its own beyond whether the run came back ``ok`` - checking is :mod:`tools.check`'s job.

**Where the values come from.** A script declares its settings as a dataclass and the
dataclass holds the defaults. A TOML beside the script - ``bench.toml`` when there is a
project directory, ``cabinet.py`` and ``cabinet.toml`` when there is not - says which one of
that thing you are building:

.. code-block:: toml

    [values]
    units_x = 4
    drawers = 6

Those become :func:`bench.script.run`'s ``overrides``, which is the argument it already takes
and the same mapping the app's panel sends. Nothing under ``src/bench`` knows this file
exists: reading it is I/O, and I/O lives at the edges. A script with no file beside it runs
on its own defaults, which is what every example does today.

No solid modeller is loaded here, so a printed part comes back with every ref, parameter and
violation it has and no triangles. Cut sheets need no kernel, which is the whole point of
being able to do this from a command line.
"""

import importlib
import sys
import tomllib
from base64 import b64decode
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tools.projects import project_dir, project_file

if TYPE_CHECKING:
    from bench.geometry import Plane
    from bench.kernel import Mesh
    from bench.scene import OkScene, Scene

# `bench` is imported inside the functions that use it, not here.
#
# `tools/check.py` runs the suite twice and drops `bench` and every `bench.*` module from
# `sys.modules` in between, so the second run imports the package from source rather than
# handing back the first run's objects. A module that bound those names at import time keeps
# the *old* classes, and `show`'s `match thing: case Part()` then compares a fresh `Part`
# against a stale one and refuses it - "cannot show 'Part'" - for a reason that has nothing
# to do with the script. Test modules are dropped for exactly this reason; `tools` is not,
# so it has to import late. `tests/functional/test_examples.py` does the same thing.

VALUES = "values"
"""The table a project's TOML keeps its parameter values in.

Named rather than taken as the whole file, so measurements and whatever else a project grows
have somewhere to go that is not confused with what the script consumes.
"""

REFERENCE = "reference"
"""The table a project's TOML keeps a dropped mesh's placement in.

See :mod:`bench.placement`: ``file`` names the STL beside the script, and ``origin``, ``up``
and ``along`` say where its datum is. A project with none of this runs unplaced, in the
mesh's own coordinates - decision-4's rule, "no table, no move".
"""

PROJECT = "project"
"""The table a project directory's TOML says things about itself in that no script can -
decision-9's ``[project]``, today only ``entry``."""

BENCH = "bench.toml"
"""The one values document a project directory holds, whatever its scripts are called -
:data:`web.src.values.BENCH` on the other side of the wire."""


def _document_path(script: Path) -> Path:
    """The TOML document ``script`` builds with: ``bench.toml`` beside it when there is one -
    decision-9's document, shared by every script of the directory - else ``<script>.toml``,
    decision-3's older, one-script shape. Named for what it is rather than read, so a caller
    printing which file it used and one reading it agree without reading twice for nothing."""
    beside = script.parent / BENCH
    return beside if beside.is_file() else script.with_suffix(".toml")


def _toml_beside(script: Path) -> dict[str, object]:
    """The whole of ``script``'s document (:func:`_document_path`), or nothing at all if
    there is none.

    Raises:
        ValueError: if the file is not readable as TOML, naming it and what was wrong, so a
            typed comma is reported rather than silently losing every table in the file.
    """
    beside = _document_path(script)
    if not beside.is_file():
        return {}
    try:
        return tomllib.loads(beside.read_text())
    except tomllib.TOMLDecodeError as exc:
        msg = f"{beside} is not readable as TOML: {exc}"
        raise ValueError(msg) from exc


def values_beside(script: Path) -> dict[str, object]:
    """What ``script``'s TOML (:func:`_document_path`) says to build, or nothing at all.

    A missing document is not a mistake - it means the script's own defaults - and neither is
    one with no ``[values]`` in it. An unknown table - ``[project]``, or anything a later
    version wrote - is passed over unread rather than refused.

    Raises:
        ValueError: if the file is not readable as TOML, or its ``[values]`` is not a table.
    """
    whole = _toml_beside(script)
    table = whole.get(VALUES, {})
    if not isinstance(table, dict):
        msg = f"{_document_path(script)} has a [{VALUES}] that is not a table"
        raise ValueError(msg)
    return dict(table)


def reference_beside(script: Path) -> dict[str, object] | None:
    """The ``[reference]`` table in ``script``'s TOML (:func:`_document_path`), or ``None`` if
    there is none.

    A missing table is not a mistake - decision-4's criterion #3, a project with no placement
    behaves exactly as today, in its own coordinates. This only reads the table; it does not
    read the STL ``file`` names or place anything.

    Raises:
        ValueError: if the file is not readable as TOML, or its ``[reference]`` is not a table.
    """
    whole = _toml_beside(script)
    table = whole.get(REFERENCE)
    if table is None:
        return None
    if not isinstance(table, dict):
        msg = f"{_document_path(script)} has a [{REFERENCE}] that is not a table"
        raise ValueError(msg)
    return dict(table)


def _entry_in(directory: Path) -> Path:
    """The script ``directory`` runs by default - decision-9's ``entry`` - mirroring
    ``web/src/project-files.ts``'s own rule (``entryOf``) exactly, so the app and this command
    line can never pick different files for the same directory: the document's declared
    ``entry`` when it names one of the directory's own scripts, else the script named for the
    directory, else the first by name. A directory with no script at all comes back naming the
    one it would have picked had there been one, so the caller's ordinary "no script at ..."
    refusal is what is said, not a different message for a project with nothing in it.

    Raises:
        ValueError: ``bench.toml`` is there and not readable as TOML.
    """
    scripts = sorted(one.name for one in directory.glob("*.py")) if directory.is_dir() else []
    bench_toml = directory / BENCH
    declared: str | None = None
    if bench_toml.is_file():
        try:
            whole = tomllib.loads(bench_toml.read_text())
        except tomllib.TOMLDecodeError as exc:
            msg = f"{bench_toml} is not readable as TOML: {exc}"
            raise ValueError(msg) from exc
        project = whole.get(PROJECT)
        said = project.get("entry") if isinstance(project, dict) else None
        declared = said if isinstance(said, str) else None
    default = f"{directory.name}.py"
    if declared is not None and declared in scripts:
        entry = declared
    elif default in scripts:
        entry = default
    else:
        entry = scripts[0] if scripts else default
    return directory / entry


def _refused(directory: Path) -> str | None:
    """Why ``directory`` must not go on the import path, or ``None`` if it may: one of its own
    ``.py`` files would otherwise shadow the standard library or ``bench`` itself, silently -
    :func:`bench.shadow.shadowed`, named, checked before anything is mounted rather than left
    to whichever import happens to ask for the real one first."""
    # Imported here, not at module level: `tools/check.py` runs the suite twice and drops
    # `bench` and every `bench.*` module from `sys.modules` in between, and this module is
    # not one of the ones it re-imports late for nothing - see the note above `VALUES`.
    from bench.shadow import shadowed

    names = [one.name for one in directory.glob("*.py")] if directory.is_dir() else []
    bad = shadowed(names)
    return None if bad is None else f"{directory / bad} would shadow the standard library or bench"


def _modules_of(directory: Path, script: Path) -> frozenset[str]:
    """``directory``'s own ``.py`` files besides ``script`` itself, as their stems - what an
    import inside ``script`` might reach, handed to :func:`bench.script.run` as ``modules`` so
    a name it does not have fails saying so (task-56), the same list :func:`_refused` already
    checked."""
    if not directory.is_dir():
        return frozenset()
    return frozenset(
        one.stem for one in directory.glob("*.py") if one.resolve() != script.resolve()
    )


@contextmanager
def _mounted(directory: Path) -> Iterator[None]:
    """``directory`` on the import path for the run inside, and gone again - from
    ``sys.path``, ``sys.modules`` and the import machinery's own caches - when it ends. This
    is decision-9 step 9 on the command line: an entry that says ``import parts`` reaches a
    ``parts.py`` beside it. Callers check :func:`_refused` first; this does not.

    Without the ``sys.modules`` half, two runs of two different projects that each have a
    ``helper.py`` would share one cached module - the second run's ``import helper`` silently
    handing back the first's. ``sys.dont_write_bytecode`` is held ``True`` for the same
    reason a maker's own editor is never raced (decision-9): a ``__pycache__`` written into a
    project directory is not this tool's file to leave there.
    """
    where = str(directory)
    was_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, where)
    before = set(sys.modules)
    try:
        yield
    finally:
        sys.path.remove(where)
        resolved = directory.resolve()
        for name in set(sys.modules) - before:
            at = getattr(sys.modules.get(name), "__file__", None)
            if at is not None and Path(at).resolve().is_relative_to(resolved):
                del sys.modules[name]
        importlib.invalidate_caches()
        sys.dont_write_bytecode = was_bytecode


_PLACING = ("origin", "up", "along")
"""The keys that make a ``[reference]`` table a placement rather than only a name - the app's
``placing`` in ``web/src/values.ts`` reads the same three."""


def _placing(table: dict[str, object]) -> bool:
    """Whether ``table`` places its body, or only names which of a project's meshes is the
    active one (task-49), which is handed over exactly as exported."""
    return any(key in table for key in _PLACING)


def _reference_placed(script: Path, table: dict[str, object]) -> tuple[Mesh, Plane | None]:
    """The STL ``table['file']`` names, beside ``script``, read and placed by the rest of
    ``table`` - or as exported, with no frame, when the table only names it.

    Raises:
        ValueError: if ``table`` has no readable ``file``, the file it names is not there, or
            :func:`bench.placement.placement` refuses the rest of ``table`` - ``main`` catches
            this the same way it catches a value a field cannot read, naming it and answering
            ``1`` rather than tracing.
    """
    from bench.placement import placed, placement
    from bench.survey import mesh_from_stl

    name = table.get("file")
    if not isinstance(name, str):
        msg = "reference table has no 'file'"
        raise ValueError(msg)
    at = script.parent / name
    if not at.is_file():
        msg = f"reference names {at}, and there is no file there"
        raise ValueError(msg)
    mesh = mesh_from_stl(at.read_bytes())
    if not _placing(table):
        return mesh, None
    frame = placement(table, mesh)
    return placed(mesh, frame), frame


def _frame_said(toml: Path, name: str, frame: Plane) -> str:
    """The sentence every move gets, printed the same way ``values_beside`` already is: the
    frame actually used, after ``along`` was projected - decision-4's rule, "the host says
    what it did"."""

    def triple(x: float, y: float, z: float) -> str:
        return f"({x:.3f}, {y:.3f}, {z:.3f})"

    return (
        f"{toml.name}: reference={name} origin={triple(*frame.origin)}"
        f" up={triple(*frame.normal)} along={triple(*frame.x_dir)}"
    )


def written(scene: OkScene, into: Path) -> list[Path]:
    """Every file the run made, written into ``into``, and where each one went.

    A scene is JSON, so its files are strings either way; :func:`bench.transport.binary` is
    the one place that says which of them are base64 and have to be decoded on the way to
    disk. Getting that wrong writes an STL full of the letters of an STL.
    """
    from bench.transport import binary

    into.mkdir(parents=True, exist_ok=True)
    made: list[Path] = []
    for name, held in scene["files"].items():
        at = into / name
        if binary(name):
            at.write_bytes(b64decode(held))
        else:
            at.write_text(held)
        made.append(at)
    return made


def _said(scene: Scene) -> list[str]:
    """What the run amounts to, in the words the app's status bar uses."""
    if not scene["ok"]:
        where = scene["error"]["line"]
        at = "" if where is None else f" at line {where}"
        return [f"failed{at}: {scene['error']['message']}"]
    summary = scene["summary"]
    lines = [
        f"ok: {summary['parts']} parts on {summary['sheets']} sheets"
        f" - {summary['errors']} errors, {summary['warnings']} warnings"
    ]
    lines += [
        f"  {one['severity']} {one['check']}: {one['message']}" for one in scene["violations"]
    ]
    return lines


def _resolve(
    named: list[str], given: dict[str, str], environ: Mapping[str, str] | None
) -> tuple[Path, Path]:
    """The script this run builds, and the directory to put on the import path for it - one
    rule for ``--project NAME [script.py]``, a bare script and a project directory, so none of
    the three can disagree about which file ``[project] entry`` names.

    ``--project NAME`` alone runs ``NAME``'s entry, exactly as a fresh open of the app would;
    ``--project NAME script.py`` runs that one script of the project instead - the tab a
    person has open, not necessarily the entry, decision-9's own rule for which script Run
    runs. A bare directory is the same as ``--project`` naming it, without the root: its
    entry, unless a script is also named. A bare script runs on its own, its directory the
    only one on the path.

    A project or script name that is not one plain name, a refused projects root, or an
    unreadable ``bench.toml`` reach the caller as the same ``ValueError``
    :func:`tools.projects.project_dir`, :func:`tools.projects.project_file` and
    :func:`_entry_in` already raise it as.
    """
    if "--project" in given:
        directory = project_dir(given["--project"], environ)
        if named:
            return project_file(given["--project"], named[0], environ), directory
        return _entry_in(directory), directory
    script = Path(named[0])
    if script.is_dir():
        return _entry_in(script), script
    return script, script.parent


def main(argv: tuple[str, ...] | None = None, environ: Mapping[str, str] | None = None) -> int:
    """Run the script or project directory named, with the values beside it, and say what it
    made.

    ``--out DIR`` writes every file the run produced into ``DIR``. Without it nothing is
    written and the run is only reported, which is what you want while you are still turning
    numbers.

    ``--project NAME`` and a bare directory are :func:`_resolve`'s to sort out - see there for
    what each becomes.

    Returns:
        ``0`` if the run produced geometry, ``1`` if it did not - so this can stand in a
        pipeline. A check that found something is not a failure of the run: it comes back on
        the scene and is printed, exactly as the app shows it.
    """
    from bench.script import run

    args = tuple(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print(__doc__, file=sys.stderr)
        return 1
    flags = {"--out", "--project"}
    given = {flag: args[at + 1] for at, flag in enumerate(args[:-1]) if flag in flags}
    named = [
        one
        for at, one in enumerate(args)
        if one not in flags and (at == 0 or args[at - 1] not in flags)
    ]
    if not named and "--project" not in given:
        print(__doc__, file=sys.stderr)
        return 1
    try:
        script, project_root = _resolve(named, given, environ)
    except ValueError as exc:
        print(f"failed: {exc}", file=sys.stderr)
        return 1
    if not script.is_file():
        print(f"no script at {script}", file=sys.stderr)
        return 1
    problem = _refused(project_root)
    if problem is not None:
        print(f"failed: {problem}", file=sys.stderr)
        return 1
    out = Path(given["--out"]) if "--out" in given else None

    with _mounted(project_root):
        values = values_beside(script)
        if values:
            said = ", ".join(f"{name}={one!r}" for name, one in sorted(values.items()))
            print(f"{_document_path(script).name}: {said}")

        reference_table = reference_beside(script)
        reference = None
        if reference_table is not None:
            try:
                reference, frame = _reference_placed(script, reference_table)
            except ValueError as exc:
                print(f"failed: {exc}", file=sys.stderr)
                return 1
            name = str(reference_table.get("file"))
            if frame is None:
                print(f"{_document_path(script).name}: reference={name} as exported, not placed")
            else:
                print(_frame_said(_document_path(script), name, frame))

        scene: Any = run(
            script.read_text(),
            values,
            reference=reference,
            modules=_modules_of(project_root, script),
        )
    for line in _said(scene):
        print(line)
    if not scene["ok"]:
        return 1
    if out is not None:
        for at in written(scene, out):
            print(f"  wrote {at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
