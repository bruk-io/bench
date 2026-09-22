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
* **The eased rim.** :func:`eased` is a prism whose rims are chamfered by how the shape was
  made rather than by finding an edge afterwards - there is no chamfer verb for the edge of
  a solid on this kernel and there is not going to be one. A rim a maker would draw with a
  chamfer is drawn here as a loft, an extrude and a loft instead, and any part that wants
  one asks for it once rather than hand-rolling it again.

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

from ..fasteners import Fit
from ..features import Top, bridge_steps, foot_chamfer, printable_top, teardrop
from ..model import Material, Orient, Printed, Volume
from ..ops import offset
from ..solids import extrude, loft, move, union
from ..topology import CHORD, Face, Solid

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


def eased(profile: Face, length: float, *, lead: float, drop: float) -> Solid:
    """A prism ``length`` long, along ``profile``'s own normal, with both rims chamfered.

    There is no chamfer verb for the edge of a solid on this kernel and there is not going
    to be one. What there is, and what a maker would have drawn anyway, is this: a loft, an
    extrude and a loft, so a rim is chamfered because the shape was made that way rather
    than because an edge was found afterwards. ``lead`` is how far the rim is inset, in the
    plane; ``drop`` is how far that inset travels along the prism before it meets the full
    profile - the chamfer is out of the vocabulary, but the angle it draws is still the
    caller's to choose, well under 45 degrees for a fit that prints clean.
    """
    on = profile.plane
    near = move(profile, on.normal * drop)
    far = move(profile, on.normal * (length - drop))
    return union(
        union(loft(offset(profile, -lead), near), extrude(near, length - 2 * drop)),
        loft(far, offset(move(profile, on.normal * length), -lead)),
    )


# ---- how big the machine is ----------------------------------------------------------


H2D = Volume(350.0, 320.0, 325.0)
"""The Bambu H2D's build volume - the machine these numbers were chosen for."""

_SMALL = Volume(256.0, 256.0, 256.0)
"""The bed every 256 mm Bambu machine shares."""

BEDS = frozendict({"h2d": H2D, "p1s": _SMALL, "a1": _SMALL})
"""Build volumes by name, so a script can say which machine it is printing on without
copying three numbers out of a manual."""
