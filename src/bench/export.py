"""Export: the text a machine reads - SVG and DXF for faces, parts and sheets.

A wire becomes one path in millimetres with absolute commands. Arcs stay arcs (``A``), and
anything past a half turn - a whole circle, or an arc that sweeps most of the way round -
is written as two halves, because an ``A`` whose ends coincide is dropped by the SVG spec.
Nothing is flattened on the way to the cutter. Every path carries the ref of the wire it
came from, which is what lets a viewer turn a click into a name.

SVG is written with the workpiece reading origin bottom-left: the page is in
millimetres and one group flips Y, so the numbers inside a path are the model's own.
Lettering gets a second flip of its own so the glyphs stay upright. Cuts go in a red
``cut`` group and engravings in a blue ``engrave`` one.

DXF is minimal R12 ASCII with a ``CUT`` and an ``ENGRAVE`` layer. It is written from the
same topology the SVG is - every wire walked once, arcs flattened to chords no further than
:data:`~bench.topology.CHORD` from the true curve - so the two can never disagree about a shape.

Coordinates are world X and Y throughout for the flat formats: a cut part is a planar face
on a plane parallel to XY.

A body is not flat, and the two formats a printer reads are bytes rather than text.
:func:`stl` and :func:`three_mf` take the :class:`~bench.kernel.Mesh` a kernel built - this
module never builds one and imports no kernel, only the record - and hand back the file. Both
are pure functions: writing them to disk is :mod:`bench.script`'s job, or a browser's.

A mesh a kernel built is in the assembly's pose - wherever the script, or :mod:`bench.mate`,
put the part - and decision-10 keeps that apart from how a part prints: :func:`as_printed`
turns one back to lying on the bed the way its :class:`~bench.model.Orient` says, which is
what :mod:`bench.views` writes into every STL and every 3MF object rather than the posed mesh
itself.
"""

import math
import struct
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass, replace
from io import BytesIO
from typing import Literal, NamedTuple, assert_never

from .geometry import ORIGIN, TOL, Plane, Point, Transform, Vector, plane, to_local, translation
from .kernel import Mesh
from .model import Part, Ref, Text, moved_part
from .nest import Sheet
from .ops import bbox
from .topology import (
    Arc,
    Circle,
    Curve,
    Face,
    Label,
    Line,
    Shape,
    Solid,
    Wire,
    chord_step,
    curve_end,
    curve_start,
    is_closed,
    under,
)

PathKind = Literal["outer", "hole", "engrave"]

_CUT_COLOUR = "#ff0000"
_ENGRAVE_COLOUR = "#0000ff"
_STROKE_MM = 0.1
_CUT_LAYER = "CUT"
_ENGRAVE_LAYER = "ENGRAVE"

_STL_HEADER = 80
"""Bytes of free text at the head of a binary STL, before the triangle count."""

_STL_TRIANGLE = 50
"""Bytes per triangle in a binary STL: twelve floats and a two-byte attribute count."""

_ZIP_STAMP = (1980, 1, 1, 0, 0, 0)
"""The date every entry of a written archive carries. A file is a function of the model and
of nothing else, so two runs of the same model give two identical bytestrings - which is
what lets a test compare them and a browser cache them."""


@dataclass(frozen=True, slots=True)
class SvgPath:
    """One wire as SVG path data in millimetres, absolute commands, Y up.

    ``ref`` is the wire's ref when it is labelled; an unlabelled outline carries the ref
    of the face or part it bounds, and an unlabelled hole or engraving names nothing.
    """

    ref: Ref | None
    kind: PathKind
    d: str


@dataclass(frozen=True, slots=True)
class SvgText:
    """A line of engraved lettering: ``x``, ``y`` its left baseline, ``size`` its height."""

    ref: Ref | None
    text: str
    x: float
    y: float
    size: float


# ---- paths ---------------------------------------------------------------------------


def face_paths(face: Face, prefix: Ref | str) -> tuple[SvgPath, ...]:
    """One closed path per bounding wire of ``face``: the outer wire, then each hole.

    ``prefix`` is the ref of whatever holds the face - a part, or ``""`` for a face on
    its own. The face's own label extends it, and an unlabelled face is transparent, so
    the refs here are the refs :func:`bench.model.index` hands out.
    """
    path = under(str(prefix), face.label)
    # an unlabelled outline is the face itself, so it answers to the face's (or part's) ref
    outer_ref = _ref(path, face.outer.label) or (Ref(path) if path else None)
    outer = SvgPath(outer_ref, "outer", _wire_d(face.outer, close=True))
    holes = tuple(
        SvgPath(_ref(path, hole.label), "hole", _wire_d(hole, close=True)) for hole in face.inner
    )
    return (outer, *holes)


