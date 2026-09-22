"""What ``test_examples_measured.py`` asks of the shipped kernel, answered inside Pyodide.

:mod:`tools.stack` writes this file beside ``bench`` in the runtime the app ships, and
:func:`measured` runs every example with the real kernel and makes the direct kernel calls a
test needs, answering with plain JSON-able data. It imports nothing but ``bench`` and the
standard library, and decides nothing: every assertion is in the test module.
"""

import math

from bench import (
    ORIGIN,
    Axis,
    Fit,
    Orient,
    Printed,
    Ref,
    Solid,
    Vector,
    cylinder,
    hole,
    move,
    overhangs,
    plane_of,
    resolve,
    rotate,
    run,
)
from bench.kernel import Kernel
from bench.library import gridfinity3d as g3
from bench.library.print import PLA, clearance

COLLAR = "depth_stop_collar.py"
ROUND = ("top=Top.TEARDROP", "top=Top.ROUND")
"""The one edit that turns the collar's teardrop set-screw bore into a round one."""

FULCRUM = "fulcrum_hinge.py"
POSES = (
    {"deployment": 0.0, "samples": 2},
    {"deployment": 0.375, "samples": 2},
    {"deployment": 0.7, "samples": 2},
    {"deployment": 1.0, "samples": 2},
    {"deployment": 0.5, "travel": 80.0, "samples": 2},
)
"""Where the fulcrum stack is posed: closed, FIG. 9's positions two and three, open, and at
a handover with the widest travel the panel offers.

``samples`` is turned down to the two ends for these five, because what they are for is the
pose each one names; the script's own default sampling of the whole travel is measured once,
on the run in ``scenes``, and costs about a second a pose."""

COLLIDING = """\
from bench import *
from bench.library.print import PLA

pla = Printed(PLA)
left = cuboid(10, 10, 10)
right = move(cuboid(10, 10, 10), Vector(9.8, 0.0, 0.0))
stack = assembly(
    "stack",
    (Placed(part("left", left, pla), XY), Placed(part("right", right, pla), XY)),
    posed=True,
)
check_clearance_within(stack, 0.5)
show(stack)
"""
"""Two posed bodies a fifth of a millimetre into each other, asked for half a millimetre.
The measurement needs a real modeller, which is why it lives here: what it is for is the
finding that comes back, and whether it says which two parts it is between."""


THROUGH = """\
from bench import *
from bench.library.print import PLA
import math

pla = Printed(PLA)
post = cuboid(10, 10, 10)


def at(t):
    # Clear at both ends and at the quarters, and 0.2 mm into the post at t = 0.5: the
    # arm stands 2.00 mm off it at t = 0 and t = 1 and 1.45 mm off at the quarters, so a
    # maker who picked the ends, or even the ends and the quarters, is told it is clear.
    arm = move(cuboid(10, 10, 10), Vector(12.0 - 2.2 * math.sin(math.pi * t) ** 4, 0.0, 0.0))
    return assembly(
        "swing",
        (Placed(part("post", post, pla), XY), Placed(part("arm", arm, pla), XY)),
        posed=True,
    )


hand_picked = (check_clearance_within(at(0.0), 0.5), check_clearance_within(at(1.0), 0.5))
print(f"{sum(len(one) for one in hand_picked)} findings at the two ends")
through = check_clearance_through(at, 0.5, samples=5)
print(through)
show(at(0.0))
"""
"""A pair a maker would have hand-picked as clear: the arm swings out and back, and the one
pose where it fouls the post is the one halfway between the two ends. Five samples include
it; the two ends alone never do."""

SEATED = """\
from bench import *
from bench.library.print import PLA
import math

pla = Printed(PLA)
AXIS = Axis(ORIGIN, Z)


def at(t):
    # A head seated flat on a ring - coincident faces, which `min_gap` reads as zero - and
    # the two turn together, so the seat holds at every pose and nothing ever collides.
    turn = math.pi * t
    ring = rotate(cylinder(8.0, 4.0), turn, about=AXIS)
    head = rotate(move(cylinder(4.0, 3.0), Vector(0.0, 0.0, 4.0)), turn, about=AXIS)
    return assembly(
        "seat",
        (Placed(part("ring", ring, pla), XY), Placed(part("head", head, pla), XY)),
        posed=True,
    )


print(check_clearance_through(at, 0.3, samples=4, contacts=(("ring", "head"),)))
print(check_clearance_through(at, 0.3, samples=4))
show(at(0.0))
"""
"""The same motion asked twice: with the seat declared, and without. Declared, it is measured
as a contact at every one of the four poses and holds; undeclared, the coincident faces are a
gap of zero at every pose and the pair is reported once."""


def _bin_body(spec: g3.Spec) -> Solid:
    shape = g3.bin_(spec).assembly.parts[0].part.shape
    assert isinstance(shape, Solid)
    return shape


def measured(kernel: Kernel, sources: dict[str, str]) -> dict[str, object]:
    """Every example run with ``kernel``, and the measurements taken off it directly."""
    scenes = {key: run(text, kernel=kernel) for key, text in sources.items()}

    round_source = sources[COLLAR].replace(*ROUND)

    stacked = g3.Spec(units_x=2, units_y=1, height=g3.Units(3), scoop=0.5, label_tab=g3.Tab.FULL)
    body = _bin_body(stacked)
    above = move(body, Vector(0.0, 0.0, g3.derive(stacked).height))
    lip = resolve(body, Ref("lip"))
    assert isinstance(lip, Solid)

    plain = kernel.mesh(_bin_body(g3.Spec()))

    knuckle = hole(
        cylinder(4.2, 20.0),
        ORIGIN,
        on=plane_of(cylinder(4.2, 20.0), "top"),
        diameter=4.0 + 2 * clearance(Fit.SLIDE, PLA),
        printed=Printed(PLA),
        label="bore",
    )
    lying = move(
        rotate(cylinder(2.0, 40.0), math.pi / 2, about=Axis(ORIGIN, Vector(0, 1, 0))),
        Vector(0, 0, 2.0),
    )
    along = overhangs(lying, Orient(up=Vector(1, 0, 0)), PLA, kernel=kernel)
    flat = overhangs(lying, Orient(), PLA, kernel=kernel)

    return {
        "scenes": scenes,
        "poses": [run(sources[FULCRUM], overrides, kernel=kernel) for overrides in POSES],
        "colliding": run(COLLIDING, kernel=kernel),
        "through": run(THROUGH, kernel=kernel),
        "seated": run(SEATED, kernel=kernel),
        "round": {
            "edited": round_source != sources[COLLAR],
            "scene": run(round_source, kernel=kernel),
        },
        "stack_gap": kernel.min_gap(lip, above, upto=1.0),
        "lip": {
            "triangles": len(plain.triangles) // 3,
            "named": any(ref is not None and ref.startswith("lip") for ref in plain.refs),
        },
        "pin_gap": kernel.min_gap(cylinder(2.0, 20.0), knuckle, upto=1.0),
        "pin_along": None if along is None else along.severity.value,
        "pin_flat": None if flat is None else flat.severity.value,
    }
