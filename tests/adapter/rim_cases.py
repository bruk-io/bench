"""The bodies ``test_rim_measured.py`` asks of the shipped kernel.

:mod:`tools.stack` writes this file beside ``bench`` in the runtime the app ships, and
:func:`measured` builds every :func:`bench.library.print.rim` this module cares about and
answers what only a real modeller can: which face names survive the union with an eased
cap, and which way an eased rim overhangs once it is triangles rather than a recipe. It
imports nothing but ``bench`` and the standard library, and decides nothing: every
assertion is in the test module.
"""

from typing import Any

from bench.checks import overhangs
from bench.geometry import Point, X, Z, plane
from bench.kernel import Kernel
from bench.library.print import PLA, rim
from bench.model import Orient
from bench.ops import circle, fill

_PROFILE = fill(circle(5.0), on=plane(Point(0.0, 0.0, 0.0), Z, X))
_LENGTH, _LEAD, _DROP = 20.0, 1.0, 2.0


def measured(kernel: Kernel) -> dict[str, Any]:
    both = rim(_PROFILE, _LENGTH, lead=_LEAD, drop=_DROP, style="chamfer", top=True, bottom=True)
    top_only = rim(_PROFILE, _LENGTH, lead=_LEAD, drop=_DROP, style="round", top=True, bottom=False)
    bottom_only = rim(
        _PROFILE, _LENGTH, lead=_LEAD, drop=_DROP, style="chamfer", top=False, bottom=True
    )
    bottom_round = rim(
        _PROFILE, _LENGTH, lead=_LEAD, drop=_DROP, style="round", top=False, bottom=True
    )

    def names(body: Any) -> list[str]:
        mesh = kernel.mesh(body)
        return sorted({str(r) for r in mesh.refs if r is not None})

    def lean(body: Any) -> str | None:
        found = overhangs(body, Orient(), PLA, kernel=kernel)
        return None if found is None else found.message

    return {
        "both_names": names(both),
        "top_only_names": names(top_only),
        "bottom_only_names": names(bottom_only),
        "top_round_overhang": lean(top_only),
        "bottom_round_overhang": lean(bottom_round),
    }
