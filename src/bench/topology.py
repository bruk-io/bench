"""Topology: how geometry connects into shapes, and where names live.

The B-rep ladder: ``Edge`` (a curve with identity) -> ``Wire`` (a chain of edges)
-> ``Face`` (a planar region: outer wire, inner wires for holes) -> ``Solid``.
Labels are optional on every rung; a label is one path segment, and the model
layer joins them into refs with :data:`SEP`.

A ``Solid`` holds a :data:`Node`: the recipe for a body rather than its boundary. The
recipe is never evaluated here - no kernel, no mesh, no triangles - and yet
:func:`faces_of` and :func:`node_children` can say what every face of it will be called,
which is what lets the model layer hand out ``plate/top`` before anything is built.

Records are dumb; validity lives in the constructor functions (``label``, ``wire``,
``face``, ``polygon``), which are the only things here that raise.
"""

import math
from dataclasses import dataclass, replace
from enum import StrEnum
from itertools import pairwise
from typing import NamedTuple, NewType, assert_never, cast

from .geometry import (
    TOL,
    XY,
    Axis,
    Plane,
    Point,
    Transform,
    Vector,
    X,
    Y,
    Z,
    cross,
    identity,
    near,
    plane,
    rotation,
    to_world,
    unit,
)

Label = NewType("Label", str)

SEP = "/"
"""What joins labels into a ref, and so the one character a label may not hold."""


def label(text: str | Label) -> Label:
    """``text`` as one label: the name of one thing, and one segment of a ref.

    Raises:
        ValueError: if it is empty or holds a :data:`SEP`, either of which would make the
            refs under it unreadable.
    """
    if not text:
        msg = "a label cannot be empty"
        raise ValueError(msg)
    if SEP in text:
        msg = f"label {text!r} holds a {SEP!r}, which is what joins labels into a ref"
        raise ValueError(msg)
    return Label(text)


def under(prefix: str, label: Label | None) -> str:
    """``prefix`` extended by ``label``: the one rule a ref path is written by.

    An unlabelled node is transparent - its children keep the prefix - and an empty prefix is
    the label on its own. Everything that names a face, a path or a triangle joins labels
    through here, so a ref reads the same whichever of them wrote it.
    """
    if label is None:
        return prefix
    return f"{prefix}{SEP}{label}" if prefix else str(label)


def _labelled(given: str | Label | None) -> Label | None:
    """``given`` checked as a label, or ``None`` left as it is - what a record with an
    optional label needs."""
    return None if given is None else label(given)


# ---- curves: the geometry an edge follows ----------------------------------------


@dataclass(frozen=True, slots=True)
class Line:
    start: Point
    end: Point


@dataclass(frozen=True, slots=True)
class Arc:
    """Counter-clockwise from ``start_angle`` to ``end_angle`` about the plane normal."""

    centre: Point
    radius: float
    start_angle: float
    end_angle: float
    plane: Plane


@dataclass(frozen=True, slots=True)
class Circle:
    centre: Point
    radius: float
    plane: Plane


Curve = Line | Arc | Circle


def _around(centre: Point, radius: float, on: Plane, theta: float) -> Point:
    return centre + on.x_dir * (radius * math.cos(theta)) + on.y_dir * (radius * math.sin(theta))


def curve_start(c: Curve) -> Point:
    match c:
        case Line(start, _):
            return start
        case Arc(centre, r, a0, _, on):
            return _around(centre, r, on, a0)
        case Circle(centre, r, on):
            return _around(centre, r, on, 0.0)
        case _:
            assert_never(c)


def curve_end(c: Curve) -> Point:
    match c:
        case Line(_, end):
            return end
        case Arc(centre, r, _, a1, on):
            return _around(centre, r, on, a1)
        case Circle():
            return curve_start(c)
        case _:
            assert_never(c)


def curve_length(c: Curve) -> float:
    match c:
        case Line(start, end):
            return abs(end - start)
        case Arc(_, r, a0, a1, _):
            return r * abs(a1 - a0)
        case Circle(_, r, _):
            return 2 * math.pi * r
        case _:
            assert_never(c)


# ---- topology records --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Edge:
    curve: Curve
    label: Label | None = None


@dataclass(frozen=True, slots=True)
class Wire:
    edges: tuple[Edge, ...]
    label: Label | None = None


@dataclass(frozen=True, slots=True)
class Face:
    plane: Plane
    outer: Wire
    inner: tuple[Wire, ...] = ()
    label: Label | None = None


# ---- the tree a body is built as ----------------------------------------------------


class FaceRole(StrEnum):
    """What one face of a body is for. The word is the ref segment it earns."""

    TOP = "top"
    BOTTOM = "bottom"
    SIDE = "side"
    START = "start"
    END = "end"


