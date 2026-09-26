"""The print domain: what a filament does, how tight a fit is, and how big the bed is.

This is the module a printed part reads. It owns four things nothing else in the package
should own:

* **The material profiles.** ``PLA``, ``PETG`` and ``ASA``, filled in with the review's
  numbers for a 0.4 mm nozzle at 0.2 mm layers, calibrated flow. Shrink, printed-hole
  compensation, first-layer spread, minimum wall, maximum overhang, longest bridge, layer
  height - and the per-side gap each :class:`~bench.fasteners.Fit` means in that plastic.
* **The public clearance.** :func:`clearance` is a plain function, not something reachable
  only through :func:`~bench.features.hole`: a lid lip, a hinge bore and a nut trap all need the
  number, and the alternative is a maker typing ``0.25`` by hand.
* **The build volumes themselves.** ``H2D`` and the rest, so a check can ask whether a part
  fits before anybody slices it.
* **The eased rim.** :func:`rim` is an extrusion whose top, bottom or both are rounded or
  chamfered by how the shape was made rather than by finding an edge afterwards - there is
  no fillet or chamfer verb for the edge of a solid on this kernel and there is not going to
  be one. A rim a maker would draw with a round-over or a chamfer is drawn here as a stack
  of hulled slices instead - the technique :func:`~bench.solids.hull`'s own docstring
  already names - and any part that wants one asks for it once rather than hand-rolling it
  again. :func:`eased` is the one case task-71 found already in the vocabulary: both rims
  chamfered, and now just :func:`rim` called that way.

The *records* it fills in - :class:`~bench.model.Material`, :class:`~bench.model.Orient`,
:class:`~bench.model.Printed`, :class:`~bench.model.Volume` - live in :mod:`bench.model`,
beside ``Stock``, because a :class:`~bench.model.Part` carries one and a check measures
against another; and the printable-hole *geometry* -
:class:`~bench.features.Top`, :func:`~bench.features.teardrop`,
:func:`~bench.features.bridge_steps`, :func:`~bench.features.printable_top`,
:func:`~bench.features.foot_chamfer` - lives in
:mod:`bench.features`, because :func:`~bench.features.hole` builds with it and the layer graph runs
that way round. Both are imported back here so that a script reading the print domain has
one module to read it from:

    from bench.library.print import PLA, Printed, Orient, clearance, teardrop, H2D

Every number here is a starting point from one reviewer's sources, not something measured
on the machine in the room. They are data, in one place, so that measuring them changes one
file.
"""

import math
from functools import reduce
from itertools import pairwise
from typing import Literal

from ..fasteners import Fit
from ..features import Top, bridge_steps, foot_chamfer, printable_top, teardrop
from ..geometry import TOL, Vector
from ..model import Material, Orient, Printed, Volume
from ..ops import offset
from ..solids import extrude, hull, move, union
from ..topology import CHORD, Face, Solid, flat_ring

__all__ = [
    "ASA",
    "BEDS",
    "H2D",
    "PETG",
    "PLA",
    "Material",
    "Orient",
    "Printed",
    "Top",
    "Volume",
    "bridge_steps",
    "clearance",
    "eased",
    "foot_chamfer",
    "printable_top",
    "rim",
    "teardrop",
]


# ---- what a filament does ------------------------------------------------------------


PLA = Material(
    name="PLA",
    shrink=0.003,
    hole_compensation=0.20,
    foot=0.15,
    min_wall=0.86,
    max_overhang=math.radians(45.0),
    bridge_max=10.0,
    layer=0.2,
    clearances=frozendict(
        {
            Fit.INTERFERENCE: -0.05,
            Fit.PRESS: 0.05,
            Fit.SNUG: 0.10,
            Fit.SLIDE: 0.20,
            Fit.CLEARANCE: 0.30,
            Fit.LOOSE: 0.50,
        }
    ),
)
"""The default filament: stiff, cheap, dimensionally the best behaved of the three, and
the one every number in this module was chosen against."""

