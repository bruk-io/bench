"""Checks: what has to be true of a part, answered as records rather than as exceptions.

A check is a pure function that takes the geometry, the numbers it has to hold, and - where
it needs one - a :class:`~bench.kernel.Kernel` as a *parameter*. Nothing here imports an
implementation, exactly as :mod:`bench.kernel` does not; a run without a modeller still
gets an answer, and the answer is :data:`Severity.UNCHECKED` rather than a pass. That
distinction is the whole point: "I could not tell" is not "it is fine", and a check that
quietly passed in the browser and failed on the desk would be worse than no check at all.

A failed check is a :class:`Violation`, not a raise. The script goes on, the geometry still
comes back, and the violation is collected the way :func:`bench.nest.nest` already collects
a part that will not fit on the bed. A script that wants to stop says so itself, with
``require(...)``, which is injected into it beside ``show``.

Two tiers, and the signature says which: :func:`fits` and :func:`exportable` read the tree's
own :func:`~bench.topology.bounds` and shape and run anywhere, including in a browser with no
kernel at all. :func:`clearance_between`, :func:`contact_between`, :func:`wall` and
:func:`overhangs` are measurements of a built body, and without a modeller they answer
``UNCHECKED``.

:func:`clearance_between` and :func:`contact_between` are the two halves of one question and
a pair gets exactly one of them. Bodies that are meant to stay apart are asked how far apart
they are; bodies a maker has *declared* meet - a head on its ring, a lug on its stop - are
asked whether they share material, because a touch and a collision are both zero millimetres
apart and no distance threshold will ever separate them. Which one a pair gets is the
script's to say and is never read off the geometry: inferring that a zero gap must have been
intentional would pass the one thing a clearance check exists to catch.

:func:`fit_between` is the pair that *was* put together, at a fit somebody asked for: it asks
the one of those two questions the fit says, and answers with a :class:`Fitted` whose sentence
is the measured gap beside the asked one, because a fit that passes is half of what a maker
wants to read.
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

from .facets import Triangle, area, normal, thinnest, triangles
from .fasteners import Contact, Fit
from .geometry import TOL, Point, Vector, unit
from .kernel import Kernel
from .model import Material, Orient, Printed, Process, Ref, Stock, Stocked, Volume
from .topology import Face, Intersection, Shape, Solid, bounds

_ORIGIN = Point(0.0, 0.0, 0.0)
"""Where a point is measured from when it has to become a vector to be projected."""


class Severity(StrEnum):
    """How much a violation matters.

    ``ERROR`` is geometry that will not work; ``WARNING`` is geometry that probably will
    not; ``UNCHECKED`` is a question nobody could answer here - no kernel, no mesh, no
    measurement - and is never a pass wearing a different word.
    """

    ERROR = "error"
    WARNING = "warning"
    UNCHECKED = "unchecked"


@dataclass(frozen=True, slots=True)
class Violation:
    """One thing a check found, with enough to point at it.

    ``check`` is the check's own name, ``message`` is the sentence a maker reads, ``refs``
    are the faces it is about (empty where the answer is about a whole body), and ``line``
    is the line of the script that asked - filled in at the edge, by the closure
    :mod:`bench.script` injects, because only the edge knows whose stack it is.
    """

    check: str
    message: str
    severity: Severity
    refs: tuple[Ref, ...] = ()
    line: int | None = None


_UNCHECKED = "there is no kernel in this run, so nothing measured it"
"""What every violation says when it could not be answered. One sentence, once, so the
checks that need a modeller cannot drift apart in how they say so."""


def unchecked(check: str) -> Violation:
    """``check``'s answer when there was no kernel to answer it with.

    Public because the checks that need a modeller are not all in this module: a motion is
    measured at the edge, in :mod:`bench.script`, where the poses are built, and it has to
    say it was not measured in the same words as everything else here.
    """
    return Violation(check=check, message=f"{check}: {_UNCHECKED}", severity=Severity.UNCHECKED)


# ---- what the tree can answer on its own ---------------------------------------------


def fits(shape: Shape, volume: Volume) -> Violation | None:
    """Whether ``shape`` fits in ``volume`` as it stands, or ``None`` when it does.

    One of the two checks that need no kernel: :func:`~bench.topology.bounds` answers it from the
    tree, and is conservative under a cut - a bound that is too big never passes a part that
    will not fit, which is the direction a build-volume check has to err in.

    The part is measured where it is drawn. Turning it to make it fit is a decision about
    the print, not about the geometry, and belongs to whoever lays out the plate.
    """
    box = bounds(shape)
    over = tuple(
        f"{axis} {size:.1f} mm against {room:.1f} mm"
        for axis, size, room in (
            ("x", box.x1 - box.x0, volume.w),
            ("y", box.y1 - box.y0, volume.d),
            ("z", box.z1 - box.z0, volume.h),
        )
        if size > room + TOL
    )
    if not over:
        return None
    return Violation(
        check="fits",
        message=f"the part is bigger than the build volume: {', '.join(over)}",
        severity=Severity.ERROR,
    )


def exportable(shape: Shape, stock: Stocked, process: Process) -> Violation | None:
    """Whether a part's shape, stock and process combine into something the cut sheets and
    the print files can actually be drawn from, or ``None`` when they do.

    Needs no kernel, the same as :func:`fits`: a sheet part is a flat :class:`~bench.topology.Face`
    that :mod:`bench.export` cuts a path from, and a :class:`~bench.topology.Solid` on sheet
    :class:`~bench.model.Stock` is not one - it needs :class:`~bench.model.Printed` stock
    instead, or, once it exists, stock that is milled. A :class:`~bench.topology.Solid` marked
    :data:`~bench.model.Process.CNC` asks to mill a billet, which nothing here builds yet,
    whatever its stock: that is refused the same way rather than quietly dropped.

    A :class:`~bench.topology.Face` marked :data:`Process.CNC` is left alone - a flat part
    routed on a CNC is still a 2D profile, cut the same way a laser cuts one, and draws
    exactly like one.
    """
    match shape:
        case Face():
            return None
        case Solid():
            if process is Process.CNC:
                return Violation(
                    check="exportable",
                    message=(
                        "Process.CNC on a solid asks to mill a billet, and milling is not"
                        " modelled yet - nothing is exported for this part"
                    ),
                    severity=Severity.ERROR,
                )
            match stock:
                case Stock():
                    return Violation(
                        check="exportable",
                        message=(
                            "a solid cannot be cut from sheet stock: a sheet part is a flat"
                            " Face that is cut out, and a solid needs Printed stock instead -"
                            " or, once it exists, stock that is milled"
                        ),
                        severity=Severity.ERROR,
                    )
                case Printed():
                    return None
                case _:
                    assert_never(stock)
        case _:
            assert_never(shape)


# ---- what only a built body can answer -----------------------------------------------


_GAP_SLACK = 1e-3
"""How far under the asked-for gap a measured one may come and still pass, in millimetres.

