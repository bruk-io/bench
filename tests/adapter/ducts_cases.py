"""The fittings ``test_ducts_measured.py`` asks the shipped kernel about, answered inside Pyodide.

:mod:`tools.stack` writes this file beside ``bench`` in the runtime the app ships, and
:func:`measured` builds every fitting :mod:`bench.library.ducts` makes, in PLA and in ASA -
whose 40 degrees is where a cone or a turn derived from the plastic bites - runs the overhang
and wall checks on each standing the way it prints, and slides a spigot into the socket of
its own size, answering with plain JSON-able data. It imports nothing but ``bench`` and the
standard library, and decides nothing: every assertion is in the test module.
"""

import math
from collections.abc import Callable

from bench import (
    Material,
    Orient,
    Point,
    Solid,
    Vector,
    Violation,
    X,
    Y,
    Z,
    common,
    cuboid,
    cut,
    cylinder,
    move,
    overhangs,
    union,
    wall,
)
from bench.fasteners import Fit
from bench.kernel import Kernel
from bench.library import ducts
from bench.library.print import ASA, PLA, clearance

DEPTH = 20.0
"""How deep the measured sockets run to their stop."""

SHORT = 1.0
"""How far short of the stop the measured spigots are pushed in."""

ELBOW = (ducts.PORT_4, 40.0, 150.0, 30.0)
"""The elbow whose volume is measured: its size, its turn in degrees, its bend's radius and
its straight legs."""


def fittings(material: Material) -> dict[str, Callable[[], Solid]]:
    """Every fitting, a few sizes and shapes of each, in ``material``."""
    turn = min(math.radians(45.0), material.max_overhang)
    return {
        "spigot": lambda: ducts.spigot(ducts.HOSE_4, material=material),
        "socket": lambda: ducts.socket(ducts.PORT_4, material=material),
        "coupler": lambda: ducts.coupler(ducts.PORT_4, ducts.PORT_2_5, material=material),
        "reducer": lambda: ducts.reducer(ducts.HOSE_4, ducts.HOSE_2_5, material=material),
        "reducer_up": lambda: ducts.reducer(ducts.VAC_1_25, ducts.DUCT_4, material=material),
        "elbow": lambda: ducts.elbow(ducts.HOSE_4, turn, material=material),
        "elbow_small": lambda: ducts.elbow(ducts.VAC_1_25, turn, material=material),
        "branch": lambda: ducts.branch(ducts.PORT_4, angle=turn, material=material),
        "branch_smaller_tap": lambda: ducts.branch(
            ducts.DUCT_6, ducts.DUCT_4, angle=turn, material=material
        ),
        "square_to_round": lambda: ducts.square_to_round(
            250.0, 100.0, ducts.DUCT_6, material=material
        ),
        "square_to_round_narrow": lambda: ducts.square_to_round(
            60.0, 40.0, ducts.DUCT_4, material=material
        ),
        "square_to_round_sharp": lambda: ducts.square_to_round(
            120.0, 50.0, ducts.PORT_2_5, corner=0.0, material=material
        ),
        "square_to_round_sharp_square": lambda: ducts.square_to_round(
            80.0, 80.0, ducts.PORT_2_5, corner=0.0, material=material
        ),
        "keyed_spigot": lambda: ducts.keyed_spigot(ducts.PORT_4, material=material),
        "keyed_spigot_small": lambda: ducts.keyed_spigot(ducts.VAC_1_25, material=material),
    }


def _printable(kernel: Kernel, material: Material) -> dict[str, object]:
    """Each fitting's overhang and wall findings, standing the way it prints."""
    found: dict[str, object] = {}
    for key, build in fittings(material).items():
        body = build()
        leaning = overhangs(body, ducts.UPRIGHT, material, kernel=kernel)
        thin = wall(body, material.min_wall, kernel=kernel)
        found[key] = {
            "overhangs": None if leaning is None else leaning.message,
            "wall": None if thin is None else thin.message,
        }
    return found


