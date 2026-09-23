"""Scene: what a run hands back, as the records that cross a wire.

:data:`Scene` is the answer :func:`bench.script.run` gives - the declared parameters, the
parts with their refs, bodies and engravings, the nested sheets, the files to download, the
violations the checks found, the warnings and what the script printed on each of its two
streams - or the one error record saying which line of the script went wrong. Every record
is a closed :class:`~typing.TypedDict`, so a key that is not in the contract is a type error
here rather than something a reader finds out about at run time.

This is a contract with the outside world rather than with the rest of the package, and that
is why it is a module of its own: ``web/src/scene.ts`` mirrors these declarations field for
field, and a change on either side has exactly one file to be made to match on the other.
:mod:`bench.script` builds them and imports its types from here.
"""

from typing import Literal, TypedDict

from .checks import Severity
from .model import Process

Scalar = bool | int | float | str
"""What a parameter can be: the values a panel widget can hold."""

Kind = Literal["bool", "int", "float", "str", "choice"]
"""Which widget a parameter wants, inferred from its default or from ``choices``."""


class ParamView(TypedDict, closed=True):
    """One declared parameter, as a panel needs it.

    ``label`` falls back to ``name``, and ``min``, ``max``, ``step`` and ``choices`` are
    ``None`` when the declaration left them out.
    """

    name: str
    label: str
    kind: Kind
    default: Scalar
    min: float | None
    max: float | None
    step: float | None
    choices: list[Scalar] | None


class StockView(TypedDict, closed=True):
    """The material a part is cut from."""

    thickness: float
    material: str
    kerf: float


class MeshView(TypedDict, closed=True):
    """A body ready to draw: ``positions`` is nine numbers per triangle - its three corners,
    already placed on the stage - and ``ref_index`` one number per triangle, the face it lies
    on as ``refs[ref_index - 1]``, or ``0`` for a triangle of no named face, which is the part
    itself. So clicking a triangle names a face with nothing worked out first.

    On the wire the two long lists travel as buffers beside the JSON rather than inside it;
    see :func:`bench.transport.scene_wire`."""

    positions: list[float]
    ref_index: list[int]
    refs: list[str]


class FrameView(TypedDict, closed=True):
    """One named face's frame, exactly what :func:`bench.solids.plane_of` answers for it:
    ``origin`` and ``normal`` already stood where the stage put the body - a translation
    only, so a direction needs none of it - and ``x`` the direction the face was authored
    with, unmoved. Three numbers each, task-61's pick draws as small axes and reads to write
    ``offset``/``spin`` by eye."""

    origin: list[float]
    normal: list[float]
    x: list[float]


class MarksView(TypedDict, closed=True):
    """The wires engraved on a plate, ready to draw: ``segments`` is six numbers per line
    segment - both ends, already placed on the stage and just clear of the plate's top - and
    ``ref_index`` one number per segment, as ``refs[ref_index - 1]`` or ``0`` for an engraving
    with no name. Its two long lists travel as buffers, as a mesh's do."""

    segments: list[float]
    ref_index: list[int]
    refs: list[str]


class LetteringView(TypedDict, closed=True):
    """A line of engraved text and where it is drawn: the four corners of the box it fills on
    the plate's top - twelve numbers, already placed, along the baseline and back along the
    cap height - and its ref, or ``None`` for lettering with no name."""

    text: str
    ref: str | None
    corners: list[float]


class GridView(TypedDict, closed=True):
    """The floor under the work: its width, how many cells across, and its middle ``x, y``."""

    size: float
    divisions: int
    centre: list[float]


class StageView(TypedDict, closed=True):
    """Where a scene's bodies stand: the box they fill, ``x0, y0, z0, x1, y1, z1``, and the
    floor under them - :mod:`bench.stage`'s answer, so the viewer works none of it out."""

    bounds: list[float]
    grid: GridView