def part_paths(part: Part) -> tuple[SvgPath, ...]:
    """Every path of a part: the shape's outline and holes, then its engraved wires.

    Refs hang off the part's label, so they read the same here as in an assembly.
    Engraved :class:`~bench.topology.Text` is not a path; :func:`part_texts` has it.
    """
    prefix = str(part.label)
    out = list(_shape_paths(part.shape, prefix))
    for engraving in part.engravings:
        match engraving:
            case Wire():
                out.append(
                    SvgPath(
                        _ref(prefix, engraving.label),
                        "engrave",
                        _wire_d(engraving, close=is_closed(engraving)),
                    )
                )
            case Text():
                continue
            case _:
                assert_never(engraving)
    return tuple(out)


def part_texts(part: Part) -> tuple[SvgText, ...]:
    """The part's engraved lettering, in the order it was given."""
    prefix = str(part.label)
    out: list[SvgText] = []
    for engraving in part.engravings:
        match engraving:
            case Text(text, at, size, label):
                out.append(SvgText(_ref(prefix, label), text, at.x, at.y, size))
            case Wire():
                continue
            case _:
                assert_never(engraving)
    return tuple(out)


def _shape_paths(shape: Shape, prefix: str) -> tuple[SvgPath, ...]:
    """A shape as the paths a cutter follows. A solid draws nothing: it is a tree, not a
    boundary, and there is no honest way to flatten a recipe onto a sheet - a body is shown
    by building it, which is a kernel's business and not this module's."""
    match shape:
        case Face():
            return face_paths(shape, prefix)
        case Solid():
            return ()
        case _:
            assert_never(shape)


# ---- path data -----------------------------------------------------------------------


def _wire_d(w: Wire, *, close: bool) -> str:
    start = curve_start(w.edges[0].curve)
    out = [f"M {_num(start.x)} {_num(start.y)}"]
    for e in w.edges:
        out.extend(_commands(e.curve))
    if close:
        out.append("Z")
    return " ".join(out)


def _commands(c: Curve) -> tuple[str, ...]:
    match c:
        case Line(_, end):
            return (f"L {_num(end.x)} {_num(end.y)}",)
        case Arc():
            return _arc_command(c)
        case Circle():
            return _circle_commands(c)
        case _:
            assert_never(c)


def _turn(on: Plane) -> float:
    """+1 when increasing angles in a curve's own frame run counter-clockwise in XY."""
    return 1.0 if on.normal.z >= 0.0 else -1.0


def _arc_command(a: Arc) -> tuple[str, ...]:
    """The ``A`` commands for one arc. SVG's sweep flag is 1 when the angle grows in the
    page's own frame, which inside the Y-up group is the same direction the arc records.

    Anything past a half turn is cut in two halves and written as two ``A``s, the way
    :func:`_circle_commands` writes a circle: an ``A`` whose ends coincide is dropped by
    the SVG spec, so a whole turn written as one command would cut nothing at all. No
    command this writes ever turns more than a half turn, so the large-arc flag is always
    ``0``.

    Raises:
        ValueError: if the arc sweeps further than a whole turn, which no single closed
            curve can mean.
    """
    sweep = (a.end_angle - a.start_angle) * _turn(a.plane)
    if abs(sweep) > 2 * math.pi + TOL:
        msg = f"an arc cannot sweep {abs(sweep)} radians, further than a whole turn"
        raise ValueError(msg)
    end = curve_end(a)
    if abs(sweep) < TOL:
        return (f"L {_num(end.x)} {_num(end.y)}",)
    if abs(sweep) > math.pi + TOL:
        half = (a.start_angle + a.end_angle) / 2
        return (
            *_arc_command(replace(a, end_angle=half)),
            *_arc_command(replace(a, start_angle=half)),
        )
    flag = 1 if sweep > 0.0 else 0
    r = _num(a.radius)
    return (f"A {r} {r} 0 0 {flag} {_num(end.x)} {_num(end.y)}",)


