"""A small mounting plate: two corners of the profile rounded, two chamfered, and the
whole plate's top rim eased round - task-71's `fillet`, `chamfer` and
`bench.library.print.rim`.

Two things a maker asks the 2D vocabulary for here.

*Chosen corners.* `fillet(wire, r, at=...)` and `chamfer(wire, d, at=...)` each take every
corner between two straight edges by default, or just the ones named in `at` - a tuple for
more than one. Here the two corners away from the wall are rounded so a hand does not catch
on them, and the two at the wall stay chamfered. Both read the corner the same way whether
it turns convex or concave, which is why `bench.ops` puts them side by side.

*The eased rim.* `rim()` generalises `eased()`: a top or a bottom, rounded or chamfered, by
a stack of hulled slices - `eased()` itself is now `rim(..., style="chamfer", top=True,
bottom=True)`. Only the top is eased here, and only rounded: every slice toward the tip
sits inside the one below it, so `check_overhangs` finds nothing. Round the *bottom* the
same way instead and it does not print clean - `docs/printing.md`'s own rule is to chamfer
an overhang rather than fillet it, because a fillet sweeps through a ceiling on its way
from vertical to flat, and `check_overhangs` is what would report it.
"""

from dataclasses import dataclass

from bench import *
from bench.library.print import H2D, PLA, rim


@dataclass(frozen=True, slots=True, kw_only=True)
class Plate:
    """The plate's size, and how far each corner and rim is eased."""

    w: float = knob(50.0, min=30.0, max=120.0, step=1.0, label="Width")
    d: float = knob(30.0, min=20.0, max=80.0, step=1.0, label="Depth")
    h: float = knob(10.0, min=6.0, max=25.0, step=0.5, label="Height")
    # Each rounded pair shares the depth edge between them and each chamfered pair shares
    # the other one, so twice the larger of the two has to stay under the depth's own
    # minimum - kept well under it here, rather than exactly at the edge a slider could
    # still reach past.
    corner_r: float = knob(6.0, min=2.0, max=6.0, step=0.5, label="Rounded corner radius")
    corner_d: float = knob(4.0, min=1.0, max=5.0, step=0.5, label="Chamfered corner size")


pla = Printed(PLA)  # +Z up: the plate lies on the bed the way it is drawn


def build(p: Plate) -> tuple[Part, ...]:
    # rect()'s corners, walked counter-clockwise from the lower-left: 0 and 1 are the two
    # nearest the far (right) side, 2 and 3 the two nearest the wall (left) side.
    outline = rect(p.w, p.d)
    outline = chamfer(outline, p.corner_d, at=(2, 3))
    outline = fillet(outline, p.corner_r, at=(0, 1))

    # Strictly smaller than the smallest feature the rim's own offset has to shrink - the
    # fillet radius most of all, since offset() collapses an arc it eats down to nothing -
    # or the slider at either end of any of the five knobs breaks the run.
    lead = 0.4 * min(p.corner_r, p.corner_d, p.h / 4)
    drop = lead * 0.75
    plate = rim(fill(outline), p.h, lead=lead, drop=drop, style="round", top=True, bottom=False)

    require(check_fits(plate, H2D))
    check_overhangs(plate, pla.orient, PLA)

    print(
        f"{p.w:.0f} x {p.d:.0f} x {p.h:.0f} mm, top rim eased {lead:.1f} mm in over {drop:.1f} mm"
    )
    print(
        "plate/bottom and plate/side-* keep their names; the eased top is a hull and names nothing"
    )

    return (part("plate", plate, pla),)


show(build)
