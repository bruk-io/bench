"""A Systainer-style stacking tote, printed, without its lid.

Four tapered plugs stand on the rim and four tapered sockets are sunk into the underside,
each one `clearance(fit, material)` wider a side, so a tote stacks on the tote below it and
the fit is the material's table rather than a number somebody typed. The taper is the point:
a straight plug in a straight socket rattles by twice the clearance, while a tapered one
wedges and centres itself as it seats. The real thing drafts its feet about 30 degrees a
side at the front and 6 at the back - measured off a printable SYS3 M187 - so `draft` here
is a knob rather than a constant.

**What a taper costs, and why it is spent here.** A taper is a `loft`, a `hull` of two
profiles, and a hull destroys identity: the plug answers to `tote/boss-1` and has no named
top or side under it. That is the trade this example exists to show. The lip is lofted too:
the wall runs straight at `wall` from the floor until the last `lip` millimetres, where it
thickens into the `rim` the plugs stand on, which is where a real Systainer keeps its
stiffness. Straight below and thick only at the top is the way round that matters - a wall
that thickened all the way up would make the opening the narrowest part of the tote and turn
the inside into an undercut nothing could be lifted back out of. Everything that must stay
nameable - the grip cut-outs, the latch lugs, the pin bores - is still built from extrusions
and cuts.

**What this does not do.** A plug in a socket resists shear and nothing else. A real
Systainer resists *lift* - rear hooks with an undercut section drop into the handle recess
of the lid below, and the front latch clamps both boxes at once - which is what lets you
carry a whole stack by the top handle. There are no hooks here, so these totes stack but a
stack is not one object. The latch lugs are the beginning of that story, not the end of it.

`check_overhangs` reports one face and it is `socket-1`: the ceiling of a blind pocket is
horizontal however far its walls are drafted. It is left standing. A flat roof spanning a
closed sixteen millimetre square is a bridge, which a slicer lays down without support, and
the check measures the angle a face leans rather than the distance it has to cross - which
is the honest thing for it to measure and the reason the warning is worth reading rather
than silencing. `gridfinity_bin.py` reaches the same junction and declines the check
outright; this one takes the warning instead.

Everything is drawn corner-at-origin, the way `rect`, `rounded_rect` and `cuboid` all place
themselves, so every offset in here is measured from the tub's own front-left-bottom corner
rather than from a centre that does not exist.
"""

import math
from dataclasses import dataclass
from typing import Literal

from bench import *
from bench.library.print import ASA, H2D, PETG, PLA, clearance

MATERIALS = {"PLA": PLA, "PETG": PETG, "ASA": ASA}


@dataclass(frozen=True, slots=True, kw_only=True)
class Tote:
    """The tote's outside, its wall, and how it stacks."""

    w: float = knob(296.0, min=120.0, max=340.0, step=4.0, label="Width")
    d: float = knob(200.0, min=100.0, max=300.0, step=4.0, label="Depth")
    h: float = knob(105.0, min=60.0, max=220.0, step=5.0, label="Height")
    wall: float = knob(2.4, min=1.6, max=4.0, step=0.2, label="Wall at the floor")
    floor: float = knob(6.0, min=3.0, max=10.0, step=0.5, label="Floor")
    radius: float = knob(12.0, min=4.0, max=30.0, step=1.0, label="Corner radius")
    lip: float = knob(24.0, min=8.0, max=60.0, step=2.0, label="Lip band")
    boss: float = knob(16.0, min=10.0, max=28.0, step=1.0, label="Stacking plug")
    boss_h: float = knob(4.0, min=2.0, max=8.0, step=0.5, label="Plug height")
    draft: float = knob(12.0, min=0.0, max=30.0, step=1.0, label="Plug draft, degrees")
    ribs: int = knob(5, min=0, max=12, step=1, label="Buttress ribs a side")
    grip: bool = knob(True, label="Grip cut-outs")
    material: Literal["PETG", "PLA", "ASA"] = "PETG"
    stack_fit: Literal["SNUG", "SLIDE", "CLEARANCE"] = "SLIDE"


