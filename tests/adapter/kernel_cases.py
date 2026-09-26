"""The bodies ``test_shipped_kernel.py`` measures, built and handed to a kernel.

Imported twice. pytest reads the trees off :data:`CASES` to see which arms of
:data:`~bench.topology.Node` they are made of; and :mod:`tools.stack` writes this file into
Pyodide beside ``bench``, where :func:`measured` hands every body to the shipped kernel and
answers with what came back as plain JSON-able data. So it imports nothing but ``bench`` and
the standard library, and decides nothing: every assertion is in the test module.
"""

import math
from collections.abc import Callable

from bench import (
    M3,
    ORIGIN,
    XY,
    Axis,
    Bend,
    Fit,
    Point,
    Printed,
    Solid,
    Straight,
    Top,
    Vector,
    Wire,
    X,
    boss,
    checks,
    circle,
    common,
    cuboid,
    cut,
    cylinder,
    extrude,
    face,
    fill,
    hole,
    hull,
    imported,
    loft,
    move,
    name,
    path,
    plane_of,
    pocket,
    raised,
    rect,
    revolve,
    rotate,
    rounded_rect,
    run,
    sweep,
    union,
)
from bench.checks import Violation
from bench.fasteners import DRYWALL_8, WOOD_8, Screw
from bench.kernel import Kernel, Mesh
from bench.library.print import PLA, Orient, clearance

PLATE = (60.0, 40.0, 5.0)
BOSS = (8.0, 4.0)
POCKET = (20.0, 10.0, 2.0)
BORE = (2.0, 5.0)
SUNK = 8.0
"""The thickness of the plate each countersink is cut into: deep enough for a bugle's cone."""

SCRIPTED = (
    "from bench import *\n"
    "plate = extrude(fill(rect(20, 10)), 3.0)\n"
    "plate = pocket(plate, fill(rect(6, 4, Point(5, 3)), on=plane_of(plate, 'top')),"
    " 1.0, label='well')\n"
    "show(part('tray', plate, Stock(0.0, 'PLA'), Process.PRINT))\n"
)
"""A part meshed through the seam the way a script reaches it."""

WALLED = (
    "from bench import *\n"
    "from bench.library.print import PLA\n"
    "block = cuboid(20, 20, 1.0)\n"
    "check_wall(block, 1.2)\n"
    "show(part('block', block, Printed(PLA)))\n"
)
"""A script whose own check is a measurement with a kernel and ``unchecked`` without one."""


def plate() -> Solid:
    """The reviewer's example, built the way a script would: a plate with a boss on it, a
    pocket in it and a bore through it, every sketch drawn in the plate's own numbers on the
    plate's own top face."""
    body = extrude(fill(rect(PLATE[0], PLATE[1], label="outline")), PLATE[2])
    top = plane_of(body, "top")
    body = boss(body, fill(circle(BOSS[0], Point(15, 20)), on=top), BOSS[1], label="boss")
    body = pocket(
        body, fill(rect(POCKET[0], POCKET[1], Point(30, 15)), on=top), POCKET[2], label="pocket"
    )
    return cut(body, cylinder(BORE[0], BORE[1], at=Point(50, 10)), label="bore")


def taper() -> Solid:
    return loft(fill(rect(20, 20)), fill(rect(10, 10, Point(5, 5)), on=raised(XY, 8.0)), label="t")


def capped() -> Solid:
    """A hull under a boolean, where a tagged neighbour could have lent it a name."""
    cap = loft(fill(rect(10, 10)), fill(rect(4, 4, Point(3, 3)), on=raised(XY, 6.0)), label="cap")
    return cut(cap, cylinder(1.0, 6.0, at=Point(5, 5)), label="bore")


_KNOB = fill(rect(4, 10, Point(2, 0)))
"""The profile both revolves turn: a rectangle standing clear of the axis."""


def part_turn() -> Solid:
    return revolve(_KNOB, Axis(ORIGIN, Vector(0, 1, 0)), angle=4.0, label="knob")


def whole_turn() -> Solid:
    return revolve(_KNOB, Axis(ORIGIN, Vector(0, 1, 0)), label="knob")


def elbow() -> Solid:
    """A round duct turned a quarter round a bend, which the modeller cannot sweep and bench
    meshes itself."""
    route = path(ORIGIN, Vector(0, 0, 1), Straight(10.0), Bend(20.0, math.pi / 2, X))
    return sweep(fill(circle(5.0)), route, label="elbow")


