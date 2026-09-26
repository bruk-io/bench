"""Adapter: bodies hollowed by :func:`bench.shell`, built by the modeller the app ships.

:mod:`shell_cases` is run inside Pyodide by :mod:`tools.stack` with the real kernel, and what
comes back is checked against arithmetic done by hand. Four things only a built body can say:

* **The volume** - an open box, a closed one, a tube, a turned cup and a funnel each take out
  exactly what a wall of that thickness leaves, to the chords the kernel cuts a circle into.
* **The openings** - Euler's ``V - E + F`` of the mesh counts the holes through it: a cup and
  an open box are 2 (one surface, no hole through), a closed box 4 (two surfaces, the outside
  and the hollow), a tube or a funnel open at both ends 0. A skin a coplanar cut left across
  an opening would add a face and show here, where the volume cannot see it.
* **The inner faces are picked and mated by name** - every triangle the kernel calls
  ``inside/bottom`` lies on the floor facing up into the box, and every such triangle is
  called that; a puck mated onto ``inside/bottom`` stands on the floor inside the box.
* **The wall** - a shell under the filament's minimum is the wall check's finding, and a
  loft's wall is measured level with its profiles: a 45 degree side shelled at 2 mm is
  ``2 cos 45`` through.
"""

import math
from pathlib import Path
from typing import Any

import pytest

from bench import Mesh, Ref
from bench.facets import normal, triangles
from bench.library.print import PLA
from bench.topology import CHORD
from tests.adapter.shell_cases import BOX, CUP, FUNNEL, STEEP, THIN, WALL
from tools import stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)

_CASES = Path(__file__).with_name("shell_cases.py")

PROGRAM = """\
import json

from pyodide.ffi import JsException

import shell_cases
from bench.adapters.browser import JsKernel


def main(js, given):
    return json.dumps(shell_cases.measured(JsKernel(js, JsException)))
"""

_TINY = 1e-4
"""Millimetres: float noise on a single-precision mesh vertex at these sizes."""


@pytest.fixture(scope="module")
def measured() -> dict[str, Any]:
    """Every shell this module reads, built and measured once by the shipped kernel."""
    found: dict[str, Any] = stack.run(PROGRAM, {}, modules={"shell_cases.py": _CASES.read_text()})
    return found


def _mesh(data: dict[str, Any]) -> Mesh:
    return Mesh(
        tuple(data["vertices"]),
        tuple(data["triangles"]),
        tuple(None if one is None else Ref(one) for one in data["refs"]),
    )


def _body(measured: dict[str, Any], key: str) -> tuple[float, Mesh]:
    body = measured["bodies"][key]
    return body["volume"], _mesh(body["mesh"])


