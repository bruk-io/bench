"""Views: what a run collected, as the scene a browser reads.

:mod:`bench.script` runs a script and collects what it said: the assembly it showed, the
parameters it declared, the violations its checks found and what it printed. This module turns
that into a :data:`bench.scene.Scene`. It nests the parts onto sheets, builds each part's body -
a laser part's plate here, a printed part's body with the kernel - lays the bodies out on the
stage, writes every file a run offers, and converts each record into the closed view the wire
carries.

It runs no script and knows nothing of one: it is handed data and gives back data, so the
runtime and the answer it produces can each change without the other.
"""

import base64
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import NamedTuple, assert_never

from .checks import Severity, Violation, exportable
from .export import as_printed, part_svg, sheet_dxf, sheet_svg, stl, three_mf
from .kernel import Kernel, Mesh
from .model import Assembly, Part, Printed, Process, Ref, Stock, Stocked, index
from .nest import Bed, PartSpec, Sheet, nest, sheet_name
from .ops import BBox, bbox
from .plates import Lettering, Marks, Plate, plate
from .scene import (
    ErrorScene,
    ErrorView,
    FrameView,
    GridView,
    LetteringView,
    MarksView,
    MeshView,
    OkScene,
    ParamView,
    PartView,
    Scalar,
    SheetView,
    StageView,
    StockView,
    SummaryView,
    ViolationView,
)
from .solids import plane_of
from .stage import Box, Offset, as_given, grid, layout, positions, ref_table, shifted
from .telemetry import Tracer, timed
from .topology import SEP, Face, Label, Shape, Solid
from .transport import STL, THREE_MF

_Built = Plate | Mesh | None
"""What a part's body turned out to be: a plate, a kernel's mesh, or nothing to draw."""


class Finding(NamedTuple):
    """One thing a check found, with what the check was handed.

    A check measures a bare shape and knows nothing of parts, so its answer names faces in the
    shape's own namespace. ``subjects`` are the shapes it measured, in the order it was given
    them - the one whose faces ``violation.refs`` name first, then any body it was measured
    against - and they are what lets :func:`scene` say which part each finding is about.
    """

    violation: Violation
    subjects: tuple[Shape, ...]


def scene(
    *,
    assembly: Assembly,
    quantities: Mapping[Ref, int],
    extra: Mapping[str, str],
    params: Sequence[ParamView],
    values: Mapping[str, Scalar],
    findings: Sequence[Finding],
    bed: Bed,
    kernel: Kernel | None,
    reference: Mesh | None = None,
    stdout: str,
    stderr: str,
    tracer: Tracer,
) -> OkScene:
    """What a run that showed ``assembly`` hands back.

    ``quantities`` says how many of each part to cut, and ``extra`` is whatever files the build
    brought with it. ``findings`` are what the checks found, each with the shapes it measured,
    and reach the scene with their refs in the scene's own namespace - see :func:`_qualified`.
    ``assembly.posed`` decides only where the bodies stand for the view - as the script
    placed them, or laid out in rows - and nothing else: the nesting above it, the
    quantities and every file below it read ``assembly.parts`` the same way either way.
    ``bed`` is the stock the parts are nested onto. ``kernel`` builds the printed bodies, which
    have no ``mesh`` when there is none; a laser part's plate needs no kernel. Each stretch of
    the work is a span on ``tracer``.
    """
    parts = tuple(placed.part for placed in assembly.parts)
    refused = _export_findings(parts)
    violations = tuple(_qualified(one, parts) for one in (*findings, *refused))
    counts = tuple(quantities.get(Ref(part.label), 1) for part in parts)
    cut_list: tuple[PartSpec, ...] = tuple(zip(parts, counts, strict=True))
    with timed(tracer, "bench.scene.nest") as nesting:
        sheets, warnings = nest(cut_list, bed)
        nested = tuple((_sheet_view(name, one), one) for name, one in _named(sheets))
        nesting["bench.sheets"] = len(sheets)
    built = tuple(_timed_build(part, kernel, tracer) for part in parts)
    bodies = tuple(_body(one) for one in built)
    boxes = tuple(bbox(part.shape) for part in parts)
    with timed(tracer, "bench.stage.layout") as staging:
        # The one branch a posed assembly asks for. `layout` packs bodies into rows because
        # a scene of unrelated bodies would otherwise pile up on the origin; an assembly
        # whose parts the script placed relative to each other has already answered that
        # question, and re-packing it would take a mechanism apart. Nothing downstream can
        # tell which arm ran - both hand back an offset per body and the box they fill - and
        # nothing about manufacture reads either: the parts were nested above, before this.
        staging["bench.stage.posed"] = assembly.posed
        offsets, box = as_given(bodies) if assembly.posed else layout(bodies)
    printed = tuple(
        _as_printed(part, body) if part.process is Process.PRINT else None
        for part, body in zip(parts, bodies, strict=True)
    )
    with timed(tracer, "bench.scene.files"):
        files = _files(nested, parts, printed, extra, str(assembly.label))
    return OkScene(
        ok=True,
        params=list(params),
        values=dict(values),
        parts=[
            _part_view(part, qty, one, offset, frame, tracer)
            for part, qty, one, offset, frame in zip(
                parts, counts, built, offsets, boxes, strict=True
            )
        ],
        stage=_stage_view(box),
        summary=_summary(violations, len(parts), len(sheets), bodies),
        refs=[str(found) for found in index(assembly)],
        sheets=[view for view, _ in nested],
        files=files,
        violations=[_violation_view(one) for one in violations],
        warnings=list(warnings),
        stdout=stdout,
        stderr=stderr,
        # Left where it was drawn rather than laid out beside the parts: a reference is the
        # thing being copied, and moving it onto the stage's rows would put it somewhere its
        # own numbers do not describe. Its refs are all None, so `ref_table` hands back an
        # empty table and an index of zeros - a body that answers to no name, which is what
        # keeps a click on it from naming anything.
        reference=None if reference is None else _mesh_view(reference, "", (0.0, 0.0, 0.0)),
    )