A thousandth, for the same reason :data:`_ANGLE_SLACK` is a hundredth of a degree: a gap is
measured between two meshes whose vertices are single precision, so two faces drawn exactly
0.10 mm apart measure 0.099998 and a check against :data:`~bench.geometry.TOL` would fail a
part that is right. No printer holds a thousandth of a millimetre, so nothing real is hidden
by it.
"""


def clearance_between(
    a: Solid, b: Solid, least: float, *, kernel: Kernel | None
) -> Violation | None:
    """Whether ``a`` and ``b`` stay at least ``least`` millimetres apart.

    The gap two printed parts need so they do not fuse - a hinge knuckle and its leaf, a
    lid's lip inside its box. Searching stops at ``least`` itself, because a check only ever
    asks whether the gap is big enough, never how big it is.
    """
    if kernel is None:
        return unchecked("clearance")
    gap = kernel.min_gap(a, b, upto=least)
    if gap >= least - _GAP_SLACK:
        return None
    return Violation(
        check="clearance",
        message=f"the two bodies come within {gap:.2f} mm of each other, not {least:.2f} mm",
        severity=Severity.ERROR,
    )


_SHARED_SLACK = 1e-6
"""How much material two bodies declared to be in contact may share and still read as a
touch outright, in cubic millimetres, whatever the size of the faces that meet.

