"""Mate: one part's face put on another's, at the fit the pair is for.

A face already carries everything a placement needs. :func:`~bench.solids.plane_of` answers
a full frame - origin, normal out of the material, X in the face - and it is the frame the
face was *authored* in: the corner its profile was drawn from, X the way the profile ran,
and for a ``bottom`` that same frame turned over. So one face on each part places a part
fully: lay the moving face's frame on the fixed face's, normals opposed, and the whole body
follows. :func:`placing` is that move and :func:`mating` is it done to a part.

**The authored frame is the rule, and ``offset`` and ``spin`` are how it is corrected.** Two
parts drawn from the same corner - the wall vent's frame and its attachment - go together
with nothing more said. Two parts drawn from different corners do not, and nothing about a
face shows where its origin is, so the correction is written in the script where it can be
read: ``offset`` slides the moving face across the fixed one, in the fixed face's own X and
Y, and ``spin`` turns it about the fixed face's normal, counter-clockwise seen from outside
the fixed body. Nothing is snapped to a face's centre, because a centre moves every time the
face's outline does.

**The gap along the normal is the fit's.** :data:`~bench.fasteners.CONTACT` lays the faces on
each other; a :class:`~bench.fasteners.Fit` stands the moving face off by that fit's gap in
the moving part's own filament - ``material.clearances[fit]``, the very figure
:func:`bench.library.print.clearance` reads - so a slide between two faces comes out of the
same table as every other printed fit. Only a printed part has a table to read.

**One pair per mate.** A second pair - a pin in its hole beside a shoulder on its face - is
not solved for: it is a check of where the first pair put the part, which is what
``check_fit`` is. bench is not a constraint solver.

**The moved part is the part.** Its shape is the one object a script puts in its assembly
and a check measures, so a finding about the pair reaches the part by identity, the way
:mod:`bench.views` matches every finding. It is never a copy made for looking at.

**Where a part sits is not how it prints.** A body is exported exactly where the script put
it - an STL or a 3MF is the posed mesh, verbatim, as every part's has always been, and no
file is turned to its print orientation on the way out. What says which way up a part
prints is its :class:`~bench.model.Orient`, whose ``up`` is in the part's own coordinates;
move the part and those coordinates move with it. So :func:`mating` turns ``up`` by the same
rotation it moves the body with: a part mated upside down still prints the way it was
authored to, its bed face still on the bed and its overhangs still what they were, and only
its place in the assembly has changed. The exported mesh is still the posed one, and laying
it along ``up`` for the slicer is the maker's, as it is for a lid that prints upside down.

**Round faces - a bore and its pin - are the other kind of pair.** A round face has no one
plane to lay another on, but it has an axis, and :func:`~bench.solids.axis_of` answers it as
a frame the same way ``plane_of`` answers a flat face's: origin where the axis crosses the
plane the profile was drawn on, normal the way the sweep ran, X at the face's zero. A round
pair puts the moving axis on the fixed one - :func:`coaxial` - running the same way, so a
pin swept up from its foot goes into a bore from the end the bore was drawn from. A round
pair leaves two things free that a flat pair does not, and neither is guessed: ``along``
slides the moving frame up the fixed axis, and ``spin`` turns it about that axis, from the
fixed face's zero. ``offset`` has nothing to slide across and is refused, as ``along`` is on
a flat pair. A pin wanted in from the other end is a pin swept the other way.

The radial gap of a round pair is not placed - two coaxial faces are as far apart as their
radii say - so it is only *measured*, against the fit's own figure: the table's gap, what a
bore drawn with ``clearance(fit, material, concave=True)`` measures as once its wall is
meshed into chords that stand inside the circle. A pin too fat for the fit comes in tight,
or overlaps its bore, and that is the finding. The gap is measured over the length the two
round faces share and nowhere else - :class:`~bench.checks.RoundPair` is what a round mate
hands the measurement to say so - because a pin or a screw whose head or shoulder sits on
the bore's plate comes within nothing of it there, and that zero is the head's seat, not the
gap round the shank. The seat is a second pair, a flat one, and a second pair is a check:
``check_fit`` of the two at :data:`~bench.fasteners.CONTACT`, beside the mate, reports it as
the contact it is, and the mate never infers one.

Pure: a mate is geometry and a record, and the measuring - which needs a kernel - is
:mod:`bench.script`'s, which fills :attr:`Mate.fitted` in at the edge.
"""