def failed(
    message: str, line: int | None, traceback: str, stdout: str = "", stderr: str = ""
) -> ErrorScene:
    """What a run that did not produce geometry hands back: why, on which line of the
    script, the traceback, and what it printed before it stopped."""
    return ErrorScene(
        ok=False,
        error=ErrorView(message=message, line=line, traceback=traceback),
        stdout=stdout,
        stderr=stderr,
    )


# ---- the bodies ----------------------------------------------------------------------------


def _timed_build(part: Part, kernel: Kernel | None, tracer: Tracer) -> _Built:
    """:func:`_built`, as one ``bench.scene.mesh`` span naming the part and its process - a
    part with no body is a span too, so a slow part is found by its name whatever it turned
    out to be."""
    with timed(
        tracer,
        "bench.scene.mesh",
        **{"bench.part.ref": str(part.label), "bench.part.process": str(part.process)},
    ) as attributes:
        one = _built(part, kernel)
        body = _body(one)
        if body is not None:
            attributes["bench.mesh.triangles"] = len(body.refs)
        return one


def _built(part: Part, kernel: Kernel | None) -> _Built:
    """``part``'s body, or ``None``.

    A face is swept into its plate here, kernel or not, so every wall answers to the ref its
    cut path does. A body is built by the kernel, and is ``None`` without one: it is still
    fully named, which is what the refs are, and there is nothing honest to draw.
    """
    match part.shape:
        case Face():
            return plate(part)
        case Solid():
            return None if kernel is None else kernel.mesh(part.shape)
        case _:
            assert_never(part.shape)


def _body(built: _Built) -> Mesh | None:
    match built:
        case Plate():
            return built.mesh
        case Mesh() | None:
            return built
        case _:
            assert_never(built)


