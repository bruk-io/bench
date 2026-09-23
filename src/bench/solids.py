"""Solids: the body verbs - what a sketch becomes when it is swept, and what two bodies
make of each other.

:func:`extrude` and :func:`revolve` lift a :class:`~bench.topology.Face` off its plane;
:func:`union`, :func:`common` and :func:`cut` put bodies together or take one out of
another; :func:`hull` wraps whatever it is given, which is how a kernel that cannot sweep
still builds a taper; and :func:`cuboid`, :func:`cylinder`, :func:`loft`, :func:`pocket`
and :func:`boss` are sentences a script could have written out of the others.
:func:`plane_of` is the way back down: the plane of one named face, in the frame that face
was authored in, so the next sketch is drawn in the numbers the body was.

The verbs that take a body as readily as a sketch live here rather than in
:mod:`bench.ops`, because a body is the widest of the three subjects and this is the lowest
module that knows what one is: :func:`move`, :func:`rotate`, :func:`mirror`,
:func:`pattern`, :func:`grid` and :func:`name` are one verb each whatever they are handed,
and nothing in :mod:`bench.ops` needs them.

Nothing here evaluates anything. A body is a tree - the recipe, not its boundary - so no
mesh is made and no kernel is imported; what a script gets back is the recipe, and the names
every face of it will answer to.
"""

import math
from dataclasses import replace
from typing import NamedTuple, assert_never, cast, overload

from .geometry import (
    ORIGIN,
    TOL,
    XY,
    Axis,
    Plane,
    Point,
    Transform,
    Vector,
    Z,
    cross,
    plane,
    raised,
    rotation,
    translation,
    unit,
)
from .model import Ref, Text, index
from .ops import Geom, circle, fill, rect
from .topology import (
    SEP,
    Arc,
    Circle,
    Curve,
    Curved,
    Difference,
    Edge,
    Extrude,
    Face,
    Hull,
    Intersection,
    Label,
    Line,
    Revolve,
    Shape,
    Solid,
    SolidFace,
    Union,
    Wire,
    holed,
    moved,
    wire,
)
from .topology import label as _label

Labelled = Edge | Wire | Face | Solid | Text

# ---- bodies --------------------------------------------------------------------------


def _named(given: str | Label | None) -> Label | None:
    """``given`` checked as a label, or ``None`` left as it is."""
    return None if given is None else _label(given)


def _drawn(at: Point) -> tuple[Point, Plane]:
    """A point drawn flat and the plane it is drawn on: ``at``'s height becomes the plane's,
    and the point keeps only its X and Y, because a sketch is read in the frame of the plane
    it is put on and would otherwise be lifted twice."""
    return Point(at.x, at.y, 0.0), raised(XY, at.z)


def extrude(profile: Face, distance: float, *, label: str | Label | None = None) -> Solid:
    """The body ``profile`` sweeps out ``distance`` millimetres along its own normal.

    Makes a body and nothing else: joining and cutting are their own verbs with their own
    subjects, so nothing here quietly modifies something handed in. A negative ``distance``
    sweeps the other way, which is how a tool that hangs below a surface is built.

    Its faces are ``top`` at ``distance``, ``bottom`` on the profile's own plane,
    ``side-<edge label or index>`` per outer edge, and one per hole wire.

    Raises:
        ValueError: if ``distance`` is zero, which sweeps out no body at all.
    """
    if abs(distance) < TOL:
        msg = "an extrusion needs a distance to sweep"
        raise ValueError(msg)
    return Solid(Extrude(profile, distance), _named(label))


def revolve(
    profile: Face, axis: Axis, *, angle: float = math.tau, label: str | Label | None = None
) -> Solid:
    """The body ``profile`` sweeps out turning ``angle`` radians about ``axis``.

    Its faces are ``side-<edge label or index>`` per outer edge and one per hole wire, none
    of which is planar - a straight edge sweeps a cone - plus ``start`` and ``end`` where a
    partial turn leaves the profile showing.

    Raises:
        ValueError: if ``angle`` is not a turn between nothing and a whole one, or ``axis``
            does not lie in the profile's own plane, which describes no solid. A profile
            that crosses its axis is not checked for and is the caller's to avoid.
    """
    if not TOL < angle <= math.tau + TOL:
        msg = "a revolve turns between nothing and one whole turn"
        raise ValueError(msg)
    if not _lies_in(axis, profile.plane):
        msg = "the axis of a revolve must lie in the profile's own plane"
        raise ValueError(msg)
    return Solid(Revolve(profile, axis, angle), _named(label))


