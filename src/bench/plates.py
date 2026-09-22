"""Plates: a flat laser part as the sheet of stock it is cut from, ready to draw in 3D.

A laser part is a face and a thickness. This builds the plate the two make - the region
triangulated for its top and its bottom, and a wall up every step of every outline - with each
triangle already answering to the ref a person reads in the cut files: a wall to its edge when
the edge has a name, else to its wire, else to nothing, which means the part; the top and the
bottom to the face. A kernel would sweep the same plate and call its walls ``side-3``. The
names here are the ones the script wrote, which is why a plate is swept here and not there.

Its engravings come with it: an engraved wire as line segments, and a line of lettering as the
four corners of the box it fills, both lifted just clear of the top so they are drawn on it.

Pure, as ``meshing`` is: a part in, numbers out, no modeller anywhere - so a laser part is drawn
whether or not the browser's modeller loaded.
"""

from itertools import pairwise
from typing import NamedTuple, assert_never

from .geometry import TOL, Plane, Point
from .kernel import Mesh
from .model import Part, Ref, Stock, Text
from .ops import text_width
from .topology import Face, Wire, curve_end, flat_ring, is_closed, under
from .triangulate import signed_area, triangles

LIFT = 0.05
"""Millimetres above the top that an engraving is drawn at, so a screen never has to choose
between the plate's face and the line cut into it."""


class Marks(NamedTuple):
    """Engraved wires as line segments: six numbers a segment, one end then the other, and
    one ref a segment - ``None`` for an engraving with no name of its own."""

    segments: tuple[float, ...]
    refs: tuple[Ref | None, ...]


class Lettering(NamedTuple):
    """A line of engraved text and the box it fills on the top: four corners, twelve numbers,
    along the baseline and back along the cap height."""

    text: str
    ref: Ref | None
    corners: tuple[float, ...]


class Plate(NamedTuple):
    """A laser part's plate: its body, and what is engraved on it. Refs are the part's own,
    as a kernel's are for a body it built - the scene adds the part's label in front."""

    mesh: Mesh
    marks: Marks
    lettering: tuple[Lettering, ...]


def plate(part: Part) -> Plate | None:
    """``part`` as a plate, or ``None`` when it is not one: a body rather than a face, stock
    with no thickness to sweep, or a region with no inside to fill."""
    match part.shape, part.stock:
        case (Face() as face, Stock() as stock) if stock.thickness > TOL:
            body = _swept(face, stock.thickness)
            if body is None:
                return None
            top = stock.thickness + LIFT
            return Plate(body, _marks(part, face.plane, top), _lettering(part, face.plane, top))
        case _:
            return None


# ---- the body ----------------------------------------------------------------------------


class _Ring(NamedTuple):
    points: tuple[tuple[float, float], ...]
    owners: tuple[Ref | None, ...]
    """The ref each step of the ring answers to - the wall swept up it answers to the same."""


def _swept(face: Face, thickness: float) -> Mesh | None:
    on = face.plane
    base = under("", face.label)
    face_ref = Ref(base) if base else None
    rings = tuple(
        _ring(wire, on, base, face_ref, outline=number == 0)
        for number, wire in enumerate((face.outer, *face.inner))
    )
    found = triangles(rings[0].points, [ring.points for ring in rings[1:]])
    if not found:
        return None

    flat = [point for ring in rings for point in ring.points]
    count = len(flat)
    vertices: list[float] = []
    for height in (0.0, thickness):
        for u, v in flat:
            p = _lifted(on, u, v, height)
            vertices += (p.x, p.y, p.z)

    corners: list[int] = []
    refs: list[Ref | None] = []
    for a, b, c in found:
        # The bottom looks back down the sweep, so it is wound the other way round.
        corners += (a, c, b, a + count, b + count, c + count)
        refs += (face_ref, face_ref)

    start = 0
    for number, ring in enumerate(rings):
        steps = len(ring.points)
        # A wall faces out of the plate when its ring runs with the region on its left: an
        # outline counter-clockwise and a hole clockwise, whichever way the script drew them.
        forward = (signed_area(ring.points) > 0.0) == (number == 0)
        for k in range(steps):
            i, j = start + k, start + (k + 1) % steps
            if not forward:
                i, j = j, i
            corners += (i, j, j + count, i, j + count, i + count)
            refs += (ring.owners[k], ring.owners[k])
        start += steps
    return Mesh(vertices=tuple(vertices), triangles=tuple(corners), refs=tuple(refs))


def _ring(wire: Wire, on: Plane, base: str, face_ref: Ref | None, *, outline: bool) -> _Ring:
    """``wire`` flattened, each step owned by its edge's ref, else the wire's.

    A wire's ref is what its cut path answers to in the SVG: its own label, or - for the
    outline, which bounds the face - the face's ref, and for an unnamed hole nothing at all.
    An edge's ref hangs off its wire's when the wire is named and the face's when it is not,
    which is how :func:`bench.model.index` hands them out.
    """
    if wire.label is not None:
        wire_ref: Ref | None = Ref(under(base, wire.label))
        prefix = str(wire_ref)
    else:
        wire_ref = face_ref if outline else None
        prefix = base
    edges = tuple(
        Ref(under(prefix, edge.label)) if edge.label is not None else wire_ref
        for edge in wire.edges
    )
    flat = flat_ring(wire, on, tuple(range(len(wire.edges))))
    return _Ring(flat.points, tuple(edges[owner] for owner in flat.faces))


def _lifted(on: Plane, u: float, v: float, height: float) -> Point:
    return on.origin + on.x_dir * u + on.y_dir * v + on.normal * height


def _uv(p: Point, on: Plane) -> tuple[float, float]:
    offset = p - on.origin
    return (offset @ on.x_dir, offset @ on.y_dir)


# ---- what is engraved on it --------------------------------------------------------------


def _marks(part: Part, on: Plane, top: float) -> Marks:
    segments: list[float] = []
    refs: list[Ref | None] = []
    for engraving in part.engravings:
        match engraving:
            case Wire():
                ref = None if engraving.label is None else Ref(under("", engraving.label))
                points = list(flat_ring(engraving, on, (0,) * len(engraving.edges)).points)
                if is_closed(engraving):
                    points.append(points[0])
                else:
                    points.append(_uv(curve_end(engraving.edges[-1].curve), on))
                for (u0, v0), (u1, v1) in pairwise(points):
                    a, b = _lifted(on, u0, v0, top), _lifted(on, u1, v1, top)
                    segments += (a.x, a.y, a.z, b.x, b.y, b.z)
                    refs.append(ref)
            case Text():
                continue
            case _:
                assert_never(engraving)
    return Marks(tuple(segments), tuple(refs))


def _lettering(part: Part, on: Plane, top: float) -> tuple[Lettering, ...]:
    out: list[Lettering] = []
    for engraving in part.engravings:
        match engraving:
            case Text(text, at, size, label):
                u, v = _uv(at, on)
                width = text_width(text, size)
                corners: list[float] = []
                for du, dv in ((0.0, 0.0), (width, 0.0), (width, size), (0.0, size)):
                    p = _lifted(on, u + du, v + dv, top)
                    corners += (p.x, p.y, p.z)
                ref = None if label is None else Ref(under("", label))
                out.append(Lettering(text, ref, tuple(corners)))
            case Wire():
                continue
            case _:
                assert_never(engraving)
    return tuple(out)
