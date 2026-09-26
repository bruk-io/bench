"""A dust collector's branch line, as `library/ducts` calls: a wye off the main, a coupler, a
reducer down to the tool's size, an elbow, and a hood from a rectangular opening to the round.

What the wall vent's manifold drew by hand - a socket at a sliding fit, a port a hose slips
over, a hopper leaning 45 degrees into a round port - is one call each here, sized off a
table of real hoses and ports rather than a knob in inches. `port-4` is a 4 inch fitting's
port, sold by its outside, so the wye's spigots are drawn at 4 inches and the coupler's
sockets a slide wider; pick `hose-4` instead and the spigots come out a slide under the
hose's inside. Which side a size is measured on is the table's, not the script's.

Every fitting is drawn standing on its start the way it prints (`ducts.UPRIGHT`), and each
one's overhangs and walls are checked there. The elbow's turn stops at 45 degrees, what PLA
holds up; `ducts.elbow` draws any turn, and past that the overhang check says so. The fit test slides the coupler down onto the
wye's outlet, the way it goes on, and stops a millimetre short of the socket's stop - past
that the spigot's end meets the stop, which is where it is meant to be and is a seat, not a
fit.
"""

import math
from dataclasses import dataclass
from typing import Literal

from bench import *
from bench.library import ducts
from bench.library.print import H2D, PLA, clearance

stock = Printed(PLA, ducts.UPRIGHT)  # every fitting stands on its start, rising up +Z

slide = clearance(Fit.SLIDE, PLA)

Named = Literal[
    "hose-4", "port-4", "hose-2.5", "port-2.5", "vac-1.25", "vac-2.5", "duct-4", "duct-6"
]


@dataclass(frozen=True, slots=True, kw_only=True)
class Line:
    """The two sizes the line joins, the elbow's turn, the hood's opening, and the fit test."""

    main: Named = knob("port-4", label="Main line")
    drop: Named = knob("port-2.5", label="Drop to the tool")
    turn: float = knob(45.0, min=10.0, max=45.0, step=5.0, label="Elbow turn (degrees)")
    hood_w: float = knob(120.0, min=60.0, max=200.0, step=5.0, label="Hood opening width")
    hood_d: float = knob(50.0, min=30.0, max=120.0, step=5.0, label="Hood opening depth")
    wall: float = knob(2.0, min=1.4, max=4.0, step=0.2, label="Wall")
    samples: int = knob(5, min=3, max=21, step=2, label="Fit test poses")


def build(p: Line) -> Assembly:
    main, drop = ducts.SIZES[p.main], ducts.SIZES[p.drop]
    wye = ducts.branch(main, wall=p.wall)
    coupler = ducts.coupler(main, wall=p.wall)
    reducer = ducts.reducer(main, drop, wall=p.wall)
    elbow = ducts.elbow(drop, math.radians(p.turn), wall=p.wall)
    hood = ducts.square_to_round(p.hood_w, p.hood_d, drop, wall=p.wall)

    fittings = (
        ("wye", wye),
        ("coupler", coupler),
        ("reducer", reducer),
        ("elbow", elbow),
        ("hood", hood),
    )
    for _, body in fittings:
        require(check_fits(body, H2D))
        check_overhangs(body, stock.orient, PLA)
        check_wall(body, PLA.min_wall)

    # The coupler slid down onto the wye's outlet: well clear above it at 0, and at 1 with
    # the outlet's end a millimetre short of the socket's stop.
    outlet = bounds(wye).z1
    home = outlet + 1.0 - ducts.SOCKET_DEPTH

    def slid(t: float) -> Assembly:
        at = home + (1.0 - t) * (ducts.SOCKET_DEPTH + 5.0)
        return assembly(
            "slid",
            (
                Placed(part("wye", wye, stock), XY),
                Placed(part("coupler", move(coupler, Vector(0.0, 0.0, at)), stock), XY),
            ),
            posed=True,
        )

    seated = move(coupler, Vector(0.0, 0.0, home))
    print(f"coupler round the wye's outlet: {check_fit(seated, wye, Fit.SLIDE, PLA)}")
    print(
        f"sliding the coupler on: {check_clearance_through(slid, slide * 0.99, samples=p.samples)}"
    )

    spigot = ducts.spigot_diameter(main)
    socket = ducts.socket_diameter(main)
    print(
        f"{main.name} ({main.side} {main.diameter:.1f} mm): spigot {spigot:.2f} mm,"
        f" socket {socket:.2f} mm; {drop.name}: spigot {ducts.spigot_diameter(drop):.2f} mm"
    )
    for size in (main, drop):
        if size.estimate:
            print(f"{size.name}: {size.source}")
    return assembly("line", tuple(Placed(part(name, body, stock), XY) for name, body in fittings))


show(build)
