"""What ``test_threads_measured.py`` asks of the shipped kernel, answered inside Pyodide.

:mod:`tools.stack` writes this file beside ``bench`` in the runtime the app ships, and
:func:`measured` builds twisted and tapered extrusions and printed bolt and nut pairs with the
real kernel, answering with plain JSON-able data. It imports nothing but ``bench`` and the
standard library, and decides nothing: every assertion is in the test module.
"""

import math

from bench import (
    Face,
    Fit,
    Material,
    Point,
    Thread,
    Vector,
    common,
    cut,
    cylinder,
    extrude,
    fill,
    move,
    name,
    rect,
    rotate,
    thread,
    wire,
)
from bench.kernel import Kernel, Mesh
from bench.library.print import PETG, PLA

SQUARE = 4.0
"""The side of the square every twisted and tapered case sweeps, centred on its own axis."""

RISE = 10.0
"""How far every twisted and tapered case sweeps."""

TURN = math.pi / 2
"""How far the twisted cases turn their far end: a quarter, right-handed about the sweep."""

TAPER = 0.5
"""How big the tapered case's far end is beside its profile."""

EDGES = ("south", "east", "north", "west")
"""What the square's four edges are called, counter-clockwise from the one along -Y, so the
sides of a twisted square read ``side-south`` and the naming can be checked edge by edge."""

PAIRS: dict[str, tuple[float, float, Material, Fit]] = {
    "m12": (12.0, 2.0, PLA, Fit.SLIDE),
    "m8": (8.0, 1.25, PLA, Fit.SLIDE),
    "jar": (40.0, 3.0, PETG, Fit.CLEARANCE),
}
"""Bolt and nut pairs: diameter, pitch, material and fit - a coarse metric size, a fine one,
and a jar neck at a looser fit in the other filament."""

BOLT_LENGTH = 16.0
NUT = (5.0, 6.0)
"""Where the nut starts up the bolt, and how tall it is."""


def square() -> Face:
    """The labelled square, as a face on XY centred on the origin, for sweeping."""
    half = SQUARE / 2
    outline = rect(SQUARE, SQUARE, Point(-half, -half))
    edges = tuple(name(e, n) for e, n in zip(outline.edges, EDGES, strict=True))
    return fill(wire(edges))


OFF_AXIS = (1.0, -1.0, 2.0)
"""A square ``(x, y, side)`` standing off its sweep's axis, wholly on +X: turned a quarter
right-handed about +Z it lands wholly on +Y, and about -Z wholly on -Y, so its far end says
which way it turned without a name being read."""


def _off_axis() -> Face:
    x, y, side = OFF_AXIS
    return fill(rect(side, side, Point(x, y)))


def _far_points(mesh: Mesh, distance: float) -> list[list[float]]:
    """Every vertex of ``mesh`` on its far end, found by height alone."""
    v = mesh.vertices
    return [
        [v[k], v[k + 1], v[k + 2]] for k in range(0, len(v), 3) if abs(v[k + 2] - distance) < 1e-4
    ]


def _mesh(mesh: Mesh) -> dict[str, object]:
    return {
        "vertices": list(mesh.vertices),
        "triangles": list(mesh.triangles),
        "refs": [None if one is None else str(one) for one in mesh.refs],
    }


def _pair(kernel: Kernel, key: str) -> dict[str, object]:
    """A bolt and a nut drawn in place on it, measured at three poses: as drawn, screwed on
    a further quarter turn along the helix, and pushed half a pitch up the axis without
    turning, which takes it off the helix."""
    diameter, pitch, material, fit = PAIRS[key]
    bolt = thread(Thread.EXTERNAL, diameter, pitch, BOLT_LENGTH, label="bolt")
    tool = thread(Thread.INTERNAL, diameter, pitch, BOLT_LENGTH, material=material, fit=fit)
    start, tall = NUT
    blank = move(cylinder(diameter, tall), Vector(0.0, 0.0, start))
    nut = cut(blank, tool, label="thread")
    poses = {
        "matched": nut,
        "advanced": move(rotate(nut, math.pi / 2), Vector(0.0, 0.0, pitch / 4)),
        "off": move(nut, Vector(0.0, 0.0, pitch / 2)),
    }
    return {
        "asked": material.clearances[fit],
        "compensation": material.hole_compensation,
        "gaps": {pose: kernel.min_gap(bolt, one, upto=2.0) for pose, one in poses.items()},
        "shared": {pose: kernel.volume(common(bolt, one)) for pose, one in poses.items()},
        "bolt_refs": sorted({str(r) for r in kernel.mesh(bolt).refs if r is not None}),
        "nut_refs": sorted({str(r) for r in kernel.mesh(nut).refs if r is not None}),
    }


def measured(kernel: Kernel) -> dict[str, object]:
    """Everything ``test_threads_measured.py`` reads, built by ``kernel``."""
    up = extrude(square(), RISE, twist=TURN)
    down = extrude(square(), -RISE, twist=TURN)
    tapered = extrude(square(), RISE, scale=TAPER)
    return {
        "twisted": _mesh(kernel.mesh(up)),
        "hanging": _mesh(kernel.mesh(down)),
        "hanging_volume": kernel.volume(down),
        "twisted_volume": kernel.volume(up),
        "off_axis_up": _far_points(kernel.mesh(extrude(_off_axis(), RISE, twist=TURN)), RISE),
        "off_axis_down": _far_points(kernel.mesh(extrude(_off_axis(), -RISE, twist=TURN)), -RISE),
        "tapered": _mesh(kernel.mesh(tapered)),
        "tapered_volume": kernel.volume(tapered),
        "plain_volume": kernel.volume(extrude(square(), RISE)),
        "pairs": {key: _pair(kernel, key) for key in PAIRS},
    }