def _joint(kernel: Kernel, size: ducts.Size) -> dict[str, object]:
    """A spigot pushed into the socket of its own size to ``SHORT`` from the stop, and how far
    apart the two stay; and the socket's bore, as the triangles its name is on."""
    socket = ducts.socket(size, depth=DEPTH)
    length = 30.0
    spigot = move(ducts.spigot(size, length=length), Vector(0.0, 0.0, DEPTH - SHORT - length))
    mesh = kernel.mesh(socket)
    bore = [
        [mesh.vertices[3 * mesh.triangles[3 * t + k] + axis] for axis in range(3)]
        for t in range(len(mesh.triangles) // 3)
        if mesh.refs[t] == "inside/side-socket"
        for k in range(3)
    ]
    return {
        "gap": kernel.min_gap(spigot, socket, upto=2.0),
        "shared": kernel.volume(common(spigot, socket)),
        "bore": bore,
    }


STEEP: tuple[tuple[str, Callable[[], Solid], Material], ...] = (
    ("elbow-90-PLA", lambda: ducts.elbow(ducts.HOSE_4, math.radians(90.0)), PLA),
    ("elbow-45-ASA", lambda: ducts.elbow(ducts.HOSE_4, math.radians(45.0), material=ASA), ASA),
    ("branch-60-PLA", lambda: ducts.branch(ducts.PORT_4, angle=math.radians(60.0)), PLA),
)
"""Fittings turned past what their plastic holds up: drawn all the same, for the overhang
check to find."""


def _steep(kernel: Kernel) -> dict[str, object]:
    """What the overhang check finds on each of :data:`STEEP`, standing the way it prints."""
    found: dict[str, object] = {}
    for key, build, material in STEEP:
        leaning = overhangs(build(), ducts.UPRIGHT, material, kernel=kernel)
        found[key] = None if leaning is None else [leaning.message, [str(r) for r in leaning.refs]]
    return found


THROUGH = 6.0
"""How thick the wall is that a measured keyed socket's inlet goes through."""

STAND = 2 * clearance(Fit.SLIDE, PLA)
"""How far off its socket's floor a measured keyed spigot stands, as the wall vent's does."""


def _host(cavity: Solid) -> Solid:
    """A block printing up ``+Z`` with ``cavity`` cut into it lying on its side: the socket
    running in from the block's back face along ``-Y`` to its floor ``THROUGH`` from the
    front, and the inlet on through the front - placed by :func:`ducts.place`, its key up."""
    radius = ducts.socket_diameter(ducts.PORT_4) / 2
    deep = THROUGH + ducts.SOCKET_DEPTH
    block = cuboid(4 * radius, deep, 4 * radius, at=Point(-2 * radius, 0.0, 0.0), label="host")
    stop = Point(0.0, THROUGH, 2 * radius)
    return cut(block, ducts.place(cavity, at=stop, toward=-Y, across=Z), label="port")


def _round_socket() -> Solid:
    """The keyed socket's hole with round bores instead of pointed ones: the control."""
    socket = ducts.socket_diameter(ducts.PORT_4) / 2
    bore = ducts.spigot_diameter(ducts.PORT_4) / 2 - ducts.WALL
    return union(
        cylinder(socket, ducts.SOCKET_DEPTH + 1.0, label="socket"),
        cylinder(bore, THROUGH + 2.0, at=Point(0.0, 0.0, -THROUGH - 1.0), label="inlet"),
    )


def _said(found: Violation | None) -> list[object] | None:
    """A finding as its message and the faces it names, or ``None``."""
    return None if found is None else [found.message, [str(r) for r in found.refs]]


def _lying(kernel: Kernel) -> dict[str, object]:
    """A port that has to lie on its side, measured in PLA: a plain spigot printed lying
    down, and its outside alone, with no bore to be the worst of it; a block with a keyed
    socket cut in it lying down, and the same block with round bores; and the keyed spigot
    put in the keyed socket by the same :func:`ducts.place`, ``STAND`` off its floor."""
    rod = cylinder(ducts.spigot_diameter(ducts.HOSE_4) / 2, ducts.SPIGOT_LENGTH, label="outside")
    keyed = _host(ducts.keyed_socket(ducts.PORT_4, THROUGH))
    key = ducts.keyed_spigot(ducts.PORT_4, key=ducts.SOCKET_DEPTH - STAND)
    radius = ducts.socket_diameter(ducts.PORT_4) / 2
    seated = ducts.place(key, at=Point(0.0, THROUGH + STAND, 2 * radius), toward=-Y, across=Z)
    found: dict[str, object] = {
        "spigot": _said(overhangs(ducts.spigot(ducts.HOSE_4), Orient(up=X), PLA, kernel=kernel)),
        "outside": _said(overhangs(rod, Orient(up=X), PLA, kernel=kernel)),
        "gap": kernel.min_gap(seated, keyed, upto=2.0),
        "shared": kernel.volume(common(seated, keyed)),
    }
    for called, body in (("keyed_host", keyed), ("round_host", _host(_round_socket()))):
        found[called] = {
            "overhangs": _said(overhangs(body, ducts.UPRIGHT, PLA, kernel=kernel)),
            "wall": _said(wall(body, PLA.min_wall, kernel=kernel)),
        }
    return found


def measured(kernel: Kernel) -> dict[str, object]:
    """Everything ``test_ducts_measured.py`` reads, built by ``kernel``."""
    size, turn, radius, leg = ELBOW
    elbow = ducts.elbow(size, math.radians(turn), radius=radius, length=leg)
    return {
        "printable": {one.name: _printable(kernel, one) for one in (PLA, ASA)},
        "joints": {one.name: _joint(kernel, one) for one in (ducts.HOSE_4, ducts.PORT_4)},
        "elbow": kernel.volume(elbow),
        "steep": _steep(kernel),
        "lying": _lying(kernel),
    }
