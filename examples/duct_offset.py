"""A round duct that steps sideways - an S-bend offset - with a flange mated on its far end.

Two bends of the same radius, one each way, move a duct across without turning it: it leaves
the way it came in, `offset` millimetres over. The path is written the way a duct is
described - straight on, round so far towards X, round as far back - and the circle is swept
along it with `sweep`, then hollowed with `shell`, open at both ends. A sweep keeps its
names, so the far end is `duct/end`, a flat face with the profile's own frame carried round
both bends, and the flange is put on it with `mated` the same way a lid goes on a box.

It prints standing on its start: the bends lean no further off the vertical than the angle
they turn, and that stays under 45 degrees for every offset the panel allows.
"""

import math
from dataclasses import dataclass

from bench import *
from bench.library.print import H2D, PLA

stock = Printed(PLA)  # standing on its start face, the duct rising off the bed


@dataclass(frozen=True, slots=True, kw_only=True)
class Duct:
    """The duct's size, how far it steps over, and the flange on its end."""

    diameter: float = knob(50.0, min=20.0, max=120.0, step=1.0, label="Outside diameter")
    wall: float = knob(2.0, min=1.2, max=5.0, step=0.2, label="Wall")
    offset: float = knob(40.0, min=5.0, max=80.0, step=1.0, label="Offset")
    radius: float = knob(80.0, min=65.0, max=200.0, step=5.0, label="Bend radius")
    straight: float = knob(20.0, min=5.0, max=60.0, step=1.0, label="Straight ends")
    flange: float = knob(15.0, min=5.0, max=40.0, step=1.0, label="Flange width")


def _turn(p: Duct) -> float:
    """How far each bend turns: two bends of radius R, each turning a, step the path over by
    2 R (1 - cos a). The panel's widest offset is under twice its tightest radius."""
    return math.acos(1.0 - p.offset / (2.0 * p.radius))


def duct(p: Duct) -> Solid:
    """The duct as it prints: its start on the bed at the origin, rising along +Z."""
    turn = _turn(p)
    route = path(
        ORIGIN,
        Z,
        Straight(p.straight),
        Bend(p.radius, turn, X),
        Bend(p.radius, turn, -X),
        Straight(p.straight),
    )
    return shell(sweep(fill(circle(p.diameter / 2)), route), p.wall, open=("start", "end"))


def flange(p: Duct) -> Solid:
    """A ring as wide as `flange` round the duct's bore, drawn flat at the origin."""
    bore = p.diameter / 2 - p.wall
    ring = face(circle(p.diameter / 2 + p.flange), holes=(circle(bore),))
    return extrude(ring, 4.0, label="ring")


def build(p: Duct) -> Assembly:
    held = part("duct", duct(p), stock)
    # The flange's back face on the duct's far end, centred on it: both frames stand at the
    # middle of the circle they were drawn round, so nothing is said about offset or spin.
    fitted = mated(
        held, ref("duct/end"), part("flange", flange(p), stock), ref("flange/ring/bottom")
    )
    print(fitted)

    require(check_fits(held.shape, H2D))
    check_wall(held.shape, PLA.min_wall)
    turn = math.degrees(_turn(p))
    print(f"duct {p.diameter:.0f} mm across, {p.offset:.0f} mm over, bends of {turn:.1f} degrees")
    return assembly("duct", (Placed(held, XY), Placed(fitted.part, XY)), posed=True)


show(build)
