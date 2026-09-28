"""Adapter: the view's *On bed* - each printed part laid the way it prints, by a move Python
worked out and the view only applies (task-89).

:mod:`bed_cases` runs a few printed scripts inside Pyodide with the app's real Manifold kernel
and the app's own printer. What is asked here is the promise the placements make: applied to
the body the view already drew, a part's placement puts every corner exactly where the part's
own STL - :func:`bench.export.as_printed`'s mesh, the bytes a maker downloads - has it, moved
only across the bed to the part's own place; the parts on one bed do not overlap; and the fit
the view marks is the one ``check_fits`` answers. Everything is read off the scene and the
files by hand, never by re-running the code under test.
"""

import math
import struct
from base64 import b64decode
from pathlib import Path
from typing import Any

import pytest

from bench.scene import OkScene, PartView
from bench.views import STANDING
from tools import stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)

_CASES = Path(__file__).with_name("bed_cases.py")

_TINY = 1e-3
"""Float noise on a single-precision mesh vertex, in millimetres."""

_EYE = 1e-4
"""How near a sight's eye is to exact: it is sent to four decimals."""

PROGRAM = """\
import json

from pyodide.ffi import JsException

import bed_cases
from bench.adapters.browser import JsKernel


def main(js, given):
    return json.dumps(bed_cases.measured(JsKernel(js, JsException)))
"""


@pytest.fixture(scope="module")
def measured() -> dict[str, Any]:
    """Every case of :mod:`bed_cases`, run once by the shipped kernel."""
    found: dict[str, Any] = stack.run(PROGRAM, {}, modules={"bed_cases.py": _CASES.read_text()})
    return found


def _ok(scene: Any) -> OkScene:
    if not scene["ok"]:
        error = scene["error"]
        pytest.fail(f"line {error['line']}: {error['message']}\n{error['traceback']}")
    ok: OkScene = scene
    return ok


def _part(scene: OkScene, label: str) -> PartView:
    return next(one for one in scene["parts"] if one["label"] == label)


def _stl_corners(data: bytes) -> list[tuple[float, float, float]]:
    """Every triangle's three corners, in the order the file writes them."""
    (count,) = struct.unpack_from("<I", data, 80)
    corners: list[tuple[float, float, float]] = []
    for at in range(count):
        base = 84 + 50 * at + 12
        for k in range(3):
            x, y, z = struct.unpack_from("<3f", data, base + 12 * k)
            corners.append((x, y, z))
    return corners


def _laid(part: PartView) -> list[tuple[float, float, float]]:
    """``part``'s drawn corners with its placement applied - what the view does, done by hand."""
    printing = part["printing"]
    mesh = part["mesh"]
    assert printing is not None
    assert mesh is not None
    rows = printing["placement"]
    assert rows is not None
    assert len(rows) == 12
    p = mesh["positions"]
    return [
        tuple(
            rows[4 * r] * p[at]
            + rows[4 * r + 1] * p[at + 1]
            + rows[4 * r + 2] * p[at + 2]
            + rows[4 * r + 3]
            for r in range(3)
        )  # type: ignore[misc]
        for at in range(0, len(p), 3)
    ]


def _footprint(corners: list[tuple[float, float, float]]) -> tuple[float, float, float, float]:
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    return min(xs), min(ys), max(xs), max(ys)


# ---- a placement is the STL's own move, then a step across the bed ---------------------


@pytest.mark.parametrize("case", ["laid_out", "posed"])
def test_every_printed_part_lands_where_its_stl_has_it_moved_only_across_the_bed(
    measured: dict[str, Any], case: str
) -> None:
    """AC#2: the placement applied to the drawn body is the STL's mesh corner for corner, one
    constant step apart - across the bed, never up it - for a part turned onto its back, one
    turned on its side, one left as drawn, and a part mated upside down in a posed pair."""
    scene = _ok(measured[case])
    for part in scene["parts"]:
        written = _stl_corners(b64decode(scene["files"][f"{part['label']}.stl"]))
        laid = _laid(part)
        assert len(laid) == len(written), part["label"]
        dx, dy, dz = (laid[0][k] - written[0][k] for k in range(3))
        assert dz == pytest.approx(0.0, abs=_TINY), part["label"]
        for on_bed, in_file in zip(laid, written, strict=True):
            assert on_bed[0] - in_file[0] == pytest.approx(dx, abs=_TINY), part["label"]
            assert on_bed[1] - in_file[1] == pytest.approx(dy, abs=_TINY), part["label"]
            assert on_bed[2] - in_file[2] == pytest.approx(0.0, abs=_TINY), part["label"]