def _circle_commands(c: Circle) -> tuple[str, ...]:
    """A whole circle as two half-arcs; one ``A`` can never turn a full turn."""
    start = curve_start(c)
    opposite = c.centre + (c.centre - start)
    flag = 1 if _turn(c.plane) > 0.0 else 0
    r = _num(c.radius)
    return (
        f"A {r} {r} 0 0 {flag} {_num(opposite.x)} {_num(opposite.y)}",
        f"A {r} {r} 0 0 {flag} {_num(start.x)} {_num(start.y)}",
    )


# ---- svg -----------------------------------------------------------------------------


def sheet_svg(sheet: Sheet, title: str, *, stroke: float = _STROKE_MM) -> str:
    """One nested sheet as a standalone SVG, the sheet's own corner at the origin.

    ``stroke`` is how wide its lines are drawn, in millimetres: a cutter's hairline unless
    asked otherwise, and wider for a picture of the sheet that will be shrunk to a thumbnail,
    where a hairline is thinner than a pixel and draws nothing at all.
    """
    paths = tuple(path for placed in sheet.parts for path in part_paths(placed.placed))
    texts = tuple(text for placed in sheet.parts for text in part_texts(placed.placed))
    return _svg(sheet.w, sheet.h, title, paths, texts, stroke)


def part_svg(part: Part) -> str:
    """One part as a standalone SVG, its extent moved to the origin and the page cut to
    it. Engravings ride along; the extent is the shape's."""
    box = bbox(part.shape)
    at_origin = moved_part(part, translation(Vector(-box.x0, -box.y0)))
    return _svg(box.w, box.h, str(part.label), part_paths(at_origin), part_texts(at_origin))


def _svg(
    w: float,
    h: float,
    title: str,
    paths: tuple[SvgPath, ...],
    texts: tuple[SvgText, ...],
    stroke_mm: float = _STROKE_MM,
) -> str:
    cuts = tuple(p for p in paths if p.kind != "engrave")
    engraves = tuple(p for p in paths if p.kind == "engrave")
    stroke = _num(stroke_mm)
    lines = (
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{_num(w)}mm"'
        f' height="{_num(h)}mm" viewBox="0 0 {_num(w)} {_num(h)}">',
        f"<title>{_escape(title)}</title>",
        f'<g transform="translate(0 {_num(h)}) scale(1 -1)">',
        f'<g id="cut" stroke="{_CUT_COLOUR}" stroke-width="{stroke}" fill="none">',
        *(_path_element(p) for p in cuts),
        "</g>",
        f'<g id="engrave" stroke="{_ENGRAVE_COLOUR}" stroke-width="{stroke}" fill="none">',
        *(_path_element(p) for p in engraves),
        *(_text_element(t) for t in texts),
        "</g>",
        "</g>",
        "</svg>",
        "",
    )
    return "\n".join(lines)


def _path_element(p: SvgPath) -> str:
    return f'<path{_data_ref(p.ref)} data-kind="{p.kind}" d="{p.d}"/>'


def _text_element(t: SvgText) -> str:
    """Lettering sits inside the Y-up group, so it carries a flip of its own to stand
    the glyphs back up; it is filled rather than stroked so small type stays readable."""
    return (
        f'<text{_data_ref(t.ref)} data-kind="engrave"'
        f' transform="translate({_num(t.x)} {_num(t.y)}) scale(1 -1)"'
        f' font-size="{_num(t.size)}" font-family="sans-serif"'
        f' fill="{_ENGRAVE_COLOUR}" stroke="none">{_escape(t.text)}</text>'
    )


def _data_ref(ref: Ref | None) -> str:
    return "" if ref is None else f' data-ref="{_escape(ref)}"'


def _escape(text: str) -> str:
    out = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return out.replace('"', "&quot;").replace("'", "&apos;")


# ---- dxf -----------------------------------------------------------------------------


def sheet_dxf(sheet: Sheet) -> str:
    """One nested sheet as minimal R12 ASCII DXF in millimetres.

    Outlines and holes go on layer ``CUT``, engravings on ``ENGRAVE``. Every wire is one
    ``POLYLINE`` of ``VERTEX`` records with arcs flattened to chords, and every line of
    lettering is one ``TEXT``.
    """
    out = [_dxf_head()]
    for placed in sheet.parts:
        out += _part_entities(placed.placed)
    out.append(_dxf_tail())
    return "".join(out)