Measured rather than chosen, on the modeller the app ships. Two bodies whose faces are
exactly coincident share **exactly** zero: a 10 mm cube against a 10 mm cube reads 0.0, and
so does a 8 mm disc with a 4 mm boss seated flat on it, which is the curved case a shaft
head on a ring actually is. The smallest overlap that was tried at that size - the same boss
sunk one micron into the same disc - reads 0.0494 mm3, four orders of magnitude above this
figure. So the gap in the data is enormous and this constant sits in the empty middle of it
rather than on either edge: it is not a fudge for a reading that came out slightly wrong,
because no reading came out slightly wrong.

It is not zero only because a volume is the sum of a mesh's signed tetrahedra and summing to
a hard zero is a promise no floating-point boolean makes in general - not because anything
measured here needed the room.

This is the whole check at the sizes it was measured on. It stops being enough once a face
gets large: task-57 found two 317.5 mm rounded-square plates with a 266.7 mm window and four
holes, stacked face to face on the plane where one ends and the other begins, reading
0.0005 mm3 of shared material - five hundred times this figure - on faces that only ever
touched. :data:`_DEPTH_SLACK` is what a face that large is checked against instead.
"""

_DEPTH_SLACK = 1e-6
"""How far into each other, on average across the area they share, two bodies declared to be
in contact may sit and still read as a touch, in millimetres - the mean penetration depth a
shared volume above :data:`_SHARED_SLACK` is turned into before it is judged.

A fixed volume cannot be the whole check: the same rounding that reads a genuinely coincident
pair of 10 mm faces as exactly 0.0 mm3 does not stay at 0.0 mm3 once the faces are large. Two
317.5 mm rounded-square plates - a 266.7 mm rounded-square window, four holes, corners
rounded to 6.35 mm, the geometry task-57 was found on - stacked exactly on the plane where one
ends and the other begins read 0.0005 mm3 shared on the modeller the app ships: five hundred
times :data:`_SHARED_SLACK`, on a pair of faces that only ever touched. A fixed volume slack
big enough to pass that would have to be bigger than the 0.0494 mm3 a one-micron sink of the
small disc and boss reads, which is exactly the collision :data:`_SHARED_SLACK` exists to
catch - so no fixed volume separates a large coincident face from a small real overlap.

