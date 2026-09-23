"""Fasteners: the hole a screw, an insert, a nut or a magnet asks for, as data.

One frozen record per size, and one function - :func:`bore` - that turns a screw and a
:class:`Fit` into a diameter. Everything here is a number somebody measured off a standard,
so this module imports nothing at all: not geometry, not topology, not a material. It is
the bottom of the layer graph beside :mod:`bench.geometry`, and it is the only place a
fastener dimension is written down.

**Every figure here is the nominal metal one.** The clearance columns are ISO 273 (close,
medium and coarse), the tap drills are for cutting a thread in metal, the head, nut and
countersink dimensions are the fastener's own. A printed hole comes out undersize - the
extruder pulls inward tracing a circle - and the compensation for that is applied *on top*
of these numbers by the material profile in :mod:`bench.library.print`, never baked in
here. That separation is the whole reason the table is a separate layer: the screw does not
change when the filament does.

**An insert is not a fit of a screw.** A heat-set insert's hole is designed from the
*insert's* outer diameter and knurl, not from the screw that goes through it, so
:class:`Insert` is keyed on the insert and :func:`bore` never answers for one. The same
goes for a nut trap and a magnet pocket: each is its own record, because each is its own
part with its own numbers.
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never


class Fit(StrEnum):
    """How tight a joint is meant to be - intent, not a number.

    The number comes later: :func:`bore` reads it off the screw for a fastener hole, and
    :func:`bench.library.print.clearance` reads it off the material for everything else -
    a lid lip, a hinge bore, a nut trap. A :class:`str` as well as an enum, because it
    crosses the wire to the app as JSON and reads there as the word itself.

    Six arms, ordered loosest-last. There is deliberately no ``SNAP``: what latches a
    snap-fit is arm length, wall count and deflection, and a gap that pretended to stand
    in for those would be a lie with a name.
    """

    INTERFERENCE = "interference"
    PRESS = "press"
    SNUG = "snug"
    SLIDE = "slide"
    CLEARANCE = "clearance"
    LOOSE = "loose"


class Contact(StrEnum):
    """The one way two parts go together that is not a gap: they touch.

    Beside :class:`Fit` rather than a seventh arm of it, because every arm of :class:`Fit`
    is a number somewhere - a column of :class:`Screw` that :func:`bore` reads, a row of
    every material's clearance table - and a touch is neither: there is no hole a screw
    makes to touch, and no plastic that needs a gap of nothing written down. A pair that is
    put face to face says ``Fit | Contact``, and :data:`CONTACT` is the arm a script
    writes.
    """

    CONTACT = "contact"


CONTACT = Contact.CONTACT
"""Two faces put together that touch - what :func:`bench.mate.mating` does when no
:class:`Fit` is asked for."""


@dataclass(frozen=True, slots=True)
class Screw:
    """One metric size, with every hole it can ask for.

    ``close``, ``normal`` and ``loose`` are ISO 273's three clearance holes; ``tap`` is the
    drill for cutting a thread in metal and ``self_tap`` the larger one for driving the
    screw straight into plastic, which is a different question and a different number.
    ``counterbore_d`` and ``counterbore_depth`` swallow a socket cap; ``countersink_d`` is
    the diameter a flat head sinks to at ``countersink_angle`` (the ISO 90 degrees, in
    radians, not the imperial 82). ``nut_across_flats`` is the nut itself,
    ``nut_trap_across_flats`` the pocket it drops into - a tenth or two wider, so it drops -
    and ``nut_trap_depth`` how deep that pocket goes, a shade more than the nut is thick so
    the nut seats rather than props the joint open.
    """

    name: str
    diameter: float
    close: float
    normal: float
    loose: float
    tap: float
    self_tap: float
    socket_head_d: float
    socket_head_h: float
    button_head_d: float
    button_head_h: float
    flat_head_d: float
    flat_head_h: float
    counterbore_d: float
    counterbore_depth: float
    countersink_d: float
    countersink_angle: float
    nut_across_flats: float
    nut_trap_across_flats: float
    nut_thickness: float
    nut_trap_depth: float


COUNTERSINK = math.radians(90.0)
"""The included angle of a countersink, in radians. 90 degrees is the ISO metric one - and
what a printed countersink wants, because it is the shallowest cone whose wall is still a
45 degree overhang. The imperial 82 degrees is not offered."""


M2 = Screw(
    name="M2",
    diameter=2.0,
    close=2.2,
    normal=2.4,
    loose=2.6,
    tap=1.6,
    self_tap=1.7,
    socket_head_d=3.8,
    socket_head_h=2.0,
    button_head_d=3.8,
    button_head_h=1.3,
    flat_head_d=4.0,
    flat_head_h=1.2,
    counterbore_d=4.3,
    counterbore_depth=2.2,
    countersink_d=4.4,
    countersink_angle=COUNTERSINK,
    nut_across_flats=4.0,
    nut_trap_across_flats=4.1,
    nut_thickness=1.6,
    nut_trap_depth=1.7,
)

M2_5 = Screw(
    name="M2.5",
    diameter=2.5,
    close=2.7,
    normal=2.9,
    loose=3.1,
    tap=2.05,
    self_tap=2.2,
    socket_head_d=4.5,
    socket_head_h=2.5,
    button_head_d=4.7,
    button_head_h=1.5,
    flat_head_d=5.0,
    flat_head_h=1.5,
    counterbore_d=5.0,
    counterbore_depth=2.7,
    countersink_d=5.5,
    countersink_angle=COUNTERSINK,
    nut_across_flats=5.0,
    nut_trap_across_flats=5.1,
    nut_thickness=2.0,
    nut_trap_depth=2.1,
)

M3 = Screw(
    name="M3",
    diameter=3.0,
    close=3.2,
    normal=3.4,
    loose=3.6,
    tap=2.5,
    self_tap=2.6,
    socket_head_d=5.5,
    socket_head_h=3.0,
    button_head_d=5.7,
    button_head_h=1.65,
    flat_head_d=6.0,
    flat_head_h=1.7,
    counterbore_d=6.2,
    counterbore_depth=3.2,
    countersink_d=6.3,
    countersink_angle=COUNTERSINK,
    nut_across_flats=5.5,
    nut_trap_across_flats=5.6,
    nut_thickness=2.4,
    nut_trap_depth=2.6,
)

M4 = Screw(
    name="M4",
    diameter=4.0,
    close=4.3,
    normal=4.5,
    loose=4.8,
    tap=3.3,
    self_tap=3.4,
    socket_head_d=7.0,
    socket_head_h=4.0,
    button_head_d=7.6,
    button_head_h=2.2,
    flat_head_d=8.0,
    flat_head_h=2.3,
    counterbore_d=7.6,
    counterbore_depth=4.2,
    countersink_d=8.4,
    countersink_angle=COUNTERSINK,
    nut_across_flats=7.0,
    nut_trap_across_flats=7.2,
    nut_thickness=3.2,
    nut_trap_depth=3.4,
)

M5 = Screw(
    name="M5",
    diameter=5.0,
    close=5.3,
    normal=5.5,
    loose=5.8,
    tap=4.2,
    self_tap=4.3,
    socket_head_d=8.5,
    socket_head_h=5.0,
    button_head_d=9.5,
    button_head_h=2.75,
    flat_head_d=10.0,
    flat_head_h=2.8,
    counterbore_d=9.2,
    counterbore_depth=5.2,
    countersink_d=10.4,
    countersink_angle=COUNTERSINK,
    nut_across_flats=8.0,
    nut_trap_across_flats=8.2,
    nut_thickness=4.0,
    nut_trap_depth=4.4,
)

M6 = Screw(
    name="M6",
    diameter=6.0,
    close=6.4,
    normal=6.6,
    loose=7.0,
    tap=5.0,
    self_tap=5.2,
    socket_head_d=10.0,
    socket_head_h=6.0,
    button_head_d=10.5,
    button_head_h=3.3,
    flat_head_d=12.0,
    flat_head_h=3.3,
    counterbore_d=10.8,
    counterbore_depth=6.2,
    countersink_d=12.6,
    countersink_angle=COUNTERSINK,
    nut_across_flats=10.0,
    nut_trap_across_flats=10.2,
    nut_thickness=5.0,
    nut_trap_depth=5.4,
)

M8 = Screw(
    name="M8",
    diameter=8.0,
    close=8.4,
    normal=9.0,
    loose=10.0,
    tap=6.8,
    self_tap=7.0,
    socket_head_d=13.0,
    socket_head_h=8.0,
    button_head_d=14.0,
    button_head_h=4.4,
    flat_head_d=16.0,
    flat_head_h=4.4,
    counterbore_d=14.0,
    counterbore_depth=8.2,
    countersink_d=16.4,
    countersink_angle=COUNTERSINK,
    nut_across_flats=13.0,
    nut_trap_across_flats=13.2,
    nut_thickness=6.5,
    nut_trap_depth=6.9,
)

SCREWS = (M2, M2_5, M3, M4, M5, M6, M8)
"""Every size in the table, smallest first - what a test walks and a menu lists."""


def bore(screw: Screw, fit: Fit) -> float:
    """The hole ``screw`` wants at ``fit``, in millimetres, before any printed compensation.

    The six fits read straight across the screw's own columns, tightest first: a metal tap
    drill is the smallest hole the screw can enter at all, the self-tap drill is the larger
    one plastic wants when the screw is to form its own thread, the nominal diameter is the
    shank exactly, and then the three ISO clearance holes. So the answer rises with the fit
    and never has to be interpolated:

    ===================== =========================== ======
    fit                   column                      M3
    ===================== =========================== ======
    ``INTERFERENCE``      ``tap`` (metal tap drill)    2.5
    ``PRESS``             ``self_tap`` (into plastic)  2.6
    ``SNUG``              ``diameter`` (the shank)     3.0
    ``SLIDE``             ``close`` clearance          3.2
    ``CLEARANCE``         ``normal`` clearance         3.4
    ``LOOSE``             ``loose`` clearance          3.6
    ===================== =========================== ======

    The ``match`` ends in :func:`~typing.assert_never`, so a seventh :class:`Fit` cannot be
    added without this function - and the column it reads - being written for it.
    """
    match fit:
        case Fit.INTERFERENCE:
            return screw.tap
        case Fit.PRESS:
            return screw.self_tap
        case Fit.SNUG:
            return screw.diameter
        case Fit.SLIDE:
            return screw.close
        case Fit.CLEARANCE:
            return screw.normal
        case Fit.LOOSE:
            return screw.loose
        case _:
            assert_never(fit)


# ---- the parts that are not screws ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class Insert:
    """A heat-set insert, keyed on the insert rather than on the screw through it.

    ``bore`` is the hole to print, and it comes from the insert's own outside diameter and
    knurl - the insert is melted into the plastic, so the wall has to be able to flow around
    it - never from a fit of the screw. ``od`` is that outside diameter and ``length`` how
    far the boss has to be deep enough for; a boss also wants at least 1.6 to 2 mm of
    plastic around the bore, or it splits as the insert goes in.
    """

    size: str
    od: float
    length: float
    bore: float


INSERT_M3 = Insert(size="M3", od=4.0, length=5.7, bore=4.2)
"""A standard-length M3 heat-set insert. The bore is the top of the review's 4.0-4.2 band:
an insert that will not seat splits the boss trying."""

INSERT_M4 = Insert(size="M4", od=5.6, length=8.1, bore=5.6)
"""A standard-length M4 heat-set insert."""

INSERT_M5 = Insert(size="M5", od=6.8, length=9.5, bore=6.8)
"""A standard-length M5 heat-set insert."""


@dataclass(frozen=True, slots=True)
class NutTrap:
    """A pocket a hex nut drops into and cannot turn in.

    ``across_flats`` is the pocket, already a couple of tenths wider than the nut itself;
    ``depth`` is how deep it goes, a shade more than the nut is thick so the nut seats
    rather than props the joint open; ``lead_in`` is the chamfer at the mouth that lets the
    nut start straight.
    """

    size: str
    across_flats: float
    depth: float
    lead_in: float


LEAD_IN = 0.4
"""The default chamfer at the mouth of a nut trap or an insert bore, in millimetres - one
layer or two of taper, which is what a nut or an insert needs to start straight."""


def nut_trap(screw: Screw, *, lead_in: float = LEAD_IN) -> NutTrap:
    """The trap ``screw``'s nut drops into, read off the screw's own nut columns.

    Built rather than tabulated, so the trap and the nut can never disagree: both columns
    are the screw's own, and the only thing this adds is the lead-in.
    """
    return NutTrap(
        size=screw.name,
        across_flats=screw.nut_trap_across_flats,
        depth=screw.nut_trap_depth,
        lead_in=lead_in,
    )


@dataclass(frozen=True, slots=True)
class Magnet:
    """A disc magnet and the pocket it is pressed into.

    ``d`` and ``h`` are the magnet; ``hole`` is the pocket, deliberately wider than the
    magnet, and ``ribs`` crush ribs of diameter ``rib_d`` stand proud inside it. The ribs
    are what hold the magnet: they are printed a fraction *under* the magnet's diameter and
    crush as it goes in, which is a press fit that survives a printer whose holes come out
    a tenth either way.
    """

    d: float
    h: float
    hole: float
    ribs: int
    rib_d: float


MAGNET_6X2 = Magnet(d=6.0, h=2.0, hole=6.5, ribs=8, rib_d=5.9)
"""The 6 by 2 mm disc every Gridfinity bin takes, with gridfinity-rebuilt's own pocket:
a 6.5 mm hole with eight crush ribs at 5.9 mm, experimentally chosen for a press fit."""