def test_the_parts_on_a_bed_lie_on_it_side_by_side_and_do_not_overlap(
    measured: dict[str, Any],
) -> None:
    scene = _ok(measured["laid_out"])
    bed = scene["bed"]
    assert bed is not None
    w, d, _h = bed["volume"]
    feet = []
    for part in scene["parts"]:
        laid = _laid(part)
        assert min(c[2] for c in laid) == pytest.approx(0.0, abs=_TINY)
        x0, y0, x1, y1 = _footprint(laid)
        assert x0 >= -_TINY and y0 >= -_TINY and x1 <= w + _TINY and y1 <= d + _TINY
        feet.append((x0, y0, x1, y1))
    for i, a in enumerate(feet):
        for b in feet[i + 1 :]:
            apart = a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]
            assert apart, (a, b)


def test_a_part_laid_down_stands_the_way_its_orient_says(measured: dict[str, Any]) -> None:
    """The post is a 40 mm cylinder drawn standing and printed ``up=X``: on the bed it lies,
    12 mm tall; the lid is 3 mm thick whichever way up it prints."""
    scene = _ok(measured["laid_out"])
    post = _laid(_part(scene, "post"))
    assert max(c[2] for c in post) == pytest.approx(12.0, abs=0.05)
    lid = _laid(_part(scene, "lid"))
    assert max(c[2] for c in lid) == pytest.approx(3.0, abs=_TINY)
    printing = _part(scene, "post")["printing"]
    assert printing is not None
    assert printing["up"] == [1.0, 0.0, 0.0]


# ---- the bed, and whether a part fits it ------------------------------------------------


def test_a_script_that_asks_check_fits_about_the_h2d_is_laid_on_the_h2d(
    measured: dict[str, Any],
) -> None:
    bed = _ok(measured["laid_out"])["bed"]
    assert bed is not None
    assert (bed["printer"], bed["said"]) == ("H2D", "script")
    assert bed["volume"] == [350.0, 320.0, 325.0]
    assert bed["bounds"] == [0.0, 0.0, 0.0, 350.0, 320.0, 325.0]


def test_a_script_that_names_no_printer_is_laid_on_the_hosts(measured: dict[str, Any]) -> None:
    bed = _ok(measured["posed"])["bed"]
    assert bed is not None
    assert (bed["printer"], bed["said"]) == ("H2D", "host")


def test_a_script_asking_about_another_machine_is_laid_on_that_one(
    measured: dict[str, Any],
) -> None:
    bed = _ok(measured["small_machine"])["bed"]
    assert bed is not None
    assert bed["said"] == "script"
    assert bed["volume"] == [256.0, 256.0, 256.0]
    assert bed["printer"] is None


def test_a_part_bigger_than_the_bed_is_marked_and_runs_off_it(measured: dict[str, Any]) -> None:
    """AC#2's other half: the 400 mm beam does not fit the 350 mm bed. It is laid all the
    same, and the box the view frames grows to take it in."""
    scene = _ok(measured["too_big"])
    printing = _part(scene, "beam")["printing"]
    assert printing is not None
    assert printing["fits"] is False
    assert printing["over"] is not None and "x 400.0 mm against 350.0 mm" in printing["over"]
    bed = scene["bed"]
    assert bed is not None
    assert bed["bounds"][3] > 350.0
    x0, _y0, x1, _y1 = _footprint(_laid(_part(scene, "beam")))
    assert x1 - x0 == pytest.approx(400.0, abs=_TINY)


def test_parts_that_fit_say_so(measured: dict[str, Any]) -> None:
    for part in _ok(measured["laid_out"])["parts"]:
        printing = part["printing"]
        assert printing is not None
        assert (printing["fits"], printing["over"]) == (True, None)