DROPPED_SIDE = 10.0
"""The edge of the cube :data:`DROPPED` is, so the arithmetic every import measurement is
checked against is one multiplication."""


def _cube_mesh(side: float) -> Mesh:
    """A cube of ``side`` standing on the origin, as the mesh a host would have dropped.

    Written out by hand rather than meshed by the kernel, so what the import is measured
    against is arithmetic and not another run of the thing being tested. Eight corners and
    twelve triangles, every one wound counter-clockwise seen from outside, which is what
    Manifold means by an oriented 2-manifold; no refs, because a file nobody's script wrote
    has none.
    """
    s = side
    corners = (
        (0.0, 0.0, 0.0),
        (s, 0.0, 0.0),
        (s, s, 0.0),
        (0.0, s, 0.0),
        (0.0, 0.0, s),
        (s, 0.0, s),
        (s, s, s),
        (0.0, s, s),
    )
    faces = (
        (0, 2, 1),
        (0, 3, 2),  # bottom, looking up at it
        (4, 5, 6),
        (4, 6, 7),  # top
        (0, 1, 5),
        (0, 5, 4),  # front
        (1, 2, 6),
        (1, 6, 5),  # right
        (2, 3, 7),
        (2, 7, 6),  # back
        (3, 0, 4),
        (3, 4, 7),  # left
    )
    return Mesh(
        tuple(value for corner in corners for value in corner),
        tuple(corner for face in faces for corner in face),
        (None,) * len(faces),
    )


DROPPED = _cube_mesh(DROPPED_SIDE)
"""A 10 mm cube as a bare mesh: what a maker drops on the view, standing in for an STL."""

TORN = Mesh((0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 10.0, 0.0), (0, 1, 2), (None,))
"""One lone triangle: a boundary that bounds nothing, and so no body at all. What a
non-manifold import has to fail on."""


def dropped() -> Solid:
    """The dropped mesh as a body, which is the whole of :data:`~bench.topology.Imported`."""
    return imported(DROPPED, label="dropped")


def shared() -> Solid:
    """Two 20 mm boxes overlapping by 10 mm on every axis, and what they share."""
    left = name(cuboid(20, 20, 20), "left")
    right = name(move(cuboid(20, 20, 20), Vector(10, 10, 10)), "right")
    return common(left, right, label="shared")


CASES: dict[str, Callable[[], Solid]] = {
    "plate": plate,
    "taper": taper,
    "capped": capped,
    "part-turn": part_turn,
    "whole-turn": whole_turn,
    "elbow": elbow,
    "shared": shared,
    "dropped": dropped,
}
"""Bodies meshed whole, and between them every arm of ``Node``."""


def _sunk(screw: Screw) -> Solid:
    """A countersunk hole for ``screw`` at its own angle, through a plate :data:`SUNK`
    thick, its cone answering to ``sunk/head``."""
    plate = cuboid(20, 20, SUNK)
    return hole(
        plate,
        Point(10, 10),
        on=plane_of(plate, "top"),
        screw=screw,
        countersink=True,
        printed=Printed(PLA),
        label="sunk",
    )


def _extra() -> dict[str, Solid]:
    """The other bodies a test meshes or weighs."""
    block = cuboid(2, 2, 2, label="block")
    drilled_plate = cuboid(20, 20, 4)
    return {
        "bore": cylinder(BORE[0], BORE[1], label="bore"),
        "flat": loft(fill(rect(10, 10)), fill(rect(4, 4, Point(3, 3))), label="flat"),
        "block": block,
        "block-moved": move(block, Vector(100, -50, 7)),
        "drilled-plate": drilled_plate,
        # A hull round an import, which is the one verb that reaches an `Imported` leaf
        # through a path nobody wrote a case for: `_cloud` in the adapter falls back to
        # building the node and reading its own vertices, and an import lands there the way
        # any node that catch-all has never heard of does. A cube is its own convex hull, so
        # this weighs what the import weighs - and if the fallback did not compose, it would
        # not build at all.
        "import-hulled": hull(imported(DROPPED), label="wrapped"),
        "import-moved": move(imported(DROPPED, label="dropped"), Vector(100, -50, 7)),
        "drilled": hole(
            drilled_plate,
            Point(10, 10),
            on=plane_of(drilled_plate, "top"),
            screw=M3,
            printed=Printed(PLA),
            label="m3",
        ),
        "sunk-m3": _sunk(M3),
        "sunk-wood-8": _sunk(WOOD_8),
        "sunk-drywall-8": _sunk(DRYWALL_8),
    }