PETG = Material(
    name="PETG",
    shrink=0.004,
    hole_compensation=0.25,
    foot=0.20,
    min_wall=0.86,
    max_overhang=math.radians(45.0),
    bridge_max=8.0,
    layer=0.2,
    clearances=frozendict(
        {
            Fit.INTERFERENCE: -0.05,
            Fit.PRESS: 0.05,
            Fit.SNUG: 0.125,
            Fit.SLIDE: 0.25,
            Fit.CLEARANCE: 0.35,
            Fit.LOOSE: 0.55,
        }
    ),
)
"""Tougher and stringier than PLA: every gap opens a little, and a bridge is shorter."""

ASA = Material(
    name="ASA",
    shrink=0.007,
    hole_compensation=0.30,
    foot=0.25,
    min_wall=1.2,
    max_overhang=math.radians(40.0),
    bridge_max=6.0,
    layer=0.2,
    clearances=frozendict(
        {
            Fit.INTERFERENCE: 0.00,
            Fit.PRESS: 0.075,
            Fit.SNUG: 0.15,
            Fit.SLIDE: 0.30,
            Fit.CLEARANCE: 0.40,
            Fit.LOOSE: 0.60,
        }
    ),
)
"""For outdoors, and the one that moves: 0.7 per cent of shrink is 2.4 mm across a
350 mm bed, which is why ``shrink`` is a field rather than a footnote."""

MATERIALS = (PLA, PETG, ASA)
"""Every profile that ships, in the order the review tabulates them."""


def clearance(fit: Fit, material: Material, *, concave: bool = False) -> float:
    """The gap ``fit`` means in ``material``, in millimetres **per side**.

    Public on purpose, and the review's decisive point: the number has to be reachable
    without cutting a hole. A lid's lip against its box, a hinge pin in its knuckle, a nut
    in its trap and a bin in its baseplate are all mating dimensions, and none of them goes
    through :func:`~bench.features.hole`.

    Per side means per side: a bore that must slide on a 4 mm pin is
    ``4 + 2 * clearance(Fit.SLIDE, PLA)`` across. And it is applied to *one* of the two
    parts - printed holes come out small while outside features come out slightly large, so
    a gap taken off both faces comes out twice as wide as it should.

    ``concave`` is for the side of the gap that runs along an internal arc - a bore's wall,
    a socket, a lug's inside - rather than a flat or an outside round. A concave arc is
    meshed as chords lying inside its true circle, so the printed material there bulges
    into the gap by up to :data:`~bench.topology.CHORD` beyond where the ideal geometry
    puts it, and a fit measured against the ideal radius alone reads that much short once
    it is meshed - task-27's stop lug read 0.16 mm against a 0.20 mm ask this way. Passing
    ``concave=True`` folds that sag into the ask itself, so geometry drawn from the result
    keeps the fit it was drawn for once a kernel tessellates it; a convex or planar pair
    passes nothing and gets the same number as always.
    """
    base = material.clearances[fit]
    return base + CHORD if concave else base


# ---- the eased rim ---------------------------------------------------------------------

_EaseStyle = Literal["round", "chamfer"]