def _part_entities(part: Part) -> tuple[str, ...]:
    """One part's DXF entities, in the order :func:`part_paths` names its wires: the shape's
    outline and holes on ``CUT``, then the engraved wires and the lettering on ``ENGRAVE``."""
    cuts = tuple(_polyline(_ring(w), _CUT_LAYER) for w in _cut_wires(part.shape))
    scores = tuple(_polyline(_ring(w), _ENGRAVE_LAYER) for w in _engraved_wires(part))
    return (*cuts, *scores, *(_text_entity(t) for t in part_texts(part)))


def _cut_wires(shape: Shape) -> tuple[Wire, ...]:
    """Every wire of a shape that gets cut: a face's outline then its holes. A solid has
    none - see :func:`_shape_paths`."""
    match shape:
        case Face(_, outer, inner, _):
            return (outer, *inner)
        case Solid():
            return ()
        case _:
            assert_never(shape)


def _engraved_wires(part: Part) -> tuple[Wire, ...]:
    """The part's engraved wires; its lettering is :func:`part_texts`' business."""
    out: list[Wire] = []
    for engraving in part.engravings:
        match engraving:
            case Wire():
                out.append(engraving)
            case Text():
                continue
            case _:
                assert_never(engraving)
    return tuple(out)


def _pair(code: int, value: str) -> str:
    return f"{code}\n{value}\n"


def _dxf_head() -> str:
    return "".join(
        (
            _pair(0, "SECTION"),
            _pair(2, "HEADER"),
            _pair(9, "$ACADVER"),
            _pair(1, "AC1009"),
            _pair(9, "$INSUNITS"),
            _pair(70, "4"),
            _pair(0, "ENDSEC"),
            _pair(0, "SECTION"),
            _pair(2, "TABLES"),
            _pair(0, "TABLE"),
            _pair(2, "LAYER"),
            _pair(70, "2"),
            _layer(_CUT_LAYER, 1),
            _layer(_ENGRAVE_LAYER, 5),
            _pair(0, "ENDTAB"),
            _pair(0, "ENDSEC"),
            _pair(0, "SECTION"),
            _pair(2, "ENTITIES"),
        )
    )


def _dxf_tail() -> str:
    return "".join((_pair(0, "ENDSEC"), _pair(0, "EOF")))


def _layer(name: str, colour: int) -> str:
    return "".join(
        (
            _pair(0, "LAYER"),
            _pair(2, name),
            _pair(70, "0"),
            _pair(62, str(colour)),
            _pair(6, "CONTINUOUS"),
        )
    )


def _polyline(ring: _Ring, layer: str) -> str:
    head = (
        _pair(0, "POLYLINE"),
        _pair(8, layer),
        _pair(66, "1"),
        _pair(70, "1" if ring.closed else "0"),
        _pair(10, "0.0"),
        _pair(20, "0.0"),
        _pair(30, "0.0"),
    )
    body = tuple(
        "".join(
            (
                _pair(0, "VERTEX"),
                _pair(8, layer),
                _pair(10, _dxf_num(x)),
                _pair(20, _dxf_num(y)),
                _pair(30, "0.0"),
            )
        )
        for x, y in ring.points
    )
    return "".join((*head, *body, _pair(0, "SEQEND"), _pair(8, layer)))


def _text_entity(t: SvgText) -> str:
    return "".join(
        (
            _pair(0, "TEXT"),
            _pair(8, _ENGRAVE_LAYER),
            _pair(10, _dxf_num(t.x)),
            _pair(20, _dxf_num(t.y)),
            _pair(30, "0.0"),
            _pair(40, _dxf_num(t.size)),
            _pair(1, t.text),
        )
    )


# ---- topology flattened to points -----------------------------------------------------


class _Ring(NamedTuple):
    """One wire as plain points, arcs already flattened to chords."""

    points: tuple[tuple[float, float], ...]
    closed: bool


def _ring(w: Wire) -> _Ring:
    """``w`` as points in world X and Y: every corner it turns, plus a chord every
    :func:`~bench.topology.chord_step` around an arc.

    A closed ring does not repeat its first point - a DXF polyline says it is closed with a
    flag, so the walk back to the start is already in the flag.
    """
    start = curve_start(w.edges[0].curve)
    points = [(start.x, start.y)]
    for e in w.edges:
        points += _chords(e.curve)
    closed = is_closed(w)
    if closed and len(points) > 1 and math.dist(points[0], points[-1]) < TOL:
        points.pop()
    return _Ring(tuple(points), closed)


