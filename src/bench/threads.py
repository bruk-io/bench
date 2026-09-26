"""Threads: a printed screw thread, as a twisted extrusion of an offset circle.

A circle drawn a little off its axis and swept up that axis turning one whole turn per
pitch is a single-start screw thread: every section of it is the same circle, turned as far
as its height says, so the crest and root run round the axis as a helix. It is the one
thread a mesh kernel builds exactly from what it already has - Manifold's extrude takes a
twist - and it prints: the profile is round, with no knife edge at the crest to lose and no
sharp root to crack from.

**What a thread is here.** :func:`thread` makes one, and :class:`Thread` says which side of
the joint it is. An ``EXTERNAL`` thread is the bolt, or the neck of a jar: material, drawn at
the nominal size with nothing taken off it. An ``INTERNAL`` thread is the cavity in the nut
or the lid: a tool a script cuts out of the part with :func:`~bench.solids.cut`, and the one
of the two the fit's clearance and the printed hole's compensation go on - the same rule
:func:`bench.library.print.clearance` states, that a gap goes on one side of a joint and not
both. Drawn round the same axis and the same ``at``, the two halves are the same helix, so a
nut designed in place on its bolt is already screwed onto it.

**The depth.** ``depth`` is how far the root sits inside the crest, radially. Twice the
circle's offset, it also decides how steep the flanks are: the steepest leans
``atan(pi * depth / pitch)`` off the axis, so :data:`ROUND_DEPTH` is the deepest round
thread whose flanks lean no more than :data:`FLANK`. It is a default worked out from
geometry, not from a print.

**The gap.** A fit's clearance is a gap measured square to the surfaces, and a thread's
flanks lean: two sections a clearance apart in the plane of the section stand closer than
that across a leaning flank. So the internal thread's section is opened by the clearance
times ``sqrt(1 + (pi * depth / pitch) ** 2)`` - what the steepest flank takes back - plus
:data:`~bench.topology.CHORD`, because the cavity is concave and its chords sag into the
gap. Before compensation that left 0.20 to 0.21 mm on the real mesh where 0.20 was asked,
and about 0.17 without the chord's allowance.

**Compensation.** The cavity is a printed hole, so it takes the material's
``hole_compensation`` exactly as :func:`~bench.features.hole` gives a printed bore: the
diameter grows by it, so the section - one circle - grows by half of it on its radius, the
same half per edge ``hole`` grows a profile by. Each layer of the cavity is traced as that
section and pulled inward in its own plane, so the growth is in that plane too and is not
opened by the flank's lean the way the clearance is: across the steepest flank it adds
``hole_compensation / 2 * cos(flank)``. So the model, measured square to its surfaces, stands
the clearance *plus* that apart - an M12 x 2 in PLA at a slide measures 0.28 mm where the
fit's 0.20 and PLA's 0.20 compensation ask for 0.20 + 0.10 * cos(40) - and it is the print
that is meant to close it back to the clearance. On a fine thread the opening can pass the
depth: an M8 x 1.25's is 0.41 mm on a thread 0.33 deep, so the model's nut clears its bolt
even pushed straight along the axis, and only the print engages it - which the ``thread``
check says, as a warning, whenever an internal thread is drawn that far open
(:func:`drawn_clear`); in PLA at a slide that is any pitch under about 1.54 mm at the
default depth. Nothing else adds
compensation to a thread, so it is added once; whether a printed thread shrinks by as much
as a printed bore does is still the table's figure, unmeasured on a thread.

**The name.** A twisted extrusion's side is named by the same rule as any other: one face
per profile edge, however many turns it makes. The section is one circle, so a thread is
three faces - ``top``, ``bottom`` and ``side-0``, the whole helical flank - and cut into a
nut under ``label="thread"`` its flank is ``nut/thread/side-0``. The flank is neither flat
nor round, so :func:`~bench.solids.plane_of` and :func:`~bench.solids.axis_of` refuse it.

**Small threads.** :data:`SMALLEST` and :data:`FINEST` are Slant 3D's figures for where a
modelled plastic thread stops working on a 0.4 mm nozzle. They are **unmeasured defaults**:
bench has printed nothing to confirm them, so a thread under either is warned about and still
built, never refused. Each warning - these two, and :func:`drawn_clear`'s - is a finding
of the ``thread`` check: logged with the
:data:`~bench.telemetry.CHECK` field, which a run records as a ``WARNING`` violation at the
script's line that asked for the thread - in the app's Problems panel and ``tools.build``'s
summary, beside what the script's own checks found. Outside a run it is a log record and
nothing more. The depth one fires on ordinary fine pitches: an M8 x 1.25 at the default depth
is 0.33 mm deep.
"""

import logging
import math
from enum import StrEnum

from .fasteners import Fit
from .geometry import ORIGIN, Point
from .model import Material
from .ops import circle, fill
from .solids import extrude, move
from .telemetry import CHECK, fields
from .topology import CHORD, Label, Solid


class Thread(StrEnum):
    """Which side of a threaded joint a thread is: the bolt's, or the nut's."""

    EXTERNAL = "external"
    INTERNAL = "internal"


FLANK = math.radians(40.0)
"""How far off the axis the default thread's steepest flank leans: ASA's rated overhang, the
least of the filaments that ship. PLA and PETG are rated for 45, and the degree or so a
mesh's facets add to a flank - measured: a thread drawn at exactly 45 meshes at 46 - stays
inside that."""

ROUND_DEPTH = math.tan(FLANK) / math.pi
"""The default depth, as a fraction of the pitch - about 0.27 - the deepest round thread whose
steepest flank leans :data:`FLANK` off the axis. Geometry, not a measured print."""