def _lies_in(axis: Axis, on: Plane) -> bool:
    """Whether ``axis`` runs inside ``on``: its origin on the plane, its direction across
    the normal. A zero direction is no axis and lies in nothing."""
    if abs(axis.direction) < TOL:
        return False
    return (
        abs((axis.origin - on.origin) @ on.normal) <= TOL
        and abs(unit(axis.direction) @ on.normal) <= TOL
    )


_BOX_SIDES = (Label("front"), Label("right"), Label("back"), Label("left"))
"""What :func:`cuboid` calls the four edges of its rectangle, counter-clockwise from the
one nearest the viewer - so the box's faces read ``side-front`` and not ``side-0``."""


def cuboid(
    w: float, d: float, h: float, *, at: Point = ORIGIN, label: str | Label | None = None
) -> Solid:
    """A box ``w`` by ``d`` by ``h`` with its lower-left-front corner at ``at``.

    Sugar for extruding a labelled rectangle, so its faces read ``top``, ``bottom``,
    ``side-front``, ``side-right``, ``side-back`` and ``side-left`` under the one naming
    rule. There is no ``Box`` node: this is a sentence a script could have written itself.
    """
    corner, on = _drawn(at)
    outline = wire(
        tuple(
            replace(e, label=side)
            for e, side in zip(rect(w, d, corner).edges, _BOX_SIDES, strict=True)
        )
    )
    return extrude(fill(outline, on=on), h, label=label)


def cylinder(r: float, h: float, *, at: Point = ORIGIN, label: str | Label | None = None) -> Solid:
    """A cylinder of radius ``r`` and height ``h`` standing on ``at``.

    Its faces are ``top``, ``bottom`` and ``side-0``: the profile is one circular edge, and
    the naming rule numbers the edges it cannot name.
    """
    centre, on = _drawn(at)
    return extrude(fill(circle(r, centre), on=on), h, label=label)


def hull(*shapes: Face | Solid, label: str | Label | None = None) -> Solid:
    """The convex hull of everything given: the smallest body that wraps the lot.

    The verb the Gridfinity ecosystem is built out of, and the one this kernel needs most.
    There is no sweep here and no fillet, so a profile that changes as it rises - a base
    foot, a stacking lip, a countersink, a gusset - is written as a stack of flat slices
    with a hull round them, which is exactly how ``baseplate_scad`` already writes one in
    OpenSCAD. Every straight run between two slices comes out exact; a curve has to be
    sliced finely enough to stand in for itself.

    A :class:`~bench.topology.Face` enters as an extrusion of no height, which is the planar
    region itself and all a hull asks of it, so slices need no thickness of their own.

    Face identity does not survive a hull - a mesh kernel builds one from a point cloud -
    so the whole body answers to ``label`` and nothing under it. A shape whose faces must be
    named is built from extrusions and cuts instead.

    Raises:
        ValueError: if nothing was given to wrap.
    """
    if not shapes:
        msg = "a hull needs at least one shape to wrap"
        raise ValueError(msg)
    return Solid(Hull(tuple(_as_body(one) for one in shapes)), _named(label))


def _as_body(shape: Face | Solid) -> Solid:
    """A hull's operand as a body: a face is the planar region it bounds, which is an
    extrusion of no height."""
    match shape:
        case Face():
            return Solid(Extrude(shape, 0.0))
        case Solid():
            return shape
        case _:
            assert_never(shape)


def loft(bottom: Face, top: Face, *, label: str | Label | None = None) -> Solid:
    """The convex hull of two profiles - a taper, a draft, a chamfered rim on a convex
    outline. :func:`hull` of exactly two, under the name a maker knows it by.
    """
    return hull(bottom, top, label=label)


