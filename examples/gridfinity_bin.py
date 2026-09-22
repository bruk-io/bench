"""A Gridfinity bin, 2 x 1 x 3 units, with a label lip and a scoop.

The object the whole ecosystem is built on, and the one the maker review wrote first. Every
number in it comes from `bench.library.gridfinity3d`: the 42 mm grid, the 41.5 mm top of
the base that leaves a quarter of a millimetre a side, and the four-point base profile that
the stacking lip is cut to as well - so the bin stacks on another bin because the lip is
that same profile with a `Fit.CLEARANCE` round it, not because two tables were kept in
step by hand.

The foot is the hull of four flat slices, which is how a chamfered sweep is written on a
kernel with no sweep in it and how every Gridfinity generator has always written it. The
scoop is a quarter circle taken out of a square and swept along the compartment, which is
what a fillet would have been. Print it base down: the 45 degree flanks of the base, the
flare under the mouth of the compartment and the label tab are all at exactly the angle a
printer holds up.

`check_overhangs` is not called here, and the reason is worth reading. A bin of more than
one unit has a half-millimetre gap between its feet - the standard's own gap, the one that
lets the bin drop into a baseplate - and the floor above it bridges that gap. The check
measures the angle of a face and not the distance it has to span, so it reports that strip
as a 90 degree overhang. It is right about the angle and wrong about the part. What the bin
is checked for instead is the thing a bin is for: that it stacks.
"""

from dataclasses import dataclass
from typing import Literal

from bench import *
from bench.library import gridfinity3d
from bench.library.gridfinity3d import Tab, Units
from bench.library.print import PLA, H2D


@dataclass(frozen=True, slots=True, kw_only=True)
class Bin:
    """The bin's size in Gridfinity units, and what goes in and on it."""

    units_x: int = knob(2, min=1, max=6, label="Units across")
    units_y: int = knob(1, min=1, max=6, label="Units deep")
    height_u: int = knob(3, min=1, max=12, label="Height (7 mm units)")
    divisions: int = knob(1, min=1, max=6, label="Compartments across")
    scoop: float = knob(0.5, min=0.0, max=1.0, step=0.05, label="Scoop")
    lip: bool = knob(True, label="Stacking lip")
    tab: Literal["none", "left", "centre", "right", "full"] = knob("full", label="Label tab")
    magnets: bool = knob(False, label="Magnet pockets")
    wall: float = knob(1.2, min=0.86, max=4.0, step=0.02, label="Wall")


def build(p: Bin) -> Build:
    spec = gridfinity3d.Spec(
        units_x=p.units_x,
        units_y=p.units_y,
        height=Units(p.height_u),
        lip=p.lip,
        wall=p.wall,
        divisions=(p.divisions, 1),
        scoop=p.scoop,
        label_tab=Tab(p.tab),
        magnets=p.magnets,
        material=PLA,
    )
    made = gridfinity3d.bin_(spec)
    dims = gridfinity3d.derive(spec)
    body = made.assembly.parts[0].part.shape

    require(check_fits(body, H2D))

    # It stacks because the lip is the base profile with the fit round it, and this is that
    # sentence measured: this bin's lip against the base of a bin sitting on it, one body
    # height up. A gap of `stack` a side reads as `stack / sqrt(2)` across a 45 degree flank,
    # and a corner rounded in a mesh has no circle in it, so a chord's worth of that can be
    # lost at each of the two corners that face each other. The lip is reached by its own
    # ref, which is the point of naming a feature as it enters the tree.
    if p.lip:
        stacked = move(body, Z * dims.height)
        lip = resolve(made.assembly, ref("bin/lip"))
        check_clearance(lip, stacked, dims.stack / 2 - CHORD)

    print(f"{dims.outer_w:.1f} x {dims.outer_d:.1f} x {dims.total:.2f} mm over the lip")
    print(f"{p.divisions} compartment(s) of {dims.compartment_w:.1f} x {dims.compartment_d:.1f} mm")

    return made


show(build)
