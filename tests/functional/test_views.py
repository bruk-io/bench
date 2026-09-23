"""Functional: the facts a scene carries so the app words them rather than works them out.

Real runs, read back through what :mod:`bench.views` gives a scene beyond its records: a body
for every part there is one for - a laser part's plate, swept whether or not there is a kernel
- standing on one stage, the files a cutter and a printer read, and the summary the status line
is worded from.
"""

import re
from pathlib import Path

import pytest

from bench import XY, Placed, Printed, Ref, Severity, assembly, cuboid, part, run, views
from bench.checks import Violation
from bench.library.print import PLA
from bench.nest import Bed
from bench.scene import OkScene, Scene
from bench.stage import GAP
from bench.telemetry import SILENT

pytestmark = pytest.mark.functional

CABINET = Path(__file__).resolve().parents[2] / "examples" / "gridfinity_cabinet.py"

PRINTED = """\
from bench import *
from bench.library.print import PLA

show(part("block", cuboid(20, 20, 5), Printed(PLA)))
"""

TOO_BIG = """\
from bench import *
from bench.library.print import H2D, PLA

block = cuboid(400, 20, 5)
check_fits(block, H2D)
show(part("block", block, Printed(PLA)))
"""


def _ok(scene: Scene) -> OkScene:
    assert scene["ok"], scene
    return scene


def test_two_parts_sharing_a_face_name_keep_their_own_findings() -> None:
    """A wall check on a bare cuboid answers ``top``; every cuboid has one. The scene puts the
    finding under the part whose shape is the very object the check was handed - ``b/top`` -
    and a suffix match would have marked ``a/top`` first and been wrong.

    Built through :func:`bench.views.scene` directly rather than a run, because a wall
    measurement takes a kernel and this layer has none; the ``Finding`` is what the run would
    have recorded, real in every field.
    """
    a = part("a", cuboid(20, 20, 5), Printed(PLA))
    b = part("b", cuboid(20, 20, 5), Printed(PLA))
    assert a.shape == b.shape and a.shape is not b.shape
    found = Violation("wall", "the thinnest wall is 0.40 mm", Severity.ERROR, (Ref("top"),))
    scene = views.scene(
        assembly=assembly("pair", (Placed(a, XY), Placed(b, XY))),
        quantities={},
        extra={},
        params=[],
        values={},
        findings=[views.Finding(found, (b.shape,))],
        bed=Bed(320.0, 320.0),
        kernel=None,
        stdout="",
        stderr="",
        tracer=SILENT,
    )
    assert [one["refs"] for one in scene["violations"]] == [["b/top"]]
    assert {"a/top", "b/top"} <= set(scene["refs"])


def test_every_laser_part_is_a_plate_on_the_stage_with_no_kernel_at_all() -> None:
    scene = _ok(run(CABINET.read_text()))
    bounds = scene["stage"]["bounds"]
    for view in scene["parts"]:
        mesh = view["mesh"]
        assert mesh is not None, view["ref"]
        xs, ys, zs = mesh["positions"][0::3], mesh["positions"][1::3], mesh["positions"][2::3]
        assert min(zs) == pytest.approx(0.0), "a plate lies on the floor"
        assert max(zs) == pytest.approx(view["stock"]["thickness"]), "as thick as its stock"
        assert bounds[0] - 1e-6 <= min(xs) and max(xs) <= bounds[3] + 1e-6
        assert bounds[1] - 1e-6 <= min(ys) and max(ys) <= bounds[4] + 1e-6


def test_a_long_run_of_plates_wraps_into_rows() -> None:
    bounds = _ok(run(CABINET.read_text()))["stage"]["bounds"]
    assert bounds[3] - bounds[0] <= 600.0 + 1e-6


def test_every_ref_a_plate_answers_to_is_one_the_scene_names() -> None:
    scene = _ok(run(CABINET.read_text()))
    named = set(scene["refs"])
    for view in scene["parts"]:
        mesh = view["mesh"]
        assert mesh is not None
        assert set(mesh["refs"]) <= named, set(mesh["refs"]) - named
        assert all(one["ref"] is None or one["ref"] in named for one in view["lettering"])
    front = next(view for view in scene["parts"] if view["ref"] == "drawer-front-1")
    assert front["mesh"] is not None
    assert "drawer-front-1/pull" in front["mesh"]["refs"]
    assert [(one["text"], one["ref"]) for one in front["lettering"]] == [
        ("1", "drawer-front-1/label")
    ]