FLANGE_SIDE = 317.5
"""The frame flange task-57 was found on, in millimetres: a 12.5 inch square, read off
``projects/frame/frame.py`` and multiplied out by hand rather than kept in inches, so a plate
built here is a plate anyone can check against the sketch without a conversion."""

FLANGE_CORNER = 6.35
"""The flange's corner radius: a quarter inch."""

FLANGE_WINDOW = 266.7
"""The flange's own window, a rounded square 10.5 inches on a side, centred in it."""

FLANGE_T = 11.1125
"""The flange's own thickness, a lower plate stands to: 0.4375 inch."""

ATTACHMENT_T = 6.35
"""The upper plate's thickness, standing off wherever the lower plate's top face is: a
quarter inch, the attachment's own base."""

_FLANGE_WINDOW_INSET = (FLANGE_SIDE - FLANGE_WINDOW) / 2
FLANGE_HOLE_D = 4.5
"""An M4 clearance hole's diameter - the four screw holes the flange is checked with."""
_FLANGE_HOLE_INSET = 9.525
_FLANGE_HOLE_ALONG = 28.575


def large_outline() -> Wire:
    """The flange's own outline: a rounded square :data:`FLANGE_SIDE` across."""
    return rounded_rect(FLANGE_SIDE, FLANGE_SIDE, FLANGE_CORNER)


def large_window() -> Wire:
    """The flange's own window: a rounded square :data:`FLANGE_WINDOW` across, centred."""
    at = Point(_FLANGE_WINDOW_INSET, _FLANGE_WINDOW_INSET)
    return rounded_rect(FLANGE_WINDOW, FLANGE_WINDOW, FLANGE_CORNER, at)


def _large_holes() -> tuple[Point, ...]:
    near, far = _FLANGE_HOLE_INSET, FLANGE_SIDE - _FLANGE_HOLE_INSET
    along, back = _FLANGE_HOLE_ALONG, FLANGE_SIDE - _FLANGE_HOLE_ALONG
    return (Point(near, along), Point(far, along), Point(near, back), Point(far, back))


def _large_plate(z0: float, height: float, label: str) -> Solid:
    """A large rounded-square plate with a rounded-square window and four corner clearance
    holes, standing from ``z0`` to ``z0 + height`` - the shape :func:`large_plates` stacks."""
    body = extrude(
        face(large_outline(), holes=(large_window(),), on=raised(XY, z0)), height, label=label
    )
    for i, at in enumerate(_large_holes()):
        body = cut(
            body,
            cylinder(FLANGE_HOLE_D / 2, height, at=Point(at.x, at.y, z0)),
            label=f"{label}-hole-{i + 1}",
        )
    return body


def large_plates(sink: float = 0.0) -> tuple[Solid, Solid]:
    """Two large rounded-square plates task-57 was found on: a lower plate from z=0 to
    :data:`FLANGE_T`, and an upper one extruded from the exact plane the lower's top face is
    on - or ``sink`` millimetres into it, for the overlap a declared contact still has to
    catch."""
    lower = _large_plate(0.0, FLANGE_T, "lower")
    upper = _large_plate(FLANGE_T - sink, ATTACHMENT_T, "upper")
    return lower, upper


def scattered_bosses(sink: float = 0.0) -> tuple[Solid, Solid]:
    """The same large flange, and two small bosses - the disc-and-boss's own 8 mm across -
    seated at opposite corners of it rather than one shared face in the middle, or sunk
    ``sink`` millimetres into it.

    What an area read off a bounding box gets wrong: two overlaps this small are real
    material a declared contact has to catch, but they sit 260-odd millimetres apart on a
    317.5 mm plate, so a box around both of them is most of the plate rather than either
    boss's own footprint. A contact area measured off the shared shape's own surface does not
    have this failure, and this is the pair that tells the two apart.
    """
    plate = _large_plate(0.0, FLANGE_T, "base")
    at = FLANGE_SIDE - 20.0
    corner_a = move(cylinder(4.0, 3.0, label="boss-a"), Vector(20.0, 20.0, FLANGE_T - sink))
    corner_b = move(cylinder(4.0, 3.0, label="boss-b"), Vector(at, at, FLANGE_T - sink))
    return plate, union(corner_a, corner_b, label="bosses")