def union(a: Solid, b: Solid, *, label: str | Label | None = None) -> Solid:
    """``a`` and ``b`` as one body.

    Both keep their own names and their own faces, so the result has none of its own. At
    most one of them may be anonymous: two anonymous bodies would each offer a face called
    ``top``, and :func:`~bench.model.part` refuses the pair.
    """
    return Solid(Union(a, b), _named(label))


def common(a: Solid, b: Solid, *, label: str | Label | None = None) -> Solid:
    """What ``a`` and ``b`` share."""
    return Solid(Intersection(a, b), _named(label))


@overload
def cut(subject: Face, tool: Wire, *, label: str | Label) -> Face: ...
@overload
def cut(subject: Solid, tool: Solid, *, label: str | Label) -> Solid: ...
def cut(subject: Shape, tool: Wire | Solid, *, label: str | Label) -> Shape:
    """``subject`` with ``tool`` taken out of it, under ``label``.

    One sentence over the whole ladder: a wire out of a face is a hole in it, and a body
    out of a body is a pocket, a bore or a slot. Either way the *tool* takes the label as
    it enters, which is what puts a pocket's floor at ``plate/pocket/bottom`` and a hole's
    wall at ``front/vent``.

    A wire tool is read in the face's own frame and lifted onto it, the same way
    :func:`bench.ops.fill` reads a sketch, so a hole is placed in the numbers the face was drawn in
    rather than in world coordinates.

    The overloads pair each subject with the tool it can take; a script that hands a face a
    solid gets the ordinary ``TypeError`` from the record it is building, which is why
    nothing here checks it again.
    """
    match subject:
        case Face():
            return holed(subject, name(cast("Wire", tool), label))
        case Solid():
            return Solid(Difference(subject, name(cast("Solid", tool), label)))
        case _:
            assert_never(subject)


def pocket(base: Solid, profile: Face, depth: float, *, label: str | Label) -> Solid:
    """``base`` with ``profile`` sunk ``depth`` into it from the plane it was drawn on.

    Sugar over :func:`cut` and :func:`extrude`, and the thinnest tier of the vocabulary:
    the tool is ``profile`` dropped ``depth`` down its own normal and swept back up to it,
    so the pocket's floor is that tool's own ``bottom`` - ``plate/pocket/bottom`` - and its
    opening the tool's ``top``. Calling the floor ``floor`` would take a kernel, which
    would have to say which face of the tool survived the cut.

    Raises:
        ValueError: if ``depth`` is not positive; a pocket goes in.
    """
    if depth <= TOL:
        msg = "a pocket needs a positive depth"
        raise ValueError(msg)
    return cut(base, extrude(move(profile, profile.plane.normal * -depth), depth), label=label)


def boss(base: Solid, profile: Face, height: float, *, label: str | Label) -> Solid:
    """``base`` with ``profile`` standing ``height`` proud of the plane it was drawn on.

    The twin of :func:`pocket`: the boss enters the tree as a named body of its own, so its
    crown is ``plate/boss/top`` and its wall ``plate/boss/side-0``.

    Raises:
        ValueError: if ``height`` is not positive; a boss stands out.
    """
    if height <= TOL:
        msg = "a boss needs a positive height"
        raise ValueError(msg)
    return union(base, extrude(profile, height, label=label))


