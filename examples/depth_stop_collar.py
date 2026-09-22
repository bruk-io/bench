"""A depth-stop collar for a 6.35 mm drill shank, with a radial M4 set screw.

The part the maker review could not write at all. A collar is a cylinder, a cylinder's side
has no plane, and a hole has to be drawn on one - so `plane_of(collar, "side-0")` used to
raise and the commonest horizontal hole in the shop had nowhere to go. It now takes
`around=` and `along=`: the plane tangent to that round face a given turn round it and a
given height up it, normal pointing out of the material, in the same frame every other
sketch plane uses. The radius comes off the body, so changing the collar's diameter moves
the seat with it.

Lying on its side, the set screw's bore is the one thing on this part that cannot be
printed round, so it is cut as a teardrop: every surface of it is then at most 45 degrees
off the build direction, and `check_overhangs` passes. Ask for `top=Top.ROUND` instead and
the same check reports the ceiling of the bore, which is the honest answer.
"""

import math
from dataclasses import dataclass

from bench import *
from bench.library.print import PLA, H2D, clearance


@dataclass(frozen=True, slots=True, kw_only=True)
class Collar:
    """The shank it grips, the collar's size, and where round it the set screw goes."""

    shank: float = knob(6.35, min=3.0, max=13.0, step=0.05, label="Drill shank diameter")
    od: float = knob(16.0, min=8.0, max=40.0, step=0.5, label="Collar outside diameter")
    height: float = knob(12.0, min=5.0, max=40.0, step=0.5, label="Collar height")
    seat_turn: float = knob(0.0, min=0.0, max=360.0, step=15.0, label="Set screw, degrees")


pla = Printed(PLA)  # +Z up: the collar prints standing on one end


def build(p: Collar) -> Assembly:
    collar = cylinder(p.od / 2, p.height)

    # The shank bore. A sliding fit on a bought steel shank, so the gap is the material's fit
    # table and the compensation for a printed hole is the material's too.
    collar = hole(
        collar,
        ORIGIN,
        on=plane_of(collar, "top"),
        diameter=p.shank + 2 * clearance(Fit.SLIDE, PLA),
        printed=pla,
        label="shank",
    )

    # The set screw, radial: the plane tangent to the collar's side, half way up.
    seat = plane_of(collar, "side-0", around=math.radians(p.seat_turn), along=p.height / 2)
    collar = hole(
        collar,
        ORIGIN,
        on=seat,
        screw=M4,
        fit=Fit.PRESS,  # self-tapping into plastic - the screw cuts its own thread
        printed=pla,
        top=Top.TEARDROP,
        label="set-screw",
    )

    require(check_fits(collar, H2D))
    check_overhangs(collar, pla.orient, PLA)
    # No `check_wall` here: it measures from the middle of every triangle straight into the
    # material, and a teardrop comes to a point, so the honest answer at the apex is nought.
    # The wall that matters is arithmetic anyway - half of (od - shank), and the panel says so.

    shank_bore = p.shank + 2 * clearance(Fit.SLIDE, PLA) + PLA.hole_compensation
    print(f"shank bore {shank_bore:.2f} mm")
    print(f"set screw bore {bore(M4, Fit.PRESS) + PLA.hole_compensation:.2f} mm, half way up")

    return assembly("depth-stop", (Placed(part("collar", collar, pla), XY),))


show(build)