@dataclass(frozen=True, slots=True)
class Extrude:
    """A profile swept along its own normal; a negative ``distance`` sweeps the other way."""

    profile: Face
    distance: float


@dataclass(frozen=True, slots=True)
class Revolve:
    """A profile swept about an axis lying in its own plane."""

    profile: Face
    axis: Axis
    angle: float = math.tau


@dataclass(frozen=True, slots=True)
class Union:
    a: Solid
    b: Solid


@dataclass(frozen=True, slots=True)
class Difference:
    base: Solid
    tool: Solid


@dataclass(frozen=True, slots=True)
class Intersection:
    a: Solid
    b: Solid


@dataclass(frozen=True, slots=True)
class Hull:
    """The convex hull of its parts.

    Face identity does not survive a hull - a mesh kernel builds one from a point cloud and
    hands back surfaces belonging to nothing that went in - so it is a leaf for naming: the
    whole result answers to the enclosing :class:`Solid`'s label and nothing under it. That
    the parts are unreachable as refs is the kernel's constraint written into the data.
    """

    parts: tuple[Solid, ...]


@dataclass(frozen=True, slots=True)
class Moved:
    """A subtree under a transform - what :func:`moved` records rather than does.

    The one node that takes a bare :data:`Node`: a move creates no new named thing, so it
    grows no rung and renames nothing. The transform need not be rigid; a reflection is
    recorded here too.
    """

    node: Node
    at: Transform


@dataclass(frozen=True, slots=True)
class Imported:
    """A body somebody else made, as the recipe for one: its own triangles, and nothing else.

    The one leaf that is not swept from a profile. A mesh dropped on the view - an STL a
    maker downloaded, the ``reference`` a script already has bound - is a boundary already,
    so there is nothing here to sweep and nothing to name: like :class:`Hull` it is a leaf
    for naming, and the whole of it answers to the enclosing :class:`Solid`'s label with
    nothing under it, because a file somebody else wrote has no names in it to keep.

    ``vertices`` and ``triangles`` are :class:`bench.kernel.Mesh`'s own flat layout - x, y, z
    per vertex, three vertex indices per triangle wound counter-clockwise seen from outside -
    rather than that record itself, because this layer may not see it: a ``Mesh`` carries a
    ``Ref`` per triangle and so stands above ``model``, while topology stands on ``geometry``
    alone. :func:`bench.imported.imported` is the constructor a script calls, and unpacking a
    ``Mesh`` into these two is the whole of what it does.
    """

    vertices: tuple[float, ...]
    triangles: tuple[int, ...]


Node = Extrude | Revolve | Union | Difference | Intersection | Hull | Moved | Imported
"""The recipe for a body. Eight kinds; every consumer matches and ends in ``assert_never``."""


@dataclass(frozen=True, slots=True)
class Solid:
    """A body: how it is built, and the name it answers to.

    Labels live here and nowhere else on the tree, exactly as they live on ``Edge``,
    ``Wire`` and ``Face`` and nowhere else on the 2D ladder: a node is a recipe, a solid is
    a named thing. So the combining nodes take solids as operands, and ``Moved`` - which
    names nothing new - is the one that takes a bare node.
    """

    node: Node
    label: Label | None = None


@dataclass(frozen=True, slots=True)
class Curved:
    """Where a face swept from a curved profile edge lies: the axis it turns about, how far
    off that axis it stands, and which way ``0`` points round it.

    A round face has no single plane, but it has a plane at every point of it, and this is
    what :func:`bench.solids.plane_of` builds one from: at ``a`` radians round from ``zero``
    and ``d`` millimetres along ``axis``, the surface is flat, and the tangent plane there
    is as good a place to draw a sketch as ``top`` is. ``outward`` is whether the material
    is inside - true for the side of a boss, false for the wall of a bore - which is what
    decides where that plane's normal points.

    ``axis.direction`` is the way the sweep runs, so ``along`` is measured from the
    profile's own plane into the body.
    """

    axis: Axis
    radius: float
    zero: Vector
    outward: bool = True


@dataclass(frozen=True, slots=True)
class SolidFace:
    """One named face of a solid, as the tree knows it before anything is built.

    Not geometry: nothing here says where the boundary runs, only what the face is for and
    the frame it lies in - which is all :func:`bench.solids.plane_of` reads and all a
    per-triangle tag has to carry back. ``plane`` is ``None`` for a face with no single
    plane: a revolve's side, and the wall of a hole through an extrusion. A face swept from
    an arc or a circle carries a :class:`Curved` instead, which is the same promise a turn
    at a time.
    """

    role: FaceRole
    plane: Plane | None
    label: Label
    curved: Curved | None = None


class Bounds(NamedTuple):
    """An axis-aligned extent in world X, Y and Z."""

    x0: float
    y0: float
    z0: float
    x1: float
    y1: float
    z1: float


Shape = Face | Solid


