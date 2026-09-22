"""Shared test data builders - plain values, no doubles.

Everything here just builds a :class:`~bench.model.Part` (or the :class:`~bench.model.Stock`
it is cut from) the way a script would, so more than one test file can start from the same
fixture instead of typing it out twice. Nothing here stands in for a real boundary - the
guard in :mod:`tests.conftest` scans this file exactly as it scans every test module, and it
has nothing to flag.
"""

from bench import (
    Label,
    Part,
    Point,
    Process,
    Stock,
    Text,
    circle,
    cut,
    fill,
    part,
    rect,
)

PLY = Stock(3.0, "birch ply", kerf=0.25)
"""3 mm birch ply with a quarter-millimetre kerf - the stock most fixture parts are cut
from."""


def panel() -> Part:
    """A 60 by 40 mm front panel with a vent hole, a scored rectangle and an engraved
    number - one of everything :mod:`bench.export` writes: an outer wire, a hole, an
    engraved wire and a line of lettering, all labelled and all on ``PLY``."""
    front = cut(
        fill(rect(60, 40, label=Label("outline")), label=Label("front")),
        circle(4, Point(50, 30)),
        label=Label("vent"),
    )
    return part(
        Label("drawer-3"),
        front,
        PLY,
        Process.LASER,
        engravings=(
            rect(20, 6, Point(5, 5), Label("score")),
            Text("3 & up", Point(5, 20), 6.0, Label("number")),
        ),
    )
