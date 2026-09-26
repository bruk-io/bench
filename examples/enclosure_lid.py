"""A box and its lid: four M3 heat-set inserts in bosses, and a lip that registers into the
box at a real `clearance(Fit.SNUG, PLA)` rather than at a number somebody typed.

Two parts, drawn where they sit rather than each at the origin, because the fit between
them is the whole point: `check_clearance(lip, box, ...)` measures the gap the table asked
for on the bodies themselves. The box prints as it is drawn; the lid prints upside down, so
it carries `Orient(up=-Z)` and every print-aware check reads that - which is the difference
between a lid whose lip and bosses stand up off the bed and one printed in mid-air.

The insert bores are the one hole here that is *not* compensated for the filament. Every
other figure in `fasteners` is the nominal metal one and the material adds the printed
allowance on top; an insert bore is quoted the other way round - 4.2 mm is the hole to
print for an M3 insert - so `hole(insert=..., printed=...)` draws it exactly, and `printed=`
is passed anyway so `top=Top.AUTO` still has an orientation to read, upright here.
"""

from dataclasses import dataclass

from bench import *
from bench.library.print import H2D, PLA, clearance


@dataclass(frozen=True, slots=True, kw_only=True)
class Enclosure:
    """The box's outside, its wall, and the lid that closes it."""

    box_w: float = knob(80.0, min=30.0, max=200.0, step=1.0, label="Box width")
    box_d: float = knob(60.0, min=30.0, max=200.0, step=1.0, label="Box depth")
    box_h: float = knob(30.0, min=10.0, max=120.0, step=1.0, label="Box height")
    wall: float = knob(2.4, min=1.2, max=6.0, step=0.2, label="Wall")
    lid_t: float = knob(3.0, min=1.6, max=8.0, step=0.2, label="Lid thickness")
    lip_h: float = knob(5.0, min=2.0, max=15.0, step=0.5, label="Lip depth")
    boss_h: float = knob(10.0, min=6.0, max=25.0, step=0.5, label="Boss length")


box_stock = Printed(PLA)
lid_stock = Printed(PLA, Orient(up=-Z))  # the lid prints on its face, lip upwards

gap = clearance(Fit.SNUG, PLA)  # per side: a lip you push home by hand, with no slop
corner = 4.0
lip_t = 2.0
boss_d = INSERT_M3.od + 2 * 2.0  # 2 mm of plastic round an insert, or the boss splits


def build(p: Enclosure) -> Assembly:
    # ---- the box: rounded outside, square inside, open at the top --------------------

    inside_w, inside_d = p.box_w - 2 * p.wall, p.box_d - 2 * p.wall
    box = extrude(fill(rounded_rect(p.box_w, p.box_d, corner)), p.box_h)
    box = cut(
        box,
        extrude(
            fill(rect(inside_w, inside_d, Point(p.wall, p.wall)), on=raised(XY, p.wall)), p.box_h
        ),
        label="cavity",
    )

    # ---- the lid: a plate, a lip that drops into the box, four insert bosses ---------

    lid = extrude(fill(rounded_rect(p.box_w, p.box_d, corner), on=raised(XY, p.box_h)), p.lid_t)

    lip_w, lip_d = inside_w - 2 * gap, inside_d - 2 * gap
    lip_at = p.wall + gap
    inner = rect(lip_w - 2 * lip_t, lip_d - 2 * lip_t, Point(lip_at + lip_t, lip_at + lip_t))
    lip = extrude(
        face(rect(lip_w, lip_d, Point(lip_at, lip_at)), holes=(inner,), on=raised(XY, p.box_h)),
        -p.lip_h,
        label="lip",
    )

    # A boss hangs from the lid's underside, drawn on its own centre so its end face is the
    # frame the insert bore is placed in: `at=ORIGIN` on that plane is the middle of the boss.
    inset = p.wall + gap + lip_t + boss_d / 2
    end = plane(Point(inset, inset, p.box_h), -Z, X)
    boss = extrude(fill(circle(boss_d / 2), on=end), p.boss_h, label="boss")
    bosses = grid(boss, (2, 2), (X * (p.box_w - 2 * inset), Y * (p.box_d - 2 * inset)))

    lid = union(lid, lip)
    for one in bosses:
        lid = union(lid, one)
    for i in range(len(bosses)):
        lid = hole(
            lid,
            ORIGIN,
            on=plane_of(lid, f"boss-{i + 1}/top"),
            insert=INSERT_M3,
            depth=INSERT_M3.length + 1.0,
            printed=lid_stock,
            label=f"insert-{i + 1}",
        )

    require(check_fits(box, H2D))
    require(check_fits(lid, H2D))
    check_wall(box, PLA.min_wall)
    check_clearance(lip, box, gap)
    check_overhangs(box, box_stock.orient, PLA)
    check_overhangs(lid, lid_stock.orient, PLA)

    print(f"lip {lip_w:.2f} x {lip_d:.2f} mm into a {inside_w:.1f} x {inside_d:.1f} mm box")
    print(f"{gap:.2f} mm a side, and four {INSERT_M3.bore:.1f} mm insert bores")

    return assembly(
        "enclosure",
        (Placed(part("box", box, box_stock), XY), Placed(part("lid", lid, lid_stock), XY)),
    )


show(build)
