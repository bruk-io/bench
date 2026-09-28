"""What ``test_on_bed.py`` asks of the shipped kernel, answered inside Pyodide.

:mod:`tools.stack` writes this file beside ``bench`` in the runtime the app ships, and
:func:`measured` runs a few printed scripts with the real kernel and the app's own printer, so
the placements, the fits and the face areas the test reads are the ones the app draws. It
imports nothing but ``bench`` and the standard library, and decides nothing: every assertion
is in the test module.
"""

from bench import run
from bench.kernel import Kernel
from bench.library.print import PRINTER

LAID_OUT = """\
from bench import *
from bench.library.print import H2D, PLA

lid = part("lid", cuboid(80, 60, 3), Printed(PLA, Orient(up=-Z)))
post = part("post", cylinder(6, 40), Printed(PLA, Orient(up=X)))
flat = part("flat", cuboid(30, 20, 5), Printed(PLA))
require(check_fits(lid, H2D))
show((lid, post, flat))
"""
"""Three printed parts a script shows as a loose tuple, so the stage lays them in a row: one
printed upside down, one on its side and one the way it is drawn - three different moves onto
the bed, and ``check_fits`` asked about the host's own machine."""

POSED = """\
from bench import *
from bench.library.print import PLA

pla = Printed(PLA)
base = part("base", cuboid(40, 40, 5), pla)
plate = part("plate", cuboid(20, 20, 4), pla)
fitted = mated(base, "base/top", plate, "plate/top")
show(assembly("pair", (Placed(base, XY), Placed(fitted.part, XY)), posed=True))
"""
"""A posed pair, the plate mated upside down onto the base: nothing names a printer, so the
host's is used, and the plate is laid right way up however it is posed."""

TOO_BIG = """\
from bench import *
from bench.library.print import PLA

beam = part("beam", cuboid(400, 20, 10), Printed(PLA))
show(beam)
"""
"""A part longer than the H2D is wide: laid all the same, and marked as not fitting."""

SMALL_MACHINE = """\
from bench import *
from bench.library.print import BEDS, PLA

tray = part("tray", cuboid(100, 80, 10), Printed(PLA))
check_fits(tray, BEDS["a1"])
show(tray)
"""
"""A script asking about a 256 mm machine: its parts are laid on that bed, not the host's."""


def measured(kernel: Kernel) -> dict[str, object]:
    """Each script above, run with ``kernel`` and the app's printer."""
    return {
        name: run(source, kernel=kernel, printer=PRINTER)
        for name, source in (
            ("laid_out", LAID_OUT),
            ("posed", POSED),
            ("too_big", TOO_BIG),
            ("small_machine", SMALL_MACHINE),
        )
    }
