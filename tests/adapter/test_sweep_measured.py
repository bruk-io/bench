"""Adapter: profiles swept along a path, built by the modeller the app ships.

The modeller has no sweep: bench lays the mesh itself (:func:`bench.meshing.swept`) and the
modeller takes it in whole. :mod:`sweep_cases` is run inside Pyodide by :mod:`tools.stack`
with the real kernel, and what comes back is checked here against arithmetic done by hand:

* **what was laid is what was built** - the kernel's volume is the laid mesh's own, and one
  closed surface comes back (``V - E + F`` of 2, or 0 through a hollow duct);
* **the volume is Pappus's** - the profile's area times the path its centroid runs, to the
  chords, for a circle and for an L a hull would have filled in;
* **every triangle is on the face it is called** - ``end`` is exactly the triangles lying on
  the end plane facing on along the path, ``start`` the ones on the start facing back;
* **a swept bend shells and mates** - hollowed open at both ends it is a tube through, and a
  flange mated onto its ``end`` by name stands on that end, centred on it, touching it.
"""

import math
from pathlib import Path
from typing import Any

import pytest

from bench import Mesh, Ref
from bench.facets import normal, triangles
from bench.topology import CHORD
from tests.adapter.sweep_cases import FLANGE, ROUND, WALL, R
from tools import stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)

_CASES = Path(__file__).with_name("sweep_cases.py")

PROGRAM = """\
import json

from pyodide.ffi import JsException

import sweep_cases
from bench.adapters.browser import JsKernel


def main(js, given):
    return json.dumps(sweep_cases.measured(JsKernel(js, JsException)))
"""

_TINY = 1e-4
"""Millimetres: float noise on a single-precision mesh vertex at these sizes."""

_ELBOW = 40.0 + R * math.pi / 2
"""How long the elbow's path is: two 20 mm straights and a quarter turn round ``R``."""

_END = (R + 20.0, 20.0 + R)
"""Where the elbow ends, in X and Z."""


@pytest.fixture(scope="module")
def measured() -> dict[str, Any]:
    """Every sweep this module reads, built and measured once by the shipped kernel."""
    found: dict[str, Any] = stack.run(PROGRAM, {}, modules={"sweep_cases.py": _CASES.read_text()})
    return found


def _mesh(data: dict[str, Any]) -> Mesh:
    return Mesh(
        tuple(data["vertices"]),
        tuple(data["triangles"]),
        tuple(None if one is None else Ref(one) for one in data.get("refs", ())),
    )


def _body(measured: dict[str, Any], key: str) -> tuple[float, Mesh]:
    body = measured["bodies"][key]
    return body["volume"], _mesh(body["mesh"])