# ---- constructors: where validity is checked -----------------------------------------


def wire(edges: tuple[Edge, ...], label: str | Label | None = None) -> Wire:
    """A chain of edges, each starting where the previous one ends, and none of them
    crossing another.

    The crossing check covers wires of straight edges only; a wire holding an ``Arc`` or a
    ``Circle`` goes through unchecked, so a round feature folded through itself is still
    the caller's to avoid.

    Raises:
        ValueError: if the chain is empty, has a gap, or crosses itself.
    """
    named = _labelled(label)
    if not edges:
        msg = "a wire needs at least one edge"
        raise ValueError(msg)
    for i, (a, b) in enumerate(pairwise(edges)):
        if not near(curve_end(a.curve), curve_start(b.curve)):
            msg = f"wire has a gap between edge {i} and edge {i + 1}"
            raise ValueError(msg)
    crossing = _self_intersects(edges)
    if crossing is not None:
        i, j = crossing
        msg = f"wire crosses itself between edge {i} and edge {j}"
        raise ValueError(msg)
    return Wire(edges, named)


def _self_intersects(edges: tuple[Edge, ...]) -> tuple[int, int] | None:
    """The first pair of straight edges that cross, or ``None``.

    Every pair is tried, which is quadratic and fine at the sizes a panel has. Edges that
    meet - neighbours in the chain, or any two sharing an end - are not crossing, and
    neither is one whose end merely lands on another: an offset mitre or a bridged corner
    touches, and touching is allowed. Only interiors meeting counts.

    Crossings are read in X and Y, which is where v1's work lies; a wire standing out of
    that plane is as unchecked as a curved one.
    """
    lines: list[Line] = []
    for e in edges:
        if not isinstance(e.curve, Line):
            return None
        lines.append(e.curve)
    for i, a in enumerate(lines):
        for j in range(i + 2, len(lines)):
            b = lines[j]
            if not _shares_an_end(a, b) and _interiors_cross(a, b):
                return (i, j)
    return None


def _shares_an_end(a: Line, b: Line) -> bool:
    return any(near(p, q) for p in (a.start, a.end) for q in (b.start, b.end))


def _interiors_cross(a: Line, b: Line) -> bool:
    """Whether two straight edges meet strictly between both their ends."""
    r = a.end - a.start
    s = b.end - b.start
    den = r.x * s.y - r.y * s.x
    if abs(den) < TOL:  # parallel, or one of them too short to have a direction
        return False
    gap = b.start - a.start
    t = (gap.x * s.y - gap.y * s.x) / den
    u = (gap.x * r.y - gap.y * r.x) / den
    return TOL < t < 1.0 - TOL and TOL < u < 1.0 - TOL


def is_closed(w: Wire) -> bool:
    first, last = w.edges[0].curve, w.edges[-1].curve
    return near(curve_end(last), curve_start(first)) or isinstance(first, Circle)


def lifted(w: Wire, on: Plane) -> Wire:
    """``w``'s points read as coordinates in ``on``'s own frame, lifted into the world.

    This is what ``on=`` means: a profile is *drawn* on a plane rather than checked against
    one, so ``rect(10, 6)`` filled ``on=plane_of(plate, "top")`` lands on the plate's top
    face at the profile's own ten by six - the same numbers wherever that face happens to
    be. A wire already standing in space is moved with :func:`moved`, not lifted.

    ``XY``'s frame is the world's, so its lift is the identity and the wire itself comes
    back: every flat drawing goes through untouched, down to the object.
    """
    t = to_world(on)
    return w if t == identity() else _moved_wire(w, t)


def face(
    outer: Wire,
    *,
    holes: tuple[Wire, ...] = (),
    on: Plane = XY,
    label: str | Label | None = None,
) -> Face:
    """A planar region bounded by ``outer`` with ``holes`` in it, drawn on ``on``.

    Every bounding wire is read in ``on``'s own frame and :func:`lifted` into the world, so
    a sketch is written in the flat numbers it was designed with whatever plane it ends up
    on. Drawing on ``XY`` lifts nothing, which is what makes every flat drawing identical to
    what it was before there were any other planes to draw on.

    Raises:
        ValueError: if any bounding wire is open.
    """
    named = _labelled(label)
    for which, w in (("outer", outer), *(("inner", w) for w in holes)):
        if not is_closed(w):
            msg = f"{which} wire of a face must be closed"
            raise ValueError(msg)
    return Face(on, lifted(outer, on), tuple(lifted(w, on) for w in holes), named)


def holed(f: Face, hole: Wire) -> Face:
    """``f`` with one more hole in it, ``hole`` read in ``f``'s own frame and lifted the way
    every wire handed to :func:`face` is.

    The face's plane, outer wire and label are its own; only the list of holes grows. This
    is the second arm of :func:`bench.solids.cut` written where the checks live.

    Raises:
        ValueError: if ``hole`` is open, so it bounds nothing to take away.
    """
    if not is_closed(hole):
        msg = "a hole in a face must be closed"
        raise ValueError(msg)
    return replace(f, inner=(*f.inner, lifted(hole, f.plane)))