class SummaryView(TypedDict, closed=True):
    """What a run amounts to, counted once here so the app words it rather than works it out.

    ``parts`` and ``sheets`` are what was made and nested; ``errors`` and ``warnings`` are what
    the checks found, and ``error_line`` is the script line of the first error, or ``None``.
    ``solid`` counts the parts with a body to draw and ``unbuilt`` the parts without one.
    """

    parts: int
    sheets: int
    errors: int
    warnings: int
    error_line: int | None
    solid: int
    unbuilt: int


class PartView(TypedDict, closed=True):
    """One part of the shown assembly: what to call it, how many to cut, and its body.

    ``bbox`` is the part's extent in its own coordinates. ``mesh`` is its body on the stage -
    a laser part's plate, or a printed part's body as a kernel built it - and ``None`` for a
    part there is no body for, such as a printed part in a run given no kernel. ``marks`` and
    ``lettering`` are what is engraved on a plate; ``marks`` is ``None`` when nothing is.
    ``frames`` is every named planar face's frame, under its own ref the way ``refs`` names
    it - one entry per face :func:`~bench.solids.plane_of` can answer for, which is only a
    printed part's: a laser part's plate has none, and neither does a round face with no
    ``around=`` to take a tangent at, which is task-61's own "cannot frame" case.
    """

    ref: str
    label: str
    qty: int
    stock: StockView
    process: Process
    bbox: list[float]
    mesh: MeshView | None
    marks: MarksView | None
    lettering: list[LetteringView]
    frames: dict[str, FrameView]


class ViolationView(TypedDict, closed=True):
    """One thing a check found, as the app shows it: which check, what it says, how much it
    matters, the refs to highlight, and the line of the script that asked - so a violation
    reads like a warning with somewhere to point. ``line`` is ``None`` only for a check
    recorded from outside the script's own frames."""

    check: str
    message: str
    severity: Severity
    refs: list[str]
    line: int | None


class SheetView(TypedDict, closed=True):
    """One nested sheet: its name, the stock it is, its SVG, the same drawing with lines wide
    enough to see in a thumbnail, and the refs on it - one entry per placement, so a part cut
    twice on a sheet appears twice."""

    name: str
    thickness: float
    svg: str
    preview: str
    parts: list[str]


class ErrorView(TypedDict, closed=True):
    """Why a run failed. ``line`` is the line of the script's own frame, or ``None`` when
    the failure belongs to no line of it."""

    message: str
    line: int | None
    traceback: str


class OkScene(TypedDict, closed=True):
    """A run that produced geometry.

    ``stdout`` and ``stderr`` are what the script printed on each stream, kept apart rather
    than woven together: the order between the two is lost, which costs nothing a reader of
    either one misses, and what it buys is a panel that can say which is which.

    ``reference`` is a body somebody else made, handed to the run rather than built by it, so
    the view can stand the work against the thing it is copying. It is a body to look at and
    nothing else: it names no faces - every one of its triangles indexes nothing, which is
    what keeps it out of a selection - it is not a part, it is nested onto no sheet and it
    reaches no exported file. ``None`` when the host offered nothing.
    """

    ok: Literal[True]
    params: list[ParamView]
    values: dict[str, Scalar]
    parts: list[PartView]
    stage: StageView
    summary: SummaryView
    refs: list[str]
    sheets: list[SheetView]
    files: dict[str, str]
    violations: list[ViolationView]
    warnings: list[str]
    stdout: str
    stderr: str
    reference: MeshView | None


class ErrorScene(TypedDict, closed=True):
    """A run that did not.

    It carries the two streams as well, and for the same reason an :class:`OkScene` does:
    what a script printed before it fell over is the last thing it managed to say, and a
    script that prints its way to the line that breaks needs it most of all. Both are empty
    when the failure was the compile, where nothing ran to say anything.
    """

    ok: Literal[False]
    error: ErrorView
    stdout: str
    stderr: str


Scene = OkScene | ErrorScene
"""What :func:`bench.script.run` returns: tell the two apart by ``scene["ok"]``."""
