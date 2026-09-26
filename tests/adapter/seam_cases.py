"""The joins ``test_seams_measured.py`` asks the shipped kernel about, answered inside Pyodide.

:mod:`tools.stack` writes this file beside ``bench`` in the runtime the app ships, and
:func:`measured` builds the four ways of putting pieces together that task-77 found leaving
false findings - pieces hollowed one by one and set end to end, a loft stood on a plate, a
shelled elbow open at a leaning end, a tap drilled straight into a run of its own size - and
runs the overhang and wall checks on each standing the way it prints, beside a real overhang
and a real thin wall those checks still have to find. It imports nothing but ``bench`` and
the standard library, and decides nothing: every assertion is in the test module.
"""

import math
from collections.abc import Callable

from bench import (
    ORIGIN,
    XY,
    Bend,
    Orient,
    Point,
    Solid,
    Straight,
    Vector,
    X,
    Y,
    Z,
    circle,
    cuboid,
    cut,
    cylinder,
    extrude,
    face,
    fill,
    loft,
    move,
    overhangs,
    path,
    plane,
    polygon,
    raised,
    rounded_rect,
    shell,
    sweep,
    union,
    wall,
)
from bench.facets import normal, triangles
from bench.kernel import Kernel
from bench.library import ducts
from bench.library.print import ASA, PLA
from bench.shell import PAST

WALL = 2.0
UPRIGHT = Orient()

TAP = 40.0
"""The tap's angle off the run, in degrees: ASA's limit, so every real surface of the branch
holds itself up in ASA and the tangent lip - leaning ``90 - TAP`` - is the only thing past
it."""

PLATE = (0.7, 3.0)
"""Where the plate the loft stands on starts, and how thick it is: its top lands at 3.7 mm,
which a 32-bit float cannot hold - measured, one of the heights that left the loft standing
apart from the plate."""


def _stacked() -> Solid:
    """A register boot built the obvious way: a rectangular collar, a loft to the round and a
    spigot, each hollowed with :func:`shell` and set end to end - ducts' own
    ``square_to_round(250, 100, DUCT_6)`` without the overlaps it was built with instead."""
    width, deep, corner, collar = 250.0, 100.0, 2.0, 10.0
    radius = ducts.spigot_diameter(ducts.DUCT_6) / 2
    lean = PLA.max_overhang
    reach = math.hypot(width / 2 - corner, deep / 2 - corner) + corner + WALL - radius
    top = collar + reach / math.tan(lean)
    opening = rounded_rect(
        width + 2 * WALL, deep + 2 * WALL, corner + WALL, Point(-width / 2 - WALL, -deep / 2 - WALL)
    )
    both = ("bottom", "top")
    pieces = (
        shell(extrude(fill(opening), collar), WALL, open=both),
        shell(
            loft(fill(opening, on=raised(XY, collar)), fill(circle(radius), on=raised(XY, top))),
            WALL,
            open=both,
        ),
        shell(cylinder(radius, ducts.SPIGOT_LENGTH, at=Point(0.0, 0.0, top)), WALL, open=both),
    )
    return union(union(pieces[0], pieces[1]), pieces[2])


def _on_a_plate() -> Solid:
    """A loft stood on a plate face to face and unioned - the vent's funnel on its base."""
    at, thick = PLATE
    top = at + thick
    lofted = loft(
        fill(rounded_rect(60.0, 40.0, 2.0, Point(-30.0, -20.0)), on=raised(XY, top)),
        fill(circle(15.0), on=raised(XY, top + 30.0)),
    )
    return union(move(cuboid(100.0, 80.0, thick), Vector(-50.0, -40.0, at)), lofted)


def _elbow(turn: float, *legs: Straight | Bend) -> Solid:
    """A 4 inch hose's spigot swept up and round ``turn`` degrees and shelled open at both
    ends - the elbow ducts builds by sweeping the ring, built instead the way shell offers."""
    radius = ducts.spigot_diameter(ducts.HOSE_4) / 2
    route = path(
        ORIGIN, Z, Straight(ducts.SPIGOT_LENGTH), Bend(3 * radius, math.radians(turn), X), *legs
    )
    return shell(sweep(fill(circle(radius)), route), WALL, open=("start", "end"))


