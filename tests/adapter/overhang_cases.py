"""The parts ``test_overhangs_measured.py`` asks the shipped kernel about, answered inside Pyodide.

:mod:`tools.stack` writes this file beside ``bench`` in the runtime the app ships, and
:func:`measured` builds parts with more than one place that needs support - a ledge beside a
tube lying on its side, one bar hanging off both sides of its post, caps of two sizes, a slab
tilted short of a ceiling - and runs the overhang check on each, beside a printed part handed
to the checks whole. It imports nothing but ``bench`` and the standard library, and decides
nothing: every assertion is in the test module.
"""

import math

from bench import (
    ORIGIN,
    Axis,
    Orient,
    Point,
    Printed,
    Solid,
    Vector,
    X,
    Y,
    cuboid,
    cut,
    cylinder,
    move,
    overhangs,
    part,
    rotate,
    run,
    union,
    wall,
)
from bench.checks import Violation
from bench.kernel import Kernel
from bench.library.print import PLA


def _vent() -> Solid:
    """The shape task-78 was found on, cut down to its two overhangs: a post with a ledge
    run out from one side near the top, and a tube lying on its side run out from the other
    lower down - a side port - both hanging over nothing. The ledge's underside is a
    ceiling, the port's underside and its bore's crown lean all but 90 degrees, and the
    three are on three different faces, none of them touching another."""
    post = cuboid(20.0, 20.0, 60.0, label="post")
    ledge = cuboid(15.0, 20.0, 4.0, at=Point(20.0, 0.0, 50.0), label="ledge")
    lying = Axis(ORIGIN, Y)
    outer = rotate(cylinder(8.0, 30.0, label="port"), -math.pi / 2, about=lying)
    bore = rotate(cylinder(5.0, 32.0), -math.pi / 2, about=lying)
    port = cut(
        move(outer, Vector(1.0, 10.0, 25.0)), move(bore, Vector(1.0, 10.0, 25.0)), label="bore"
    )
    return union(union(post, ledge), port)


def _bar() -> Solid:
    """A post with a bar across its top, hanging 15 mm off either side: the bar's one
    ``bottom`` is two ceilings of the same lean and the same size, one each side."""
    post = cuboid(10.0, 10.0, 30.0, label="post")
    bar = cuboid(40.0, 10.0, 5.0, at=Point(-15.0, 0.0, 30.0), label="bar")
    return union(post, bar)


def _capped(sizes: tuple[float, ...]) -> Solid:
    """A post per size, each with a square cap that far across on top: every cap's
    underside is a ceiling, all of them leaning alike and each on a face of its own name.
    A plate under them all keeps them one body."""
    body = cuboid(40.0 * len(sizes), 40.0, 2.0, label="plate")
    for n, size in enumerate(sizes):
        x = 40.0 * n + 20.0
        post = cuboid(6.0, 6.0, 20.0, at=Point(x - 3.0, 17.0, 2.0), label=f"post-{n}")
        cap = cuboid(
            size, size, 3.0, at=Point(x - size / 2, 20.0 - size / 2, 22.0), label=f"cap-{n}"
        )
        body = union(union(body, post), cap)
    return body


def _tilted() -> Solid:
    """A post with a slab on its top tilted 30 degrees - its underside leans 60, past PLA's
    45 - built first, and a flat ledge lower down built after it, leaning 90. Built in that
    order so the steeper is not the first a walk over the mesh meets."""
    post = cuboid(20.0, 20.0, 60.0, label="post")
    slab = rotate(
        cuboid(20.0, 30.0, 3.0, at=Point(0.0, -5.0, 60.0), label="slab"),
        math.radians(30.0),
        about=Axis(Point(10.0, 10.0, 60.0), X),
    )
    ledge = cuboid(10.0, 20.0, 4.0, at=Point(20.0, 0.0, 30.0), label="ledge")
    return union(union(post, slab), ledge)


def _rod() -> Solid:
    """A rod lying along X, lifted clear of the bed: its underside leans 90 degrees drawn
    as it is, and nothing leans at all stood on its end."""
    return move(rotate(cylinder(2.0, 40.0), math.pi / 2, about=Axis(ORIGIN, Y)), Vector(0, 0, 2.0))


SCRIPT = """\
from bench import *
from bench.library.print import PLA

bar = union(cuboid(10, 10, 30, label="post"), cuboid(40, 10, 5, at=Point(-15, 0, 30), label="bar"))
tee = part("tee", bar, Printed(PLA))
check_overhangs(tee)
show(tee)
"""
"""The bar, as a part a script hands to ``check_overhangs`` whole."""


def _found(found: Violation | None) -> list[object] | None:
    return None if found is None else [found.message, [str(one) for one in found.refs]]


def measured(kernel: Kernel, tote: str) -> dict[str, object]:
    """Everything ``test_overhangs_measured.py`` reads, built by ``kernel`` - ``tote`` is
    the source of ``examples/systainer_tote.py``, run as the app runs it."""
    upright = Orient()
    on_end = Orient(up=X)
    rod = _rod()
    lying = part("rod", rod, Printed(PLA))
    standing = part("rod", rod, Printed(PLA, on_end))
    thin = cut(
        cuboid(20.0, 20.0, 20.0), cuboid(19.0, 19.0, 19.0, at=Point(0.5, 0.5, 0.5)), label="void"
    )
    return {
        "vent": _found(overhangs(_vent(), upright, PLA, kernel=kernel)),
        "bar": _found(overhangs(_bar(), upright, PLA, kernel=kernel)),
        "caps": _found(overhangs(_capped((12.0, 20.0)), upright, PLA, kernel=kernel)),
        "many": _found(overhangs(_capped((12.0,) * 7), upright, PLA, kernel=kernel)),
        "tilted": _found(overhangs(_tilted(), upright, PLA, kernel=kernel)),
        "rod": {
            "bare_flat": _found(overhangs(rod, upright, PLA, kernel=kernel)),
            "bare_on_end": _found(overhangs(rod, on_end, PLA, kernel=kernel)),
            "part_flat": _found(overhangs(lying, kernel=kernel)),
            "part_on_end": _found(overhangs(standing, kernel=kernel)),
            "overridden": _found(overhangs(standing, upright, kernel=kernel)),
        },
        "wall": {
            "bare": _found(wall(thin, PLA.min_wall, kernel=kernel)),
            "part": _found(wall(part("box", thin, Printed(PLA)), PLA.min_wall, kernel=kernel)),
        },
        "script": run(SCRIPT, kernel=kernel),
        "tote": run(tote, kernel=kernel),
    }