def polygon(points: tuple[Point, ...], label: str | Label | None = None) -> Wire:
    """A closed wire of straight edges through ``points`` in order. Being all straight, it
    is also checked for crossing itself, by :func:`wire`.

    Raises:
        ValueError: if fewer than three points are given or consecutive points coincide.
    """
    if len(points) < 3:
        msg = "a polygon needs at least three points"
        raise ValueError(msg)
    edges: list[Edge] = []
    for a, b in zip(points, (*points[1:], points[0]), strict=True):
        if near(a, b):
            msg = "consecutive polygon points coincide"
            raise ValueError(msg)
        edges.append(Edge(Line(a, b)))
    return wire(tuple(edges), label)


# ---- transforms over topology ------------------------------------------------------------


def _moved_plane(p: Plane, t: Transform) -> Plane:
    return plane(t @ p.origin, t @ p.normal, t @ p.x_dir)


def _moved_curve(c: Curve, t: Transform) -> Curve:
    match c:
        case Line(start, end):
            return Line(t @ start, t @ end)
        case Arc(centre, r, a0, a1, p):
            return Arc(t @ centre, r, a0, a1, _moved_plane(p, t))
        case Circle(centre, r, p):
            return Circle(t @ centre, r, _moved_plane(p, t))
        case _:
            assert_never(c)


def _moved_wire(w: Wire, t: Transform) -> Wire:
    return replace(w, edges=tuple(replace(e, curve=_moved_curve(e.curve, t)) for e in w.edges))


def _moved_face(f: Face, t: Transform) -> Face:
    return replace(
        f,
        plane=_moved_plane(f.plane, t),
        outer=_moved_wire(f.outer, t),
        inner=tuple(_moved_wire(w, t) for w in f.inner),
    )


def moved[T: Wire | Shape](shape: T, t: Transform) -> T:
    """The shape under a rigid transform; labels ride along unchanged.

    One function over the whole ladder rather than three overloads, so a caller holding a
    ``Face | Solid`` gets a ``Face | Solid`` back without matching on it again. A wire and
    a face are moved; a solid *records* the move as a :class:`Moved` node, because a recipe
    has nothing to move until something builds it.
    """
    match shape:
        case Wire():
            return cast("T", _moved_wire(shape, t))
        case Face():
            return cast("T", _moved_face(shape, t))
        case Solid():
            return cast("T", replace(shape, node=Moved(shape.node, t)))
        case _:
            assert_never(shape)


# ---- what the tree can say about itself ----------------------------------------------

_SIDE = "side"
"""The prefix every face swept from a profile edge earns.

Load-bearing, not decoration: :func:`bench.joints.open_box` labels a panel's edges
``top``, ``bottom``, ``right`` and ``left``, so an extruded panel would have two faces
called ``top`` without it.
"""

_HOLE = "hole"
"""What an unlabelled hole wire is called, numbered by its place among the profile's."""


def node_children(node: Node, at: Transform) -> tuple[Solid | SolidFace, ...]:
    """What the model layer walks under a solid: the named bodies that went into it, and
    the named faces it will have.

    Pure and kernel-free - this is what lets ``index()`` hand out ``plate/top`` and
    ``plate/pocket/bottom`` before anything is meshed. ``at`` is the transform accumulated
    by the :class:`Moved` nodes above, so a face's plane comes out where the face will be;
    an operand of a boolean under a move comes back as a solid with that move pushed into
    its own node, which means it is an equal value rather than the identical object.

    The naming rule, in one place:

    * ``Extrude``: ``top`` at ``distance``, ``bottom`` at the profile's plane,
      ``side-<edge label or index>`` per outer-wire edge, and one face per profile hole
      wire under that wire's label (``hole-0``, ``hole-1`` ... when unlabelled). A side
      swept from an arc or a circle has no plane and carries a :class:`Curved` instead.
    * ``Revolve``: the same ``side-`` and hole faces, plus ``start`` and ``end`` when the
      angle is less than a full turn.
    * ``Union``, ``Difference``, ``Intersection``: the operands themselves, so each keeps
      its own label path - a tool labelled ``pocket`` puts its floor at ``pocket/bottom``.
    * ``Hull``: nothing. Identity does not survive a hull.
    * ``Imported``: nothing. A file somebody else wrote has no names in it to keep.
    * ``Moved``: what is under it, planes transformed; it renames nothing.
    """
    match node:
        case Extrude():
            return _extruded_faces(node, at)
        case Revolve():
            return _revolved_faces(node, at)
        case Union(a, b) | Intersection(a, b):
            return (_body_at(a, at), _body_at(b, at))
        case Difference(base, tool):
            return (_body_at(base, at), _body_at(tool, at))
        case Hull() | Imported():
            return ()
        case Moved(inner, t):
            return node_children(inner, at @ t)
        case _:
            assert_never(node)