PANELS = """\
from bench import *

stock = Stock(3.0, "ply")
panels = tuple(
    Placed(
        part(f"panel-{{n}}", fill(rect(40, 30, Point(200 * n, 60 * n))), stock, Process.LASER),
        XY,
    )
    for n in range(3)
)
show(assembly("frame", panels, posed={posed}))
"""
"""Three panels drawn far apart on purpose: laid out they are packed into one row a
:data:`bench.stage.GAP` apart, and posed they stay two hundred millimetres from each other,
so the two placements cannot be confused for one another."""


def _panels(*, posed: bool) -> OkScene:
    return _ok(run(PANELS.format(posed=posed)))


def test_a_posed_assembly_is_drawn_where_the_script_put_its_parts() -> None:
    """The whole of the viewer's branch, read off the scene: posed, the third panel's plate
    still begins at the 400 mm its own face was drawn at, and the stage is the box the three
    of them already fill. Laid out, that same panel is packed to 2 * (40 + GAP)."""
    posed = _panels(posed=True)
    third = next(view for view in posed["parts"] if view["ref"] == "panel-2")
    assert third["mesh"] is not None
    assert min(third["mesh"]["positions"][0::3]) == pytest.approx(400.0)
    assert posed["stage"]["bounds"][0::3][:2] == [pytest.approx(0.0), pytest.approx(440.0)]

    laid = _panels(posed=False)
    packed = next(view for view in laid["parts"] if view["ref"] == "panel-2")
    assert packed["mesh"] is not None
    assert min(packed["mesh"]["positions"][0::3]) == pytest.approx(2 * (40.0 + GAP))


def test_a_posed_assembly_is_manufactured_exactly_as_an_unposed_one() -> None:
    """decision-6's claim, asserted rather than argued: ``posed`` is a drawing flag, so
    every file a cutter or a printer reads, every sheet, every quantity and every part's own
    bounds come back byte for byte the same. Only where the bodies stand differs."""
    posed, laid = _panels(posed=True), _panels(posed=False)
    assert posed["files"] == laid["files"]
    assert posed["sheets"] == laid["sheets"]
    assert posed["refs"] == laid["refs"]
    assert posed["warnings"] == laid["warnings"]
    assert posed["violations"] == laid["violations"]
    assert posed["summary"] == laid["summary"]
    assert [(one["ref"], one["qty"], one["bbox"]) for one in posed["parts"]] == [
        (one["ref"], one["qty"], one["bbox"]) for one in laid["parts"]
    ]
    assert posed["stage"] != laid["stage"], "and the one thing that does differ, differs"


def test_a_plate_is_cut_not_printed_so_it_writes_no_stl() -> None:
    files = _ok(run(CABINET.read_text()))["files"]
    assert not any(name.endswith((".stl", ".3mf")) for name in files)
    assert any(name.endswith(".dxf") for name in files)


def test_a_sheets_preview_is_its_cut_file_drawn_with_lines_a_thumbnail_can_show() -> None:
    """A cutter's 0.1 mm hairline, shrunk to a thumbnail, is a hundredth of a pixel and draws
    nothing: the first thumbnails were white boxes. The preview is the same paths with lines
    a sixty-fourth of the sheet wide, and the cut file is untouched."""
    sheet = _ok(run(CABINET.read_text()))["sheets"][0]
    assert 'stroke-width="0.1"' in sheet["svg"]
    assert 'stroke-width="0.1"' not in sheet["preview"]
    strip = re.compile(r'stroke-width="[^"]*"')
    assert strip.sub("", sheet["preview"]) == strip.sub("", sheet["svg"])


def test_a_printed_part_with_no_kernel_is_unbuilt() -> None:
    scene = _ok(run(PRINTED))
    [only] = scene["parts"]
    assert only["mesh"] is None
    assert (scene["summary"]["solid"], scene["summary"]["unbuilt"]) == (0, 1)


