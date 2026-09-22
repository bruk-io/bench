"""Worker: the one place the browser's worker calls into Python.

``web/src/worker.ts`` boots Pyodide, writes ``bench`` into its filesystem, and calls
:func:`start` once. It hands over two things: the page's telemetry, and the exception a
refused call to the modeller raises - Pyodide's ``JsException``, imported on that side so
nothing here needs Pyodide. What comes back is the runner the worker calls for every run: a
source, its overrides as JSON, the modeller (or ``None``), a dropped body (or ``None``) and
its `[reference]` table (or ``None``) in, and the scene as :func:`bench.transport.scene_wire`
writes it out. :func:`surveyed` and :func:`detected` are the worker's other calls into
Python, both under the same placement: the survey of a body dropped on the view, and which
of its triangles belong to which detected face.

This used to be a string of Python inside the TypeScript, where no linter, type checker or
test could reach it. It is the most important edge in the app, so it lives here.

It is a host, not a layer of the vocabulary: it routes :mod:`logging` to a handler, which is
configuration. It does that when :func:`start` is called and never on import, and a second
call replaces its handler rather than adding another.
"""

import base64
import json
import logging
from array import array
from dataclasses import dataclass
from typing import Protocol

from . import script, transport
from .adapters.browser import JsKernel, Modeller
from .kernel import Mesh
from .library import gridfinity
from .placement import named_origins, placed, placement
from .report import report
from .survey import ROUND, flat_faces, mesh_from_stl, survey
from .telemetry import FIELDS, Span, timed

Wire = tuple[str, list[array[float] | array[int]]]
"""What a run hands the worker: the scene's JSON and the buffers its meshes were taken out
into."""


class Runner(Protocol):
    """What :func:`start` gives back: a source, its overrides as JSON, the modeller or
    ``None``, a reference body as base64 STL or ``None``, and the project's `[reference]`
    table as JSON or ``None``.

    A Protocol rather than a :class:`~collections.abc.Callable` alias because the last three
    arguments have defaults and a ``Callable`` cannot say so - it would make every caller
    that wants none of a modeller, a reference or a placement pass three ``None``s to satisfy
    a type rather than a runtime.

    The reference crosses as text rather than as bytes because a string is the one thing both
    runtimes agree about without a proxy in the middle - and a body dropped on the view is
    read once per run, not per frame, so the copy costs nothing anybody can feel. ``table`` is
    ``None`` without a ``stl``, or with one that has nothing said about it - decision-4's
    "no table, no move".
    """

    def __call__(
        self,
        source: str,
        overrides: str,
        modeller: Modeller | None = None,
        stl: str | None = None,
        table: str | None = None,
        /,
    ) -> Wire: ...


class Telemetry(Protocol):
    """The page's two telemetry calls, as the worker hands them over: plain arguments,
    attributes as JSON text, and times in milliseconds since the epoch."""

    def span(self, name: str, start: float, duration: float, attributes: str, /) -> None: ...

    def log(
        self, level: str, logger: str, message: str, time: float, attributes: str, /
    ) -> None: ...


_LEVELS = {"WARNING": "warn", "CRITICAL": "error"}
""":mod:`logging`'s level names that the page spells differently."""


def level(name: str) -> str:
    """A :mod:`logging` level name as the page's telemetry spells it: ``debug``, ``info``,
    ``warn`` or ``error``."""
    return _LEVELS.get(name, name.lower())


@dataclass(frozen=True, slots=True)
class _Spans:
    """A tracer that hands every finished span to the page, in milliseconds."""

    telemetry: Telemetry

    def record(self, span: Span, /) -> None:
        self.telemetry.span(
            span.name, span.start * 1000, span.duration * 1000, json.dumps(dict(span.attributes))
        )


class _Records(logging.Handler):
    """``bench``'s log records, handed to the page with their structured fields.

    The one subclass in the package, because a handler is how :mod:`logging` is extended.
    """

    def __init__(self, telemetry: Telemetry) -> None:
        super().__init__(logging.DEBUG)
        self._telemetry = telemetry

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._telemetry.log(
                level(record.levelname),
                record.name,
                record.getMessage(),
                record.created * 1000,
                json.dumps(getattr(record, FIELDS, {}), default=str),
            )
        except Exception:  # a handler must not raise into the code that logged
            self.handleError(record)


def _placed(mesh: Mesh, table: str | None) -> Mesh:
    """``mesh``, placed by ``table`` - the project's `[reference]` table as JSON, crossed as
    text for the reason :class:`Runner` gives - or ``mesh`` itself when there is nothing to
    place it with: decision-4's rule, "no table, no move".

    A ``table`` that is not readable as a `[reference]` table fails the way a bad value
    already does: :func:`~bench.placement.placement`'s own ``ValueError`` reaches the caller
    unchanged, naming the key it could not read.
    """
    if table is None:
        return mesh
    return placed(mesh, placement(json.loads(table), mesh))