# ---- a face's area ----------------------------------------------------------------------


def test_a_faces_area_is_what_its_triangles_cover(measured: dict[str, Any]) -> None:
    """AC#6: the flat part is a 30 by 20 by 5 block - its top 600 mm2, a long side 150."""
    areas = _part(_ok(measured["laid_out"]), "flat")["areas"]
    assert areas["flat/top"] == pytest.approx(600.0, abs=_TINY)
    assert areas["flat/bottom"] == pytest.approx(600.0, abs=_TINY)
    assert sorted(areas.values()) == pytest.approx(
        sorted([600.0, 600.0, 150.0, 150.0, 100.0, 100.0]), abs=_TINY
    )


# ---- where to stand to see a place (task-94) ----------------------------------------------


def _drawn_box(part: PartView, named: str) -> list[float]:
    """The box the drawn corners of every triangle on ``named`` or under it fill, read off the
    mesh by hand: ``ref_index`` counts a triangle's ref from one, and nothing is zero."""
    mesh = part["mesh"]
    assert mesh is not None
    p, refs = mesh["positions"], mesh["refs"]
    corners = [
        (p[9 * t + 3 * k], p[9 * t + 3 * k + 1], p[9 * t + 3 * k + 2])
        for t, at in enumerate(mesh["ref_index"])
        if at != 0 and (refs[at - 1] == named or refs[at - 1].startswith(f"{named}/"))
        for k in range(3)
    ]
    assert corners, named
    return [
        *(min(c[i] for c in corners) for i in range(3)),
        *(max(c[i] for c in corners) for i in range(3)),
    ]


def test_a_face_is_seen_from_the_way_it_faces_an_underside_from_underneath(
    measured: dict[str, Any],
) -> None:
    """AC#2: the flat block's top is looked at from above and its bottom from below, each leaning
    toward the view's standing corner rather than square on, over the box its own triangles
    fill where the stage drew them."""
    flat = _part(_ok(measured["laid_out"]), "flat")
    top, bottom = flat["sights"]["flat/top"], flat["sights"]["flat/bottom"]
    assert top["eye"][2] > 0.5
    assert bottom["eye"][2] < -0.5
    for sight in (top, bottom):
        assert math.hypot(*sight["eye"]) == pytest.approx(1.0, abs=_EYE)
        assert sight["eye"][0] > 0.0 and sight["eye"][1] < 0.0, (
            "not leaning toward the standing view"
        )
    for ref in ("flat/top", "flat/bottom"):
        assert flat["sights"][ref]["bounds"] == pytest.approx(_drawn_box(flat, ref), abs=_TINY)


def test_a_whole_part_faces_every_way_and_is_seen_from_the_standing_view(
    measured: dict[str, Any],
) -> None:
    """A closed body's facings cancel out, so it is looked at the way *Fit* looks at the work,
    over the box every triangle of it fills."""
    flat = _part(_ok(measured["laid_out"]), "flat")
    whole = flat["sights"]["flat"]
    reach = math.hypot(*STANDING)
    assert whole["eye"] == pytest.approx([one / reach for one in STANDING], abs=_EYE)
    assert whole["bounds"] == pytest.approx(_drawn_box(flat, "flat"), abs=_TINY)


def test_every_named_place_has_a_sight_and_none_looks_straight_up_or_down(
    measured: dict[str, Any],
) -> None:
    """Every face a mesh names, and every step of its ref, can be framed - and no eye is so
    near vertical that a camera whose up is Z could not turn to it."""
    for case in ("laid_out", "posed"):
        for part in _ok(measured[case])["parts"]:
            mesh = part["mesh"]
            assert mesh is not None
            for ref in mesh["refs"]:
                steps = ref.split("/")
                for depth in range(1, len(steps) + 1):
                    assert "/".join(steps[:depth]) in part["sights"], ref
            for ref, sight in part["sights"].items():
                ex, ey, ez = sight["eye"]
                assert math.hypot(ex, ey) >= 0.1 * math.hypot(ex, ey, ez), ref