SMALLEST = 3.2
"""The smallest diameter, in millimetres, Slant 3D reports a modelled thread working at on a
0.4 mm nozzle - about 1/8 in (sza8wg5FIxQ 03:59). An **unmeasured default**: below it a
thread is built and a warning logged."""

FINEST = 0.4
"""The shallowest thread depth, in millimetres, Slant 3D says a thread feature should keep
on a 0.4 mm nozzle - the top of its 0.2-0.4 mm range (sza8wg5FIxQ 04:08). An **unmeasured
default**, logged rather than refused, exactly as :data:`SMALLEST` is."""

_log = logging.getLogger(__name__)
"""A thread smaller than a printer is said to manage, said so as a finding and built anyway."""


def thread(
    kind: Thread,
    diameter: float,
    pitch: float,
    length: float,
    *,
    depth: float | None = None,
    fit: Fit = Fit.SLIDE,
    material: Material | None = None,
    at: Point = ORIGIN,
    label: str | Label | None = None,
) -> Solid:
    """A right-hand thread ``diameter`` across its crests, rising ``pitch`` a turn for
    ``length`` millimetres up +Z from ``at``.

    ``EXTERNAL`` is the bolt, drawn nominal: crests at ``diameter`` and roots ``depth``
    inside them. ``INTERNAL`` is the cavity in the nut, to be cut out of it: the same helix,
    with its section opened by ``material``'s clearance for ``fit`` (see the module's **The
    gap**) and grown by its ``hole_compensation`` as any printed hole is (**Compensation**),
    so an external and an internal thread drawn at the same ``at`` print to screw together
    at that fit. ``depth`` defaults to :data:`ROUND_DEPTH` of the pitch.

    The helix starts at ``at``: its crest faces +X there. So a nut's thread is drawn from its
    bolt's ``at`` and run the bolt's length, and the nut cut from that - one drawn from the
    nut's own height starts at another point of the helix, and collides with the bolt.

    Its faces are ``top``, ``bottom`` and ``side-0``, the one helical flank.

    Raises:
        ValueError: if a size is not positive, if ``depth`` is not less than the radius -
            the section would no longer hold its own axis, and would sweep a coil rather
            than a rod - or if an internal thread is asked for with no material to read its
            clearance from.
    """
    deep = pitch * ROUND_DEPTH if depth is None else depth
    if min(diameter, pitch, length, deep) <= 0.0:
        msg = "a thread needs a positive diameter, pitch, length and depth"
        raise ValueError(msg)
    if deep >= diameter / 2.0:
        msg = f"a thread {deep} deep has no core left inside a {diameter} diameter"
        raise ValueError(msg)
    offset = deep / 2.0
    radius = diameter / 2.0 - offset
    warnings = too_small(diameter, deep)
    if kind is Thread.INTERNAL:
        if material is None:
            msg = "an internal thread takes its clearance from a material's fit table"
            raise ValueError(msg)
        radius += _opened(material, fit, pitch, deep)
        warnings += drawn_clear(diameter, pitch, deep, material, fit)
    for warning in warnings:
        _log.warning("%s", warning, extra=fields(**{CHECK: "thread"}))
    section = fill(circle(radius, Point(offset, 0.0)))
    swept = extrude(section, length, twist=math.tau * length / pitch, label=label)
    return move(swept, at - ORIGIN)


def thread_opening(gap: float, pitch: float, depth: float) -> float:
    """How much wider an internal thread's section is drawn than its external one's, so that
    ``gap`` stands square across the steepest flank and not only across the crest.

    A flank leaning at ``atan(pi * depth / pitch)`` off the axis stands ``cos`` of that
    closer to its neighbour than the two sections do, so the section is opened by the gap
    over that cosine, plus :data:`~bench.topology.CHORD` for the chords of the concave
    cavity sagging into it.
    """
    return gap * math.hypot(1.0, math.pi * depth / pitch) + CHORD


def _opened(material: Material, fit: Fit, pitch: float, depth: float) -> float:
    """How far an internal thread's section is drawn out past its bolt's, on its radius: the
    fit's clearance stood across the steepest flank, and half the printed compensation."""
    return thread_opening(material.clearances[fit], pitch, depth) + material.hole_compensation / 2


def drawn_clear(
    diameter: float, pitch: float, depth: float, material: Material, fit: Fit
) -> tuple[str, ...]:
    """What an internal thread is warned about when it is drawn clear of its bolt: its
    section opened, by the clearance and the compensation, as far as the thread is deep or
    further, so the modelled nut would slide straight off the modelled bolt. The print is
    meant to shrink it back into engagement; the sentence says that is all it rests on."""
    opening = _opened(material, fit, pitch, depth)
    if opening < depth:
        return ()
    return (
        f"a {diameter:g} x {pitch:g} internal thread in {material.name} at {fit.name} is drawn"
        f" clear of its bolt - opened {opening:.2f} mm on a thread {depth:.2f} mm deep - so it"
        " engages only if the print shrinks as compensated; a coarser pitch or a deeper thread"
        " engages in the model",
    )


def too_small(diameter: float, depth: float) -> tuple[str, ...]:
    """What a thread this size is warned about: each of :data:`SMALLEST` and :data:`FINEST`
    it falls under, as a sentence that says the limit is an unmeasured default."""
    said: list[str] = []
    if diameter < SMALLEST:
        said.append(
            f"a {diameter:g} mm thread is under the {SMALLEST:g} mm Slant 3D reports modelled"
            " threads failing below on a 0.4 mm nozzle (an unmeasured default)"
        )
    if depth < FINEST:
        said.append(
            f"a thread {depth:.2f} mm deep is under the {FINEST:g} mm Slant 3D says a thread"
            " feature should keep on a 0.4 mm nozzle (an unmeasured default)"
        )
    return tuple(said)
