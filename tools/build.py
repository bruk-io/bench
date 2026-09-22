"""Run a script and keep what it made: ``uv run python -m tools.build <script.py> [--out DIR]``.

The repository had no way to run a script without a browser. Every other host of
:func:`bench.script.run` is either the app - :mod:`bench.worker`, inside Pyodide - or a test.
So a maker with a script and a cutting machine had to open a browser to get an SVG out of it,
and a values file had nowhere to be read.

This is that host, and it is deliberately the smallest one that is useful: a path in, a scene
out, and the files written down if you ask for them. It asserts nothing and has no verdict of
its own beyond whether the run came back ``ok`` - checking is :mod:`tools.check`'s job.

**Where the values come from.** A script declares its settings as a dataclass and the
dataclass holds the defaults. A TOML beside the script - ``cabinet.py`` and ``cabinet.toml``
- says which one of that thing you are building:

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

import sys
import tomllib
from base64 import b64decode
from pathlib import Path
from typing import TYPE_CHECKING, Any

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


def _toml_beside(script: Path) -> dict[str, object]:
    """The whole of ``script``'s TOML, or nothing at all if there is no file beside it.

    Raises:
        ValueError: if the file is not readable as TOML, naming it and what was wrong, so a
            typed comma is reported rather than silently losing every table in the file.
    """
    beside = script.with_suffix(".toml")
    if not beside.is_file():
        return {}
    try:
        return tomllib.loads(beside.read_text())
    except tomllib.TOMLDecodeError as exc:
        msg = f"{beside} is not readable as TOML: {exc}"
        raise ValueError(msg) from exc


def values_beside(script: Path) -> dict[str, object]:
    """What ``script``'s TOML says to build, or nothing at all.

    The file is ``script`` with a ``.toml`` suffix instead of its own. A missing file is not a
    mistake - it means the script's own defaults - and neither is a file with no ``[values]``
    in it.

    Raises:
        ValueError: if the file is not readable as TOML, or its ``[values]`` is not a table.
    """
    whole = _toml_beside(script)
    table = whole.get(VALUES, {})
    if not isinstance(table, dict):
        msg = f"{script.with_suffix('.toml')} has a [{VALUES}] that is not a table"
        raise ValueError(msg)
    return dict(table)


def reference_beside(script: Path) -> dict[str, object] | None:
    """The ``[reference]`` table in ``script``'s TOML, or ``None`` if there is none.

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
        msg = f"{script.with_suffix('.toml')} has a [{REFERENCE}] that is not a table"
        raise ValueError(msg)
    return dict(table)


def _reference_placed(script: Path, table: dict[str, object]) -> tuple[Mesh, Plane]:
    """The STL ``table['file']`` names, beside ``script``, read and placed by the rest of
    ``table``.

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


def main(argv: tuple[str, ...] | None = None) -> int:
    """Run the script named, with the values beside it, and say what it made.

    ``--out DIR`` writes every file the run produced into ``DIR``. Without it nothing is
    written and the run is only reported, which is what you want while you are still turning
    numbers.

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
    script = Path(args[0])
    if not script.is_file():
        print(f"no script at {script}", file=sys.stderr)
        return 1
    out = Path(args[args.index("--out") + 1]) if "--out" in args[1:] else None

    values = values_beside(script)
    if values:
        said = ", ".join(f"{name}={one!r}" for name, one in sorted(values.items()))
        print(f"{script.with_suffix('.toml').name}: {said}")

    reference_table = reference_beside(script)
    reference = None
    if reference_table is not None:
        try:
            reference, frame = _reference_placed(script, reference_table)
        except ValueError as exc:
            print(f"failed: {exc}", file=sys.stderr)
            return 1
        name = str(reference_table.get("file"))
        print(_frame_said(script.with_suffix(".toml"), name, frame))

    scene: Any = run(script.read_text(), values, reference=reference)
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