def plane_of(
    solid: Solid, at: str | Ref, *, around: float | None = None, along: float = 0.0
) -> Plane:
    """The plane of one named face of ``solid``, its normal pointing out of the material.

    Its frame is the one the face was authored in: a point that was ``Point(5, 5)`` on the
    profile is ``Point(5, 5)`` on ``top``, so a sketch placed ``on=plane_of(plate, "top")``
    is drawn with the same numbers the plate was. ``bottom`` faces the other way, so it is
    that frame turned over - X still runs the profile's way and Y runs backwards, which is
    what keeps a wire drawn counter-clockwise on it counter-clockwise seen from outside.

    **A round face has a plane at every point of it, and ``around`` is how you ask for one.**
    The side of a cylinder is where a set screw goes, and it has no single plane, so
    ``plane_of(collar, "side-0", around=0.0, along=6.0)`` is the plane tangent to it a turn
    of ``around`` radians round from the profile's own X and ``along`` millimetres up the
    sweep, with its origin at that point of the surface, its normal out of the material, its
    X running round the surface and its Y up the sweep - the same frame a flat side gets.
    The radius is read off the body, so the seat follows the part when the part changes.

    ``at`` is a path under the solid and may start with the solid's own label, which is
    what the editor inserts when a face is clicked; a name no face answers to is
    :func:`face_of`'s :class:`LookupError`.

    Raises:
        ValueError: if ``along`` is given without ``around``, if ``around`` is given for a
            face that is not round, or if the face has no plane and no turn to take a
            tangent at - a revolve's side, the wall of a hole with corners in it.
    """
    if around is None and abs(along) > TOL:
        msg = "along= places a sketch up a round face; give around= as well to say where"
        raise ValueError(msg)
    return _face_plane(face_of(solid, at), str(at), around, along)


def face_of(solid: Solid, at: str | Ref) -> SolidFace:
    """The named face of ``solid`` itself, as the tree knows it before anything is built:
    what it is for, and the plane - or, for a round face, the :class:`~bench.topology.Curved`
    surface - it lies in.

    What :func:`plane_of` and :func:`axis_of` both read, and what a caller asks when it has to
    know which of the two a face has: a flat face has a ``plane``, a round one a ``curved``.
    ``at`` may start with the solid's own label, as it may for :func:`plane_of`.

    Raises:
        LookupError: if no face of ``solid`` answers to ``at``.
    """
    table = index(solid)
    asked = Ref(str(at))
    under = Ref(asked.removeprefix(f"{solid.label}{SEP}")) if solid.label is not None else asked
    for key in (asked, under):
        found = table.get(key)
        if isinstance(found, SolidFace):
            return found
    msg = f"no face named {str(at)!r}"
    raise LookupError(msg)


def axis_of(solid: Solid, at: str | Ref) -> Plane:
    """The axis of one named round face of ``solid``, as a frame: its normal is the axis.

    The frame is the one the face was authored in, exactly as :func:`plane_of`'s is. Its
    origin is where the axis crosses the plane the profile was drawn on - the centre the arc
    or circle was drawn about - its normal runs the way the sweep did, into the body, and its
    X points at the face's zero, the profile's own X, from which :func:`plane_of`'s
    ``around`` is measured. So ``plane_of(pin, "side-0", around=a, along=d)`` is the plane
    tangent to the face ``a`` radians round this frame's X and ``d`` up its normal, and the
    radius between the two is read off the body.

    That X is what makes the frame more than an :class:`~bench.geometry.Axis`: a turn about
    an axis needs somewhere to be measured from, and inventing a perpendicular would move
    whenever the axis did. Nothing about which side the material is on is said here - a
    bore's axis and its pin's are the same kind of line. A name no face answers to is
    :func:`face_of`'s :class:`LookupError`.

    Raises:
        ValueError: if the face is not round - a flat face has :func:`plane_of`'s plane, and
            a revolve's side or the wall of a hole with corners in it has no one axis.
    """
    found = face_of(solid, at)
    if found.curved is None:
        told = "is flat; plane_of is its plane" if found.plane is not None else "has no one axis"
        msg = f"face {str(at)!r} {told}, and only a round face has an axis"
        raise ValueError(msg)
    curved = found.curved
    run = unit(curved.axis.direction)
    return plane(curved.axis.origin, run, curved.zero - run * (curved.zero @ run))


def _face_plane(found: SolidFace, at: str, around: float | None, along: float) -> Plane:
    """The plane a named face offers: its own, or the one tangent to it at a turn.

    Raises:
        ValueError: if what was asked for is not what the face has.
    """
    if around is not None:
        if found.curved is None:
            msg = f"face {at!r} is not round, so there is no turn to take a tangent at"
            raise ValueError(msg)
        return _tangent(found.curved, around, along)
    if found.plane is None:
        if found.curved is not None:
            msg = f"face {at!r} is round; give around= (and along=) for the plane tangent to it"
            raise ValueError(msg)
        msg = f"face {at!r} has no single plane to draw on"
        raise ValueError(msg)
    return found.plane