def faces_of(solid: Solid) -> tuple[SolidFace, ...]:
    """Every named face of ``solid``'s own root node.

    A body built by a boolean has none of its own: its faces belong to its operands, which
    keep their own names. A hull has none at all.
    """
    return tuple(
        child for child in node_children(solid.node, identity()) if isinstance(child, SolidFace)
    )


def _body_at(solid: Solid, at: Transform) -> Solid:
    """``solid`` with an accumulated move pushed into its own node, so the faces under it
    come out where they will be. The identity is left alone, which is what keeps an
    unmoved tree walking the very objects a script built."""
    return solid if at == identity() else replace(solid, node=Moved(solid.node, at))


def _role_label(role: FaceRole) -> Label:
    """The ref segment a whole-face role earns: the word itself, as a plain string rather
    than the enum member, so a ref joined out of it is ordinary text."""
    return Label(role.value)


def _face_plane(p: Plane, along: float, out: float) -> Plane:
    """A plane parallel to ``p``, ``along`` millimetres up its normal, facing ``out``
    (``+1`` the way ``p`` does, ``-1`` the other way)."""
    return plane(p.origin + p.normal * along, p.normal * out, p.x_dir)


def _side_label(e: Edge, i: int) -> Label:
    return Label(f"{_SIDE}-{i if e.label is None else e.label}")


def _hole_label(w: Wire, i: int) -> Label:
    return Label(f"{_HOLE}-{i}") if w.label is None else w.label


def _swept_plane(c: Curve, on: Plane, at: Transform) -> Plane | None:
    """The plane a profile edge sweeps out along the profile's normal, or ``None`` where it
    sweeps something curved.

    Its origin is the edge's start, its X runs along the edge and its Y up the sweep, so a
    point at ``(u, v)`` on it is ``u`` along the edge and ``v`` up from the profile.
    """
    match c:
        case Line(start, end):
            along = end - start
            out = cross(along, on.normal)
            if abs(out) < TOL:
                return None
            return _moved_plane(plane(start, out, along), at)
        case Arc() | Circle():
            return None
        case _:
            assert_never(c)


def _swept_curved(c: Curve, node: Extrude, at: Transform, *, hole: bool = False) -> Curved | None:
    """The round surface a curved profile edge sweeps out, or ``None`` for a straight one.

    The axis is the edge's own centre carried along the sweep and ``zero`` the direction
    angles are measured from, so a tangent plane can be taken anywhere on it.

    Which side the material is on comes from the same rule :func:`_swept_plane` uses for a
    flat side - it is to the left of travel, so an edge walked counter-clockwise about its
    own centre has the material inside it - with one exception, and it is why ``hole`` is a
    parameter rather than something worked out: a profile's hole wire is a hole whichever way
    round it was drawn. ``circle()`` walks counter-clockwise and :func:`bench.solids.cut` puts it
    straight in as a hole, so travel says nothing there.
    """
    match c:
        case Line():
            return None
        case Arc(centre, r, a0, a1, on):
            sense = 1.0 if a1 >= a0 else -1.0
        case Circle(centre, r, on):
            sense = 1.0
        case _:
            assert_never(c)
    profile = node.profile.plane
    run = profile.normal * (1.0 if node.distance >= 0.0 else -1.0)
    sense *= 1.0 if on.normal @ profile.normal >= 0.0 else -1.0
    return Curved(
        axis=Axis(at @ centre, at @ run),
        radius=r,
        zero=at @ profile.x_dir,
        outward=False if hole else sense > 0.0,
    )


def _extruded_faces(node: Extrude, at: Transform) -> tuple[SolidFace, ...]:
    """``top``, ``bottom``, one ``side-`` per outer edge and one face per hole wire.

    ``top`` is the face at ``distance`` and ``bottom`` the one on the profile's own plane,
    whichever way the sweep runs; both normals point out of the material, so the frame of
    ``top`` is the profile's own and ``bottom``'s is that frame turned over.
    """
    on = node.profile.plane
    out = 1.0 if node.distance >= 0.0 else -1.0
    return (
        SolidFace(
            FaceRole.TOP,
            _moved_plane(_face_plane(on, node.distance, out), at),
            _role_label(FaceRole.TOP),
        ),
        SolidFace(
            FaceRole.BOTTOM,
            _moved_plane(_face_plane(on, 0.0, -out), at),
            _role_label(FaceRole.BOTTOM),
        ),
        *(
            SolidFace(
                FaceRole.SIDE,
                _swept_plane(e.curve, on, at),
                _side_label(e, i),
                _swept_curved(e.curve, node, at),
            )
            for i, e in enumerate(node.profile.outer.edges)
        ),
        *(
            SolidFace(FaceRole.SIDE, None, _hole_label(w, i), _round_hole(w, node, at))
            for i, w in enumerate(node.profile.inner)
        ),
    )