def _chords(c: Curve) -> tuple[tuple[float, float], ...]:
    """The points after a curve's start, the last of them its end: one for a straight edge,
    and as many as :func:`~bench.topology.chord_step` asks for around an arc or a whole
    circle."""
    match c:
        case Line(_, end):
            return ((end.x, end.y),)
        case Arc(centre, r, a0, a1, on):
            return _swept(centre, r, on, a0, a1 - a0)
        case Circle(centre, r, on):
            return _swept(centre, r, on, 0.0, 2 * math.pi)
        case _:
            assert_never(c)


def _swept(
    centre: Point, r: float, on: Plane, a0: float, span: float
) -> tuple[tuple[float, float], ...]:
    """``span`` radians of a circle about ``centre``, as the points after ``a0``."""
    steps = max(1, math.ceil(abs(span) / chord_step(r)))
    walked = tuple(_at_angle(centre, r, on, a0 + span * k / steps) for k in range(1, steps + 1))
    return tuple((p.x, p.y) for p in walked)


def _at_angle(centre: Point, r: float, on: Plane, theta: float) -> Point:
    return centre + on.x_dir * (r * math.cos(theta)) + on.y_dir * (r * math.sin(theta))


# ---- small helpers -------------------------------------------------------------------


def _ref(prefix: str, label: Label | None) -> Ref | None:
    return None if label is None else Ref(under(prefix, label))


def _num(value: float) -> str:
    """A millimetre as short as it can be written without losing a micron."""
    text = f"{value:.4f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _dxf_num(value: float) -> str:
    return f"{value:.6f}"


# ---- what a printer reads --------------------------------------------------------------


def as_printed(mesh: Mesh, up: Vector, bed_along: Vector | None = None) -> Mesh:
    """``mesh`` turned to lie on the bed the way ``up`` says it prints, not however an
    assembly posed it: rotated so ``up`` becomes +Z, then moved so its lowest point sits at
    z = 0. This is what :mod:`bench.views` writes into every STL and 3MF object instead of
    the posed mesh a kernel actually built - a part mated upside down still prints the way it
    was authored to (decision-10; :func:`bench.mate.oriented` is what keeps ``up`` itself
    honest through a move).

    ``bed_along`` is the X of the face an :class:`~bench.model.Orient`'s ``bed_face`` names,
    when there is one - the turn about ``up`` that rotating ``up`` to +Z leaves free, settled
    by the face the part was authored to stand on rather than left to whichever perpendicular
    :func:`~bench.geometry.plane` would otherwise pick, so the same part turns out the same
    way every run it is exported. ``None`` leaves that turn to ``plane``'s own choice, which
    is deterministic too.

    X and Y are centred on the origin rather than left wherever the rotation put them: a
    build plate's own origin is its centre on nearly every slicer, and centring needs no
    bed size to be true, the way keeping a corner at the origin would.

    Pure: an assembly's pose never reaches this, only the direction a part prints in.
    """
    turned = _moved_mesh(mesh, to_local(plane(ORIGIN, up, bed_along)))
    if not turned.vertices:
        return turned
    xs, ys, zs = turned.vertices[0::3], turned.vertices[1::3], turned.vertices[2::3]
    shift = Vector(-(min(xs) + max(xs)) / 2.0, -(min(ys) + max(ys)) / 2.0, -min(zs))
    return _moved_mesh(turned, translation(shift))


def _moved_mesh(mesh: Mesh, t: Transform) -> Mesh:
    """``mesh`` under a rigid transform: only the vertices move, so every triangle still
    answers to the same ref and the same two other corners."""
    vertices = mesh.vertices
    moved: list[float] = []
    for i in range(0, len(vertices), 3):
        p = t @ Point(vertices[i], vertices[i + 1], vertices[i + 2])
        moved.extend((p.x, p.y, p.z))
    return replace(mesh, vertices=tuple(moved))


