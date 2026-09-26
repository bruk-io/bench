"""A jar and the lid that screws onto it: a printed thread on the neck, and the same thread
cut into the lid at `Fit.CLEARANCE`.

Both threads are `thread(...)`: an offset circle swept up the neck turning a whole turn per
pitch, which is a twisted extrusion and nothing else. The jar's is `Thread.EXTERNAL`, drawn
at the nominal size; the lid's is `Thread.INTERNAL`, the cavity cut out of it, opened by
what the fit table says PLA wants at that fit - measured square to the leaning flank, not
just across the crest - and grown by PLA's hole compensation, as any printed hole is. Drawn about the same axis from the same `at`, the two are one helix,
so the lid is designed in place, already screwed on, and `check_clearance` measures the
gap between them on the bodies themselves.

The thread's side is one face, `jar/neck/side-0`, however many turns it makes: the naming
rule gives a side per profile edge and the profile is one circle. It is neither flat nor
round, so nothing can be sketched on it with `plane_of`.

The depth is left to `thread`: about a quarter of the pitch, the deepest round thread whose
steepest flank leans 40 degrees - so the neck prints upright with no support, and the lid,
printed on its face, has the same flanks leaning the other way. The jar's overhangs are
checked. The lid's are not: its thread stops in a flat ledge where the well above it is cut,
and printed on its face that ledge is a short bridge - as wide as the thread is deep, round
the inside of the skirt - which `check_overhangs` reports, correctly, as a face leaning 90
degrees. Ending the thread in a taper instead would take a loft this example does not need.
"""

from dataclasses import dataclass

from bench import *
from bench.library.print import H2D, PLA, clearance


@dataclass(frozen=True, slots=True, kw_only=True)
class Jar:
    """The jar's neck and thread, its body, and the lid's wall."""

    neck_d: float = knob(40.0, min=20.0, max=100.0, step=1.0, label="Neck (thread) diameter")
    pitch: float = knob(3.0, min=2.0, max=5.0, step=0.5, label="Thread pitch")
    turns: float = knob(2.5, min=1.5, max=5.0, step=0.5, label="Thread turns")
    body_h: float = knob(30.0, min=10.0, max=120.0, step=1.0, label="Body height")
    wall: float = knob(2.0, min=1.2, max=5.0, step=0.2, label="Wall")


jar_stock = Printed(PLA)  # upright, neck up
lid_stock = Printed(PLA, Orient(up=-Z))  # on its face, skirt up

fit = Fit.CLEARANCE
gap = clearance(fit, PLA)  # per side, square to the flank
axial = 0.5  # what the lid stands off the shoulder, and its ceiling off the neck


def build(p: Jar) -> Assembly:
    length = p.turns * p.pitch
    depth = p.pitch * ROUND_DEPTH
    start = Point(0.0, 0.0, p.body_h - 1.0)  # a millimetre down into the body, so it joins
    neck_top = p.body_h + length - 1.0
    root = p.neck_d / 2 - depth
    opened = thread_opening(gap, p.pitch, depth) + PLA.hole_compensation / 2
    crest = p.neck_d / 2 + opened  # the lid thread's reach

    # ---- the jar: a body, a threaded neck on it, hollowed from the floor up -----------

    body = cylinder(crest + 2 * p.wall, p.body_h, label="body")
    neck = thread(Thread.EXTERNAL, p.neck_d, p.pitch, length, at=start, label="neck")
    jar = union(body, neck)
    inside = cylinder(root - p.wall, neck_top - p.wall + 1.0, at=Point(0.0, 0.0, p.wall))
    jar = cut(jar, inside, label="inside")

    # ---- the lid: a cap round the neck, its thread cut where the neck's already is ----

    lid_z = p.body_h + axial
    ceiling = neck_top + axial
    lid = cylinder(crest + p.wall, ceiling + p.wall - lid_z, at=Point(0.0, 0.0, lid_z))
    tool = thread(Thread.INTERNAL, p.neck_d, p.pitch, length, material=PLA, fit=fit, at=start)
    lid = cut(lid, tool, label="thread")
    lid = cut(
        lid,
        cylinder(crest, ceiling - neck_top + 0.5, at=Point(0.0, 0.0, neck_top - 0.5)),
        label="well",
    )

    require(check_fits(jar, H2D))
    require(check_fits(lid, H2D))
    check_clearance(jar, lid, gap)
    check_overhangs(jar, jar_stock.orient, PLA)

    print(f"{p.neck_d:g} mm x {p.pitch:g} thread, {p.turns:g} turns, {depth:.2f} mm deep")
    print(f"lid thread opened {opened:.2f} mm so the printed flanks clear by {gap:.2f}")

    return assembly(
        "jar",
        (
            Placed(part("jar", jar, jar_stock), XY),
            Placed(part("lid", lid, lid_stock), XY),
        ),
    )


show(build)