def _tangent(curved: Curved, around: float, along: float) -> Plane:
    """The plane touching a round face ``around`` radians from its zero and ``along``
    millimetres up its axis, normal out of the material."""
    run = unit(curved.axis.direction)
    zero = unit(curved.zero - run * (curved.zero @ run))
    quarter = cross(run, zero)
    radial = zero * math.cos(around) + quarter * math.sin(around)
    tangent = quarter * math.cos(around) - zero * math.sin(around)
    out = 1.0 if curved.outward else -1.0
    origin = curved.axis.origin + run * along + radial * curved.radius
    return plane(origin, radial * out, tangent * out)


# ---- modifiers ---------------------------------------------------------------------


def move[T: Geom](shape: T, by: Vector) -> T:
    """``shape`` displaced by ``by``."""
    return moved(shape, translation(by))


def rotate[T: Geom](shape: T, angle: float, *, about: Point | Axis = ORIGIN) -> T:
    """``shape`` turned ``angle`` radians counter-clockwise about ``about``.

    A ``Point`` means the Z axis through it - the turn a flat drawing wants, and what this
    verb used to be able to say at all. An ``Axis`` means itself, which is how a body is
    laid on its side or a profile stood up.
    """
    return moved(shape, rotation(_turning(about), angle))


def _turning(about: Point | Axis) -> Axis:
    match about:
        case Point():
            return Axis(about, Z)
        case Axis():
            return about
        case _:
            assert_never(about)


def mirror[T: Geom](shape: T, across: Axis | Plane) -> T:
    """``shape`` reflected across ``across``: an ``Axis`` means the plane that holds it and
    stands up along Z, and a ``Plane`` means itself.

    Reflection reverses a loop, so every wire is walked the other way round
    afterwards: an outline that came in counter-clockwise goes out the same. A solid is a
    recipe rather than a boundary, so it records the reflection as a move and reverses
    nothing - the one place a :class:`~bench.topology.Moved` node holds a transform that is
    not rigid.
    """
    t = _mirroring(across)
    match shape:
        case Wire():
            return cast("T", _reversed_wire(_reflected_wire(shape, t)))
        case Face():
            return cast("T", _reflected_face(shape, t))
        case Solid():
            return cast("T", moved(shape, t))
        case _:
            assert_never(shape)


def _mirroring(across: Axis | Plane) -> Transform:
    match across:
        case Axis():
            return _reflection(across)
        case Plane():
            return _reflection_in(across)
        case _:
            assert_never(across)


class Turn(NamedTuple):
    """A pattern's step as a turn rather than a move: ``angle`` radians about ``axis``.

    What makes :func:`pattern` polar without a second verb - eight crush ribs round a magnet
    pocket, six bolts round a flange - since a pattern is a step repeated either way.
    """

    axis: Axis
    angle: float


def pattern[T: Geom](shape: T, count: int, step: Vector | Turn) -> tuple[T, ...]:
    """``count`` copies of ``shape``, each one ``step`` further on than the last and the
    first where ``shape`` already is. A label gets ``-1``, ``-2`` ... appended so the
    copies keep distinct refs.

    A :class:`~bench.geometry.Vector` steps along a line and a :class:`Turn` steps round an
    axis; both are one step applied ``i`` times, which is why they are one verb.

    Raises:
        ValueError: if ``count`` is less than one.
    """
    if count < 1:
        msg = "a pattern needs at least one copy"
        raise ValueError(msg)
    return tuple(_copy(shape, _stepped(shape, step, i), i) for i in range(count))


def grid[T: Geom](shape: T, counts: tuple[int, int], steps: tuple[Vector, Vector]) -> tuple[T, ...]:
    """A rectangular grid of ``shape``: ``counts`` copies along each of ``steps``, the first
    where ``shape`` already is.

    Rows run along the first step and are stacked along the second, and the labels are **one
    flat run** - ``foot-1`` to ``foot-12`` for a four by three - rather than a pattern of
    patterns, which would name the same body ``foot-1-1`` and leave a ref that reads like a
    mistake. That is the whole reason this is a verb of its own and not two nested calls.

    Raises:
        ValueError: if either count is less than one.
    """
    across, up = counts
    if across < 1 or up < 1:
        msg = f"a grid needs at least one copy each way, not {across} by {up}"
        raise ValueError(msg)
    along, over = steps
    return tuple(
        _copy(shape, move(shape, along * float(i) + over * float(j)), j * across + i)
        for j in range(up)
        for i in range(across)
    )