Area does. Divide the shared volume by half the surface area of the shape the two bodies
share - see :func:`_contact_area` for why that reads a real overlap's footprint almost
exactly, wherever on the pair it sits - and rounding noise on a coincident plane reads as a
depth of 2.8e-8 mm on the large plates above, still the same vanishing figure the small cube
and disc read at 0.0 mm3 outright. A one-micron sink of the same large plates reads 29.6 mm3
shared, which is 0.0010 mm deep by the same division - the sink itself, recovered almost to
the last digit; the small disc and boss sunk the same one micron read 0.0494 mm3 shared and
the same 0.0010 mm deep. Both are actual overlaps and both have to fail, so
:data:`_DEPTH_SLACK` sits at 1e-6 mm - a decade and a half above the noise floor and three
orders of magnitude below either real sink, in the same empty middle :data:`_SHARED_SLACK`
sits in.
"""


def contact_between(a: Solid, b: Solid, *, kernel: Kernel | None) -> Violation | None:
    """Whether ``a`` and ``b`` - which somebody has *declared* meet - only touch, rather
    than overlapping.

    The check a pair gets instead of :func:`clearance_between` when a maker says these two
    are meant to be in contact: a head seats on its ring, a lug bears on its stop, a
    shoulder lands. :meth:`~bench.kernel.Kernel.min_gap` reads such a pair as zero and
    :func:`clearance_between` calls that a failure, so before this existed the only remedy
    was to move geometry that was right until the faces were no longer coincident.

    Declaring a contact is not skipping the pair. The measurement still runs; what changes
    is the question asked of it. ``clearance_between`` asks "are these ``least`` apart",
    which a touch can never satisfy; this asks "do these two occupy the same material",
    which a touch satisfies and a collision does not. So a declared pair that turns out to
    interpenetrate is still reported - it is simply reported as an overlap rather than as a
    gap that came up short.

    That is also why the answer is a shared volume and not a distance. ``min_gap`` returns
    zero for a touch and zero for a body driven clean through another; the two are
    indistinguishable to it, and no amount of care with a distance threshold separates them.
    How much material the two share separates them exactly.

    A shared volume under :data:`_SHARED_SLACK` passes outright. Above it, the volume alone
    is not asked to carry the answer: it is turned into a mean penetration depth - shared
    volume over the area the bodies could meet over - and that depth is what is judged
    against :data:`_DEPTH_SLACK`, because the same rounding a small coincident face reads as
    zero a large one does not, and no fixed volume separates that from a real overlap at
    every size faces come in.

    Two things this deliberately does not promise, because nothing here can measure them:

    * **It does not check that the two actually meet.** Two bodies a mile apart share no
      material and pass. "Declared contact" names which pair is *allowed* to touch, never
      which pair *must*; a check that insisted on contact would be a different question
      (and would need the gap this one throws away) and no script has asked for it yet.
    * **It is per pair of bodies, not per pair of faces.** A kernel that answers ``mesh``,
      ``volume`` and ``min_gap`` cannot be asked about one face against another, so
      declaring a contact relaxes the whole pair: two faces on these same two bodies that
      should have stayed ``least`` apart are no longer watched. Declare the pairs that
      really seat, and no others.
    """
    if kernel is None:
        return unchecked("contact")
    overlap = Solid(Intersection(a, b))
    shared = kernel.volume(overlap)
    if shared <= _SHARED_SLACK:
        return None
    met_over = _contact_area(kernel, overlap)
    depth = shared / met_over if met_over > 0.0 else math.inf
    if depth <= _DEPTH_SLACK:
        return None
    return Violation(
        check="contact",
        message=(
            f"the two bodies share {shared:.3f} mm3 of material, and a declared contact may"
            " touch but not overlap"
        ),
        severity=Severity.ERROR,
    )


def _contact_area(kernel: Kernel, overlap: Solid) -> float:
    """The area two bodies could meet over, read off the shape they actually share.

    ``overlap`` is meshed rather than measured on ``a`` or ``b`` themselves, because the
    kernel cannot be asked about one face against another (see :func:`contact_between`'s
    second caveat) and the shared volume's own extent is what is available instead: half its
    total surface area. A genuine overlap is a thin slab wherever it sits - the depth two
    bodies sink into each other, not the size of either one - and a thin slab's surface is
    almost entirely its two flat faces, top and bottom, each one the contact patch itself;
    the sliver of side wall around its edge is what makes this an overestimate of the area,
    which is an underestimate of the depth the caller divides by - the safer direction to err
    in, since the alternative is failing a touch, but a small one: on a slab thin enough to be
    rounding noise in the first place, the side wall is negligible next to the two faces it
    stands between.

    An axis-aligned bounding box was tried first and rejected: it reads the extent of
    whatever the shared shape spans, not of the shape itself, so two overlaps far apart on
    the same pair of bodies - a boss sunk a micron into each of two opposite corners of one
    plate, say - inflate it to the box that contains both islands, which can be most of the
    plate. That is not a small error the way the side wall above is: it can put a real
    one-micron interference at the same depth as genuine rounding noise on a face the size of
    the whole plate, which is exactly the false pass :data:`_DEPTH_SLACK` exists to prevent.
    A mesh's own surface area does not have this failure: two islands contribute their own
    two faces each, wherever they are, and nothing about being apart inflates it.
    """
    mesh = kernel.mesh(overlap)
    return sum(area(t) for t in triangles(mesh)) / 2.0


# ---- a pair put together at a fit ----------------------------------------------------


_REACH = 1.0
"""How far past the asked gap a fit's measurement keeps looking, in millimetres.

