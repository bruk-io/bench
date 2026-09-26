"""Adapter: twisted and tapered extrusions, and printed threads, built by the shipped kernel.

:mod:`thread_cases` is run inside Pyodide by :mod:`tools.stack` with the real kernel -
:class:`~bench.adapters.browser.JsKernel` driving Manifold's WASM through
``web/src/modeller.ts`` - and every number below is checked against arithmetic done here:
a square turned a quarter about its sweep, a frustum's volume, and the gap a fit table asks.

Two things only a built body can answer. **A twisted side is named edge by edge**: every
triangle the kernel calls ``side-south`` lies, once turned back by as much as its height
turned it, on the south edge of the square it was swept from - and the far end's south side
sits where a right-hand quarter turn puts it, whichever way the sweep runs. And **a printed
bolt goes into a printed nut at the fit**: drawn in place, the gap between them is the fit
table's per-side clearance to within the sag of a chord; screwed a quarter turn further along
the helix it is the same gap, so the pitch and the hand agree; and pushed half a pitch up the
axis without turning, the two collide, so the flanks really engage rather than the nut being a
loose bore round the bolt.

The gap is the fit's clearance plus the cavity's printed compensation: the section grows by
half the material's ``hole_compensation`` in its own plane, which stands ``cos(FLANK)`` of that
across the steepest flank. It is the model's gap, meant to close back to the clearance once
the printer takes the compensation back - and on a fine thread it is more than the thread is
deep, so the modelled M8 x 1.25 nut no longer engages its bolt at all.
"""

import math
from pathlib import Path
from typing import Any

import pytest

from bench import ROUND_DEPTH, thread_opening
from bench.threads import FLANK
from bench.topology import CHORD
from tests.adapter.thread_cases import EDGES, PAIRS, RISE, SQUARE, TAPER, TURN
from tools import stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)

_CASES = Path(__file__).with_name("thread_cases.py")

PROGRAM = """\
import json

from pyodide.ffi import JsException

import thread_cases
from bench.adapters.browser import JsKernel


def main(js, given):
    return json.dumps(thread_cases.measured(JsKernel(js, JsException)))
"""

_TINY = 1e-3
"""Float noise on a single-precision mesh vertex, in millimetres."""

_HALF = SQUARE / 2

_ON_EDGE = {"south": (1, -_HALF), "east": (0, _HALF), "north": (1, _HALF), "west": (0, -_HALF)}
"""Each named edge's line in the profile's own plane: which coordinate it fixes, and at what."""


def _off(edge: str, x: float, y: float) -> float:
    """How far ``(x, y)`` is off the named edge's line."""
    axis, at = _ON_EDGE[edge]
    return abs((x, y)[axis] - at)


@pytest.fixture(scope="module")
def measured() -> dict[str, Any]:
    """Every twisted body and every bolt and nut, built and measured once."""
    found: dict[str, Any] = stack.run(PROGRAM, {}, modules={"thread_cases.py": _CASES.read_text()})
    return found


def _corners(mesh: dict[str, Any], t: int) -> list[tuple[float, float, float]]:
    """The three corners of triangle ``t``."""
    v = mesh["vertices"]
    return [(v[3 * i], v[3 * i + 1], v[3 * i + 2]) for i in mesh["triangles"][3 * t : 3 * t + 3]]


def _turned_back(x: float, y: float, z: float, distance: float) -> tuple[float, float]:
    """``(x, y)`` at height ``z`` turned back by as much as a right-hand quarter turn about
    the sweep had turned it there: the sweep runs +Z for a positive ``distance`` and -Z for
    a negative one, so seen from +Z the turn is counter-clockwise going up and clockwise
    going down."""
    angle = -TURN * (z / distance) * (1.0 if distance > 0 else -1.0)
    return x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle)


@pytest.mark.parametrize(("key", "distance"), [("twisted", RISE), ("hanging", -RISE)])
def test_every_triangle_of_a_twisted_square_lies_on_the_face_it_is_named_for(
    measured: dict[str, Any], key: str, distance: float
) -> None:
    mesh = measured[key]
    refs = mesh["refs"]
    assert set(refs) == {"top", "bottom", *(f"side-{name}" for name in EDGES)}
    for t, ref in enumerate(refs):
        corners = _corners(mesh, t)
        if ref == "top":
            assert all(abs(z - distance) < _TINY for _, _, z in corners), (t, corners)
        elif ref == "bottom":
            assert all(abs(z) < _TINY for _, _, z in corners), (t, corners)
        else:
            edge = ref.removeprefix("side-")
            for x, y, z in corners:
                assert _off(edge, *_turned_back(x, y, z, distance)) < _TINY, (ref, x, y, z)


@pytest.mark.parametrize(("key", "y"), [("off_axis_up", 2.0), ("off_axis_down", -2.0)])
def test_the_far_end_is_turned_right_handed_about_the_sweep(
    measured: dict[str, Any], key: str, y: float
) -> None:
    """A square standing wholly on +X of its axis, centred at ``(2, 0)``. A right-hand quarter
    turn about +Z carries its centre to ``(0, +2)``; about -Z, to ``(0, -2)``. Read off the
    far end's vertices, picked by height alone - no name is read, so the naming cannot agree
    with a turn the wrong way round."""
    far = measured[key]
    assert len(far) == 4
    assert sum(p[0] for p in far) / 4 == pytest.approx(0.0, abs=_TINY)
    assert sum(p[1] for p in far) / 4 == pytest.approx(y, abs=_TINY)


