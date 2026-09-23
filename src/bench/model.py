"""Model: the user's vocabulary. Parts with stock and process, placed into assemblies,
and refs - label paths like ``drawer-3/front/pull`` - that resolve to topology.

Labels are checked for uniqueness among siblings when a part or assembly is
built, so a ref either resolves to exactly one thing or the build fails.

Lettering lives here rather than on the topology ladder: a :class:`Text` is a string, a
place and a height, not a curve anything can be cut from, and what it belongs to is a
part's ``engravings``.

What a part is made *of* is a two-armed union: :class:`Stock` is a sheet with a thickness
and a kerf, and :class:`Printed` is a filament and a print orientation. Neither is the
other - a print has no thickness and no kerf, and ``Stock(0.0, "PLA")`` was three lies -
and :func:`process_of` reads the process off the arm rather than off a fourth field. That
union is the first half of the proposal's ``Plate | Filament | Billet``; the rest, and the
deletion of ``Part.process``, is still to come.

:class:`Material`, :class:`Orient` and :class:`Volume` live here, beside :class:`Stock`,
because they are what a part *has* and what it has to fit inside. The numbers that fill
them - PLA, PETG, ASA, the fit table, the beds - are the print domain's, in
:mod:`bench.library.print`. Records here, numbers there: that is the line, and it is what
lets :func:`bench.features.hole` compensate a bore for the filament without the core ever
importing a library.
"""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import NamedTuple, NewType, assert_never

from .fasteners import Fit
from .geometry import Plane, Point, Transform, Vector, Z, identity
from .topology import (
    Edge,
    Face,
    Label,
    Shape,
    Solid,
    SolidFace,
    Wire,
    moved,
    node_children,
    under,
)
from .topology import label as _label

Ref = NewType("Ref", str)


class Process(StrEnum):
    """How a part is made. A :class:`str` as well as an enum, because it crosses the wire
    to the app as JSON and reads there as the word itself."""

    LASER = "laser"
    PRINT = "print"
    CNC = "cnc"


@dataclass(frozen=True, slots=True)
class Text:
    """A line of lettering to draw, never to cut: ``at`` is its left baseline point
    and ``size`` its cap height."""

    text: str
    at: Point
    size: float
    label: Label | None = None


@dataclass(frozen=True, slots=True)
class Stock:
    """A sheet a part is cut out of: how thick it is, what it is, and how wide the tool's
    own cut is."""

    thickness: float
    material: str
    kerf: float = 0.0


@dataclass(frozen=True, slots=True)
class Material:
    """One filament on one machine: what it does that the geometry has to allow for.

    Every field is a physical fact about the plastic and the nozzle rather than an opinion
    about a part. ``shrink`` is the fraction a cooled part comes in by; ``hole_compensation``
    is how much a printed hole comes out *under* on diameter, so it is added back;
    ``foot`` is how far the first layer spreads, which a bottom chamfer takes off again;
    ``min_wall`` is the thinnest wall worth printing; ``max_overhang`` is the greatest angle
    a wall may lean away from the build direction, in radians; ``bridge_max`` is the longest
    unsupported span, in millimetres; ``layer`` is the layer height. ``clearances`` is the
    per-side gap each :class:`~bench.fasteners.Fit` means in this plastic, and
    :func:`bench.library.print.clearance` is how it is read.

    The record lives here, beside :class:`Stock`, because a :class:`Printed` part carries
    one. The three profiles that fill it in - ``PLA``, ``PETG``, ``ASA`` - are the print
    domain's, in :mod:`bench.library.print`, and so is every number in them.
    """

    name: str
    shrink: float
    hole_compensation: float
    foot: float
    min_wall: float
    max_overhang: float
    bridge_max: float
    layer: float
    clearances: frozendict[Fit, float]


@dataclass(frozen=True, slots=True)
class Orient:
    """Which way up a part prints.

    ``up`` is the build direction in the part's own coordinates - the way the layers stack -
    and defaults to ``+Z``, which is how nearly every part is drawn. ``bed_face`` is the ref
    of the face that lies on the bed, when the part names one; it is what an elephant's-foot
    chamfer and a first-layer check read, and it is ``None`` when nobody has said.

    Every print-aware behaviour in the package refers to this and to nothing else: a
    teardrop, a bridged top, an overhang check, the direction the layers run. Without one,
    "a horizontal hole" is a phrase with no referent, which is why
    :data:`bench.features.Top.AUTO` refuses to guess.
    """

    up: Vector = Z
    bed_face: Ref | None = None