:meth:`~bench.kernel.Kernel.min_gap` stops at ``upto`` and answers ``upto`` for anything
further, so a fit measured with ``upto`` at the asked gap could only ever say "at least what
was asked" - never the number a maker wants beside it. A millimetre past the ask is enough to
read every fit in the table in any plastic it holds, and a pair that is further apart than
that is not at the fit it was asked for in any sense worth a decimal place.
"""


@dataclass(frozen=True, slots=True)
class Fitted:
    """What a pair put together at a fit measured, beside what it was asked for.

    A record rather than a bare violation because a fit that passes is half of what a maker
    wants to read: "clear by 0.203 mm, asked 0.200 (slide)" says the groove is where the
    table said it should be, where no violation at all says only that nothing went wrong.
    :meth:`__str__` is that sentence, written once here; ``finding`` is what went wrong,
    ``None`` when nothing did.

    ``gap`` is the measured distance between the two bodies and ``asked`` the one the fit
    means, both in millimetres; ``gap`` is ``None`` when there was no kernel to measure with,
    and then ``finding`` is the ``UNCHECKED`` answer. A gap that reached :data:`_REACH` past
    the ask reads as "more than", because the search stopped there.
    """

    fit: Fit | Contact
    asked: float
    gap: float | None
    finding: Violation | None

    def __str__(self) -> str:
        if self.gap is None:
            return f"asked {_asked(self.fit, self.asked)}, not measured: {_UNCHECKED}"
        match self.fit:
            case Contact() if self.gap > _GAP_SLACK:
                said = f"stand {self.gap:.3f} mm apart"
            case Contact():
                said = "touch" if self.finding is None else "overlap"
            case Fit():
                more = "more than " if self.gap >= self.asked + _REACH - _GAP_SLACK else ""
                said = f"clear by {more}{self.gap:.3f} mm"
            case _:
                assert_never(self.fit)
        told = f"{said}, asked {_asked(self.fit, self.asked)}"
        return told if self.finding is None else f"{told}: {self.finding.message}"


def _asked(fit: Fit | Contact, asked: float) -> str:
    """What a fit asks for, in the words :class:`Fitted` reports it with."""
    match fit:
        case Contact():
            return "contact"
        case Fit():
            return f"{asked:.3f} ({fit})"
        case _:
            assert_never(fit)


def fit_between(
    a: Solid, b: Solid, fit: Fit | Contact, asked: float, *, kernel: Kernel | None
) -> Fitted:
    """How ``a`` and ``b`` - which somebody has put together at ``fit`` - actually sit, and
    whether that is the fit that was asked for.

    ``asked`` is the gap ``fit`` means, in millimetres per side: zero for :data:`CONTACT`,
    the material's own figure for a :class:`Fit` - this module reads no material table, so
    the caller that knows the plastic says the number.

    A contact is asked :func:`contact_between`'s question, unchanged - do the two share
    material - and then one more a put-together pair can answer where a bare declaration
    cannot: whether they meet at all. Two faces laid on each other and then slid off the
    edge by an ``offset`` share nothing and pass ``contact_between``; they are not in
    contact, and that is a warning here.

    A fit is measured, not merely thresholded: the gap is read up to :data:`_REACH` past the
    ask, so the sentence can say how far apart the two really are. Coming in under the ask
    by more than :data:`_GAP_SLACK` is an error, exactly as :func:`clearance_between` would
    call it; standing further off than asked is not, because the ask is the least a fit
    needs, and the sentence already says by how much. Whole bodies again, as every check
    here is: the gap reported is the nearest the two come anywhere, which on a groove round
    a collar is the groove.
    """
    if kernel is None:
        return Fitted(fit, asked, None, unchecked("fit"))
    match fit:
        case Contact():
            overlap = contact_between(a, b, kernel=kernel)
            gap = kernel.min_gap(a, b, upto=_REACH)
            return Fitted(fit, asked, gap, overlap or _apart(gap))
        case Fit():
            gap = kernel.min_gap(a, b, upto=asked + _REACH)
            return Fitted(fit, asked, gap, _tight(fit, asked, gap))
        case _:
            assert_never(fit)


def _apart(gap: float) -> Violation | None:
    """The warning a declared contact earns when its two bodies do not meet."""
    if gap <= _GAP_SLACK:
        return None
    more = "more than " if gap >= _REACH - _GAP_SLACK else ""
    return Violation(
        check="fit",
        message=f"the two bodies were put together to touch, and stand {more}{gap:.3f} mm apart",
        severity=Severity.WARNING,
    )


def _tight(fit: Fit, asked: float, gap: float) -> Violation | None:
    """The error a fit earns when its two bodies come closer than the fit allows."""
    if gap >= asked - _GAP_SLACK:
        return None
    return Violation(
        check="fit",
        message=(
            f"the two bodies come within {gap:.3f} mm of each other, and a {fit} fit asks"
            f" {asked:.3f}"
        ),
        severity=Severity.ERROR,
    )


# ---- a motion, which is poses and not a sweep ----------------------------------------


@dataclass(frozen=True, slots=True)
class Sampled:
    """What a clearance check made of a whole parameter range answered, and how it answered
    it.

    A record rather than a bare tuple of violations because the *method* is half the answer.
    "Clear at 21 poses, one every 0.05" and "clear throughout" are different claims, and only
    the first one was ever made here: the geometry is measured at each of ``samples`` poses
    across ``over``, and between two of them nothing is measured at all. :meth:`__str__` is
    that sentence, written once here so a script cannot word it more strongly than it was
    earned; ``findings`` is what went wrong, empty when nothing did.

    ``measured`` is ``False`` when there was no kernel to measure with, which is the browser
    before the modeller has loaded and every run of the pure test layers. Then ``findings``
    holds the one ``UNCHECKED`` answer and no pose was built at all.
    """

    least: float
    over: tuple[float, float]
    samples: int
    spacing: float
    findings: tuple[Violation, ...]
    measured: bool

    def __str__(self) -> str:
        if not self.measured:
            return f"the motion was not measured: {_UNCHECKED}"
        how = (
            f"sampled at {self.samples} poses from {self.over[0]:.3f} to {self.over[1]:.3f},"
            f" one every {self.spacing:.4f}"
        )
        found = (
            f"{len(self.findings)} pair(s) came closer than {self.least:.2f} mm"
            if self.findings
            else f"every pair stayed {self.least:.2f} mm apart at every one of them"
        )
        return (
            f"{how}: {found}. Sampled, not swept - a pair that fouls between two samples is"
            " not found, and nothing here is about force, friction or binding, only about"
            " whether the geometry interferes."
        )


def sampling(over: tuple[float, float], samples: int) -> tuple[float, ...]:
    """The parameter values a range is measured at: ``samples`` of them, evenly spaced, both
    ends included.

    Both ends are included on purpose - the closed and open poses of a mechanism are the two
    a maker has already thought about, and a sampling that left one out would be measuring
    somewhere nobody asked about instead of somewhere they did.

    Raises:
        ValueError: if fewer than two samples are asked for, which cannot include both ends,
            or if the range runs backwards or has no width.
    """
    if samples < 2:
        msg = f"a motion is sampled at both ends and between them, so at least twice, not {samples}"
        raise ValueError(msg)
    low, high = over
    if not high > low:
        msg = f"a motion runs from a lower value to a higher one, and {low} to {high} does not"
        raise ValueError(msg)
    step = (high - low) / (samples - 1)
    return (*(low + step * n for n in range(samples - 1)), high)


def wall(solid: Solid, least: float, *, kernel: Kernel | None) -> Violation | None:
    """Whether every wall of ``solid`` is at least ``least`` millimetres thick.

    Measured on the mesh, because thickness is not something a recipe knows: from the middle
    of each triangle, straight into the material, to the first surface facing back. The
    smallest of those distances is the part's thinnest wall, and the ref it comes back with
    is the face it was measured from. The measuring is :func:`bench.facets.thinnest`, which
    is also what :func:`bench.survey.survey` reports a downloaded model's walls with, so the
    two can never disagree about the same mesh.
    """
    if kernel is None:
        return unchecked("wall")
    mesh = kernel.mesh(solid)
    found = thinnest(mesh)
    if found is None:
        return None
    thickness, index = found
    at = mesh.refs[index]
    if thickness >= least - TOL:
        return None
    return Violation(
        check="wall",
        message=f"the thinnest wall is {thickness:.2f} mm, not {least:.2f} mm",
        severity=Severity.ERROR,
        refs=() if at is None else (at,),
    )


_ANGLE_SLACK = math.radians(0.01)
"""How far past the limit a face may measure before it counts as an overhang, in radians.