def _checked(kernel: Kernel) -> dict[str, Violation | None]:
    """Every check a test reads, answered with ``kernel``."""
    thick = cuboid(40, 40, 4)
    block = cuboid(20, 20, 10)
    centred = cut(block, cylinder(5.0, 10.0, at=Point(10, 10), label="bore"), label="bore")
    near_edge = cut(block, cylinder(5.0, 10.0, at=Point(6.0, 10), label="bore"), label="bore")
    sideways = cut(
        block,
        move(
            rotate(cylinder(4.0, 30.0, label="bore"), math.pi / 2, about=Axis(ORIGIN, X)),
            Vector(10, 25, 5),
        ),
        label="bore",
    )
    wide = cuboid(30, 20, 20)
    front = plane_of(wide, "side-front")
    round_bore = hole(wide, Point(15, 10), on=front, diameter=8.0, top=Top.ROUND, label="pin")
    pointed = hole(wide, Point(15, 10), on=front, diameter=8.0, printed=Printed(PLA), label="pin")
    pin = cylinder(2.0, 10.0, label="pin")
    knuckle = cut(
        cuboid(10, 10, 10, at=Point(-5, -5, 0)),
        cylinder(2.0 + clearance(Fit.SLIDE, PLA), 10.0, label="bore"),
        label="bore",
    )
    # A shoulder and the face it seats on: the shape `check_contact` exists for. The boss is
    # drawn four ways - exactly seated, driven a fifth of a millimetre in, and standing clear
    # - so one pair of bodies answers every question the check is asked.
    disc = cylinder(8.0, 6.0, label="disc")
    seated = move(cylinder(4.0, 3.0, label="head"), Vector(0.0, 0.0, 6.0))
    driven = move(cylinder(4.0, 3.0, label="head"), Vector(0.0, 0.0, 5.8))
    sunk_one_micron = move(cylinder(4.0, 3.0, label="head"), Vector(0.0, 0.0, 6.0 - 0.001))
    standing_clear = move(cylinder(4.0, 3.0, label="head"), Vector(0.0, 0.0, 11.0))
    # The large faces task-57 was found on: a lower and an upper plate extruded from the
    # exact plane where the first's top face is, and the same pair sunk a micron into each
    # other - which is what a declared contact still has to fail, at this size as much as at
    # the disc and boss's.
    large_lower, large_upper = large_plates()
    _, large_upper_sunk = large_plates(sink=0.001)
    scattered_plate, scattered_seated = scattered_bosses()
    _, scattered_sunk = scattered_bosses(sink=0.001)
    return {
        "wall-thick": checks.wall(thick, 1.2, kernel=kernel),
        "wall-thin": checks.wall(thick, 6.0, kernel=kernel),
        "wall-centred": checks.wall(centred, 4.0, kernel=kernel),
        "wall-near-edge": checks.wall(near_edge, 4.0, kernel=kernel),
        "overhang-block": checks.overhangs(block, Orient(), PLA, kernel=kernel),
        "overhang-sideways": checks.overhangs(sideways, Orient(), PLA, kernel=kernel),
        "overhang-round": checks.overhangs(round_bore, Orient(), PLA, kernel=kernel),
        "overhang-teardrop": checks.overhangs(pointed, Orient(), PLA, kernel=kernel),
        "clearance-loose": checks.clearance_between(pin, knuckle, 0.15, kernel=kernel),
        "clearance-tight": checks.clearance_between(pin, knuckle, 0.5, kernel=kernel),
        "contact-seated": checks.contact_between(disc, seated, kernel=kernel),
        "contact-seated-undeclared": checks.clearance_between(disc, seated, 0.2, kernel=kernel),
        "contact-driven": checks.contact_between(disc, driven, kernel=kernel),
        "contact-driven-undeclared": checks.clearance_between(disc, driven, 0.2, kernel=kernel),
        "contact-sunk-one-micron": checks.contact_between(disc, sunk_one_micron, kernel=kernel),
        "contact-apart": checks.contact_between(disc, standing_clear, kernel=kernel),
        "contact-large-plates": checks.contact_between(large_lower, large_upper, kernel=kernel),
        "contact-large-plates-sunk-one-micron": checks.contact_between(
            large_lower, large_upper_sunk, kernel=kernel
        ),
        "contact-scattered": checks.contact_between(
            scattered_plate, scattered_seated, kernel=kernel
        ),
        "contact-scattered-sunk-one-micron": checks.contact_between(
            scattered_plate, scattered_sunk, kernel=kernel
        ),
        # The same two questions asked of a dropped mesh, which is the point of the leaf:
        # a check takes an import exactly as it takes anything else, and neither function
        # was touched to make that true.
        "clearance-imported": checks.clearance_between(
            imported(DROPPED, label="dropped"),
            move(
                cuboid(DROPPED_SIDE, DROPPED_SIDE, DROPPED_SIDE, label="candidate"),
                Vector(15, 0, 0),
            ),
            0.15,
            kernel=kernel,
        ),
        "clearance-imported-tight": checks.clearance_between(
            imported(DROPPED, label="dropped"),
            move(
                cuboid(DROPPED_SIDE, DROPPED_SIDE, DROPPED_SIDE, label="candidate"),
                Vector(15, 0, 0),
            ),
            8.0,
            kernel=kernel,
        ),
        "contact-imported": checks.contact_between(
            imported(DROPPED, label="dropped"), _candidate(), kernel=kernel
        ),
    }