def _round_hole(w: Wire, node: Extrude, at: Transform) -> Curved | None:
    """The round surface a hole wire sweeps, when the whole wire is one arc or circle.

    A hole is walked the other way round from an outline, so the same rule that puts the
    material inside a boss puts it outside a bore: :class:`Curved` comes back with
    ``outward`` false and a normal pointing at the axis, which is out of the material.
    """
    if len(w.edges) != 1:
        return None
    return _swept_curved(w.edges[0].curve, node, at, hole=True)


def _revolved_faces(node: Revolve, at: Transform) -> tuple[SolidFace, ...]:
    """One ``side-`` per outer edge and one face per hole wire, none of them planar - even
    a straight edge sweeps a cone or a cylinder - plus ``start`` and ``end`` where a
    partial turn leaves the profile showing."""
    on = node.profile.plane
    sides = (
        *(
            SolidFace(FaceRole.SIDE, None, _side_label(e, i))
            for i, e in enumerate(node.profile.outer.edges)
        ),
        *(
            SolidFace(FaceRole.SIDE, None, _hole_label(w, i))
            for i, w in enumerate(node.profile.inner)
        ),
    )
    if node.angle >= math.tau - TOL:
        return sides
    turned = at @ rotation(node.axis, node.angle)
    out = _sweep_sense(node.profile, node.axis)
    return (
        *sides,
        SolidFace(
            FaceRole.START,
            _moved_plane(_face_plane(on, 0.0, -out), at),
            _role_label(FaceRole.START),
        ),
        SolidFace(
            FaceRole.END,
            _moved_plane(_face_plane(on, 0.0, out), turned),
            _role_label(FaceRole.END),
        ),
    )


def _sweep_sense(profile: Face, axis: Axis) -> float:
    """Which way out of the profile's own plane a positive turn about ``axis`` carries the
    material: ``+1`` the way the plane's normal points and ``-1`` the other way.

    Which side of the axis the profile sits on decides it, so one point of the profile has
    to be looked at; a profile lying on its own axis sweeps nothing and answers ``+1``.
    """
    for e in profile.outer.edges:
        motion = cross(axis.direction, curve_start(e.curve) - axis.origin)
        if abs(motion) > TOL:
            return 1.0 if motion @ profile.plane.normal > 0.0 else -1.0
    return 1.0


# ---- what a kernel builds a swept body from -------------------------------------------

CHORD = 0.05
"""How far, in millimetres, a chord may sit inside the arc it stands in for when a curve is
flattened for a machine or a kernel. One number for the whole package, so a mesh and a DXF
can never disagree about the shape of the same hole; the step it implies is driven by the
radius, so a 500 mm arc is no coarser than a 5 mm one."""


class Ring(NamedTuple):
    """One closed wire flattened to plane coordinates, with the face each step sweeps.

    ``points`` are ``(u, v)`` in the frame the ring was flattened in, walked once and not
    repeating the first. ``faces`` has one entry per point - the step running from it to the
    next - and holds the index of the :class:`SolidFace` that step sweeps, in the order
    :func:`node_children` names them. That index is the whole point of the record: a kernel
    reads a ring to build the body and reads ``faces`` to tag what it built.
    """

    points: tuple[tuple[float, float], ...]
    faces: tuple[int, ...]


def profile_frame(node: Extrude | Revolve) -> Plane:
    """Where a swept body is built: the frame a kernel puts its own result into.

    An extrusion is built on its profile's own plane and swept up the normal, so the frame
    is that plane and nothing moves. A revolve is built about its axis, so the frame stands
    on the axis with its normal along it and its X pointing at the profile - a local point
    ``(r cos t, r sin t, h)`` is then ``r`` out from the axis, turned ``t`` about it and
    ``h`` along it, which is the shape every mesh kernel's revolve hands back.
    """
    match node:
        case Extrude(profile, _):
            return profile.plane
        case Revolve(profile, axis, _):
            return plane(axis.origin, axis.direction, _radial(profile, axis))
        case _:
            assert_never(node)