from dataclasses import dataclass, replace
from typing import assert_never

from .checks import Fitted, RoundPair
from .fasteners import CONTACT, Contact, Fit
from .geometry import ORIGIN, TOL, Axis, Plane, Transform, Vector, rotation, to_local, to_world
from .model import Material, Orient, Part, Printed, Ref, Stock, Stocked, index, moved_part
from .solids import axis_of, face_of, plane_of
from .topology import SEP, Label, Solid

_TURNED_OVER = Transform(((1.0, 0.0, 0.0, 0.0), (0.0, -1.0, 0.0, 0.0), (0.0, 0.0, -1.0, 0.0)))
"""A frame turned over about its own X: the normal reversed, X kept, Y reversed so the frame
stays right-handed - exactly how a ``bottom`` face's frame is its ``top``'s turned over."""

UNMOVED = Vector(0.0, 0.0)
"""An ``offset`` of nothing: the moving face's origin on the fixed face's own."""


@dataclass(frozen=True, slots=True)
class Mate:
    """A part put on another by one face each, and the fit it was put there at.

    ``part`` is the moving part, moved - its shape is the body a script shows and a check
    measures, and its orientation is turned with it. ``on`` is the body it was put on, the
    very object the fixed part holds. ``gap`` is how far apart the fit asks the two faces to
    stand, in millimetres: nothing for :data:`~bench.fasteners.CONTACT`, the fit's figure
    otherwise - the gap a flat pair was put at, and the one a round pair is measured
    against.
    ``faces`` names the moving face and then the fixed one, the way the scene names them.

    ``fitted`` is what a kernel measured of the pair, and is ``None`` until the edge measures
    it - the same way a :class:`~bench.checks.Violation`'s ``line`` is filled in there -
    because this module is pure and a measurement is not. :meth:`__str__` is the sentence:
    ``attachment/base/bottom on frame/flange/top: touch, asked contact``.

    ``pair`` is the round faces and the axis they share, for a pin put in a bore - what the
    measurement reads the gap round the pin along, rather than across the whole two bodies -
    and ``None`` for a flat pair, whose gap is the nearest the two bodies come.
    """

    part: Part
    on: Solid
    fit: Fit | Contact
    gap: float
    faces: tuple[str, str]
    fitted: Fitted | None = None
    pair: RoundPair | None = None

    def __str__(self) -> str:
        moving, fixed = self.faces
        told = "not measured" if self.fitted is None else str(self.fitted)
        return f"{moving} on {fixed}: {told}"


def placing(
    fixed: Plane,
    moving: Plane,
    *,
    gap: float = 0.0,
    offset: Vector = UNMOVED,
    spin: float = 0.0,
) -> Transform:
    """The rigid move that lays ``moving`` on ``fixed``, normals opposed, ``gap`` apart.

    After it, ``moving``'s origin is ``fixed``'s moved by ``offset`` in ``fixed``'s own X and
    Y and by ``gap`` along its normal; ``moving``'s normal is ``fixed``'s reversed; and
    ``moving``'s X runs along ``fixed``'s X turned ``spin`` radians about the normal,
    counter-clockwise seen from the side the normal points to. It is ``to_world`` of that
    seat, turned over, after ``to_local`` of ``moving`` - a rotation and a translation and
    nothing else, so a body moved by it keeps its shape and every name.

    Raises:
        ValueError: if ``offset`` has a Z, which would be a gap by another name - the fit
            says how far apart the faces stand.
    """
    if abs(offset.z) > TOL:
        msg = (
            f"offset= slides a face across the one it is put on, so it has no Z, not"
            f" {offset.z}; the gap along the normal is the fit's to say"
        )
        raise ValueError(msg)
    at = fixed.origin + fixed.x_dir * offset.x + fixed.y_dir * offset.y + fixed.normal * gap
    along = rotation(Axis(ORIGIN, fixed.normal), spin) @ fixed.x_dir
    return to_world(Plane(at, fixed.normal, along)) @ _TURNED_OVER @ to_local(moving)


