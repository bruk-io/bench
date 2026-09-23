"""What ``test_export_as_printed.py`` asks of the shipped kernel, answered inside Pyodide.

:mod:`tools.stack` writes this file beside ``bench`` in the runtime the app ships, and
:func:`measured` runs the enclosure and a part mated upside down with the real kernel, so the
STL and 3MF bytes the test parses are the ones a maker would actually download - not a mesh
stood in for by hand. It imports nothing but ``bench`` and the standard library, and decides
nothing: every assertion is in the test module.
"""

from bench import run
from bench.kernel import Kernel

MATED_UPSIDE_DOWN = """\
from bench import *
from bench.library.print import PLA

pla = Printed(PLA)
base = part("base", cuboid(40, 40, 5), pla)
plate = part("plate", cuboid(20, 20, 4), pla)
fitted = mated(base, "base/top", plate, "plate/top")
print(fitted)
show(assembly("pair", (Placed(base, XY), Placed(fitted.part, XY)), posed=True))
"""
"""A plate put face-to-face on a box's top, normals opposed: mating turns it over, so the
posed part sits upside down at the top of the assembly - a printer still has to read it
right way up, from underneath the pose rather than through it."""


def measured(kernel: Kernel, enclosure_source: str) -> dict[str, object]:
    """The enclosure example and the upside-down mate, both run with ``kernel``."""
    return {
        "enclosure": run(enclosure_source, kernel=kernel),
        "mated": run(MATED_UPSIDE_DOWN, kernel=kernel),
    }