def _as_printed(part: Part, body: Mesh | None) -> Mesh | None:
    """``body`` - the assembly-posed mesh the 3D view still draws - laid on the bed the way
    ``part`` prints (:func:`bench.export.as_printed`), which is what goes in the files a run
    offers instead. ``None`` without a kernel to have built one in the first place, and the
    posed mesh unchanged for any stock but :class:`~bench.model.Printed`, which is the only
    one with a way up to read - :func:`_files` only ever calls this on a printed part's body,
    so that never actually happens, but a stray call should move nothing rather than guess.

    A ``bed_face`` is read the same way a script's own ``ref()`` is: a name the part has no
    face by, or a face with no one plane, is :func:`~bench.solids.plane_of`'s to refuse - and
    that refusal is left to propagate to the script's own error rather than caught here and
    traded for an arbitrary turn nobody asked for. A bad ``bed_face`` is the maker's mistake
    to fix, the same as a bad ref anywhere else in a script.
    """
    if body is None or not isinstance(part.stock, Printed):
        return body
    orient = part.stock.orient
    shape = part.shape
    bed_along = None
    if orient.bed_face is not None and isinstance(shape, Solid):
        bed_along = plane_of(shape, orient.bed_face).x_dir
    return as_printed(body, orient.up, bed_along)


# ---- the files -----------------------------------------------------------------------------


def _named(sheets: tuple[Sheet, ...]) -> tuple[tuple[str, Sheet], ...]:
    """Every sheet with its name. A name counts a sheet's place in its own thickness
    series, so the second 3 mm sheet is ``sheet-3mm-02`` however many 6 mm ones precede it."""
    seen: dict[float, int] = {}
    out: list[tuple[str, Sheet]] = []
    for one in sheets:
        place = seen.get(one.thickness, 0)
        seen[one.thickness] = place + 1
        out.append((sheet_name(one, place), one))
    return tuple(out)


def _files(
    nested: tuple[tuple[SheetView, Sheet], ...],
    parts: tuple[Part, ...],
    printed: tuple[Mesh | None, ...],
    extra: Mapping[str, str],
    name: str,
) -> dict[str, str]:
    """Everything a run offers to download: both formats of every sheet, whatever the
    build brought with it, one SVG per part for cutting a single panel again, an STL for
    every printed body a kernel actually built, and one 3MF holding all of them together.

    ``printed`` is each part's body when the part is printed and ``None`` otherwise: a plate
    is drawn so a person can see the part, and it is cut from the sheet's files, not printed.
    An STL is one nameless body, which is what a slicer wants when a part is printed on its
    own; the 3MF is the whole print job with every part named inside it, and is written only
    when there is a body to put in it.

    A part whose shape is a :class:`~bench.topology.Solid` gets no ``part-*.svg`` at all,
    ordinary printed part or a part :func:`bench.checks.exportable` refuses alike:
    :func:`bench.export.part_paths` draws nothing for a solid - a body is shown by building
    it, which is a kernel's business, not a cutter's - so the file would be a page with no
    path on it, the empty file this whole task exists to stop writing rather than a blank
    download that looks like a real one.
    """
    files: dict[str, str] = {}
    for view, one in nested:
        files[f"{view['name']}.svg"] = view["svg"]
        files[f"{view['name']}.dxf"] = sheet_dxf(one)
    files.update(extra)
    for part in parts:
        match part.shape:
            case Face():
                files[f"part-{part.label}.svg"] = part_svg(part)
            case Solid():
                continue
            case _:
                assert_never(part.shape)
    built = tuple(
        (str(part.label), body)
        for part, body in zip(parts, printed, strict=True)
        if body is not None
    )
    for label, body in built:
        files[f"{label}{STL}"] = base64.b64encode(stl(body)).decode("ascii")
    if built:
        files[f"{name}{THREE_MF}"] = base64.b64encode(three_mf(built)).decode("ascii")
    return files


# ---- the records, as the wire carries them -------------------------------------------------


_PREVIEW_PX = 64.0
"""How many pixels across a sheet's thumbnail is: its preview's lines are a sheet's width over
this, so they come out about a pixel wide however big the sheet."""


def _sheet_view(name: str, one: Sheet) -> SheetView:
    return SheetView(
        name=name,
        thickness=one.thickness,
        svg=sheet_svg(one, name),
        preview=sheet_svg(one, name, stroke=max(one.w, one.h) / _PREVIEW_PX),
        parts=[str(placed.part.label) for placed in one.parts],
    )