@dataclass(frozen=True, slots=True)
class Printed:
    """What a printed part is made of: a filament and a way up.

    The second arm of :data:`Stocked`, and the small version of the proposal's
    ``Plate | Filament | Billet``: a print has no thickness and no kerf, so it is not a
    :class:`Stock` with zeroes in it. :func:`bench.features.hole` takes one of these too - the
    same record the part will carry - because a bore's diameter depends on the filament and
    its top on the orientation.
    """

    material: Material
    orient: Orient = Orient()


class Volume(NamedTuple):
    """A build volume in millimetres: how wide, how deep and how tall a machine can go.

    Beside :class:`Orient` because it is the other half of the same question - which way up
    a part stands, and what it has to stand inside. The volumes themselves, machine by
    machine, are the print domain's, in :mod:`bench.library.print`.
    """

    w: float
    d: float
    h: float


Stocked = Stock | Printed
"""What a part is made of. Two arms today; consumers ``match`` and end in
``assert_never``, so the third (a billet) cannot be added without every one of them
being written for it."""


@dataclass(frozen=True, slots=True)
class Part:
    """One piece of stock, or one printed body. ``engravings`` are drawn on it rather than
    cut out, so they are named like the shape but never kerf-compensated."""

    label: Label
    shape: Shape
    stock: Stocked
    process: Process
    engravings: tuple[Engraving, ...] = ()


@dataclass(frozen=True, slots=True)
class Placed:
    part: Part
    on: Plane


@dataclass(frozen=True, slots=True)
class Assembly:
    """Parts shown together. ``posed`` says the script has already put each one where it
    belongs relative to the others - a mechanism, not a cut list - so a viewer draws them
    at their own coordinates instead of laying them out in rows.

    It is a drawing flag and nothing else. Cut sheets, quantities and every exported file
    read ``parts`` exactly the same way either way, because none of them ever went through
    :func:`bench.stage.layout`: a part in a posed assembly is a real part, cut or printed on
    its own, and ``posed`` never means "for looking at only".
    """

    label: Label
    parts: tuple[Placed, ...]
    posed: bool = False


@dataclass(frozen=True, slots=True)
class Build:
    """What a library returns: an assembly, how many of each part to cut, and whatever else
    the thing needs to be made.

    ``assembly`` holds one :class:`Part` per *distinct* panel - a cut list rather than an
    arrangement in space - and ``quantities`` maps a part's ref to how many of it to cut.
    ``files`` is anything else a maker downloads with the cut sheets, keyed by filename: the
    OpenSCAD text for a printed baseplate, a README, a drilling schedule.
    """

    assembly: Assembly
    quantities: frozendict[Ref, int]
    files: frozendict[str, str] = frozendict()


Engraving = Wire | Text
"""What is drawn on a part rather than cut out of it."""

Named = Part | Face | Solid | SolidFace | Wire | Edge | Text

Root = Assembly | Part | Solid
"""What a ref table can be built from. A bare :class:`~bench.topology.Solid` is one of
them so a script can ask a body for its own faces - ``plane_of(plate, "top")`` - without
wrapping it in a part first."""


# ---- constructors --------------------------------------------------------------------


def part(
    label: str | Label,
    shape: Shape,
    stock: Stocked,
    process: Process | None = None,
    *,
    engravings: tuple[Engraving, ...] = (),
) -> Part:
    """A part in which every ref names exactly one thing.

    ``process`` may be left out, and then it is :func:`process_of` the stock: a sheet is
    cut and a filament is printed, and saying so twice is how the two get to disagree.
    """
    return _checked(
        Part(
            _label(label),
            shape,
            stock,
            process_of(stock) if process is None else process,
            engravings,
        )
    )


def process_of(stock: Stocked) -> Process:
    """How a part made of ``stock`` is made.

    The halfway house the proposal asks for: the process is a fact about the material, not
    a fourth field beside it, and this is where that becomes true. A sheet is cut on the
    laser by default - a billet to be milled is the arm of :data:`Stocked` that does not
    exist yet, so a script that means to mill one says so with ``Process.CNC`` itself, over a
    :class:`~bench.topology.Solid`, and :func:`bench.checks.exportable` refuses it rather
    than exporting nothing: milling is not modelled yet. ``Process.CNC`` over a
    :class:`~bench.topology.Face` is a different part of the same machine - a flat profile
    routed rather than lasered - and is exported exactly like one.
    """
    match stock:
        case Stock():
            return Process.LASER
        case Printed():
            return Process.PRINT
        case _:
            assert_never(stock)