A hundredth of a degree, and it is not a fudge: the geometry a maker draws at exactly the
limit - a 45 degree chamfer, a teardrop's flank, a countersink's cone - reaches this check
as single-precision mesh vertices, so its measured angle lands a few millionths either side
of 45 degrees. :data:`~bench.geometry.TOL` is a millimetre tolerance and far too tight to
read an angle off a mesh with; a part is not unprintable for a rounding error.
"""


def overhangs(
    solid: Solid, orient: Orient, material: Material, *, kernel: Kernel | None
) -> Violation | None:
    """Whether anything on ``solid`` leans further off the build direction than the plastic
    can hold up unsupported.

    Every triangle is classified by its normal against ``orient.up``: a surface leaning
    ``theta`` from the build direction has a normal ``theta`` off the horizontal, so
    ``theta`` is the arcsine of how far the normal points downward, and the limit is the
    material's ``max_overhang``.

    The first layer is not an overhang: a triangle lying on the bed is what the part stands
    on, so everything within one layer height of the lowest point is left out - which is the
    same reason a part with no orientation cannot be checked at all.
    """
    if kernel is None:
        return unchecked("overhangs")
    mesh = kernel.mesh(solid)
    up = unit(orient.up)
    corners_of = triangles(mesh)
    floor = min(((p - _ORIGIN) @ up for t in corners_of for p in t), default=0.0)
    worst = 0.0
    at: Ref | None = None
    for i, corners in enumerate(corners_of):
        if all((p - _ORIGIN) @ up <= floor + material.layer + TOL for p in corners):
            continue
        lean = _lean_of(corners, up)
        if lean > worst:
            worst, at = lean, mesh.refs[i]
    if worst <= material.max_overhang + _ANGLE_SLACK:
        return None
    return Violation(
        check="overhangs",
        message=(
            f"a face leans {math.degrees(worst):.0f} degrees off the build direction, and"
            f" {material.name} holds up {math.degrees(material.max_overhang):.0f}"
        ),
        severity=Severity.WARNING,
        refs=() if at is None else (at,),
    )


# ---- reading a mesh --------------------------------------------------------------------


def _lean_of(t: Triangle, up: Vector) -> float:
    """How far a triangle leans off the build direction: nothing for a wall parallel to it,
    a quarter turn for a ceiling facing straight down, and nothing at all for anything
    facing upward, which holds itself up."""
    n = normal(t)
    if n is None:
        return 0.0
    down = -(n @ up)
    return 0.0 if down <= 0.0 else math.asin(min(1.0, down))
