"""Adapter: a printed part's STL and 3MF, built by the shipped kernel and laid on the bed the
way its :class:`~bench.model.Orient` says - task-64's own acceptance, decision-10's "print
orientation stays apart from where a part sits in an assembly".

:mod:`export_cases` runs the enclosure example and a part mated upside down inside Pyodide,
with the app's real Manifold kernel, and hands back the scenes those runs produced - files,
mesh views and all. What is asked here is what only a built body answers: the bytes a maker
actually downloads, decoded and measured by hand, never by re-running the code under test.
The pure arithmetic of the turn itself is ``tests/unit/test_export.py``'s.
"""

import struct
import xml.etree.ElementTree as ET
import zipfile
from base64 import b64decode
from io import BytesIO
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from bench.export import _MODEL_NS
from bench.scene import OkScene
from tools import stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)

_CASES = Path(__file__).with_name("export_cases.py")
_ENCLOSURE = Path(__file__).resolve().parents[2] / "examples" / "enclosure_lid.py"

_TINY = 1e-3
"""Float noise on a single-precision mesh vertex, in millimetres."""

PROGRAM = """\
import json

from pyodide.ffi import JsException

import export_cases
from bench.adapters.browser import JsKernel


def main(js, given):
    kernel = JsKernel(js, JsException)
    return json.dumps(export_cases.measured(kernel, json.loads(given)["enclosure"]))
"""


@pytest.fixture(scope="module")
def measured() -> dict[str, Any]:
    """The enclosure and the upside-down mate, run once by the shipped kernel."""
    found: dict[str, Any] = stack.run(
        PROGRAM,
        {"enclosure": _ENCLOSURE.read_text()},
        modules={"export_cases.py": _CASES.read_text()},
    )
    return found


def _ok(scene: Any) -> OkScene:
    if not scene["ok"]:
        error = scene["error"]
        pytest.fail(f"line {error['line']}: {error['message']}\n{error['traceback']}")
    ok: OkScene = scene
    return ok


# ---- reading the bytes a maker downloads -------------------------------------------------


def _stl_facets(data: bytes) -> list[list[tuple[float, float, float]]]:
    """Every facet of a binary STL as its three corners, in the file's own order - which is
    ``mesh.triangles``'s order (:func:`bench.export.stl` reads no other), the very order a
    view's own ``ref_index`` counts triangles in and :func:`bench.export.as_printed` leaves
    untouched. So facet ``t`` here is triangle ``t`` of a part's ``mesh`` view, whichever ref
    it answers to."""
    count = struct.unpack("<I", data[80:84])[0]
    out: list[list[tuple[float, float, float]]] = []
    for at in range(count):
        start = 84 + 50 * at + 12
        out.append(
            [struct.unpack("<3f", data[start + 12 * k : start + 12 * k + 12]) for k in range(3)]
        )
    return out


def _stl_corners(data: bytes) -> list[tuple[float, float, float]]:
    """Every triangle corner in a binary STL, in millimetres."""
    return [corner for facet in _stl_facets(data) for corner in facet]


def _z_of(data: bytes, ref_index: list[int], refs: list[str], named: str) -> float:
    """The average z of every corner of every facet of ``data`` that a view's ``ref_index``
    (counted the way :func:`~bench.stage.ref_table` counts it) says is ``named``."""
    number = refs.index(named) + 1
    facets = _stl_facets(data)
    zs = [corner[2] for t, at in enumerate(ref_index) if at == number for corner in facets[t]]
    assert zs, f"no facet of {named!r} in this file"
    return sum(zs) / len(zs)


class _Box(NamedTuple):
    x0: float
    x1: float
    y0: float
    y1: float
    z0: float
    z1: float