def _stage_view(box: Box) -> StageView:
    """Where the bodies stand and the floor under them, as the viewer reads it."""
    floor = grid(box)
    return StageView(
        bounds=[box.x0, box.y0, box.z0, box.x1, box.y1, box.z1],
        grid=GridView(
            size=floor.size, divisions=floor.divisions, centre=[floor.centre_x, floor.centre_y]
        ),
    )


def _part_view(
    part: Part, qty: int, built: _Built, offset: Offset | None, box: BBox, tracer: Tracer
) -> PartView:
    label = str(part.label)
    body = _body(built)
    here = offset or (0.0, 0.0, 0.0)
    marks: MarksView | None = None
    lettering: list[LetteringView] = []
    if isinstance(built, Plate):
        marks = _marks_view(built.marks, label, here)
        lettering = [_lettering_view(one, label, here) for one in built.lettering]
    return PartView(
        ref=label,
        label=label,
        qty=qty,
        stock=_stock_view(part.stock),
        process=part.process,
        bbox=[box.x0, box.y0, box.x1, box.y1],
        mesh=None if body is None else _mesh_view(body, label, here),
        marks=marks,
        lettering=lettering,
        frames=_frames_view(part.shape, body, label, here, tracer),
    )


def _frames_view(
    shape: Shape, body: Mesh | None, prefix: str, offset: Offset, tracer: Tracer
) -> dict[str, FrameView]:
    """Every named planar face of ``shape`` that :func:`~bench.solids.plane_of` can answer
    for, under the same prefixed ref :func:`_mesh_view` names it by.

    One call per *named face* the mesh already carries, never per triangle - proportional to
    what a click can land on, not to what a kernel triangulated it into. Only a body has a
    face to answer for; a laser part's plate (``shape`` a ``Face``) carries none. A round
    face with no ``around=`` to take a tangent at is skipped the same way a hole with no
    single plane is: :func:`plane_of` refuses it, and a face with no frame is exactly what
    tells the app's *Insert fit* it cannot write a line for that pick.

    A frame's ``origin`` is moved by ``offset`` - the same rigid translation
    :func:`_mesh_view` stands the mesh's own triangles at - because a frame is drawn where
    the face is drawn, and the stage never rotates a body to get it there. ``normal`` and
    ``x`` are directions, which a translation leaves alone.
    """
    if body is None or not isinstance(shape, Solid):
        return {}
    dx, dy, dz = offset
    out: dict[str, FrameView] = {}
    with timed(tracer, "bench.scene.frames"):
        for raw in dict.fromkeys(ref for ref in body.refs if ref is not None):
            try:
                found = plane_of(shape, str(raw))
            except LookupError, ValueError:
                continue
            out[f"{prefix}{SEP}{raw}"] = FrameView(
                origin=[found.origin.x + dx, found.origin.y + dy, found.origin.z + dz],
                normal=[found.normal.x, found.normal.y, found.normal.z],
                x=[found.x_dir.x, found.x_dir.y, found.x_dir.z],
            )
    return out


def _summary(
    violations: Sequence[Violation], parts: int, sheets: int, bodies: Sequence[Mesh | None]
) -> SummaryView:
    """What a run amounts to: what it made and nested, what its checks found and the line of
    the first error, and how many of its parts have a body to draw."""
    errors = [one for one in violations if one.severity is Severity.ERROR]
    solid = sum(1 for body in bodies if body is not None and body.refs)
    return SummaryView(
        parts=parts,
        sheets=sheets,
        errors=len(errors),
        warnings=sum(1 for one in violations if one.severity is Severity.WARNING),
        error_line=next((one.line for one in errors if one.line is not None), None),
        solid=solid,
        unbuilt=parts - solid,
    )


def _mesh_view(mesh: Mesh, prefix: str, offset: Offset) -> MeshView:
    """``mesh`` as the browser draws it: one triangle at a time, standing where the stage put
    it, and every ref under the part's own label - a kernel is handed a bare solid and answers
    ``boss/top``, and a scene says ``plate/boss/top``."""
    table, index_of = ref_table(mesh.refs, prefix)
    return MeshView(positions=positions(mesh, offset), ref_index=index_of, refs=table)


