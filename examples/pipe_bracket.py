"""A wall bracket for a 40 mm PVC pipe: a base, an ear the pipe passes through, two M4
mounting holes and a gusset where the ear meets the base.

It prints on its back, base flat on the bed, which is what the `Orient` in its `Printed`
says - so the 40 mm bore lies on its side and `hole(top=Top.AUTO)` reads that and gives it
a teardrop instead of an unsupported arc. Nothing else on the part leans.

There is no fillet where the ear meets the base, and on this kernel there will not be one:
a fillet needs a name for an edge that did not exist until the union made it, and a CSG
tree keeps no such name. The honest substitute is a gusset, and the honest gusset here is a
`loft` - the ear's footprint flared out where it lands on the base. It is one verb, it is
exact, and it prints, which a hand-made triangular fin also would be but only after four
more lines of arithmetic.
"""

from dataclasses import dataclass

from bench import *
from bench.library.print import PLA, H2D, clearance


@dataclass(frozen=True, slots=True, kw_only=True)
class Bracket:
    """The pipe it holds, and how much bracket goes round it."""

    pipe_d: float = knob(40.0, min=10.0, max=90.0, step=0.5, label="Pipe outside diameter")
    wall: float = knob(8.0, min=3.0, max=15.0, step=0.5, label="Material round the pipe")
    ear_t: float = knob(8.0, min=3.0, max=20.0, step=0.5, label="Ear thickness")
    base_t: float = knob(5.0, min=3.0, max=12.0, step=0.5, label="Base thickness")
    flare: float = knob(8.0, min=0.0, max=20.0, step=0.5, label="Gusset flare")
    rise: float = knob(10.0, min=1.0, max=30.0, step=0.5, label="Gusset rise")
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
    # profiles, so it is exact, and it leans well under 45 degrees.
    flared = rect(p.ear_t + 2 * p.flare, base_d, Point(ear_x - p.flare, 0.0))
    gusset = loft(
        fill(flared, on=raised(XY, p.base_t)),
        fill(rect(p.ear_t, base_d, Point(ear_x, 0.0)), on=raised(XY, p.base_t + p.rise)),
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

    require(check_fits(bracket, H2D))
    check_overhangs(bracket, pla.orient, PLA)

    print(f"bore {bore_d:.2f} mm for a {p.pipe_d:.1f} mm pipe")
    print(f"bracket {base_w:.1f} x {base_d:.1f} x {ear_h:.1f} mm")

    return assembly("pipe-bracket", (Placed(part("bracket", bracket, pla), XY),))


show(build)