def coaxial(
    fixed: Plane,
    moving: Plane,
    *,
    along: float = 0.0,
    spin: float = 0.0,
) -> Transform:
    """The rigid move that puts the axis ``moving`` on the axis ``fixed``, running the same
    way - the frames :func:`~bench.solids.axis_of` answers, normal along each axis.

    After it, ``moving``'s origin is ``fixed``'s moved ``along`` millimetres up ``fixed``'s
    axis, the two normals are the same, and ``moving``'s X runs along ``fixed``'s X turned
    ``spin`` radians about the axis, counter-clockwise seen from the end the axis points to.
    Not turned over, which is where it parts from :func:`placing`: a flat face goes on
    another facing it, and a pin goes into its bore the way the bore runs.
    """
    turned = rotation(Axis(ORIGIN, fixed.normal), spin) @ fixed.x_dir
    return to_world(Plane(fixed.origin + fixed.normal * along, fixed.normal, turned)) @ to_local(
        moving
    )


def gap_of(fit: Fit | Contact, material: Material | None) -> float:
    """How far apart two faces put together at ``fit`` stand, in millimetres.

    Nothing for a contact. A :class:`~bench.fasteners.Fit`'s own figure in ``material``
    otherwise - the per-side gap :func:`bench.library.print.clearance` reads, read here off
    the same record because the core does not import a library.

    Raises:
        ValueError: if a fit is asked for with no material to read its gap from, or if the
            fit's gap in that material is not a gap at all - an interference is not something
            two flat faces can be put at, nor a gap round a pin a measurement can read, since
            bodies that share material measure zero apart however deep they share it.
    """
    match fit:
        case Contact():
            return 0.0
        case Fit():
            if material is None:
                msg = (
                    f"a {fit} fit is a gap in some plastic, and this part says none: a printed"
                    " part carries its filament, and check_fit is handed one"
                )
                raise ValueError(msg)
            gap = material.clearances[fit]
            if gap <= TOL:
                msg = (
                    f"a {fit} fit in {material.name} is {gap:.3f} mm, which no two faces stand"
                    " apart at and no measurement can read; put them together at CONTACT"
                )
                raise ValueError(msg)
            return gap
        case _:
            assert_never(fit)


def oriented(stock: Stocked, t: Transform) -> Stocked:
    """``stock`` for a part moved by ``t``: a print's way up turned with the body, so the
    part prints the way it did before it moved.

    ``Orient.up`` is in the part's own coordinates, and moving the part moves them. Only the
    rotation applies - ``up`` is a direction - and ``bed_face`` is a ref, which a move never
    renames. A sheet has no way up to turn.
    """
    match stock:
        case Printed():
            orient = stock.orient
            return replace(stock, orient=Orient(t @ orient.up, orient.bed_face))
        case Stock():
            return stock
        case _:
            assert_never(stock)


