"""A dust collector's branch line, as `library/ducts` calls: a wye off the main, a coupler, a
reducer down to the tool's size, an elbow, and a hood from a rectangular opening to the round.

What the wall vent's manifold drew by hand - a socket at a sliding fit, a port a hose slips
over, a hopper leaning 45 degrees into a round port - is one call each here, sized off a
table of real hoses and ports rather than a knob in inches. `port-4` is a 4 inch fitting's
port, sold by its outside, so the wye's spigots are drawn at 4 inches and the coupler's
sockets a slide wider; pick `hose-4` instead and the spigots come out a slide under the
hose's inside. Which side a size is measured on is the table's, not the script's, and so is
the menu of sizes: a knob typed `ducts.SizeName` offers every one.

Every fitting is drawn standing on its start the way it prints (`ducts.UPRIGHT`), and
`ducts.place` puts each one on the line by an end - onto the wye's tap, into the socket
before it - turning it with the way it prints, so each is checked for overhangs and walls
where it is shown and still standing as it prints. Two couplers of the tool's size join the
spigots the reducer, the elbow and the hood end in. The elbow's turn stops at 45 degrees,
what PLA holds up; `ducts.elbow` draws any turn, and past that the overhang check says so.
Every spigot goes into its socket to a millimetre short of the stop - past that the spigot's
end meets the stop, which is where it is meant to be and is a seat, not a fit - and the fit
test slides the first coupler down the wye's tap to there.
"""

import math
from dataclasses import dataclass

from bench import *
from bench.library import ducts
from bench.library.print import H2D, PLA, clearance

stock = Printed(PLA, ducts.UPRIGHT)  # every fitting stands on its start, rising up +Z

slide = clearance(Fit.SLIDE, PLA)

seat = ducts.SOCKET_DEPTH - 1.0  # how far each spigot goes into its socket


@dataclass(frozen=True, slots=True, kw_only=True)
class Line:
    """The two sizes the line joins, the elbow's turn, the hood's opening, and the fit test."""

    main: ducts.SizeName = knob("port-4", label="Main line")
    drop: ducts.SizeName = knob("port-2.5", label="Drop to the tool")
    turn: float = knob(45.0, min=10.0, max=45.0, step=5.0, label="Elbow turn (degrees)")
    hood_w: float = knob(120.0, min=60.0, max=200.0, step=5.0, label="Hood opening width")
    hood_d: float = knob(50.0, min=30.0, max=120.0, step=5.0, label="Hood opening depth")
    wall: float = knob(2.0, min=1.4, max=4.0, step=0.2, label="Wall")
    samples: int = knob(5, min=3, max=21, step=2, label="Fit test poses")


def joined(name: str, body: Solid, onto: Plane, end: ducts.End = "start") -> Part:
    """``body``'s ``end`` put ``seat`` into the opening ``onto`` - a socket over a spigot, or a
    spigot into a socket - facing back along it."""
    at = onto.origin - onto.normal * seat
    return ducts.place(part(name, body, stock), end, at=at, toward=-onto.normal)


def build(p: Line) -> Assembly:
    main, drop = ducts.SIZES[p.main], ducts.SIZES[p.drop]
    wye = part("wye", ducts.branch(main, wall=p.wall), stock)
    tap = ducts.end_of(wye.shape, "tap")
    coupler_body = ducts.coupler(main, wall=p.wall)
    coupler = joined("coupler", coupler_body, tap)
    reducer = joined("reducer", ducts.reducer(main, drop, wall=p.wall), ducts.end_of(coupler.shape))
    sleeve = ducts.coupler(drop, wall=p.wall)
    lower = joined("coupler-2", sleeve, ducts.end_of(reducer.shape))
    elbow = joined(
        "elbow", ducts.elbow(drop, math.radians(p.turn), wall=p.wall), ducts.end_of(lower.shape)
    )
    upper = joined("coupler-3", sleeve, ducts.end_of(elbow.shape))
    hood = joined(
        "hood",
        ducts.square_to_round(p.hood_w, p.hood_d, drop, wall=p.wall),
        ducts.end_of(upper.shape),
        "end",
    )

    fittings = (wye, coupler, reducer, lower, elbow, upper, hood)
    for one in fittings:
        require(check_fits(one, H2D))
        check_overhangs(one.shape, one.stock.orient, PLA)
        check_wall(one.shape, PLA.min_wall)

    # The coupler slid down the wye's tap: well clear of it at 0, and at 1 where it is seated.
    def slid(t: float) -> Assembly:
        off = (1.0 - t) * (ducts.SOCKET_DEPTH + 5.0)
        on = Plane(tap.origin + tap.normal * off, tap.normal, tap.x_dir)
        return assembly(
            "slid", (Placed(wye, XY), Placed(joined("coupler", coupler_body, on), XY)), posed=True
        )

    print(f"coupler round the wye's tap: {check_fit(coupler.shape, wye.shape, Fit.SLIDE, PLA)}")
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
    return assembly("line", tuple(Placed(one, XY) for one in fittings), posed=True)


show(build)