def assembly(label: str | Label, parts: tuple[Placed, ...], *, posed: bool = False) -> Assembly:
    """An assembly in which every ref names exactly one thing.

    ``posed`` is :class:`Assembly`'s own flag: the parts are already where the script put
    them, so a viewer leaves them there.
    """
    return _checked(Assembly(_label(label), parts, posed))


def _checked[T: Assembly | Part](root: T) -> T:
    """The root itself, once every ref in it is unique.

    Raises:
        ValueError: on the first duplicate ref.
    """
    seen: set[Ref] = set()
    for ref, _ in _entries(root):
        if ref in seen:
            msg = f"duplicate ref {ref!r} in {root.label}"
            raise ValueError(msg)
        seen.add(ref)
    return root


# ---- the tree ------------------------------------------------------------------------


def _children(node: Named) -> tuple[Named, ...]:
    match node:
        case Part(_, shape, _, _, engravings):
            return (shape, *engravings)
        case Solid(recipe, _):
            return node_children(recipe, identity())
        case Face(_, outer, inner, _):
            return (outer, *inner)
        case Wire(edges, _):
            return edges
        case Edge() | SolidFace() | Text():
            return ()
        case _:
            assert_never(node)


def _walk(node: Named, prefix: str) -> Iterator[tuple[Ref, Named]]:
    """Every labelled descendant with its ref. Unlabelled nodes are transparent:
    their children keep the parent's prefix, which is what makes a part's shape
    (usually unlabelled) invisible in ``drawer-3/front``."""
    for child in _children(node):
        if child.label is None:
            yield from _walk(child, prefix)
        else:
            ref = Ref(under(prefix, child.label))
            yield ref, child
            yield from _walk(child, ref)


def refs(root: Root) -> tuple[Ref, ...]:
    """Every ref in the tree, depth-first."""
    return tuple(ref for ref, _ in _entries(root))


def index(root: Root) -> frozendict[Ref, Named]:
    """The ref table: every ref mapped to the topology it names - what a viewer or editor needs."""
    return frozendict(_entries(root))


def _entries(root: Root) -> Iterator[tuple[Ref, Named]]:
    """Every ref under a root with the thing it names.

    An assembly names each part it holds; a part and a bare solid are both roots that name
    what is under them and not themselves, so a solid's own label is the caller's prefix to
    add - which is what makes ``plate/top`` inside a part and ``top`` on its own.
    """
    match root:
        case Assembly(_, parts):
            for placed in parts:
                yield Ref(placed.part.label), placed.part
                yield from _walk(placed.part, placed.part.label)
        case Part() | Solid():
            yield from _walk(root, "")
        case _:
            assert_never(root)


def resolve(root: Root, ref: Ref) -> Named:
    """The single thing a ref names.

    Raises:
        LookupError: if nothing in the tree carries that ref.
    """
    table = index(root)
    if ref not in table:
        msg = f"no geometry named {ref!r}"
        raise LookupError(msg)
    return table[ref]


def ref(path: str) -> Ref:
    """The ref a path names - what the editor inserts when you click geometry.

    It is the path itself; the name is here so a script reads as though refs were a type,
    and so :func:`resolve` can be handed one without a cast.
    """
    return Ref(path)


# ---- transforms over a part ----------------------------------------------------------


def moved_part(part: Part, t: Transform) -> Part:
    """``part`` under a rigid transform: its shape and everything engraved on it move
    together, and every label rides along.

    Nesting and exporting both need this - a blank is moved to the origin, turned, and moved
    onto its sheet - so it lives here, once, with the record it moves.
    """
    return replace(
        part,
        shape=moved(part.shape, t),
        engravings=tuple(_moved_engraving(e, t) for e in part.engravings),
    )


def _moved_engraving(engraving: Engraving, t: Transform) -> Engraving:
    """An engraving under the same transform: a wire is topology and moves as one, and
    lettering keeps its size and its reading direction and only changes place."""
    match engraving:
        case Wire():
            return moved(engraving, t)
        case Text():
            return replace(engraving, at=t @ engraving.at)
        case _:
            assert_never(engraving)