def mating(
    fixed: Solid | Part,
    at: str | Ref,
    moving: Part,
    onto: str | Ref,
    *,
    fit: Fit | Contact = CONTACT,
    offset: Vector = UNMOVED,
    spin: float = 0.0,
    along: float = 0.0,
) -> Mate:
    """``moving`` put on ``fixed``: its face ``onto`` laid on ``fixed``'s face ``at``, normals
    opposed, at ``fit`` - see :func:`placing` for ``offset`` and ``spin``.

    Or, where both faces are round, ``moving``'s axis put on ``fixed``'s - see
    :func:`coaxial` for ``along`` and ``spin`` - with the fit's gap the one the pair is
    measured against rather than one it is put at. Which kind of pair it is is read off the
    two faces, never asked: a round face has an axis and no plane, a flat one the other way
    round.

    ``at`` and ``onto`` are refs the way the scene writes them - ``frame/flange/top``, what a
    click inserts - or the same paths without the part's label. ``fixed`` may be a part or a
    bare body; ``moving`` is a part, because a part is what knows its filament (the gap a
    :class:`~bench.fasteners.Fit` means) and its way up (which turns with it). The mate is
    not measured here - :attr:`Mate.fitted` is ``None`` - because measuring needs a kernel.

    A name either part has no face by is the :class:`LookupError`, and a flat pair's face
    with no plane the :class:`ValueError`, that :func:`~bench.solids.plane_of` raises.

    Raises:
        ValueError: if either part is not a body, if a fit is asked of a part with no
            filament, if the fit is no gap, if ``offset`` has a Z, if one face is round and
            the other is not, or if a round pair is given an ``offset`` or a flat one an
            ``along``.
    """
    body, label = _held(fixed)
    shape = moving.shape
    if not isinstance(shape, Solid):
        msg = f"{moving.label} is cut from sheet, and only a body has a face to put on another"
        raise ValueError(msg)
    material = moving.stock.material if isinstance(moving.stock, Printed) else None
    gap = gap_of(fit, material)
    seat, seat_ref = _path(label, at)
    face, face_ref = _path(moving.label, onto)
    if _round(body, seat, seat_ref, shape, face, face_ref):
        if abs(offset) > TOL:
            msg = (
                f"a pin goes into its bore on the bore's axis, so there is nothing to offset=;"
                f" along= slides {face_ref} up {seat_ref}'s axis and spin= turns it about it"
            )
            raise ValueError(msg)
        axis = axis_of(body, seat)
        t = coaxial(axis, axis_of(shape, face), along=along, spin=spin)
        pair = RoundPair(axis, (_tagged(shape, face), _tagged(body, seat)))
    else:
        if abs(along) > TOL:
            msg = (
                f"along= slides a round face up the axis of the one it goes in; {seat_ref} and"
                f" {face_ref} are flat, and offset= is how one slides across the other"
            )
            raise ValueError(msg)
        t = placing(plane_of(body, seat), plane_of(shape, face), gap=gap, offset=offset, spin=spin)
        pair = None
    part = replace(moved_part(moving, t), stock=oriented(moving.stock, t))
    return Mate(part, body, fit, gap, (face_ref, seat_ref), pair=pair)


def _held(fixed: Solid | Part) -> tuple[Solid, Label | None]:
    """The body a mate is put on and the label its faces are named under.

    Raises:
        ValueError: if a part is cut from sheet, which has no face to put anything on.
    """
    match fixed:
        case Solid():
            return fixed, None
        case Part():
            if not isinstance(fixed.shape, Solid):
                msg = f"{fixed.label} is cut from sheet, and only a body has a face to put on"
                raise ValueError(msg)
            return fixed.shape, fixed.label
        case _:
            assert_never(fixed)


def _path(label: Label | None, ref: str | Ref) -> tuple[str, str]:
    """The path a face is looked up by on its body, and the ref the scene names it by.

    A scene's ref starts with the part's label and a body's own does not, so the label is
    taken off before the body is asked for the rest, and put back for the sentence.
    """
    path = str(ref)
    if label is not None:
        path = path.removeprefix(f"{label}{SEP}")
    return path, path if label is None else f"{label}{SEP}{path}"


def _tagged(solid: Solid, at: str) -> Ref:
    """The ref ``solid``'s own mesh tags the face ``at`` with: ``at`` itself where the body
    names a face so, or ``at`` without the body's own label in front - the two ways
    :func:`~bench.solids.face_of` finds a face, tried in the same order. A move renames
    nothing, so it is the same ref once the body has moved."""
    asked = Ref(at)
    if asked in index(solid) or solid.label is None:
        return asked
    return Ref(at.removeprefix(f"{solid.label}{SEP}"))


def _round(fixed: Solid, at: str, seat_ref: str, moving: Solid, onto: str, face_ref: str) -> bool:
    """Whether the two faces are a round pair - an axis each - rather than a flat one. A
    name either body has no face by is :func:`~bench.solids.face_of`'s :class:`LookupError`.

    Raises:
        ValueError: if one face is round and the other is not: a pin goes in a bore and a
            face on a face, and a round face has no plane to lay a flat one on.
    """
    seat, face = face_of(fixed, at), face_of(moving, onto)
    if (seat.curved is None) == (face.curved is None):
        return seat.curved is not None
    one, other = (seat_ref, face_ref) if seat.curved is not None else (face_ref, seat_ref)
    msg = (
        f"{one} is round and {other} is not: a round face goes on the axis of a round one,"
        " and a flat face on a flat one"
    )
    raise ValueError(msg)
