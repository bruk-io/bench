"""The pockets ``test_pockets_measured.py`` asks the shipped kernel about, answered inside Pyodide.

:mod:`tools.stack` writes this file beside ``bench`` in the runtime the app ships, and
:func:`measured` drills the vent's magnet pocket into a block four ways - opening downward as
the block prints, which :func:`~bench.features.hole` ends in a cone by itself; the same
pocket told to keep its flat end; opening upward; and opening downward on an axis leaning
off the build direction - then runs the overhang check on each and reads where the pocket's
own faces landed. It imports nothing but ``bench`` and the standard library, and decides
nothing: every assertion is in the test module.
"""

import math
from collections.abc import Callable

from bench import (
    Axis,
    End,
    Orient,
    Point,
    Printed,
    Solid,
    Vector,
    Y,
    cuboid,
    hole,
    overhangs,
    plane_of,
    rotate,
)
from bench.facets import normal, triangles
from bench.kernel import Kernel
from bench.library.print import PLA

MAGNET = (12.5, 3.0)
"""The vent's magnet pocket: its diameter and the depth the magnet seats at, in mm."""

LEAN = 20.0
"""How far the leaning pocket's axis stands off the build direction, in degrees - under
:data:`~bench.features.LEANING`, so it is still an upright pocket with an end to make."""

PRINTED = Printed(PLA)

_UNDER = Point(20.0, 20.0, 0.0)
"""The middle of the block's underside, which the lean turns it about."""


def pocket(face: str, end: End = End.AUTO, *, lean: float = 0.0) -> tuple[Solid, Point, Vector]:
    """A 40 x 40 x 20 block with a magnet pocket drilled into the middle of its ``top`` or
    ``bottom``, the block turned ``lean`` degrees about Y first - and the pocket's mouth and
    its axis into the material, read off the plane it was drilled on."""
    block = rotate(cuboid(40.0, 40.0, 20.0), math.radians(lean), about=Axis(_UNDER, Y))
    on = plane_of(block, face)
    middle = _UNDER if face == "bottom" else Point(20.0, 20.0, 20.0)
    local = Point((middle - on.origin) @ on.x_dir, (middle - on.origin) @ on.y_dir)
    drilled = hole(
        block,
        local,
        on=on,
        diameter=MAGNET[0],
        depth=MAGNET[1],
        end=end,
        printed=PRINTED,
        label="magnet",
    )
    return drilled, on.origin + on.x_dir * local.x + on.y_dir * local.y, -on.normal


BODIES: dict[str, Callable[[], tuple[Solid, Point, Vector]]] = {
    "down": lambda: pocket("bottom"),
    "down_flat": lambda: pocket("bottom", End.FLAT),
    "up": lambda: pocket("top"),
    "leaning": lambda: pocket("bottom", lean=LEAN),
}
"""Every body measured: the pocket coned by itself, kept flat, opening up, and leaning."""


def _faces(kernel: Kernel, body: Solid, mouth: Point, axis: Vector) -> dict[str, object]:
    """For each of the pocket's own faces, how deep into the block every corner stands along
    ``axis`` from ``mouth``, how far out from the axis, and how far every triangle leans off
    the build direction - the arcsine of how far its normal points down."""
    mesh = kernel.mesh(body)
    out: dict[str, dict[str, list[float]]] = {}
    for corners, ref in zip(triangles(mesh), mesh.refs, strict=True):
        n = normal(corners)
        if ref is None or not str(ref).startswith("magnet") or n is None:
            continue
        one = out.setdefault(str(ref), {"deep": [], "out": [], "leans": []})
        for p in corners:
            v = p - mouth
            along = v @ axis
            one["deep"].append(along)
            one["out"].append(abs(v - axis * along))
        one["leans"].append(math.degrees(math.asin(max(-1.0, min(1.0, -n.z)))))
    return dict(out)


def measured(kernel: Kernel) -> dict[str, object]:
    """Everything ``test_pockets_measured.py`` reads, built by ``kernel``."""
    found: dict[str, object] = {}
    for key, build in BODIES.items():
        body, mouth, axis = build()
        leaning = overhangs(body, Orient(), PLA, kernel=kernel)
        found[key] = {
            "overhangs": None
            if leaning is None
            else [leaning.message, [str(r) for r in leaning.refs]],
            "faces": _faces(kernel, body, mouth, axis),
        }
    return found