def _euler(mesh: Mesh) -> int:
    """``V - E + F``: 2 for each closed surface, less 2 for each hole through it."""
    edges = {
        (min(a, b), max(a, b))
        for t in range(len(mesh.triangles) // 3)
        for a, b in (
            (mesh.triangles[3 * t], mesh.triangles[3 * t + 1]),
            (mesh.triangles[3 * t + 1], mesh.triangles[3 * t + 2]),
            (mesh.triangles[3 * t + 2], mesh.triangles[3 * t]),
        )
    }
    return len(mesh.vertices) // 3 - len(edges) + len(mesh.triangles) // 3


def _sides(radius: float) -> int:
    """How many chords a circle of that radius is cut into - the package's one chord rule,
    restated so the expected numbers are worked out here rather than read off the code."""
    return math.ceil(math.tau / (2.0 * math.acos(1.0 - CHORD / radius)))


def _polygon_area(radius: float) -> float:
    """The area of the regular polygon a circle of that radius actually becomes."""
    n = _sides(radius)
    return 0.5 * n * radius * radius * math.sin(math.tau / n)


def _frustum(bottom: float, top: float, high: float) -> float:
    return math.pi * high / 3 * (bottom * bottom + bottom * top + top * top)


# ---- the volume, and the openings ---------------------------------------------------------


def test_an_open_box_takes_out_its_inside_less_a_floor(measured: dict[str, Any]) -> None:
    w, d, h = BOX
    volume, mesh = _body(measured, "box_open")
    assert volume == pytest.approx(w * d * h - (w - 2 * WALL) * (d - 2 * WALL) * (h - WALL))
    assert _euler(mesh) == 2


def test_a_closed_box_is_two_surfaces_the_outside_and_the_hollow(measured: dict[str, Any]) -> None:
    w, d, h = BOX
    volume, mesh = _body(measured, "box_closed")
    assert volume == pytest.approx(w * d * h - (w - 2 * WALL) * (d - 2 * WALL) * (h - 2 * WALL))
    assert _euler(mesh) == 4


def test_a_tube_open_at_both_ends_has_a_hole_through_it(measured: dict[str, Any]) -> None:
    volume, mesh = _body(measured, "tube")
    assert volume == pytest.approx((_polygon_area(10.0) - _polygon_area(10.0 - WALL)) * 20.0)
    assert _euler(mesh) == 0


def test_a_turned_cup_is_open_at_its_rim_with_nothing_left_up_its_axis(
    measured: dict[str, Any],
) -> None:
    """A revolve is cut into as many facets as its widest point asks, the outside and the
    hollow each by its own, so each is its section's area times that polygon's share of the
    true circle. A pillar left up the axis would add volume here and a hole to the count."""
    across, high = CUP
    inner = across - WALL

    def turned(radius: float, tall: float) -> float:
        return _polygon_area(radius) * tall

    volume, mesh = _body(measured, "cup")
    assert volume == pytest.approx(turned(across, high) - turned(inner, high - WALL), rel=1e-5)
    assert _euler(mesh) == 2


def test_a_funnel_open_at_both_ends_is_its_outside_less_the_inset_loft(
    measured: dict[str, Any],
) -> None:
    """Two frustums, the inner one the outer's profiles each inset by the wall: exact but for
    the chords both circles are cut into, which take a few tenths of a percent off each."""
    bottom, top, high = FUNNEL
    volume, mesh = _body(measured, "funnel")
    exact = _frustum(bottom, top, high) - _frustum(bottom - WALL, top - WALL, high)
    assert volume == pytest.approx(exact, rel=5e-3)
    assert _euler(mesh) == 0


def test_a_funnel_walled_at_its_bottom_keeps_a_floor(measured: dict[str, Any]) -> None:
    """The floor is cut level a wall above the bottom, where the inset loft has already
    narrowed: what is taken out is that loft from the floor up."""
    bottom, top, high = FUNNEL
    volume, mesh = _body(measured, "funnel_floored")
    at_floor = (bottom - WALL) + (top - bottom) * WALL / high
    exact = _frustum(bottom, top, high) - _frustum(at_floor, top - WALL, high - WALL)
    assert volume == pytest.approx(exact, rel=5e-3)
    assert _euler(mesh) == 2


def test_a_moved_funnel_is_walled_where_it_stands(measured: dict[str, Any]) -> None:
    """A loft's closed end is cut level by a slab, and the slab has to stand where the loft's
    own recipe does - moved with it, not left where the moved body's box is."""
    here, _ = _body(measured, "funnel_floored")
    there, mesh = _body(measured, "funnel_floored_moved")
    assert there == pytest.approx(here, rel=1e-6)
    assert _euler(mesh) == 2


def test_a_half_turn_open_at_both_ends_is_a_channel_through(measured: dict[str, Any]) -> None:
    _, mesh = _body(measured, "half_turn")
    assert _euler(mesh) == 0


# ---- the inner faces, picked and mated ------------------------------------------------------


def _tagged(mesh: Mesh, ref: str) -> set[int]:
    return {i for i, one in enumerate(mesh.refs) if one == ref}


def _lying_on(mesh: Mesh, axis: int, at: float, facing: float) -> set[int]:
    """Every triangle whose three corners stand at ``at`` along world ``axis`` and which faces
    ``facing`` along it - the geometric predicate a tag is checked against."""
    found = set()
    for i, t in enumerate(triangles(mesh)):
        n = normal(t)
        if n is None or abs(tuple(n)[axis] - facing) > 1e-6:
            continue
        if all(abs(tuple(p)[axis] - at) <= _TINY for p in t):
            found.add(i)
    return found


def test_every_triangle_called_the_inner_floor_is_the_floor_and_every_floor_triangle_is_called_it(
    measured: dict[str, Any],
) -> None:
    _, mesh = _body(measured, "box_open")
    tagged = _tagged(mesh, "inside/bottom")
    assert tagged
    assert tagged == _lying_on(mesh, 2, WALL, 1.0)


def test_every_triangle_called_the_inner_front_wall_faces_back_into_the_box(
    measured: dict[str, Any],
) -> None:
    _, mesh = _body(measured, "box_open")
    tagged = _tagged(mesh, "inside/side-front")
    assert tagged
    assert tagged == _lying_on(mesh, 1, WALL, 1.0)


def test_a_puck_mated_onto_the_inner_floor_stands_on_it_inside_the_box(
    measured: dict[str, Any],
) -> None:
    mated = measured["mated"]
    puck = _mesh(mated["puck"])
    zs = puck.vertices[2::3]
    xs, ys = puck.vertices[0::3], puck.vertices[1::3]
    w, d, _ = BOX
    assert min(zs) == pytest.approx(WALL, abs=_TINY)
    assert max(zs) == pytest.approx(WALL + 3.0, abs=_TINY)
    assert min(xs) >= WALL - _TINY and max(xs) <= w - WALL + _TINY
    assert min(ys) >= WALL - _TINY and max(ys) <= d - WALL + _TINY
    assert mated["shared"] == pytest.approx(0.0, abs=1e-6)
    assert mated["gap"] == pytest.approx(0.0, abs=_TINY)


# ---- the wall ---------------------------------------------------------------------------------


def test_a_shell_thinner_than_the_filament_allows_is_the_wall_checks_finding(
    measured: dict[str, Any],
) -> None:
    walls = measured["walls"]
    assert walls["sound"] is None
    severity, message = walls["thin"]
    assert severity == "error"
    assert message == f"the thinnest wall is {THIN:.2f} mm, not {PLA.min_wall:.2f} mm"


def test_a_lofts_wall_is_measured_level_with_its_profiles_not_square_to_its_side(
    measured: dict[str, Any],
) -> None:
    """The steep loft leans 45 degrees, so a wall of 2 mm across is ``2 cos 45`` through,
    to the chords its circles are cut into - which is why ``shell`` says so and the wall
    check is there to measure it."""
    bottom, top, high = STEEP
    lean = math.atan2(bottom - top, high)
    thinnest, thickest = measured["walls"]["steep"]
    assert thinnest == pytest.approx(WALL * math.cos(lean), abs=2 * CHORD)
    assert thickest == pytest.approx(WALL * math.cos(lean), abs=2 * CHORD)