def test_an_ordinary_printed_part_gets_no_blank_part_svg_either() -> None:
    """A printed body has no flat outline to draw - :func:`bench.export.part_paths` draws
    nothing for a solid - so it never had a violation to say why; the same rule that stops a
    refused part getting an empty ``part-*.svg`` (task-58) stops one here too."""
    scene = _ok(run(PRINTED))
    assert scene["violations"] == []
    assert "part-block.svg" not in scene["files"]


def test_the_summary_counts_what_the_run_made() -> None:
    scene = _ok(run(CABINET.read_text()))
    summary = scene["summary"]
    assert summary["parts"] == len(scene["parts"])
    assert (summary["solid"], summary["unbuilt"]) == (len(scene["parts"]), 0)
    assert summary["sheets"] == len(scene["sheets"])
    assert (summary["errors"], summary["warnings"], summary["error_line"]) == (0, 0, None)


def test_the_summary_counts_what_the_checks_found_and_where() -> None:
    summary = _ok(run(TOO_BIG))["summary"]
    assert summary["errors"] == 1
    assert summary["error_line"] == 5


# ---- a part exportable() refuses says so, rather than exporting nothing ---------------

SOLID_ON_SHEET = """\
from bench import *

box = extrude(fill(rect(50, 50)), 10)
show(part("frame", box, Stock(19.05, "ply")))
"""

SOLID_MARKED_CNC = """\
from bench import *

box = extrude(fill(rect(50, 50)), 10)
show(part("frame", box, Stock(19.05, "ply"), Process.CNC))
"""

FACE_MARKED_CNC = """\
from bench import *

show(part("routed", fill(rect(50, 50)), Stock(19.05, "ply"), Process.CNC))
"""


def test_a_solid_on_sheet_stock_is_an_error_naming_the_part_not_an_empty_file() -> None:
    scene = _ok(run(SOLID_ON_SHEET))
    [found] = scene["violations"]
    assert found["check"] == "exportable"
    assert found["severity"] == "error"
    assert found["refs"] == ["frame"]
    assert scene["summary"]["errors"] == 1
    assert "part-frame.svg" not in scene["files"]


def test_a_solid_marked_cnc_says_milling_is_not_modelled_not_an_empty_file() -> None:
    scene = _ok(run(SOLID_MARKED_CNC))
    [found] = scene["violations"]
    assert found["check"] == "exportable"
    assert found["refs"] == ["frame"]
    assert "milling is not modelled yet" in found["message"]
    assert "part-frame.svg" not in scene["files"]


def test_a_flat_part_marked_cnc_is_still_a_2d_profile_and_still_exports() -> None:
    """A router cutting a flat sheet part is a legitimate 2D profile, the same shape a
    laser cuts - see :func:`bench.checks.exportable`'s own docstring for the rule."""
    scene = _ok(run(FACE_MARKED_CNC))
    assert scene["violations"] == []
    assert scene["summary"]["errors"] == 0
    assert "part-routed.svg" in scene["files"]
    assert scene["sheets"]


def test_an_unexportable_part_still_appears_in_the_scene_named_and_unbuilt() -> None:
    """The finding names a part that never disappears: it is still counted, still has a
    box, and the maker sees why it has no file rather than wondering where it went."""
    scene = _ok(run(SOLID_ON_SHEET))
    [only] = scene["parts"]
    assert only["label"] == "frame"
    assert scene["summary"]["parts"] == 1


TWO_PARTS_ONE_SOLID = """\
from bench import *

box = extrude(fill(rect(50, 50)), 10)
left = part("left", box, Stock(19.05, "ply"), Process.CNC)
right = part("right", box, Stock(19.05, "ply"), Process.CNC)
show((left, right))
"""


def test_two_parts_sharing_one_solid_are_each_named_by_their_own_violation() -> None:
    """The same ``Solid`` handed to two ``part()`` calls is two objects worth refusing, and
    a finding matched by the shape's identity would name whichever part
    :func:`bench.views._label_of` happened to see first for both - see
    :func:`bench.views._export_findings`, which carries the part's own label instead of
    matching by shape."""
    scene = _ok(run(TWO_PARTS_ONE_SOLID))
    named = {one["refs"][0] for one in scene["violations"]}
    assert named == {"left", "right"}
    assert "part-left.svg" not in scene["files"]
    assert "part-right.svg" not in scene["files"]
