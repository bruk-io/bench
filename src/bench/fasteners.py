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
    the diameter a flat head sinks to at ``countersink_angle`` (in radians: the ISO 90
    degrees on a metric screw, 82 on an inch flat head), the cone
    :func:`~bench.features.hole` cuts for it. ``nut_across_flats`` is the nut itself,
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
45 degree overhang. The inch series' 82 degrees is :data:`COUNTERSINK_82`."""


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


# ---- imperial: wood, drywall and machine screws (task-69) --------------------------------
#
# decision-11's operation 1: the vent's #6 drywall screws had to be drawn as M4, because
# this table only had ISO metric sizes. The figures below are every one this reviewer could
# reach a published source for, in millimetres like the rest of the table (ASME's own tables
# are inch, so every number is the inch figure times 25.4, rounded to the table's own two
# decimal places):
#
# * **Major diameter, wood screw gauge.** ASME B18.6.1's own formula, D = 0.060 + 0.013 *
#   gauge. #6, #8 and #10 share it with a drywall screw - a bugle head changes the head, not
#   the thread.
# * **Clearance holes** (``close``, ``normal``, ``loose``) are ANSI/ASME B18.2.8's, the
#   inch counterpart of the metric table's ISO 273 - one designated drill per fit, for #6,
#   #8, #10 and 1/4 inch alike, so the same three columns cover the wood/drywall screws and
#   the machine screws below.
# * **Pilot and tap holes.** ASME B18.6.1 sets a wood screw's thread, not the hole it goes
#   into - pilot sizing is shop practice, not a dimensional standard (a point Wikipedia's
#   own wood-screw pilot-hole article makes explicitly). What is here is a widely
#   republished softwood/hardwood pilot chart: softwood takes the smaller hole (the wood
#   compresses round the thread without splitting) and reads as ``tap``, hardwood the
#   larger one (it splits otherwise) and reads as ``self_tap`` - the same ordering the
#   metric table's own ``tap`` < ``self_tap`` already carries, tightest first. A machine
#   screw's ``tap`` is a real ASME/ANSI B94.9 75 percent tap drill; its ``self_tap`` has no
#   inch table for driving into a printed boss either, so it is read off the one published
#   plastic self-tapping figure this reviewer found (1/4-20 into plastic, 0.228 in, about
#   91 percent of the major diameter - fasnetdirect.com's hole-size data) and carried across
#   at the same percentage, the way the metric table's own ``self_tap`` sits at a roughly
#   fixed fraction of ``diameter`` across every metric size without a per-size citation of
#   its own.
# * **Flat head, and the countersink it sinks to.** ASME B18.6.1 (wood) and ASME B18.6.3
#   (machine) both cut a flat countersunk head at 82 degrees, not the metric table's ISO 90
#   - ``COUNTERSINK_82`` below. ``flat_head_d`` is the head's own basic diameter,
#   ``countersink_d`` the table's max - the same min/max pair the metric table's own
#   ``flat_head_d`` / ``countersink_d`` already are, just never labelled as such.
# * **Socket and button heads** exist for the machine screws (ASME B18.3, a socket head cap
#   screw and a button head cap screw are real products in 8-32, 10-24 and 1/4-20) but not
#   for a wood or a drywall screw - nobody makes one with a hex socket - so
#   ``socket_head_*`` and ``button_head_*`` are ``0.0`` on :data:`WOOD_6` through
#   :data:`DRYWALL_10`. A ``counterbore=True`` or a nut trap built from a ``0.0`` column
#   fails loudly, on a cutter with no size, rather than quietly cutting a socket that was
#   never a real part.
# * **What is not here.** ``counterbore_d``, ``counterbore_depth`` and every nut column
#   (``nut_across_flats``, ``nut_trap_across_flats``, ``nut_thickness``, ``nut_trap_depth``)
#   are ``0.0`` on *every* record below, wood, drywall and machine alike. This reviewer
#   reached three different, disagreeing counterbore tables for inch socket head cap screws
#   and trusts none of them over saying so; the inch hex nut table splits awkwardly across
#   ASME B18.6.3 (8-32, 10-24) and ASME B18.2.2 (1/4 inch and up) and was not reached
#   cleanly either. task-69 asks for the screw and its hole, not its nut, so this is left at
#   nothing rather than invented: ``nut_trap()`` on one of these answers with a trap of
#   ``0.0`` across the flats, which is a check that fails rather than a number nobody
#   measured.
# * **A bugle head is not 90, or 82, degrees.** A drywall screw's bugle head is a curved
#   reflex under the head, not a plain cone, and it is not in ASME B18.6.1 or B18.6.3 at
#   all - it is ASTM C954/C1002 territory, and neither gives a single head angle the way a
#   flat head's 82 degrees is given. Trade references put the *included* angle around 60 to
#   63 degrees; :data:`DRYWALL_6`, :data:`DRYWALL_8` and :data:`DRYWALL_10` carry that
#   as ``countersink_angle`` - :data:`BUGLE`, the midpoint, flagged in its own docstring as
#   an estimate rather than a table figure - and reuse the flat head's own diameter and
#   depth, the only ones with a citation, as the closest honest stand-in for the bugle's own
#   swallow. :func:`~bench.features.hole` cuts a countersink at the screw's own
#   ``countersink_angle`` unless its ``angle`` says otherwise, so
#   ``hole(screw=DRYWALL_6, countersink=True)`` cuts the bugle's narrower cone - deeper than
#   a flat head's, to the same diameter at the surface - and ``WOOD_6`` the 82 degree one.