def _bbox(points: list[tuple[float, float, float]]) -> _Box:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    return _Box(min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _footprint_at(points: list[tuple[float, float, float]], z: float) -> tuple[float, float]:
    """How wide and how deep the points within a hair of ``z`` reach in X and Y - the
    footprint of whatever face is standing at that height."""
    near = [p for p in points if abs(p[2] - z) < _TINY]
    xs, ys = [p[0] for p in near], [p[1] for p in near]
    return max(xs) - min(xs), max(ys) - min(ys)


def _3mf_object(data: bytes, name: str) -> list[tuple[float, float, float]]:
    """Every vertex of the 3MF object called ``name``, in millimetres.

    Raises:
        AssertionError: if the package has no object of that name - a test's own mistake
            about what the run wrote, not something worth a softer failure.
    """
    archive = zipfile.ZipFile(BytesIO(data))
    root = ET.fromstring(archive.read("3D/3dmodel.model"))
    for element in root.findall(f".//{{{_MODEL_NS}}}object"):
        if element.get("name") == name:
            return [
                (float(v.get("x", 0)), float(v.get("y", 0)), float(v.get("z", 0)))
                for v in element.findall(f".//{{{_MODEL_NS}}}vertex")
            ]
    msg = f"no object named {name!r} in the 3MF"
    raise AssertionError(msg)


# ---- the enclosure lid: AC #1, #2, #4 -----------------------------------------------------


def test_the_lid_exports_lip_up(measured: dict[str, Any]) -> None:
    """``Orient(up=-Z)``: the lid prints on its flat face, lip and bosses standing up off the
    bed - so the STL's lowest points are the wide flat plate (80 x 60 mm), not the lip
    (narrower) or a boss (a few mm across)."""
    scene = _ok(measured["enclosure"])
    files = scene["files"]
    written = b64decode(files["lid.stl"])
    corners = _stl_corners(written)
    box = _bbox(corners)
    assert box.z0 == pytest.approx(0.0, abs=_TINY)
    w, d = _footprint_at(corners, box.z0)
    assert w == pytest.approx(80.0, abs=0.5)
    assert d == pytest.approx(60.0, abs=0.5)
    # the lip and the bosses reach further up than the plate is thick, standing proud of it
    assert box.z1 - box.z0 > 3.0


def test_the_box_exports_the_way_it_is_drawn(measured: dict[str, Any]) -> None:
    """The box carries no ``Orient`` of its own - the default, ``up=+Z`` - so exporting it
    changes nothing but where z = 0 sits and where it is centred: it comes out the same way
    up it was authored."""
    scene = _ok(measured["enclosure"])
    box = _bbox(_stl_corners(b64decode(scene["files"]["box.stl"])))
    assert box.z0 == pytest.approx(0.0, abs=_TINY)
    assert box.x1 - box.x0 == pytest.approx(80.0, abs=0.5)
    assert box.y1 - box.y0 == pytest.approx(60.0, abs=0.5)


def test_the_3mf_lays_out_every_object_the_same_way_the_stls_do(measured: dict[str, Any]) -> None:
    """Both objects of ``enclosure.3mf`` are printed bodies, so both lie on the bed - not
    only the one the STL test above already checked."""
    scene = _ok(measured["enclosure"])
    package = b64decode(scene["files"]["enclosure.3mf"])
    for name, width, depth in (("lid", 80.0, 60.0), ("box", 80.0, 60.0)):
        vertices = _3mf_object(package, name)
        z0 = min(v[2] for v in vertices)
        assert z0 == pytest.approx(0.0, abs=_TINY)
        xs, ys = [v[0] for v in vertices], [v[1] for v in vertices]
        assert max(xs) - min(xs) == pytest.approx(width, abs=0.5)
        assert max(ys) - min(ys) == pytest.approx(depth, abs=0.5)


def test_the_3d_view_still_shows_the_lid_the_way_the_script_drew_it(
    measured: dict[str, Any],
) -> None:
    """AC #3: the file a maker downloads is laid on the bed, but the scene the app draws is
    untouched - the lid's mesh in the view is not turned over the way the export is.

    The enclosure is not a posed assembly (:mod:`bench.stage`'s ``layout`` stands each body
    on ``z = 0`` without rotating it), so the lid's flat plate - drawn on top, lip and bosses
    hanging beneath it - is still what the view's highest points are, the opposite of the
    export, where the plate is what the lowest points are."""
    scene = _ok(measured["enclosure"])
    lid = next(p for p in scene["parts"] if p["label"] == "lid")
    mesh = lid["mesh"]
    assert mesh is not None
    positions = mesh["positions"]
    corners = list(zip(positions[0::3], positions[1::3], positions[2::3], strict=True))
    w, d = _footprint_at(corners, max(p[2] for p in corners))
    assert w == pytest.approx(80.0, abs=0.5)
    assert d == pytest.approx(60.0, abs=0.5)


# ---- a part mated upside down: AC #1, #2, #3, #4 -------------------------------------------


def test_a_part_mated_upside_down_exports_as_it_was_authored(measured: dict[str, Any]) -> None:
    """``plate`` was drawn a plain 20 x 20 x 4 mm block, ``up=+Z`` by default, and then
    turned over by ``mated`` to touch ``base``'s top face - its own ``top`` (normal +Z,
    authored) now facing down, touching ``base``. Exported, it is that same block again: 4 mm
    tall, 20 x 20 in plan, resting on the bed - not the 5 to 9 mm it stands at in the
    assembly - and the face that should be down (``bottom``, the one that faces the bed for
    an ordinary ``up=+Z`` part) is what is down, not the ``top`` mating turned to touch the
    base. A part that only dropped to z = 0 without truly turning over would still measure
    4 mm tall and 20 x 20 across; only checking which named face is lowest catches that."""
    scene = _ok(measured["mated"])
    written = b64decode(scene["files"]["plate.stl"])
    box = _bbox(_stl_corners(written))
    assert box.z0 == pytest.approx(0.0, abs=_TINY)
    assert box.z1 - box.z0 == pytest.approx(4.0, abs=_TINY)
    assert box.x1 - box.x0 == pytest.approx(20.0, abs=_TINY)
    assert box.y1 - box.y0 == pytest.approx(20.0, abs=_TINY)
    plate = next(p for p in scene["parts"] if p["label"] == "plate")
    mesh = plate["mesh"]
    assert mesh is not None
    bottom_z = _z_of(written, mesh["ref_index"], mesh["refs"], "plate/bottom")
    top_z = _z_of(written, mesh["ref_index"], mesh["refs"], "plate/top")
    assert bottom_z == pytest.approx(0.0, abs=_TINY)
    assert top_z == pytest.approx(4.0, abs=_TINY)


def test_the_mated_view_still_shows_it_posed_on_top_of_the_base(measured: dict[str, Any]) -> None:
    """The same comparison as the lid's, on the pair ``mated`` puts together: what the app
    draws is the posed plate, 5 to 9 mm up - not the 0 to 4 mm the file just above exports."""
    scene = _ok(measured["mated"])
    plate = next(p for p in scene["parts"] if p["label"] == "plate")
    mesh = plate["mesh"]
    assert mesh is not None
    posed_z0 = min(mesh["positions"][2::3])
    assert posed_z0 == pytest.approx(5.0, abs=0.1)


# ---- a named bed_face: AC #1 -------------------------------------------------------------


def test_a_named_bed_face_is_the_one_that_lands_on_the_bed(measured: dict[str, Any]) -> None:
    """``Orient(up=-Z, bed_face="top")``: the block's own ``top`` (normal +Z, authored) is the
    face opposite ``up``, so it is the face that should touch the bed - and reading
    ``bed_face`` at all, rather than only ``up``, must not move it anywhere else."""
    scene = _ok(measured["bed_face"])
    written = b64decode(scene["files"]["block.stl"])
    box = _bbox(_stl_corners(written))
    assert box.z0 == pytest.approx(0.0, abs=_TINY)
    assert box.z1 - box.z0 == pytest.approx(3.0, abs=_TINY)
    block = next(p for p in scene["parts"] if p["label"] == "block")
    mesh = block["mesh"]
    assert mesh is not None
    assert _z_of(written, mesh["ref_index"], mesh["refs"], "block/top") == pytest.approx(
        0.0, abs=_TINY
    )


def test_a_bed_face_naming_nothing_fails_the_run_rather_than_exporting_something_arbitrary(
    measured: dict[str, Any],
) -> None:
    """The same refusal a bad ``ref()`` gets anywhere else in a script: the run comes back
    ``ok: False``, naming the face it could not find, not a file nobody asked for."""
    scene = measured["bad_bed_face"]
    assert scene["ok"] is False
    assert "no-such-face" in scene["error"]["message"]
