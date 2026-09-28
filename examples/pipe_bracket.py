"""A wall bracket for a 40 mm PVC pipe: a base, an ear the pipe passes through, two M4
mounting holes and a gusset where the ear meets the base.

It prints on its back, base flat on the bed, which is what the `Orient` in its `Printed`
says - so the 40 mm bore lies on its side and `hole(top=Top.AUTO)` reads that and gives it
a teardrop instead of an unsupported arc. Nothing else on the part leans.

There is no fillet where the ear meets the base, and on this kernel there will not be one:
a fillet needs a name for an edge that did not exist until the union made it, and a CSG
tree keeps no such name. The honest substitute is a gusset, and the honest gusset here is a
`loft` - the ear's footprint flared out where it lands on the base. It is one verb, it is
exact, and it prints without support at any flare or rise a knob can ask for, because the
loft only ever narrows going up to the ear's own footprint - never widens - so every layer
sits on the one below it.

Narrowing is also why the loft can rise no higher than `wall` without touching the pipe. The
bore's own relief - the cut that keeps the ear clear of the pipe - stops at the ear's own two
faces; past them the loft has already narrowed to nothing more than the ear's own footprint,
at whatever height `rise` asks for, and nothing has cut it back from there. The pipe's own
underside stands `wall` plus `clearance` above the base - `wall` of it is what the loft may
climb, and `clearance` is the fit table's own gap on top of that - so building at
`min(rise, wall)` leaves the gusset exactly that clearance short of the pipe, never closer.

The pipe is shown too, through the bore where it will run, with `context`: drawn translucent
beside the bracket so the fit reads at a glance, its faces answering a click as `pipe/...`,
and never a part - it is on no sheet and in no STL or 3MF. It stands where it was drawn, so
the assembly is `posed` and the bracket stays where the pipe's numbers put it too.
"""

from dataclasses import dataclass

from bench import *
from bench.library.print import H2D, PLA, clearance


@dataclass(frozen=True, slots=True, kw_only=True)
class Bracket:
    """The pipe it holds, and how much bracket goes round it."""

    pipe_d: float = knob(40.0, min=10.0, max=90.0, step=0.5, label="Pipe outside diameter")
    wall: float = knob(8.0, min=3.0, max=15.0, step=0.5, label="Material round the pipe")
    ear_t: float = knob(8.0, min=3.0, max=20.0, step=0.5, label="Ear thickness")
    base_t: float = knob(5.0, min=3.0, max=12.0, step=0.5, label="Base thickness")
    flare: float = knob(8.0, min=0.0, max=20.0, step=0.5, label="Gusset flare")
    rise: float = knob(8.0, min=1.0, max=30.0, step=0.5, label="Gusset rise")
    screw_inset: float = knob(12.0, min=6.0, max=40.0, step=0.5, label="Screw inset")


pla = Printed(PLA)  # +Z up: the base is what lies on the bed


def build(p: Bracket) -> Assembly:
    # The bore is the pipe plus the fit the table says, not a number anybody typed.
    bore_d = p.pipe_d + 2 * clearance(Fit.CLEARANCE, PLA)
    ear_w = p.pipe_d + 2 * p.wall
    axis_z = p.base_t + p.wall + bore_d / 2
    # A teardrop's apex stands r * sqrt(2) above the bore's centre, so the ear has to be
    # taller than a round hole would need or the point would break out of the top.
    ear_h = axis_z + bore_d * 0.708 + p.wall / 2
    base_w = p.ear_t + 4 * p.screw_inset
    base_d = ear_w
    ear_x = (base_w - p.ear_t) / 2

    # The base, with an elephant's-foot chamfer so it sits flat against the wall.
    base = foot_chamfer(cuboid(base_w, base_d, p.base_t), PLA.foot * 3)

    # The ear: a sketch on a plane standing across the base, extruded along the pipe's axis.
    upright = plane(Point(ear_x, 0.0, 0.0), X, Y)  # u runs +Y, v runs +Z
    ear = extrude(fill(rounded_rect(ear_w, ear_h, p.wall), on=upright), p.ear_t, label="ear")

    # The gusset: the ear's footprint flared out where it meets the base. A hull of two
    # profiles, so it is exact, and it only ever narrows going up, so it needs no support.
    # Its own top can rise no higher than the wall under the bore - past that, nothing has
    # cut it back from the pipe - so what is actually built is capped there, never the knob's
    # own number past it.
    rise = min(p.rise, p.wall)
    flared = rect(p.ear_t + 2 * p.flare, base_d, Point(ear_x - p.flare, 0.0))
    gusset = loft(
        fill(flared, on=raised(XY, p.base_t)),
        fill(rect(p.ear_t, base_d, Point(ear_x, 0.0)), on=raised(XY, p.base_t + rise)),
        label="gusset",
    )

    bracket = union(union(base, ear), gusset)

    # The saddle bore, drilled through the ear from its own outer face. Lying on its side and
    # 40 mm across, it comes out a teardrop - see `printable_top`.
    bracket = hole(
        bracket,
        Point(ear_w / 2, axis_z),
        on=plane_of(bracket, "ear/top"),
        diameter=bore_d,
        printed=pla,
        label="saddle",
    )

    # Two M4 clearance holes through the base, one each side of the ear.
    for i, x in enumerate((p.screw_inset, base_w - p.screw_inset)):
        bracket = hole(
            bracket,
            Point(x, base_d / 2),
            on=plane_of(bracket, "top"),
            screw=M4,
            fit=Fit.CLEARANCE,
            printed=pla,
            label=f"screw-{i + 1}",
        )

    # The pipe it holds, for context: a length of it through the bore, on the bore's own axis.
    reach = p.pipe_d
    pipe = extrude(
        fill(
            circle(p.pipe_d / 2, Point(ear_w / 2, axis_z)),
            on=plane(Point(ear_x - reach, 0.0, 0.0), X, Y),
        ),
        p.ear_t + 2 * reach,
    )
    context(pipe, label="pipe")

    # The gusset's own cap above is what keeps this clear; asked here too, so a future change
    # to either number cannot quietly bring the gusset back into the pipe.
    fitted = check_fit(bracket, pipe, Fit.CLEARANCE, PLA)
    require(fitted.finding)
    require(check_fits(bracket, H2D))
    check_overhangs(bracket, pla.orient, PLA)

    print(f"bore {bore_d:.2f} mm for a {p.pipe_d:.1f} mm pipe")
    print(f"bracket {base_w:.1f} x {base_d:.1f} x {ear_h:.1f} mm")
    print(f"gusset round the pipe: {fitted}")

    return assembly("pipe-bracket", (Placed(part("bracket", bracket, pla), XY),), posed=True)


show(build)