COUNTERSINK_82 = math.radians(82.0)
"""The included angle of a flat countersunk head in the inch series - ASME B18.6.1 (wood
screws) and ASME B18.6.3 (machine screws) both cut it at 82 degrees, not the metric table's
ISO 90 (:data:`COUNTERSINK`)."""

BUGLE = math.radians(61.5)
"""A drywall screw's bugle head, as an included angle - the midpoint of the 60 to 63 degree
range trade references give. Neither ASME B18.6.1 nor B18.6.3 covers a bugle head at all
(that is ASTM C954/C1002 territory), and this reviewer found no single table figure there
either, so this is an estimate, not a citation, and is flagged as one everywhere it is used."""


def _wood_diameter(gauge: int) -> float:
    """A wood or drywall screw's major diameter, in millimetres, from ASME B18.6.1's own
    formula: ``0.060 + 0.013 * gauge`` inches."""
    return (0.060 + 0.013 * gauge) * 25.4


WOOD_6 = Screw(
    name="#6",
    diameter=round(_wood_diameter(6), 2),
    close=3.91,
    normal=4.31,
    loose=4.70,
    tap=1.98,
    self_tap=2.38,
    socket_head_d=0.0,
    socket_head_h=0.0,
    button_head_d=0.0,
    button_head_h=0.0,
    flat_head_d=6.20,
    flat_head_h=2.11,
    counterbore_d=0.0,
    counterbore_depth=0.0,
    countersink_d=7.09,
    countersink_angle=COUNTERSINK_82,
    nut_across_flats=0.0,
    nut_trap_across_flats=0.0,
    nut_thickness=0.0,
    nut_trap_depth=0.0,
)
"""A #6 flat head wood screw. ``close``/``normal``/``loose`` are ANSI/ASME B18.2.8's
designated drills; ``tap`` is the softwood pilot (5/64 in), ``self_tap`` the hardwood one
(3/32 in) - shop practice, not a dimensional standard, per the section note above. The head
is ASME B18.6.1's flat countersunk one at 82 degrees."""

WOOD_8 = Screw(
    name="#8",
    diameter=round(_wood_diameter(8), 2),
    close=4.57,
    normal=4.98,
    loose=5.41,
    tap=2.78,
    self_tap=3.18,
    socket_head_d=0.0,
    socket_head_h=0.0,
    button_head_d=0.0,
    button_head_h=0.0,
    flat_head_d=7.42,
    flat_head_h=2.54,
    counterbore_d=0.0,
    counterbore_depth=0.0,
    countersink_d=8.43,
    countersink_angle=COUNTERSINK_82,
    nut_across_flats=0.0,
    nut_trap_across_flats=0.0,
    nut_thickness=0.0,
    nut_trap_depth=0.0,
)
"""A #8 flat head wood screw. Pilot holes are 7/64 in (softwood, ``tap``) and 1/8 in
(hardwood, ``self_tap``)."""

WOOD_10 = Screw(
    name="#10",
    diameter=round(_wood_diameter(10), 2),
    close=5.22,
    normal=5.61,
    loose=6.05,
    tap=3.18,
    self_tap=3.57,
    socket_head_d=0.0,
    socket_head_h=0.0,
    button_head_d=0.0,
    button_head_h=0.0,
    flat_head_d=8.64,
    flat_head_h=2.95,
    counterbore_d=0.0,
    counterbore_depth=0.0,
    countersink_d=9.78,
    countersink_angle=COUNTERSINK_82,
    nut_across_flats=0.0,
    nut_trap_across_flats=0.0,
    nut_thickness=0.0,
    nut_trap_depth=0.0,
)
"""A #10 flat head wood screw. Pilot holes are 1/8 in (softwood, ``tap``) and 9/64 in
(hardwood, ``self_tap``)."""

WOOD_SCREWS = (WOOD_6, WOOD_8, WOOD_10)
"""Every flat head wood screw this table carries, smallest first."""

DRYWALL_6 = Screw(
    **{
        **{f: getattr(WOOD_6, f) for f in WOOD_6.__slots__},
        "name": "#6 bugle",
        "countersink_angle": BUGLE,
    }
)
"""A #6 bugle head drywall screw. Thread, clearance and pilot holes are :data:`WOOD_6`'s
own - a bugle head changes the head, not what the screw drives into - and the head and
countersink columns are the closest cited figures available (the flat head's), not a bugle
table. ``hole(..., countersink=True)`` cuts its countersink at :data:`BUGLE` - see the
section note above."""