def _euler(mesh: Mesh) -> int:
    t = mesh.triangles
    edges = {
        (min(p, q), max(p, q))
        for k in range(len(t) // 3)
        for p, q in (
            (t[3 * k], t[3 * k + 1]),
            (t[3 * k + 1], t[3 * k + 2]),
            (t[3 * k + 2], t[3 * k]),
        )
    }
    return len(mesh.vertices) // 3 - len(edges) + len(t) // 3


def _signed_volume(mesh: Mesh) -> float:
    total = 0.0
    for a, b, c in triangles(mesh):
        total += a.x * (b.y * c.z - b.z * c.y) - a.y * (b.x * c.z - b.z * c.x)
        total += a.z * (b.x * c.y - b.y * c.x)
    return total / 6.0


def _polygon_area(radius: float) -> float:
    """The area of the regular polygon a circle of that radius becomes - the package's one
    chord rule, restated here so the expected numbers are worked out and not read off."""
    n = math.ceil(math.tau / (2.0 * math.acos(1.0 - CHORD / radius)))
    return 0.5 * n * radius * radius * math.sin(math.tau / n)


def _short_of(found: float, pappus: float) -> None:
    """A sweep's volume sits just under Pappus's: cutting the bend into chords takes a few
    parts in ten thousand, and nothing adds any."""
    assert pappus * (1 - 1e-3) < found < pappus


# ---- what was laid is what was built ------------------------------------------------------


def test_the_kernel_builds_exactly_the_mesh_bench_laid(measured: dict[str, Any]) -> None:
    volume, mesh = _body(measured, "round")
    laid = _mesh(measured["laid"])
    assert volume == pytest.approx(_signed_volume(laid), rel=1e-5)
    assert _euler(mesh) == 2


@pytest.mark.parametrize("key", ["round", "boxed", "ell", "duct_capped"])
def test_a_sweep_comes_back_one_closed_surface(measured: dict[str, Any], key: str) -> None:
    _, mesh = _body(measured, key)
    assert _euler(mesh) == 2


# ---- the volume is Pappus's -----------------------------------------------------------------


def test_a_round_elbow_holds_its_profile_times_its_path(measured: dict[str, Any]) -> None:
    volume, _ = _body(measured, "round")
    _short_of(volume, _polygon_area(ROUND) * _ELBOW)


def test_an_l_is_swept_true_where_a_hull_would_fill_its_notch(measured: dict[str, Any]) -> None:
    """The L's area is 500 and its centroid stands 4 mm off the path away from the bend's
    centre, so round the quarter turn it runs a radius of ``R + 4``."""
    volume, _ = _body(measured, "ell")
    _short_of(volume, 500.0 * (40.0 + (R + 4.0) * math.pi / 2))


# ---- every triangle is on the face it is called ----------------------------------------------


def _tagged(mesh: Mesh, ref: str) -> set[int]:
    return {i for i, one in enumerate(mesh.refs) if one == ref}


def _lying_on(mesh: Mesh, axis: int, at: float, facing: float) -> set[int]:
    """Every triangle whose corners all stand at ``at`` along world ``axis`` and which faces
    ``facing`` along it."""
    found = set()
    for i, t in enumerate(triangles(mesh)):
        n = normal(t)
        if n is None or abs(tuple(n)[axis] - facing) > 1e-6:
            continue
        if all(abs(tuple(p)[axis] - at) <= _TINY for p in t):
            found.add(i)
    return found


def test_the_end_is_every_triangle_on_the_end_plane_and_nothing_else(
    measured: dict[str, Any],
) -> None:
    _, mesh = _body(measured, "round")
    tagged = _tagged(mesh, "end")
    assert tagged
    assert tagged == _lying_on(mesh, 0, _END[0], 1.0)


def test_the_start_is_every_triangle_on_the_start_plane_and_nothing_else(
    measured: dict[str, Any],
) -> None:
    _, mesh = _body(measured, "round")
    tagged = _tagged(mesh, "start")
    assert tagged
    assert tagged == _lying_on(mesh, 2, 0.0, -1.0)


def test_every_triangle_of_a_swept_rectangle_is_named_and_every_side_has_some(
    measured: dict[str, Any],
) -> None:
    _, mesh = _body(measured, "boxed")
    named = [str(one) for one in mesh.refs]
    assert None not in mesh.refs
    assert set(named) == {"start", "end", "side-0", "side-1", "side-2", "side-3"}


def test_a_swept_rectangles_flat_sides_are_the_triangles_on_them(
    measured: dict[str, Any],
) -> None:
    """The S-bend turns in XZ about axes along Y, so the rectangle's front edge (``side-0``,
    at y = -15) and back edge (``side-2``, at y = 15) each sweep one flat face the whole way:
    every triangle called either lies on it facing out, and every triangle on it is called
    that - which is what reading a face through the triangle the modeller says it came from
    has to get right."""
    _, mesh = _body(measured, "boxed")
    assert _tagged(mesh, "side-0") == _lying_on(mesh, 1, -15.0, -1.0)
    assert _tagged(mesh, "side-2") == _lying_on(mesh, 1, 15.0, 1.0)


# ---- a swept bend shells and mates ----------------------------------------------------------


def test_a_shelled_elbow_is_a_tube_through_with_its_inside_named(measured: dict[str, Any]) -> None:
    volume, mesh = _body(measured, "duct")
    assert _euler(mesh) == 0
    _short_of(volume, (_polygon_area(ROUND) - _polygon_area(ROUND - WALL)) * _ELBOW)
    assert {"inside/side-0", "side-0", "start", "end"} <= {str(one) for one in mesh.refs}


def test_a_shelled_elbow_closed_at_its_start_has_a_floor_facing_in(
    measured: dict[str, Any],
) -> None:
    _, mesh = _body(measured, "duct_capped")
    tagged = _tagged(mesh, "inside/start")
    assert tagged
    assert tagged == _lying_on(mesh, 2, WALL, 1.0)


def test_a_flange_mated_onto_the_bends_end_stands_on_it_centred(measured: dict[str, Any]) -> None:
    flanged = measured["flanged"]
    flange = _mesh(flanged["flange"])
    xs, ys, zs = flange.vertices[0::3], flange.vertices[1::3], flange.vertices[2::3]
    outside, thick = FLANGE
    assert min(xs) == pytest.approx(_END[0], abs=_TINY)
    assert max(xs) == pytest.approx(_END[0] + thick, abs=_TINY)
    reach = [math.hypot(y, z - _END[1]) for y, z in zip(ys, zs, strict=True)]
    assert max(reach) == pytest.approx(outside, abs=_TINY)
    assert min(reach) >= (ROUND - WALL) - CHORD
    assert sum(ys) / len(ys) == pytest.approx(0.0, abs=1e-3)
    assert sum(zs) / len(zs) == pytest.approx(_END[1], abs=1e-3)
    assert flanged["shared"] == pytest.approx(0.0, abs=1e-6)
    assert flanged["gap"] == pytest.approx(0.0, abs=_TINY)
