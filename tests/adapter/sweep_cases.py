"""The sweeps ``test_sweep_measured.py`` asks the shipped kernel about, answered inside Pyodide.

:mod:`tools.stack` writes this file beside ``bench`` in the runtime the app ships, and
:func:`measured` sweeps profiles along a bend and an S-bend, shells a bend, mates a flange onto
its end and hands every body to the real kernel - answering with plain JSON-able data. It
imports nothing but ``bench`` and the standard library, and decides nothing: every assertion
is in the test module.
"""

import math
from collections.abc import Callable

from bench import (
    ORIGIN,
    Bend,
    Point,
    Printed,
    Solid,
    Straight,
    Wire,
    X,
    Z,
    circle,
    common,
    extrude,
    face,
    fill,
    mating,
    part,
    path,
    polygon,
    rect,
    shell,
    sweep,
)
from bench.kernel import Kernel, Mesh
from bench.library.print import PLA
from bench.meshing import swept
from bench.topology import Swept

PRINTED = Printed(PLA)

R = 60.0
"""The radius every bend here turns at."""
ROUND = 20.0
"""The duct's outside radius."""
WALL = 2.0
FLANGE = (30.0, 4.0)
"""The flange's outside radius and its thickness."""


def elbow() -> Wire:
    """Up 20, a quarter turn towards X, on 20: ending at (80, 0, 80), heading +X."""
    return path(ORIGIN, Z, Straight(20.0), Bend(R, math.pi / 2, X), Straight(20.0))


def offset() -> Wire:
    """An S-bend: up 10, an eighth turn each way, on 10."""
    eighth = math.pi / 4
    return path(ORIGIN, Z, Straight(10.0), Bend(R, eighth, X), Bend(R, eighth, -X), Straight(10.0))


def ell() -> Solid:
    """An L 30 by 30 with 10 mm legs, round the elbow - a profile a hull would fill in."""
    corners = (
        Point(-15, -15),
        Point(15, -15),
        Point(15, -5),
        Point(-5, -5),
        Point(-5, 15),
        Point(-15, 15),
    )
    return sweep(fill(polygon(corners)), elbow())


def duct(opened: tuple[str, ...] = ("start", "end")) -> Solid:
    return shell(sweep(fill(circle(ROUND)), elbow()), WALL, open=opened)


CASES: dict[str, Callable[[], Solid]] = {
    "round": lambda: sweep(fill(circle(ROUND)), elbow()),
    "boxed": lambda: sweep(fill(rect(40, 30, Point(-20, -15))), offset()),
    "ell": ell,
    "duct": duct,
    "duct_capped": lambda: duct(("end",)),
}


def mesh_data(mesh: Mesh) -> dict[str, object]:
    """A mesh as JSON: its three lists, a ref as its text."""
    return {
        "vertices": list(mesh.vertices),
        "triangles": list(mesh.triangles),
        "refs": [None if one is None else str(one) for one in mesh.refs],
    }


def _laid(body: Solid) -> dict[str, object]:
    """The mesh bench lays for a sweep itself, before the modeller takes it in."""
    assert isinstance(body.node, Swept)
    vertices, triangles, _ = swept(body.node)
    return {"vertices": list(vertices), "triangles": list(triangles)}


def _flanged(kernel: Kernel) -> dict[str, object]:
    """A flange ring put on the shelled elbow's far end by name, and what it shares with it."""
    body = duct()
    outside, thick = FLANGE
    ring = extrude(face(circle(outside), holes=(circle(ROUND - WALL),)), thick, label="ring")
    mate = mating(body, "end", part("flange", ring, PRINTED), "flange/ring/bottom")
    placed = mate.part.shape
    assert isinstance(placed, Solid)
    return {
        "flange": mesh_data(kernel.mesh(placed)),
        "shared": kernel.volume(common(body, placed)),
        "gap": kernel.min_gap(body, placed, upto=5.0),
    }


def measured(kernel: Kernel) -> dict[str, object]:
    """Everything ``test_sweep_measured.py`` reads, built by ``kernel``."""
    bodies = {key: build() for key, build in CASES.items()}
    return {
        "bodies": {
            key: {"volume": kernel.volume(body), "mesh": mesh_data(kernel.mesh(body))}
            for key, body in bodies.items()
        },
        "laid": _laid(bodies["round"]),
        "flanged": _flanged(kernel),
    }
