"""The shells ``test_shell_measured.py`` asks the shipped kernel about, answered inside Pyodide.

:mod:`tools.stack` writes this file beside ``bench`` in the runtime the app ships, and
:func:`measured` hollows bodies with :func:`bench.shell`, mates a part onto an inner floor and
runs the wall check on what came out - answering with plain JSON-able data. It imports
nothing but ``bench`` and the standard library, and decides nothing: every assertion is in the
test module.
"""

import math
from collections.abc import Callable

from bench import (
    ORIGIN,
    XY,
    Axis,
    Point,
    Printed,
    Solid,
    Vector,
    Y,
    circle,
    common,
    cuboid,
    cylinder,
    fill,
    loft,
    mating,
    move,
    part,
    raised,
    rect,
    revolve,
    shell,
    wall,
)
from bench.facets import thicknesses
from bench.kernel import Kernel, Mesh
from bench.library.print import PLA

PRINTED = Printed(PLA)

BOX = (40.0, 30.0, 20.0)
CUP = (20.0, 30.0)
FUNNEL = (30.0, 15.0, 40.0)
STEEP = (30.0, 10.0, 20.0)
"""A loft whose side leans 45 degrees off the vertical: 20 in, over 20 up."""
WALL = 2.0
THIN = 0.5
"""A wall under PLA's minimum, which the wall check has to find."""


def _box(opened: tuple[str, ...] = ()) -> Solid:
    return shell(cuboid(*BOX), WALL, open=opened)


def _cup() -> Solid:
    across, high = CUP
    return shell(revolve(fill(rect(across, high)), Axis(ORIGIN, Y)), WALL, open=("side-2",))


def _loft(bottom: float, top: float, high: float) -> Solid:
    return loft(fill(circle(bottom)), fill(circle(top), on=raised(XY, high)))


def _half_turn() -> Solid:
    ring = revolve(fill(rect(10, 10, Point(10, 0))), Axis(ORIGIN, Y), angle=math.pi)
    return shell(ring, WALL, open=("start", "end"))


CASES: dict[str, Callable[[], Solid]] = {
    "box_open": lambda: _box(("top",)),
    "box_closed": lambda: _box(),
    "tube": lambda: shell(cylinder(10.0, 20.0), WALL, open=("top", "bottom")),
    "cup": _cup,
    "funnel": lambda: shell(_loft(*FUNNEL), WALL, open=("bottom", "top")),
    "funnel_floored": lambda: shell(_loft(*FUNNEL), WALL, open=("top",)),
    "funnel_floored_moved": lambda: shell(
        move(_loft(*FUNNEL), Vector(500.0, -40.0, 7.0)), WALL, open=("top",)
    ),
    "steep": lambda: shell(_loft(*STEEP), WALL, open=("bottom", "top")),
    "half_turn": _half_turn,
    "thin": lambda: shell(cuboid(20, 20, 10), THIN, open=("top",)),
}


def mesh_data(mesh: Mesh) -> dict[str, object]:
    """A mesh as JSON: its three lists, a ref as its text."""
    return {
        "vertices": list(mesh.vertices),
        "triangles": list(mesh.triangles),
        "refs": [None if one is None else str(one) for one in mesh.refs],
    }


def _mated(kernel: Kernel) -> dict[str, object]:
    """A puck put on the open box's inner floor by name, and what it shares with the box."""
    box = _box(("top",))
    puck = part("puck", cuboid(10, 10, 3), PRINTED)
    mate = mating(box, "inside/bottom", puck, "puck/bottom", offset=Vector(10.0, 10.0, 0.0))
    placed = mate.part.shape
    assert isinstance(placed, Solid)
    return {
        "puck": mesh_data(kernel.mesh(placed)),
        "shared": kernel.volume(common(box, placed)),
        "gap": kernel.min_gap(box, placed, upto=5.0),
    }


def _walls(kernel: Kernel) -> dict[str, object]:
    """The wall check on a thin shell and on a sound one, and how thick the steep loft is
    through its side - measured from every triangle of its inner wall, which is the figure a
    loft's wall is measured level with its profiles at."""
    thin = wall(CASES["thin"](), PLA.min_wall, kernel=kernel)
    sound = wall(CASES["box_open"](), PLA.min_wall, kernel=kernel)
    steep = kernel.mesh(CASES["steep"]())
    through = [
        one
        for one, ref in zip(thicknesses(steep), steep.refs, strict=True)
        if ref == "inside" and one is not None
    ]
    return {
        "thin": None if thin is None else [thin.severity.value, thin.message],
        "sound": None if sound is None else [sound.severity.value, sound.message],
        "steep": [min(through), max(through)],
    }


def measured(kernel: Kernel) -> dict[str, object]:
    """Everything ``test_shell_measured.py`` reads, built by ``kernel``."""
    bodies = {key: build() for key, build in CASES.items()}
    return {
        "bodies": {
            key: {"volume": kernel.volume(body), "mesh": mesh_data(kernel.mesh(body))}
            for key, body in bodies.items()
        },
        "mated": _mated(kernel),
        "walls": _walls(kernel),
    }
