"""A Gridfinity drawer cabinet, laser-cut from two thicknesses of ply.

Every drawer takes a baseplate units_x by units_y Gridfinity units across, and the
carcass is the same finger-jointed box turned on its back. Change a number in the panel
and the cut sheets follow.
"""

from dataclasses import dataclass

from bench import *
from bench.library import gridfinity

# `show` and `ref` are not imported: the runtime injects them into this script's own
# namespace, one set per run. Everything else, `knob` included, comes from `bench` and its
# libraries.


@dataclass(frozen=True, slots=True, kw_only=True)
class Cabinet:
    """What the panel shows: the Gridfinity sizes, the stock, and the drawers' labels."""

    units_x: int = knob(4, min=1, max=7, label="Units across")
    units_y: int = knob(2, min=1, max=5, label="Units deep")
    height_u: int = knob(3, min=1, max=12, label="Bin height (7 mm units)")
    drawers: int = knob(6, min=1, max=10, label="Drawers")
    columns: int = knob(1, min=1, max=4, label="Cabinets to cut")
    drawer_t: float = knob(3.0, min=2.0, max=6.0, step=0.5, label="Drawer stock")
    carcass_t: float = knob(6.0, min=4.0, max=9.0, step=0.5, label="Carcass stock")
    finger: float = knob(12.0, min=8.0, max=30.0, step=1.0, label="Finger length")
    kerf: float = knob(0.25, min=0.0, max=1.0, step=0.01, label="Kerf")
    baseplate: bool = knob(True, label="Printed baseplate")
    labels: str = knob("", label="Drawer labels, comma separated")


def build(p: Cabinet) -> Build:
    # One label per drawer, or leave it empty and the drawers are numbered instead.
    engraved = tuple(text.strip() for text in p.labels.split(",") if text.strip())

    spec = gridfinity.Spec(
        units_x=p.units_x,
        units_y=p.units_y,
        height_u=p.height_u,
        drawers=p.drawers,
        columns=p.columns,
        drawer_t=p.drawer_t,
        carcass_t=p.carcass_t,
        finger=p.finger,
        kerf=p.kerf,
        baseplate=p.baseplate,
        labels=engraved,
    )
    cabinet = gridfinity.cabinet(spec)

    dims = gridfinity.derive(spec)
    print(f"carcass {dims.cab_w:.1f} x {dims.cab_d:.1f} x {dims.cab_h:.1f} mm")
    drawer = f"{dims.drawer_w:.1f} x {dims.drawer_d:.1f} x {dims.drawer_h:.1f} mm"
    print(f"{p.drawers} drawers of {drawer}")

    return cabinet


show(build)