RIB_T = 3.0  # how far a rib stands off the wall
LUG_W, LUG_D, LUG_H = 26.0, 12.0, 14.0
GRIP_W, GRIP_H = 96.0, 24.0
LEDGE = 1.0  # the least rim left outside a plug; the material usually asks for more
LIP_FLAT = 4.0  # how much of the mouth is straight, so the rim's inner edge is not a feather


def _tapered(size: float, at: Point, z: float, height: float, draft: float, r: float) -> Solid:
    """A plug `size` square at `z`, drafted in by `draft` degrees a side as it rises.

    The one hull in this script, and the reason every face of it answers to the body rather
    than to a top or a side: see the module docstring.
    """
    shrink = math.tan(math.radians(draft)) * height
    top = max(size - 2 * shrink, 1.0)
    return loft(
        fill(rounded_rect(size, size, r, at), on=raised(XY, z)),
        fill(
            rounded_rect(top, top, max(r - shrink, 0.2), Point(at.x + shrink, at.y + shrink)),
            on=raised(XY, z + height),
        ),
    )


def build(p: Tote) -> Part:
    material = MATERIALS[p.material]
    printed = Printed(material)  # +Z, so the tote prints standing on its floor
    gap = clearance(Fit[p.stack_fit], material)  # per side: what a socket needs, not a fudge

    # The socket is sunk `ledge` in from the outside and is `gap` wider than the plug, so
    # what is left outboard of it is `ledge - gap` - and that is a wall like any other. Ask
    # the material how thin it may be rather than typing a number and hoping.
    ledge = max(LEDGE, material.min_wall + gap + 0.2)

    # The rim carries the plugs, so it has to be wider than one; the wall grows into it.
    rim = p.boss + 2 * ledge

    # A socket cannot be deeper than the floor it is sunk into, so the engagement is the
    # lesser of what was asked for and what the floor can give. Printed rather than
    # silently clamped: a floor too thin to hold the plug is worth seeing.
    engage = min(p.boss_h, p.floor - 1.2)
    rib_w = p.wall  # a rib thinner than the wall prints as two perimeters round a void

    # The lip cannot eat the whole wall, so it is what was asked for or what is left. Its
    # last `LIP_FLAT` is straight, so only the rest of it is slope to lean through.
    lip = max(min(p.lip, p.h - p.floor - 5.0), LIP_FLAT + 2.0)
    lip_z = p.h - lip
    flat_z = p.h - LIP_FLAT
    lean = math.degrees(math.atan((rim - p.wall) / (lip - LIP_FLAT)))

    # ---- the tub: straight walls, and a lip band that thickens into the rim ----------
    #
    # The cavity is the widest thing in the tote at every height below the lip, so the
    # opening really is the opening. Only the top `lip` thickens, and it does that in two
    # moves: a loft that leans in at an angle a printer can hold, and then a straight run
    # for the last `LIP_FLAT`. The straight run is what stops the rim's inner edge being a
    # feather - a mouth lofted right up to the top plane leaves the topmost slice the widest
    # of all, and the material under that edge tapers away to nothing.

    def _inner(z: float) -> Face:
        return fill(
            rounded_rect(
                p.w - 2 * p.wall,
                p.d - 2 * p.wall,
                max(p.radius - p.wall, 0.2),
                Point(p.wall, p.wall),
            ),
            on=raised(XY, z),
        )

    def _mouth(z: float) -> Face:
        return fill(
            rounded_rect(p.w - 2 * rim, p.d - 2 * rim, max(p.radius - rim, 0.2), Point(rim, rim)),
            on=raised(XY, z),
        )

    tub = extrude(fill(rounded_rect(p.w, p.d, p.radius)), p.h)
    tub = cut(
        tub,
        union(
            name(extrude(_inner(p.floor), lip_z - p.floor), "well"),
            union(
                loft(_inner(lip_z), _mouth(flat_z)),
                name(extrude(_mouth(flat_z), LIP_FLAT), "mouth"),
            ),
        ),
        label="cavity",
    )

    # ---- stacking: tapered plugs on the rim, tapered sockets under the floor ----------
    #
    # Placed a corner radius along each edge, so a plug stands on the straight run of the
    # rim rather than half over the rounding, and inset `ledge` from the outside so there is
    # rim under all of it. The socket repeats the plug's own taper, grown by the fit.

    if engage > 0.5:
        across = p.w - 2 * p.radius - p.boss
        up = p.d - 2 * ledge - p.boss
        seat = Point(p.radius, ledge)

        plug = _tapered(p.boss, Point(p.radius, ledge), p.h, engage, p.draft, 2.0)
        for i, one in enumerate(grid(plug, (2, 2), (X * across, Y * up))):
            tub = union(tub, name(one, f"boss-{i + 1}"))

        socket = _tapered(
            p.boss + 2 * gap,
            Point(seat.x - gap, seat.y - gap),
            0.0,
            engage + 0.4,  # a little deeper than the plug is tall, so the rims meet first
            p.draft,
            2.0 + gap,
        )
        for i, one in enumerate(grid(socket, (2, 2), (X * across, Y * up))):
            tub = cut(tub, one, label=f"socket-{i + 1}")

    # ---- buttress ribs down the long walls -------------------------------------------

    if p.ribs >= 1:
        span = p.w - 2 * p.radius - rib_w
        step = span / (p.ribs - 1) if p.ribs > 1 else 0.0
        start = p.radius if p.ribs > 1 else (p.w - rib_w) / 2
        for y, side in ((-RIB_T, "front"), (p.d, "back")):
            rib = cuboid(
                rib_w,
                RIB_T,
                p.h - p.floor - 10.0,
                at=Point(start, y, p.floor),
                label=f"rib-{side}",
            )
            for one in pattern(rib, p.ribs, X * step):
                tub = union(tub, one)

    # ---- grip cut-outs in the short ends ----------------------------------------------

    if p.grip:
        for x, side in ((-p.wall, "left"), (p.w - p.wall, "right")):
            slot_ = cuboid(
                2 * p.wall, GRIP_W, GRIP_H, at=Point(x, (p.d - GRIP_W) / 2, p.h - GRIP_H - 10.0)
            )
            tub = cut(tub, slot_, label=f"grip-{side}")

    # ---- latch lugs, with a pin bore that lies on its side ----------------------------
    #
    # The bore leans 90 degrees off the build direction, so `Top.AUTO` with a `printed` in
    # hand cuts it as a teardrop: every surface of it is then within the material's overhang
    # angle, which is what `check_overhangs` measures.

    for y, side, face_name in ((-LUG_D, "front", "side-front"), (p.d, "back", "side-back")):
        lug = cuboid(
            LUG_W,
            LUG_D,
            LUG_H,
            at=Point((p.w - LUG_W) / 2, y, p.h - LUG_H - 8.0),
            label=f"latch-{side}",
        )
        tub = union(tub, lug)
        tub = hole(
            tub,
            Point(LUG_W / 2, LUG_H / 2),
            on=plane_of(tub, f"latch-{side}/{face_name}"),
            screw=M4,
            fit=Fit.SLIDE,
            depth=LUG_D,
            printed=printed,
            label=f"pin-{side}",
        )

    inside_w, inside_d = p.w - 2 * p.wall, p.d - 2 * p.wall
    mouth_w, mouth_d = p.w - 2 * rim, p.d - 2 * rim
    print(
        f"{p.w:.0f} x {p.d:.0f} x {p.h:.0f} mm outside, {inside_w:.0f} x {inside_d:.0f} mm "
        f"inside, {mouth_w:.0f} x {mouth_d:.0f} mm through the lip"
    )
    print(
        f"wall {p.wall:.1f} mm straight to {lip_z:.0f} mm, leaning {lean:.0f} degrees into a "
        f"{rim:.1f} mm rim and standing straight for the last {LIP_FLAT:.0f} mm; "
        f"ribs {rib_w:.1f} mm wide"
    )
    if engage < p.boss_h:
        print(f"floor {p.floor:.1f} mm holds only {engage:.1f} mm of the {p.boss_h:.1f} mm plug")
    print(
        f"stacking socket {gap:.2f} mm a side in {p.material}, {engage:.1f} mm of engagement "
        f"at {p.draft:.0f} degrees of draft"
    )

    check_wall(tub, material.min_wall)
    check_overhangs(tub, printed.orient, material)
    require(check_fits(tub, H2D))

    return part("tote", tub, printed)


show(build)