def stl(mesh: Mesh) -> bytes:
    """``mesh`` as a binary STL.

    Eighty bytes of header, a triangle count, and fifty bytes per triangle: a facet normal,
    three corners, and a two-byte attribute count nothing reads. Every number is a
    little-endian 32-bit float, in millimetres, in world coordinates - an STL has no unit of
    its own and every slicer assumes millimetres.

    The normal is computed from the winding rather than trusted from the mesh, so it agrees
    with the corners it is written beside; a degenerate triangle gets a zero normal, which
    the format allows and every reader takes as "work it out yourself".

    Refs do not survive: an STL is a bag of triangles with no names in it. That is what
    :func:`three_mf` and the scene's own mesh are for.
    """
    count = len(mesh.triangles) // 3
    out = bytearray(b"bench\0".ljust(_STL_HEADER, b"\0"))
    out += struct.pack("<I", count)
    for t in range(count):
        corners = tuple(_corner(mesh, mesh.triangles[3 * t + k]) for k in range(3))
        out += struct.pack("<3f", *_facet_normal(corners))
        for corner in corners:
            out += struct.pack("<3f", *corner)
        out += struct.pack("<H", 0)
    return bytes(out)


def three_mf(objects: Sequence[tuple[str, Mesh]]) -> bytes:
    """``objects`` - a name and a mesh each - as a 3MF package.

    A zip of exactly three entries: the content types, the root relationship, and the model
    itself in ``3D/3dmodel.model`` with ``unit="millimeter"``, one ``<object>`` per part
    carrying its name, and one ``<build><item>`` per object so every part is actually placed.
    Nothing else goes in. In particular no ``project_settings.config`` or
    ``slice_info.config``: those are one slicer's settings for one printer, and writing them
    means telling a maker how to print a thing we were only asked to describe.

    Vertex indices are per object, as the format wants, so the meshes do not have to be
    merged or renumbered against each other.
    """
    model = _model_xml(objects)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in (
            ("[Content_Types].xml", _CONTENT_TYPES),
            ("_rels/.rels", _RELATIONSHIPS),
            ("3D/3dmodel.model", model),
        ):
            entry = zipfile.ZipInfo(name, _ZIP_STAMP)
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, text.encode("utf-8"))
    return buffer.getvalue()


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels"'
    ' ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="model"'
    ' ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
    "</Types>\n"
)

_RELATIONSHIPS = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rel0" Target="/3D/3dmodel.model"'
    ' Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
    "</Relationships>\n"
)

_MODEL_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"


def _model_xml(objects: Sequence[tuple[str, Mesh]]) -> str:
    """The ``3dmodel.model`` part: the resources, then the build that places them.

    Object ids start at one because zero is not a legal 3MF resource id.
    """
    resources = tuple(_object_xml(i + 1, name, mesh) for i, (name, mesh) in enumerate(objects))
    items = tuple(f'<item objectid="{i + 1}"/>' for i in range(len(objects)))
    return "".join(
        (
            '<?xml version="1.0" encoding="UTF-8"?>\n',
            f'<model unit="millimeter" xml:lang="en-US" xmlns="{_MODEL_NS}">',
            "<resources>",
            *resources,
            "</resources>",
            "<build>",
            *items,
            "</build>",
            "</model>\n",
        )
    )


def _object_xml(number: int, name: str, mesh: Mesh) -> str:
    vertices = "".join(
        f'<vertex x="{_num(mesh.vertices[i])}" y="{_num(mesh.vertices[i + 1])}"'
        f' z="{_num(mesh.vertices[i + 2])}"/>'
        for i in range(0, len(mesh.vertices), 3)
    )
    triangles = "".join(
        f'<triangle v1="{mesh.triangles[i]}" v2="{mesh.triangles[i + 1]}"'
        f' v3="{mesh.triangles[i + 2]}"/>'
        for i in range(0, len(mesh.triangles), 3)
    )
    return (
        f'<object id="{number}" type="model" name="{_escape(name)}">'
        f"<mesh><vertices>{vertices}</vertices>"
        f"<triangles>{triangles}</triangles></mesh></object>"
    )


def _corner(mesh: Mesh, vertex: int) -> tuple[float, float, float]:
    at = 3 * vertex
    return (mesh.vertices[at], mesh.vertices[at + 1], mesh.vertices[at + 2])


def _facet_normal(
    corners: tuple[tuple[float, float, float], ...],
) -> tuple[float, float, float]:
    """The unit normal of a triangle read off its own winding, or zeroes for one with no
    area - which the format allows and readers take as "work it out yourself"."""
    a, b, c = corners
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    length = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
    if length <= 0.0:
        return (0.0, 0.0, 0.0)
    return (n[0] / length, n[1] / length, n[2] / length)