@pytest.mark.parametrize("key", ["twisted_volume", "hanging_volume"])
def test_a_twisted_prism_keeps_its_volume_to_the_chord_rule(
    measured: dict[str, Any], key: str
) -> None:
    """Every section of a twisted square is the same square, so the exact body has the
    plain prism's volume. The built one is ruled between copies of the section, and each
    side's quad between two copies is not flat: the modeller folds it along one diagonal,
    and which way depends on the way the turn runs - one sense comes out over, the other
    under. The two folds of one quad differ by a tetrahedron of ``side**2 * rise * sin(turn)
    / 6``, and the exact surface lies between them to within a chord of sag, so the built
    volume is within the sum of those over every quad."""
    steps = math.ceil(TURN / (2 * math.acos(1 - CHORD / math.hypot(_HALF, _HALF))))
    folds = 4 * SQUARE**2 * RISE * math.sin(TURN / steps) / 6
    allowed = folds + 4 * SQUARE * RISE * CHORD
    assert abs(measured[key] - measured["plain_volume"]) <= allowed
    assert measured[key] > 0.0


def test_a_tapered_square_is_a_frustum(measured: dict[str, Any]) -> None:
    """A square's taper is exact - its sides are flat - so its volume is the frustum's to
    float noise, and its far end is the square at half size."""
    bottom = SQUARE * SQUARE
    top = bottom * TAPER * TAPER
    frustum = RISE / 3 * (bottom + top + math.sqrt(bottom * top))
    assert measured["tapered_volume"] == pytest.approx(frustum, rel=1e-6)
    mesh = measured["tapered"]
    far = [
        corner for t, ref in enumerate(mesh["refs"]) if ref == "top" for corner in _corners(mesh, t)
    ]
    reach = max(max(abs(x), abs(y)) for x, y, _ in far)
    assert reach == pytest.approx(_HALF * TAPER, abs=_TINY)


@pytest.mark.parametrize("key", list(PAIRS))
def test_a_printed_nut_drawn_on_its_bolt_clears_it_by_the_fit_and_the_compensation(
    measured: dict[str, Any], key: str
) -> None:
    """decision-11's ask, with the owner's call that the cavity is compensated like any
    printed hole: the gap between a printed bolt and nut, measured with ``min_gap`` square to
    the surfaces, is the fit table's per side plus half the material's compensation across
    the steepest flank - never under it, and over it by no more than the sag of one chord of
    the concave cavity, which the internal thread is opened by. PLA's M12 measures 0.279 mm
    where 0.20 + 0.10 * cos(40) is 0.277."""
    pair = measured["pairs"][key]
    gap = pair["gaps"]["matched"]
    want = pair["asked"] + pair["compensation"] / 2 * math.cos(FLANK)
    assert want - _TINY <= gap <= want + CHORD, (gap, want)
    assert gap > pair["asked"] + CHORD, "the compensation is in the model, not only the fit"
    assert pair["shared"]["matched"] < 1e-6


@pytest.mark.parametrize("key", list(PAIRS))
def test_a_nut_turned_along_the_helix_keeps_its_gap(measured: dict[str, Any], key: str) -> None:
    """A quarter turn and a quarter pitch up is the same pose on a right-hand thread, so the
    gap does not change - which is what says the nut screws on rather than merely fits."""
    pair = measured["pairs"][key]
    assert pair["gaps"]["advanced"] == pytest.approx(pair["gaps"]["matched"], abs=_TINY)
    assert pair["shared"]["advanced"] < 1e-6


@pytest.mark.parametrize(("key", "engaged"), [("m12", True), ("m8", False), ("jar", True)])
def test_a_nut_pushed_off_the_helix_collides_while_its_thread_engages(
    measured: dict[str, Any], key: str, engaged: bool
) -> None:
    """Half a pitch straight up puts the nut's ridges where the bolt's are: if the flanks
    did not engage, the nut would be a loose bore and this would still clear.

    They engage while the section's radial opening - the clearance over the flank's cosine,
    a chord, and half the compensation - is less than the thread is deep. The M8 x 1.25's
    default depth is 0.33 mm and its opening in PLA at a slide 0.41, so the modelled nut
    clears its bolt in every pose: it is the print, shrinking the cavity back, that is meant
    to engage it."""
    pair = measured["pairs"][key]
    _, pitch, material, fit = PAIRS[key]
    depth = pitch * ROUND_DEPTH
    opening = thread_opening(material.clearances[fit], pitch, depth)
    assert (opening + material.hole_compensation / 2 < depth) is engaged
    if engaged:
        assert pair["gaps"]["off"] < _TINY
        assert pair["shared"]["off"] > 0.1
    else:
        assert pair["gaps"]["off"] > _TINY
        assert pair["shared"]["off"] < 1e-6


@pytest.mark.parametrize("key", list(PAIRS))
def test_a_thread_is_three_named_faces_and_its_flank_is_one(
    measured: dict[str, Any], key: str
) -> None:
    pair = measured["pairs"][key]
    assert pair["bolt_refs"] == ["bolt/bottom", "bolt/side-0", "bolt/top"]
    assert "thread/side-0" in pair["nut_refs"]