def _reference(stl: str | None, table: str | None) -> Mesh | None:
    """The mesh a run binds as ``reference``: the dropped body, placed by ``table`` when
    there is one to place it with - or ``None`` when nothing was dropped.

    A ``stl`` that is not a binary STL, or a ``table`` :func:`_placed` cannot read, fails the
    same way: the reader's own ``ValueError`` reaches the caller unchanged.
    """
    if stl is None:
        return None
    return _placed(mesh_from_stl(base64.b64decode(stl)), table)


def start(telemetry: Telemetry, refused: type[Exception]) -> Runner:
    """Route ``bench``'s log records and spans to ``telemetry``, and give back the runner.

    ``refused`` is the exception a failed call to the modeller raises. Every run gets
    ``gridfinity`` pre-bound by name, so a script saved before the library had to be imported
    still runs, and ``reference`` bound to the body the host was handed - placed by ``table``
    when the project has one - or to ``None``.

    A host that hands over something which is not a binary STL, or a ``table`` that is not a
    readable `[reference]`, gets the reader's own ``ValueError`` back out of the runner, and
    the page shows that as the run failing with the reason the reader gave. Nothing is raised
    from here: this only builds the runner.
    """
    logger = logging.getLogger("bench")
    for old in [one for one in logger.handlers if isinstance(one, _Records)]:
        logger.removeHandler(old)
    logger.addHandler(_Records(telemetry))
    logger.setLevel(logging.DEBUG)
    tracer = _Spans(telemetry)

    def run(
        source: str,
        overrides: str,
        modeller: Modeller | None = None,
        stl: str | None = None,
        table: str | None = None,
    ) -> Wire:
        scene = script.run(
            source,
            json.loads(overrides),
            extras={"gridfinity": gridfinity},
            reference=_reference(stl, table),
            kernel=None if modeller is None else JsKernel(modeller, refused, tracer),
            tracer=tracer,
        )
        with timed(tracer, "bench.scene.wire"):
            return transport.scene_wire(scene)

    return run


def surveyed(stl: str, table: str | None = None) -> str:
    """The report of a body dropped on the view, placed the same way :func:`start`'s runner
    places ``reference`` - so what the report says and what a run measures never disagree.

    ``table`` is the project's `[reference]` table as JSON, or ``None`` for a drop with
    nothing said about its placement. This is what ``web/src/worker.ts``'s survey entry point
    calls, in place of composing :func:`~bench.survey.mesh_from_stl`,
    :func:`~bench.survey.survey` and :func:`~bench.report.report` itself, now that there is a
    branch here worth testing rather than three calls that already are. A ``stl`` or a
    ``table`` this cannot read fails the way :func:`_reference` does.
    """
    mesh = _placed(mesh_from_stl(base64.b64decode(stl)), table)
    return report(survey(mesh))


def detected(stl: str, table: str | None = None) -> str:
    """Which flat, by index, each triangle of a body dropped on the view belongs to - and
    the flats themselves - placed the same way :func:`surveyed` places one, so a detected
    face and a survey's own numbers never disagree about where the body sits.

    A face's own triangles are what a viewer needs to colour it and answer a click on it,
    and are not something :func:`surveyed`'s prose report carries - see
    :func:`bench.survey.flat_faces`. Returned as JSON rather than the wire's buffer split
    :mod:`bench.transport` uses for a run: this is asked for once, on demand, not on every
    frame, and a detected face is drawn on top of a body already on screen rather than
    replacing it.

    ``origins`` and ``round`` are what decision-7's pick resolves an ``origin`` against: the
    three points `[reference]`'s own words name for this body, in the frame the detection
    itself is in, and the distance within which a picked point *is* one of them rather than
    merely near it. They ride along here rather than being asked for separately because a pick
    happens in the same mode a detection does, on the same body, and a second reader of the
    same mesh could only disagree with this one.

    A ``stl`` or a ``table`` this cannot read fails the way :func:`_reference` does.
    """
    mesh = _placed(mesh_from_stl(base64.b64decode(stl)), table)
    faces = flat_faces(mesh)
    flat_of: dict[int, int] = {i: n for n, (_, region) in enumerate(faces) for i in region}
    return json.dumps(
        {
            "flat_index": [flat_of.get(i) for i in range(len(mesh.triangles) // 3)],
            "flats": [
                {
                    "normal": [flat.normal.x, flat.normal.y, flat.normal.z],
                    "centre": [flat.centre.x, flat.centre.y, flat.centre.z],
                    "area": flat.area,
                }
                for flat, _ in faces
            ],
            "origins": [
                {"name": name, "point": [point.x, point.y, point.z]}
                for name, point in named_origins(mesh)
            ],
            "round": ROUND,
        }
    )