def _stepped[T: Geom](shape: T, step: Vector | Turn, i: int) -> T:
    """``shape`` moved or turned ``i`` steps on."""
    match step:
        case Vector():
            return move(shape, step * float(i))
        case Turn(axis, angle):
            return rotate(shape, angle * float(i), about=axis)
        case _:
            assert_never(step)


def _copy[T: Labelled](shape: T, made: T, i: int) -> T:
    """One copy of a patterned shape under the name its place in the run earns it. An
    unlabelled shape stays unlabelled: there is no ref to keep distinct."""
    return made if shape.label is None else name(made, f"{shape.label}-{i + 1}")


def name[T: Labelled](node: T, to: str | Label) -> T:
    """``node`` under a new name; everything below it keeps the labels it had."""
    return replace(node, label=_label(to))


# ---- transforms --------------------------------------------------------------------


def _reflection_in(on: Plane) -> Transform:
    """Reflection across a plane, in its own terms."""
    return _mirror_matrix(on.normal, 2.0 * ((on.origin - ORIGIN) @ on.normal))


def _reflection(axis: Axis) -> Transform:
    """Reflection across the plane that holds ``axis`` and stands up along Z."""
    m = unit(cross(axis.direction, Z))
    return _mirror_matrix(m, 2.0 * ((axis.origin - ORIGIN) @ m))


def _mirror_matrix(m: Vector, k: float) -> Transform:
    """The Householder reflection in the plane with unit normal ``m`` that lies ``k / 2``
    along it from the origin."""
    return Transform(
        (
            (1 - 2 * m.x * m.x, -2 * m.x * m.y, -2 * m.x * m.z, k * m.x),
            (-2 * m.y * m.x, 1 - 2 * m.y * m.y, -2 * m.y * m.z, k * m.y),
            (-2 * m.z * m.x, -2 * m.z * m.y, 1 - 2 * m.z * m.z, k * m.z),
        )
    )


def _flipped(on: Plane, t: Transform) -> Plane:
    """A reflected frame: the normal is turned over so the same angles still name the
    mirrored points, which is what makes a reflected arc come out the right way."""
    return plane(t @ on.origin, -(t @ on.normal), t @ on.x_dir)


def _reflected_curve(c: Curve, t: Transform) -> Curve:
    match c:
        case Line(start, end):
            return Line(t @ start, t @ end)
        case Arc(centre, r, a0, a1, on):
            return Arc(t @ centre, r, a0, a1, _flipped(on, t))
        case Circle(centre, r, on):
            return Circle(t @ centre, r, _flipped(on, t))
        case _:
            assert_never(c)


def _reflected_wire(w: Wire, t: Transform) -> Wire:
    return replace(w, edges=tuple(replace(e, curve=_reflected_curve(e.curve, t)) for e in w.edges))


def _reversed_curve(c: Curve) -> Curve:
    match c:
        case Line(start, end):
            return Line(end, start)
        case Arc(centre, r, a0, a1, on):
            return Arc(centre, r, a1, a0, on)
        case Circle(centre, r, on):
            return Circle(centre, r, plane(on.origin, -on.normal, on.x_dir))
        case _:
            assert_never(c)


def _reversed_wire(w: Wire) -> Wire:
    edges = tuple(replace(e, curve=_reversed_curve(e.curve)) for e in reversed(w.edges))
    return replace(w, edges=edges)


def _reflected_face(f: Face, t: Transform) -> Face:
    on = f.plane
    return replace(
        f,
        plane=plane(t @ on.origin, t @ on.normal, t @ on.x_dir),
        outer=_reversed_wire(_reflected_wire(f.outer, t)),
        inner=tuple(_reversed_wire(_reflected_wire(h, t)) for h in f.inner),
    )
