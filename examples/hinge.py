"""A two-part hinge with a printed pin: three interleaved knuckles, every rim eased, and a
pin that turns in the bores at `Fit.SLIDE`.

Three things a maker asks for here, and only one of them was in the vocabulary.

*The fit.* `clearance(Fit.SLIDE, PLA)` is a plain function, so the bore is the pin plus the
gap the table says, per side. `hole(printed=...)` adds what the filament takes back off a
printed hole on top of that, which is why the bore as drawn is wider than pin plus fit: it
comes out of the printer at pin plus fit.

*The rim chamfer.* `eased()`, from the print library, is a prism whose rims are chamfered
by how the shape is made rather than by finding an edge afterwards - see its docstring in
`bench.library.print` for why there is no chamfer verb for the edge of a solid on this
kernel and is not going to be one.

*The overhang.* The leaves print flat, knuckles down, which is how a hinge is printed and
how the layers end up running across a leaf rather than along it. A round knuckle lying on
the bed leans past 45 degrees for the first millimetre of its rise, so `check_overhangs` on
a leaf reports it - correctly. It is left out of this script on purpose: the remedy would
be a knuckle that is not round, and a knuckle that is not round does not turn. The pin is
checked, because the pin has a choice: it prints standing on its end, `Orient(up=X)`, where
it comes out round and nothing leans, rather than lying down where it comes out elliptical.
"""

from dataclasses import dataclass

from bench import *
from bench.library.print import H2D, PLA, clearance, eased


@dataclass(frozen=True, slots=True, kw_only=True)
class Hinge:
    """The hinge's size, and the pin and knuckle wall it turns on."""

    width: float = knob(42.0, min=20.0, max=120.0, step=1.0, label="Hinge width")
    reach: float = knob(22.0, min=10.0, max=60.0, step=1.0, label="Leaf reach")
    leaf_t: float = knob(3.0, min=1.6, max=8.0, step=0.2, label="Leaf thickness")
    pin_d: float = knob(4.0, min=2.0, max=10.0, step=0.5, label="Pin diameter")
    knuckle_wall: float = knob(2.0, min=1.2, max=6.0, step=0.2, label="Knuckle wall")


leaf_stock = Printed(PLA)  # flat on the bed, knuckles down
pin_stock = Printed(PLA, Orient(up=X))  # standing on its end, so it comes out round

gap = clearance(Fit.SLIDE, PLA)  # per side, and the axial gap between knuckles too
lead, drop = 0.5, 1.0  # the rim chamfer: 0.5 in over 1.0 along, well under 45 degrees


def build(p: Hinge) -> Assembly:
    bore_d = p.pin_d + 2 * gap
    r = bore_d / 2 + p.knuckle_wall  # the knuckle's outside radius
    pitch = p.width / 3
    knuckle_w = pitch - gap

    def knuckle(index: int, side: float) -> Solid:
        """One knuckle of the three: the barrel, plus the web that joins it to its own leaf.

        The web spans the knuckle's own width and no more, which is what keeps a leaf clear
        of the other leaf's barrels - a full-width plate reaching in to the pin would have to
        pass through them. ``side`` is which way its own leaf runs, ``+1`` or ``-1``.
        """
        at_x = index * pitch + gap / 2
        axis = plane(Point(at_x, 0.0, r), X, Y)  # u runs +Y, v runs +Z, the sweep runs +X
        web = cuboid(
            knuckle_w,
            r + gap,
            p.leaf_t,
            at=Point(at_x, 0.0 if side > 0 else -(r + gap), 0.0),
            label="web",
        )
        barrel = eased(fill(circle(r), on=axis), knuckle_w, lead=lead, drop=drop)
        return name(union(barrel, web), "knuckle")

    def leaf(knuckles: tuple[Solid, ...], side: float) -> Solid:
        """One leaf: a plate, its knuckles, and the pin bore straight through the lot.

        The plate stops a clearance short of the barrels so that the two leaves never touch.
        """
        plate_d = p.reach - r - gap
        y0 = r + gap if side > 0 else -(r + gap + plate_d)
        body = cuboid(p.width, plate_d, p.leaf_t, at=Point(0.0, y0, 0.0))
        for one in knuckles:
            body = union(body, one)
        # One bore for the whole leaf, drilled from the outermost barrel's end face: `at` is
        # the origin because that face's frame is the barrel's own axis. Lying on its side
        # and wider than a printer walks across, the bore comes out a teardrop. The rim beyond
        # that face is a hull and a hull names nothing, so the mouth is that face raised by
        # the chamfer it hides - or the last millimetre of the knuckle would stay solid.
        last = raised(plane_of(body, f"knuckle-{len(knuckles)}/top"), drop)
        return hole(body, ORIGIN, on=last, diameter=bore_d, printed=leaf_stock, label="bore")

    leaf_a = leaf(pattern(knuckle(0, 1.0), 2, X * (2 * pitch)), 1.0)
    leaf_b = leaf(pattern(knuckle(1, -1.0), 1, X * (2 * pitch)), -1.0)
    pin_profile = fill(circle(p.pin_d / 2), on=plane(Point(0.0, 0.0, r), X, Y))
    pin = eased(pin_profile, p.width, lead=lead, drop=drop)

    require(check_fits(leaf_a, H2D))
    require(check_fits(pin, H2D))
    check_clearance(pin, leaf_a, gap)
    check_clearance(leaf_a, leaf_b, gap)
    check_overhangs(pin, pin_stock.orient, PLA)

    print(f"pin {p.pin_d:.1f} mm in a {bore_d + PLA.hole_compensation:.2f} mm bore")
    print(f"{gap:.2f} mm a side once it is printed, and {knuckle_w:.1f} mm knuckles")

    return assembly(
        "hinge",
        (
            Placed(part("leaf-a", leaf_a, leaf_stock), XY),
            Placed(part("leaf-b", leaf_b, leaf_stock), XY),
            Placed(part("pin", pin, pin_stock), XY),
        ),
    )


show(build)