def profile_rings(node: Extrude | Revolve) -> tuple[Ring, ...]:
    """The node's profile as closed rings in the 2D coordinates of :func:`profile_frame`,
    arcs cut into chords no further than :data:`CHORD` from the true curve.

    The outer wire comes first and every hole after it, and a region is read even-odd - a
    ring inside another is a hole in it whichever way round either is walked, which is what
    a :class:`Face` already means.

    For an extrusion the coordinates are the profile's own; for a revolve they are ``(r,
    h)`` - out from the axis and along it - which is the cross-section a kernel turns.
    """
    on = _flat_frame(node)
    profile = node.profile
    base = _first_side(node)
    count = len(profile.outer.edges)
    return (
        flat_ring(profile.outer, on, tuple(base + i for i in range(count))),
        *(
            flat_ring(w, on, (base + count + k,) * len(w.edges))
            for k, w in enumerate(profile.inner)
        ),
    )


def _first_side(node: Extrude | Revolve) -> int:
    """Where the ``side-`` faces start among the faces :func:`node_children` names: after
    ``top`` and ``bottom`` for an extrusion, and first of all for a revolve."""
    match node:
        case Extrude():
            return 2
        case Revolve():
            return 0
        case _:
            assert_never(node)


def _flat_frame(node: Extrude | Revolve) -> Plane:
    """The plane whose ``(u, v)`` are the coordinates :func:`profile_rings` reads in.

    For an extrusion that is the profile's own plane. For a revolve it is the frame turned
    a quarter about its own X, so that ``u`` measures out from the axis and ``v`` along it.
    """
    match node:
        case Extrude(profile, _):
            return profile.plane
        case Revolve():
            turning = profile_frame(node)
            return plane(turning.origin, cross(turning.x_dir, turning.normal), turning.x_dir)
        case _:
            assert_never(node)


def _radial(profile: Face, axis: Axis) -> Vector:
    """The direction in the profile's plane running from the axis out towards the profile.

    A kernel turns the half of the cross-section on the positive side, so which half that is
    has to be settled here. A profile lying on its own axis sweeps nothing and answers with
    either direction; one that straddles it is the caller's to avoid, as :func:`revolve`
    already says.
    """
    seed = cross(unit(axis.direction), profile.plane.normal)
    for e in profile.outer.edges:
        arm = (curve_start(e.curve) - axis.origin) @ seed
        if abs(arm) > TOL:
            return seed if arm > 0.0 else -seed
    return seed


def flat_ring(w: Wire, on: Plane, faces: tuple[int, ...]) -> Ring:
    """``w`` as a ring in ``on``'s coordinates, where ``faces[i]`` is whatever the wire's i-th
    edge owns - the face it sweeps, for a kernel; the edge's own number, for a plate - carried
    onto every chord that edge is cut into."""
    points: list[tuple[float, float]] = []
    owners: list[int] = []
    for i, e in enumerate(w.edges):
        steps = _chord_points(e.curve, on)
        points += steps
        owners += [faces[i]] * len(steps)
    return Ring(tuple(points), tuple(owners))


def _chord_points(c: Curve, on: Plane) -> list[tuple[float, float]]:
    """A curve as the points from its start up to but not including its end, so wires laid
    end to end make one ring with nothing repeated."""
    match c:
        case Line(start, _):
            return [_uv(start, on)]
        case Arc(centre, r, a0, a1, cp):
            steps = max(2, math.ceil(abs(a1 - a0) / chord_step(r)))
            walk = (a0 + (a1 - a0) * k / steps for k in range(steps))
            return [_uv(_around(centre, r, cp, theta), on) for theta in walk]
        case Circle(centre, r, cp):
            steps = max(3, math.ceil(math.tau / chord_step(r)))
            return [_uv(_around(centre, r, cp, math.tau * k / steps), on) for k in range(steps)]
        case _:
            assert_never(c)


def chord_step(radius: float) -> float:
    """The widest turn whose chord stays within :data:`CHORD` of the arc it stands in for.

    The one rule for cutting a round thing into straight ones, wherever that has to happen -
    a DXF polyline, a kernel's cross-section, the facets of a revolve - so two of them can
    never disagree about the shape of the same hole.
    """
    if radius <= CHORD:
        return math.pi
    return 2.0 * math.acos(1.0 - CHORD / radius)


def _uv(p: Point, on: Plane) -> tuple[float, float]:
    v = p - on.origin
    return (v @ on.x_dir, v @ on.y_dir)


# ---- where a shape reaches -----------------------------------------------------------


def curve_extremes(c: Curve) -> tuple[Point, ...]:
    """The points that can bound a curve on a world axis: its ends, plus wherever a round
    one turns back on X, Y or Z while it is sweeping. Every point is on the curve, so a
    bound taken over them is the curve's own."""
    match c:
        case Line(start, end):
            return (start, end)
        case Arc(centre, r, a0, a1, on):
            lo, hi = min(a0, a1), max(a0, a1)
            middle = (lo + hi) / 2
            return (
                curve_start(c),
                curve_end(c),
                *(
                    _around(centre, r, on, theta)
                    for theta in (_branch(t, middle) for t in _world_extreme_angles(on))
                    if lo - TOL <= theta <= hi + TOL
                ),
            )
        case Circle(centre, r, on):
            return tuple(_around(centre, r, on, t) for t in _world_extreme_angles(on))
        case _:
            assert_never(c)