def _tap_body() -> tuple[Solid, float]:
    """A wye whose tap is drilled straight into a run of its own size: two rods unioned, two
    bores unioned and cut out of them, the tap setting off from the run's axis at ``TAP``
    degrees - and the run's radius."""
    radius = ducts.spigot_diameter(ducts.PORT_4) / 2
    leg, run = 60.0, 480.0
    heading = Vector(math.sin(math.radians(TAP)), 0.0, math.cos(math.radians(TAP)))
    start = Point(0.0, 0.0, leg)
    on = plane(start, heading, Y)

    def tap(r: float, long: float) -> Solid:
        return sweep(fill(circle(r), on=on), path(start, heading, Straight(long)), label="tap")

    rods = union(cylinder(radius, run, label="run"), tap(radius, 4 * leg))
    bores = union(
        cylinder(radius - WALL, run + 2 * PAST, at=Point(0.0, 0.0, -PAST), label="run"),
        tap(radius - WALL, 4 * leg + PAST),
    )
    return cut(rods, bores, label="bore"), radius


def _ledge(across: float) -> Solid:
    """A block with a ledge ``across`` millimetres wide on its side, leaning 60 degrees off
    the vertical and 40 long - a real overhang, drawn."""
    out = across * math.sin(math.radians(60.0))
    up = across * math.cos(math.radians(60.0))
    outline = polygon(
        (
            Point(0.0, 0.0),
            Point(10.0, 0.0),
            Point(10.0, 10.0),
            Point(10.0 + out, 10.0 + up),
            Point(10.0 + out, 20.0),
            Point(0.0, 20.0),
        )
    )
    return extrude(face(outline, on=plane(ORIGIN, Vector(0.0, -1.0, 0.0), X)), 40.0)


BODIES: dict[str, Callable[[], Solid]] = {
    "stacked": _stacked,
    "on_a_plate": _on_a_plate,
    "elbow_on_a_straight": lambda: _elbow(TAP, Straight(ducts.SPIGOT_LENGTH)),
    "elbow_on_the_bend": lambda: _elbow(TAP),
    "tap": lambda: _tap_body()[0],
    "elbow_too_far": lambda: _elbow(60.0, Straight(ducts.SPIGOT_LENGTH)),
    "ledge": lambda: _ledge(0.4),
    "thin_elbow": lambda: shell(
        sweep(
            fill(circle(20.0)),
            path(ORIGIN, Z, Straight(20.0), Bend(60.0, math.radians(30.0), X), Straight(20.0)),
        ),
        0.5,
        open=("start", "end"),
    ),
}
"""Every body measured: the four joins first, then a real overhang and a real thin wall."""


def _lip(kernel: Kernel) -> dict[str, object]:
    """The tap's own tangent lip: every triangle of the tap's start that leans past ASA's
    limit, how far it leans, and how far its corners stand from the run's axis."""
    body, radius = _tap_body()
    mesh = kernel.mesh(body)
    leans: list[float] = []
    reach: list[float] = []
    for corners, ref in zip(triangles(mesh), mesh.refs, strict=True):
        n = normal(corners)
        if ref != "tap/start" or n is None:
            continue
        lean = math.degrees(math.asin(max(-1.0, min(1.0, -n.z))))
        if lean > math.degrees(ASA.max_overhang):
            leans.append(lean)
            reach += [math.hypot(p.x, p.y) for p in corners]
    return {"radius": radius, "leans": leans, "reach": reach}


def measured(kernel: Kernel) -> dict[str, object]:
    """Everything ``test_seams_measured.py`` reads, built by ``kernel``."""
    found: dict[str, object] = {}
    for key, build in BODIES.items():
        body = build()
        found[key] = {
            one.name: {
                "overhangs": None
                if (leaning := overhangs(body, UPRIGHT, one, kernel=kernel)) is None
                else [leaning.message, [str(r) for r in leaning.refs]],
                "wall": None
                if (thin := wall(body, one.min_wall, kernel=kernel)) is None
                else thin.message,
            }
            for one in (PLA, ASA)
        }
    return {"bodies": found, "lip": _lip(kernel)}