def rim(
    profile: Face,
    length: float,
    *,
    lead: float,
    drop: float,
    style: _EaseStyle = "chamfer",
    top: bool = True,
    bottom: bool = True,
    steps: int = 8,
) -> Solid:
    """The extrusion of ``profile`` by ``length`` along its own normal, with the chosen
    rim or rims eased instead of left square: ``lead`` millimetres narrower in the plane,
    reached over ``drop`` millimetres along the sweep, straight in one step for
    ``style="chamfer"`` or rounded over ``steps`` for ``style="round"``. :func:`eased` is
    this called with both rims chamfered - task-71's generalisation of it.

    There is no fillet or chamfer verb for the edge of a solid on this kernel and there is
    not going to be one. What there is, and what a maker would have drawn anyway, is a
    stack of slices - the full profile where the eased rim meets the body, narrower slices
    approaching the rim itself - each consecutive pair wrapped in a :func:`~bench.solids.hull`,
    the way :func:`~bench.solids.hull`'s own docstring already describes a profile that
    changes as it rises. A chamfer is the two end slices of that stack and nothing between
    them; a round is the same stack with the narrowing slices traced along a quarter
    ellipse from the full profile to the inset tip, close enough to the curve for
    ``steps`` steps that a maker chooses the way :data:`~bench.topology.CHORD` chooses it
    for a circle - more steps for a rim large enough that eight would show as facets.

    **A round eased rim is not a fillet, and only one direction of it is usually
    printable.** A rim that narrows going *up*, from the full profile to the tip, is a dome
    over the whole run - every slice sits inside the one below it, so nothing overhangs and
    ``check_overhangs`` finds nothing. A rim that narrows going *down* - easing the
    ``bottom`` this way while printing with the profile's own normal up - widens as it
    rises off the bed, and the middle of a round curve reaches a horizontal tangent before
    it reaches vertical: `docs/printing.md`'s own rule, "chamfer it rather than filleting
    it", because a fillet used as an overhang sweeps through a ceiling. ``check_overhangs``
    on the built solid is how a script confirms which side its own rim is really on;
    nothing here refuses the other one, because bench does not know which way up a body
    will print until a part is built from it.

    **A hulled slice is convex, so ``profile`` has to be, and it has to be empty of
    holes.** The chain of hulls that builds an eased cap fills in anything the real outline
    does not - a notch, a fillet's own concave corner, a hole in ``profile.inner`` - the
    same way :func:`~bench.solids.loft` already does between two profiles. So both are
    refused here, before anything is built, rather than eased into a wrong solid: an outline
    that turns the other way anywhere along it, flattened the way a kernel flattens it, and
    a profile with any hole at all. Round or chamfered, the rim is convex-only; a notched
    outline is eased by hand, one convex piece at a time. A wire's own corners are another
    matter - :func:`~bench.ops.fillet` and :func:`~bench.ops.chamfer` round or cut a concave
    corner of a sketch as readily as a convex one; it is only the rim that cannot follow it
    afterwards. ``lead`` is checked too, but indirectly: it has to stay under the smallest
    arc radius in ``profile``, or the cap's innermost slice asks :func:`~bench.ops.offset` to
    shrink that arc past zero, and ``offset``'s own ``ValueError`` - "offset collapses an
    arc" - propagates from here with no kernel needed to raise it. A caller filleting a
    corner and then easing the rim keeps ``lead`` comfortably under that radius.

    **Face names.** A straight run between two eased rims keeps its own ``side-<n>`` faces,
    since that part of the body is a plain :func:`~bench.solids.extrude` and a hull only
    erases names in the parts it wraps. The extrusion's own ``top`` survives only when
    ``top=False`` and ``bottom`` only when ``bottom=False`` - the flat end nobody asked to
    ease. Where an end *is* eased, the coincident face it shares with the straight run's own
    end is removed by the union between them, the same as any two solids joined at a shared
    face, and that end's own eased cap answers to nothing but the whole solid's label,
    because :class:`~bench.topology.Hull` is a leaf for naming.

    Raises:
        ValueError: if ``length``, ``lead`` or ``drop`` is not positive, neither ``top``
            nor ``bottom`` is asked for, ``style="round"`` is given fewer than two
            ``steps``, the two eased rims meet or cross in the middle of the run,
            ``profile`` has a hole or a concave outline - a hull would fill either in - or
            ``lead`` reaches past one of ``profile``'s own arcs - :func:`~bench.ops.offset`'s
            own error, raised from here with no kernel needed.
    """
    if length <= TOL:
        msg = "a rim needs a positive length to run the extrusion along"
        raise ValueError(msg)
    if lead <= TOL or drop <= TOL:
        msg = "an eased rim needs a positive lead and drop"
        raise ValueError(msg)
    if not top and not bottom:
        msg = "a rim needs at least one end asked for, top or bottom"
        raise ValueError(msg)
    if profile.inner:
        msg = (
            "a rim eases a profile by hulling slices of it, and a hull would fill in its"
            f" {len(profile.inner)} hole(s); ease the outline and cut the holes afterwards"
        )
        raise ValueError(msg)
    if not _convex(profile):
        msg = (
            "a rim eases a profile by hulling slices of it, and a hull would fill in this"
            " one's concave outline; ease each convex piece and join them"
        )
        raise ValueError(msg)
    on = profile.plane
    n = on.normal
    lo = drop if bottom else 0.0
    hi = length - drop if top else length
    if hi <= lo + TOL:
        msg = "the two eased rims meet or cross before the middle of the run"
        raise ValueError(msg)
    body = extrude(move(profile, n * lo), hi - lo)
    if bottom:
        body = union(body, _eased_cap(profile, lead, drop, style, steps, n, at=0.0, rise=True))
    if top:
        body = union(body, _eased_cap(profile, lead, drop, style, steps, n, at=length, rise=False))
    return body