DRYWALL_8 = Screw(
    **{
        **{f: getattr(WOOD_8, f) for f in WOOD_8.__slots__},
        "name": "#8 bugle",
        "countersink_angle": BUGLE,
    }
)
"""A #8 bugle head drywall screw - see :data:`DRYWALL_6`."""

DRYWALL_10 = Screw(
    **{
        **{f: getattr(WOOD_10, f) for f in WOOD_10.__slots__},
        "name": "#10 bugle",
        "countersink_angle": BUGLE,
    }
)
"""A #10 bugle head drywall screw - see :data:`DRYWALL_6`."""

DRYWALL_SCREWS = (DRYWALL_6, DRYWALL_8, DRYWALL_10)
"""Every bugle head drywall screw this table carries, smallest first."""

MACHINE_8_32 = Screw(
    name="#8-32",
    diameter=4.17,
    close=4.57,
    normal=4.98,
    loose=5.41,
    tap=3.45,
    self_tap=3.80,
    socket_head_d=6.86,
    socket_head_h=4.17,
    button_head_d=7.92,
    button_head_h=2.21,
    flat_head_d=7.24,
    flat_head_h=2.54,
    counterbore_d=0.0,
    counterbore_depth=0.0,
    countersink_d=7.93,
    countersink_angle=COUNTERSINK_82,
    nut_across_flats=0.0,
    nut_trap_across_flats=0.0,
    nut_thickness=0.0,
    nut_trap_depth=0.0,
)
"""An 8-32 machine screw. ``tap`` is the ANSI 75 percent tap drill (#29); ``close``,
``normal`` and ``loose`` are ANSI/ASME B18.2.8's clearance holes, the same table the wood
screws above read; ``socket_head_*`` and ``button_head_*`` are ASME B18.3's cap screw
figures. ``self_tap`` and the nut and counterbore columns are as the section note above
says: carried at a fixed percentage or left at ``0.0`` and said so, never invented."""

MACHINE_10_24 = Screw(
    name="#10-24",
    diameter=4.83,
    close=5.22,
    normal=5.61,
    loose=6.05,
    tap=3.80,
    self_tap=4.40,
    socket_head_d=7.92,
    socket_head_h=4.83,
    button_head_d=9.17,
    button_head_h=2.57,
    flat_head_d=8.46,
    flat_head_h=2.95,
    counterbore_d=0.0,
    counterbore_depth=0.0,
    countersink_d=9.20,
    countersink_angle=COUNTERSINK_82,
    nut_across_flats=0.0,
    nut_trap_across_flats=0.0,
    nut_thickness=0.0,
    nut_trap_depth=0.0,
)
"""A 10-24 machine screw. ``tap`` is the ANSI 75 percent tap drill (#25)."""

MACHINE_1_4_20 = Screw(
    name="1/4-20",
    diameter=6.35,
    close=6.75,
    normal=7.14,
    loose=7.54,
    tap=5.11,
    self_tap=5.79,
    socket_head_d=9.53,
    socket_head_h=6.35,
    button_head_d=11.10,
    button_head_h=3.35,
    flat_head_d=11.23,
    flat_head_h=3.89,
    counterbore_d=0.0,
    counterbore_depth=0.0,
    countersink_d=12.12,
    countersink_angle=COUNTERSINK_82,
    nut_across_flats=0.0,
    nut_trap_across_flats=0.0,
    nut_thickness=0.0,
    nut_trap_depth=0.0,
)
"""A 1/4-20 machine screw. ``tap`` is the ANSI 75 percent tap drill (#7); ``self_tap``, 0.228
in, is the one figure in this section with a direct citation - a published pilot hole for a
1/4-20 self-tapping into plastic (fasnetdirect.com) - rather than a carried-over
percentage."""

MACHINE_SCREWS = (MACHINE_8_32, MACHINE_10_24, MACHINE_1_4_20)
"""Every inch machine screw this table carries, smallest first."""

IMPERIAL_SCREWS = WOOD_SCREWS + DRYWALL_SCREWS + MACHINE_SCREWS
"""Every imperial screw this table carries - what a test walks the way :data:`SCREWS` walks
the metric ones."""


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
"""The default chamfer at the mouth of a :class:`NutTrap`, in millimetres - one layer or two
of taper, which is what a nut needs to start straight.

task-75: this used to say "a nut trap or an insert bore", but :func:`~bench.features.hole`
never reads it - only :func:`nut_trap` does, and an insert bore gets no lead-in at all today.
The docstring was wrong, not the code: a lead-in on `hole()` itself is a candidate
(task-71's eased rims may cover it), not something silently already happening."""


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