def _candidate() -> Solid:
    """A box the size of the dropped cube, slid half its own width along X.

    Half of it is inside the reference and half is proud of it, so every number a fit
    measure answers with is a multiplication somebody can do in their head.
    """
    return cuboid(
        DROPPED_SIDE,
        DROPPED_SIDE,
        DROPPED_SIDE,
        at=Point(DROPPED_SIDE / 2, 0.0, 0.0),
        label="candidate",
    )


def _fit(kernel: Kernel) -> dict[str, float]:
    """How much of a candidate's volume lies inside the dropped reference's.

    The measure the whole leaf exists for: survey-diffing says two bodies have the same
    extent and the same section areas, and only a boolean says whether they occupy the same
    space. Every one of the four verbs a solid has is asked of an import here - the two
    volumes, what they share, what they make together, what is proud of the reference, and
    how far the reference stands from a body clear of it.
    """
    reference = imported(DROPPED, label="reference")
    candidate = _candidate()
    overlap = kernel.volume(common(candidate, reference, label="overlap"))
    return {
        "reference": kernel.volume(reference),
        "candidate": kernel.volume(candidate),
        "overlap": overlap,
        "both": kernel.volume(union(candidate, reference, label="both")),
        "proud": kernel.volume(cut(candidate, reference, label="proud")),
        "fraction": overlap / kernel.volume(candidate),
        "gap": kernel.min_gap(
            reference,
            move(cuboid(DROPPED_SIDE, DROPPED_SIDE, DROPPED_SIDE), Vector(15, 0, 0)),
            upto=100.0,
        ),
    }


def _refusal(kernel: Kernel) -> str | None:
    """What the kernel says when it is handed a mesh that is no body, or ``None`` if it
    says nothing - which would mean a torn import measured as if it were solid."""
    try:
        kernel.volume(imported(TORN, label="torn"))
    except ValueError as exc:
        return str(exc)
    return None


def mesh_data(mesh: Mesh) -> dict[str, object]:
    """A mesh as JSON: its three lists, a ref as its text."""
    return {
        "vertices": list(mesh.vertices),
        "triangles": list(mesh.triangles),
        "refs": [None if one is None else str(one) for one in mesh.refs],
    }


def violation_data(found: Violation | None) -> dict[str, object] | None:
    """A check's finding as JSON, or ``None`` for a check that found nothing."""
    if found is None:
        return None
    return {
        "severity": found.severity.value,
        "message": found.message,
        "refs": [str(one) for one in found.refs],
    }


def measured(kernel: Kernel) -> dict[str, object]:
    """Everything ``test_shipped_kernel.py`` reads, built by ``kernel``."""
    bodies = {key: build() for key, build in CASES.items()} | _extra()
    left = cuboid(10, 10, 10)
    return {
        "meshes": {key: mesh_data(kernel.mesh(body)) for key, body in bodies.items()},
        "volumes": {key: kernel.volume(body) for key, body in bodies.items()},
        "gaps": {
            "apart": kernel.min_gap(left, move(cuboid(10, 10, 10), Vector(15, 0, 0)), upto=100.0),
            "limited": kernel.min_gap(left, move(cuboid(10, 10, 10), Vector(15, 0, 0)), upto=2.0),
            "touching": kernel.min_gap(
                left, move(cuboid(10, 10, 10), Vector(10, 0, 0)), upto=100.0
            ),
        },
        "checks": {key: violation_data(found) for key, found in _checked(kernel).items()},
        "fit": _fit(kernel),
        "refusal": _refusal(kernel),
        "scripted": run(SCRIPTED, kernel=kernel),
        "walled": run(WALLED, kernel=kernel),
    }