def _convex(profile: Face) -> bool:
    """Whether ``profile``'s outline turns one way all the way round, flattened into the
    chords a kernel builds it from - so a hull of it is the outline itself."""
    points = flat_ring(profile.outer, profile.plane, (0,) * len(profile.outer.edges)).points
    turns = tuple(
        (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        for a, b, c in zip(points, points[1:] + points[:1], points[2:] + points[:2], strict=True)
    )
    return min(turns) >= -TOL or max(turns) <= TOL


def eased(profile: Face, length: float, *, lead: float, drop: float) -> Solid:
    """A prism ``length`` long, along ``profile``'s own normal, with both rims chamfered.

    ``lead`` is how far the rim is inset, in the plane; ``drop`` is how far that inset
    travels along the prism before it meets the full profile - well under 45 degrees for a
    fit that prints clean, on whichever rim ends up facing away from the bed. :func:`rim`
    is the general form: a round rather than a chamfer, and one rim rather than both.
    """
    return rim(profile, length, lead=lead, drop=drop, style="chamfer", top=True, bottom=True)


def _eased_cap(
    profile: Face,
    lead: float,
    drop: float,
    style: _EaseStyle,
    steps: int,
    n: Vector,
    *,
    at: float,
    rise: bool,
) -> Solid:
    """The eased cap at one rim of :func:`rim`: a chain of hulled slices from the full
    profile where it meets the body to the tip - inset ``lead`` and moved ``drop`` toward
    the rim - built at ``at`` along the extrusion's own normal and growing toward the body
    (``rise=True`` for the bottom) or away from it (``rise=False`` for the top)."""
    sign = 1.0 if rise else -1.0
    slices = [
        move(profile if inset <= TOL else offset(profile, -inset), n * (at + sign * height))
        for inset, height in _ease_curve(lead, drop, style, steps)
    ]
    return reduce(union, (hull(a, b) for a, b in pairwise(slices)))


def _ease_curve(
    lead: float, drop: float, style: _EaseStyle, steps: int
) -> tuple[tuple[float, float], ...]:
    """``(inset, height)`` pairs from the tip of an eased rim - inset ``lead`` in the
    plane, at ``height`` 0 along the sweep - to where it meets the full profile - no inset,
    at ``height`` ``drop``: two points for a straight chamfer, or ``steps + 1`` points
    (``steps`` hulled segments between them) along a quarter ellipse for a round, close
    enough to it that a maker who wants a smoother curve asks for more steps.

    Raises:
        ValueError: if ``style="round"`` is given fewer than two steps.
    """
    if style == "chamfer":
        return ((lead, 0.0), (0.0, drop))
    if steps < 2:
        msg = "a round eased rim needs at least two steps to look round"
        raise ValueError(msg)
    return tuple(
        (lead * math.cos(t), drop * math.sin(t))
        for t in (math.pi / 2 * k / steps for k in range(steps + 1))
    )


# ---- how big the machine is ----------------------------------------------------------


H2D = Volume(350.0, 320.0, 325.0)
"""The Bambu H2D's build volume - the machine these numbers were chosen for."""

_SMALL = Volume(256.0, 256.0, 256.0)
"""The bed every 256 mm Bambu machine shares."""

BEDS = frozendict({"h2d": H2D, "p1s": _SMALL, "a1": _SMALL})
"""Build volumes by name, so a script can say which machine it is printing on without
copying three numbers out of a manual."""
