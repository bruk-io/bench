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

BED_FACE = """\
from bench import *
from bench.library.print import PLA

block = part("block", cuboid(10, 6, 3), Printed(PLA, Orient(up=-Z, bed_face="top")))
show(block)
"""
"""A part that names its own ``bed_face``: printed upside down (``up=-Z``), and the face
touching the bed is the one it says, ``top`` - the block's own top when drawn, since a
cuboid's ``top`` faces +Z and ``-up`` does too."""

BAD_BED_FACE = """\
from bench import *
from bench.library.print import PLA

block = part("block", cuboid(10, 6, 3), Printed(PLA, Orient(bed_face="no-such-face")))
show(block)
"""
"""A ``bed_face`` naming nothing on the part - the same mistake a bad ``ref()`` anywhere else
in a script is, and answered the same way: the run fails, naming why, rather than exporting
something arbitrary."""


def measured(kernel: Kernel, enclosure_source: str) -> dict[str, object]:
    """The enclosure example, the upside-down mate, and a part with (and without) a real
    ``bed_face`` to read - all run with ``kernel``."""
    return {
        "enclosure": run(enclosure_source, kernel=kernel),
        "mated": run(MATED_UPSIDE_DOWN, kernel=kernel),
        "bed_face": run(BED_FACE, kernel=kernel),
        "bad_bed_face": run(BAD_BED_FACE, kernel=kernel),
    }