def _world_extreme_angles(on: Plane) -> tuple[float, ...]:
    """The angles in ``on``'s own frame where a circle drawn in it turns back on a world
    axis: where world X is stationary, where Y is, where Z is, and each one's opposite.

    A point at angle ``t`` has world x ``(X @ x_dir) cos t + (X @ y_dir) sin t`` times the
    radius, which stops growing where ``tan t`` is ``(X @ y_dir) / (X @ x_dir)`` - so the
    extreme angles are the world axes projected into the frame, which for ``XY`` is the
    quarter turns and for any other frame is not. An axis square to the frame projects to
    nothing and answers zero, which is a point on the curve like any other and so bounds
    nothing wrongly.
    """
    out: list[float] = []
    for axis in (X, Y, Z):
        theta = math.atan2(axis @ on.y_dir, axis @ on.x_dir)
        out += [theta, theta + math.pi]
    return tuple(out)


def _branch(theta: float, near_to: float) -> float:
    """``theta`` shifted by whole turns to sit as close to ``near_to`` as it can."""
    return theta + math.tau * round((near_to - theta) / math.tau)


def bounds(shape: Shape) -> Bounds:
    """A bound on where ``shape`` reaches, from the tree alone - no kernel, no mesh.

    Exact for a face, an extrusion, a full revolve, a hull, an import, a move and a union -
    an import's own vertices are its boundary, so a bound read off them needs no kernel and
    is the body's own.
    Conservative twice over: a ``Difference`` is bounded by its base and an
    ``Intersection`` by its first operand, because knowing that a tool actually bit into
    the material, or that two bodies overlap at all, is the kernel's answer and not the
    tree's; and a partial revolve is bounded by the full turn it is part of. A bound that
    is too big never passes a part that will not fit on the bed, which is what a bound is
    for.

    Raises:
        ValueError: if ``shape`` holds no geometry to bound - an empty hull, or a face
            built by hand around an empty wire.
    """
    points = _shape_points(shape)
    if not points:
        msg = "an empty shape has no extent"
        raise ValueError(msg)
    xs = tuple(p.x for p in points)
    ys = tuple(p.y for p in points)
    zs = tuple(p.z for p in points)
    return Bounds(min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def _shape_points(shape: Shape) -> tuple[Point, ...]:
    match shape:
        case Face():
            return _face_points(shape, identity())
        case Solid(node, _):
            return _node_points(node, identity())
        case _:
            assert_never(shape)


def _face_points(f: Face, at: Transform) -> tuple[Point, ...]:
    return tuple(
        at @ p for w in (f.outer, *f.inner) for e in w.edges for p in curve_extremes(e.curve)
    )


def _node_points(node: Node, at: Transform) -> tuple[Point, ...]:
    match node:
        case Extrude(profile, distance):
            lift = profile.plane.normal * distance
            return tuple(at @ q for p in _face_points(profile, identity()) for q in (p, p + lift))
        case Revolve(profile, axis, _):
            return _revolved_points(profile, axis, at)
        case Union(a, b):
            return (*_node_points(a.node, at), *_node_points(b.node, at))
        case Difference(base, _):
            return _node_points(base.node, at)
        case Intersection(a, _):
            return _node_points(a.node, at)
        case Hull(parts):
            return tuple(p for one in parts for p in _node_points(one.node, at))
        case Imported(vertices, _):
            return tuple(
                at @ Point(vertices[n], vertices[n + 1], vertices[n + 2])
                for n in range(0, len(vertices), 3)
            )
        case Moved(inner, t):
            return _node_points(inner, at @ t)
        case _:
            assert_never(node)


def _revolved_points(profile: Face, axis: Axis, at: Transform) -> tuple[Point, ...]:
    """Two opposite corners of the cylinder a full turn of ``profile`` about ``axis``
    sweeps: the profile's furthest reach from the axis, spread about it over the length of
    the profile's own shadow on it."""
    swept = _face_points(profile, at)
    if not swept:
        return ()
    origin = at @ axis.origin
    along = unit(at @ axis.direction)
    arms = tuple((p - origin) @ along for p in swept)
    reach = max(abs((p - origin) - along * ((p - origin) @ along)) for p in swept)
    spread = Vector(
        reach * math.sqrt(max(0.0, 1.0 - along.x * along.x)),
        reach * math.sqrt(max(0.0, 1.0 - along.y * along.y)),
        reach * math.sqrt(max(0.0, 1.0 - along.z * along.z)),
    )
    ends = tuple(origin + along * t for t in (min(arms), max(arms)))
    return tuple(end + sign * spread for end in ends for sign in (1.0, -1.0))