def _marks_view(marks: Marks, prefix: str, offset: Offset) -> MarksView | None:
    """A plate's engraved wires where the stage put the plate, or ``None`` when it has none."""
    if not marks.refs:
        return None
    table, index_of = ref_table(marks.refs, prefix)
    return MarksView(segments=shifted(marks.segments, offset), ref_index=index_of, refs=table)


def _lettering_view(one: Lettering, prefix: str, offset: Offset) -> LetteringView:
    return LetteringView(
        text=one.text,
        ref=None if one.ref is None else f"{prefix}{SEP}{one.ref}",
        corners=shifted(one.corners, offset),
    )


def _stock_view(stock: Stocked) -> StockView:
    """What a part is made of, in the three fields the app has always read.

    A printed part has no thickness and no kerf, and says so with zeroes rather than with a
    missing key: the wire keeps one shape, and ``process`` is what tells the two apart.
    """
    match stock:
        case Stock():
            return StockView(thickness=stock.thickness, material=stock.material, kerf=stock.kerf)
        case Printed():
            return StockView(thickness=0.0, material=stock.material.name, kerf=0.0)
        case _:
            assert_never(stock)


def _export_findings(parts: Sequence[Part]) -> tuple[Finding, ...]:
    """Every part :func:`bench.checks.exportable` refuses - a solid on sheet stock, or a
    solid marked :data:`~bench.model.Process.CNC` - as one :class:`Finding` each, so the
    reason reaches the scene's violations (the app's Problems panel and :mod:`tools.build`)
    exactly as a script's own checks do, without a script having to ask for it. A part built
    the wrong way is not something a maker should have to notice from an empty download.

    The refs are the part's own label, put there directly rather than left for
    :func:`_qualified` to find by matching ``part.shape``'s identity: two parts made from the
    very same shape - a script that hands one ``Solid`` to two ``part()`` calls - would
    otherwise both be named for whichever part :func:`_label_of` happens to see first. No
    subjects are carried, so :func:`_qualified` leaves these refs exactly as they arrive.
    """
    found: list[Finding] = []
    for part in parts:
        violation = exportable(part.shape, part.stock, part.process)
        if violation is not None:
            found.append(Finding(replace(violation, refs=(Ref(str(part.label)),)), ()))
    return tuple(found)


def _qualified(finding: Finding, parts: Sequence[Part]) -> Violation:
    """``finding``'s violation with its refs in the scene's namespace.

    A check is handed a bare shape and names its faces the way the shape does - ``socket-1`` -
    while the scene names them under the part the shape became - ``tote/socket-1`` - exactly
    as :func:`_mesh_view` prefixes what a kernel answers. Which part that is, is settled by
    identity: the part whose ``shape`` *is* the shape the check was handed. A shape that never
    became a part - a body checked before it was cut, a lip measured on its own - matches
    nothing, and its refs are left as they were rather than guessed at from their last
    segment, which is how two parts that both have a ``bottom`` keep each other's findings
    apart.

    A finding with no refs is about whole bodies, and names each one that became a part:
    ``check_fits`` on the tote's tub answers ``tote``, and a clearance between a pin and a
    leaf names both. An ``UNCHECKED`` answer names nothing, because nothing measured anything
    and there is no finding to point at.
    """
    found = finding.violation
    labels = tuple(_label_of(subject, parts) for subject in finding.subjects)
    if found.refs:
        first = labels[0] if labels else None
        if first is None:
            return found
        return replace(found, refs=tuple(Ref(f"{first}{SEP}{one}") for one in found.refs))
    if found.severity is Severity.UNCHECKED:
        return found
    return replace(found, refs=tuple(Ref(str(label)) for label in labels if label is not None))


def _label_of(subject: Shape, parts: Sequence[Part]) -> Label | None:
    """The label of the part ``subject`` became, or ``None`` when it became none of them.

    By identity and never by value: two panels drawn to the same numbers are equal and are
    two parts, and the one a check was handed is the one whose shape is this very object.
    """
    return next((part.label for part in parts if part.shape is subject), None)


def _violation_view(found: Violation) -> ViolationView:
    return ViolationView(
        check=found.check,
        message=found.message,
        severity=found.severity,
        refs=[str(one) for one in found.refs],
        line=found.line,
    )
