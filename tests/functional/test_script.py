import json
from pathlib import Path

import pytest

import bench
from bench import Bed, ref, run, scene_json
from bench.library import gridfinity
from bench.scene import ErrorView, OkScene, Scene

pytestmark = pytest.mark.functional

EXAMPLE = Path(__file__).resolve().parent.parent.parent / "examples" / "gridfinity_cabinet.py"
BOX_EXAMPLE = Path(__file__).resolve().parent.parent.parent / "examples" / "box_with_hole.py"


def _ok(scene: Scene) -> OkScene:
    if not scene["ok"]:
        pytest.fail(f"{scene['error']['message']}\n{scene['error']['traceback']}")
    return scene


def _error(scene: Scene) -> ErrorView:
    if scene["ok"]:
        pytest.fail("that script was meant to fail")
    return scene["error"]


def _source() -> str:
    return EXAMPLE.read_text()


def _box_source() -> str:
    return BOX_EXAMPLE.read_text()


# ---- the example ---------------------------------------------------------------------


def test_the_shipped_example_runs_clean_and_nests_onto_the_default_bed() -> None:
    scene = _ok(run(_source()))
    assert scene["warnings"] == []
    assert scene["sheets"]
    assert all(sheet["svg"].startswith("<?xml") for sheet in scene["sheets"])
    assert {sheet["thickness"] for sheet in scene["sheets"]} == {3.0, 6.0}


def test_the_example_names_every_panel_and_the_pull_cut_in_a_front() -> None:
    scene = _ok(run(_source()))
    labels = [part["label"] for part in scene["parts"]]
    assert "drawer-front-1" in labels
    assert "cabinet-side-left" in labels
    assert "drawer-front-1/pull" in scene["refs"]
    assert "drawer-front-1/label" in scene["refs"]
    assert all(part["ref"] in scene["refs"] for part in scene["parts"])


def test_a_part_carries_its_stock_its_process_its_box_and_its_plate() -> None:
    scene = _ok(run(_source()))
    front = next(one for one in scene["parts"] if one["label"] == "drawer-front-1")
    assert front["process"] == "laser"
    assert front["stock"] == {"thickness": 3.0, "material": "ply", "kerf": 0.25}
    assert front["qty"] == 1
    x0, y0, x1, y1 = front["bbox"]
    assert (x0, y0) == (0.0, 0.0)
    assert x1 > y1 > 0.0
    assert front["mesh"] is not None
    assert "drawer-front-1/pull" in front["mesh"]["refs"]
    assert [(one["text"], one["ref"]) for one in front["lettering"]] == [
        ("1", "drawer-front-1/label")
    ]


def test_a_part_cut_more_than_once_says_so() -> None:
    scene = _ok(run(_source()))
    sides = next(one for one in scene["parts"] if one["label"] == "drawer-side")
    assert sides["qty"] == 12


def test_the_files_hold_both_formats_of_every_sheet_a_part_svg_and_the_baseplate() -> None:
    scene = _ok(run(_source()))
    for sheet in scene["sheets"]:
        assert scene["files"][f"{sheet['name']}.svg"] == sheet["svg"]
        assert scene["files"][f"{sheet['name']}.dxf"].startswith("0\nSECTION")
    for one in scene["parts"]:
        assert f"part-{one['ref']}.svg" in scene["files"]
    assert "baseplate();" in scene["files"]["baseplate.scad"]


def test_a_cabinet_without_a_baseplate_brings_no_scad() -> None:
    scene = _ok(run(_source(), {"baseplate": False}))
    assert "baseplate.scad" not in scene["files"]


def test_every_sheet_lists_the_refs_it_carries() -> None:
    scene = _ok(run(_source()))
    on_sheets = {named for sheet in scene["sheets"] for named in sheet["parts"]}
    assert on_sheets == {one["ref"] for one in scene["parts"]}


def test_what_the_script_printed_comes_back_as_stdout() -> None:
    scene = _ok(run(_source()))
    assert scene["stdout"].startswith("carcass ")
    assert "6 drawers" in scene["stdout"]


def test_what_the_script_wrote_to_stderr_comes_back_as_stderr() -> None:
    source = (
        "from bench import *\n"
        "import sys\n"
        "print('on stdout')\n"
        "print('on stderr', file=sys.stderr)\n"
        "show(part('p', fill(rect(10, 10)), Stock(3, 'ply', kerf=0.2), Process.LASER))\n"
    )
    scene = _ok(run(source))
    assert scene["stdout"] == "on stdout\n"
    assert scene["stderr"] == "on stderr\n"


def test_a_script_that_says_nothing_says_nothing_on_either_stream() -> None:
    scene = _ok(run(_box_source()))
    assert scene["stderr"] == ""


def test_a_run_that_fell_over_still_says_what_it_printed_first() -> None:
    """The output of a run that failed is the run whose output is worth the most: a script
    prints its way to the line that breaks."""
    source = (
        "from bench import *\n"
        "import sys\n"
        "print('got this far')\n"
        "print('and this on stderr', file=sys.stderr)\n"
        "raise ValueError('boom')\n"
    )
    scene = run(source)
    assert scene["ok"] is False
    assert scene["error"]["message"] == "ValueError: boom"
    assert scene["stdout"] == "got this far\n"
    assert scene["stderr"] == "and this on stderr\n"


def test_a_script_that_never_showed_anything_keeps_what_it_printed() -> None:
    scene = run("from bench import *\nprint('but no show')\n")
    assert scene["ok"] is False
    assert scene["stdout"] == "but no show\n"


def test_a_compile_that_never_ran_printed_nothing_on_either_stream() -> None:
    """The one failure with genuinely nothing to carry: the syntax error happens before the
    streams are redirected, because it happens before anything runs at all."""
    scene = run("if :")
    assert scene["ok"] is False
    assert scene["stdout"] == ""
    assert scene["stderr"] == ""


def test_a_scene_is_json_all_the_way_down() -> None:
    scene = _ok(run(_source()))
    again = json.loads(scene_json(scene))
    assert again == scene
    assert again["parts"][0]["lettering"][0]["corners"]


# ---- the second example ---------------------------------------------------------------


def test_the_box_example_runs_clean_and_nests_onto_one_sheet() -> None:
    scene = _ok(run(_box_source()))
    assert scene["warnings"] == []
    assert scene["sheets"]
    assert {sheet["thickness"] for sheet in scene["sheets"]} == {3.0}


def test_the_box_example_cuts_a_hole_in_one_side_and_engraves_the_front() -> None:
    scene = _ok(run(_box_source()))
    labels = [part["label"] for part in scene["parts"]]
    assert {"front", "back", "side-left", "side-right", "bottom"} <= set(labels)
    assert "side-left/side-left/hole" in scene["refs"]
    assert "front/label" in scene["refs"]
    assert "side-right/side-right/hole" not in scene["refs"]


# ---- parameters ----------------------------------------------------------------------


def test_the_panel_sees_every_parameter_of_the_example_in_order() -> None:
    scene = _ok(run(_source()))
    assert [one["name"] for one in scene["params"]] == [
        "units_x",
        "units_y",
        "height_u",
        "drawers",
        "columns",
        "drawer_t",
        "carcass_t",
        "finger",
        "kerf",
        "baseplate",
        "labels",
    ]
    kinds = {one["name"]: one["kind"] for one in scene["params"]}
    assert kinds["units_x"] == "int"
    assert kinds["kerf"] == "float"
    assert kinds["baseplate"] == "bool"
    assert kinds["labels"] == "str"
    assert scene["values"]["units_x"] == 4
    assert scene["values"]["baseplate"] is True


def test_an_override_changes_the_geometry_without_touching_the_source() -> None:
    source = _source()
    narrow = _ok(run(source))
    wide = _ok(run(source, {"units_x": 6}))
    front = next(one for one in narrow["parts"] if one["label"] == "drawer-front-1")
    wider = next(one for one in wide["parts"] if one["label"] == "drawer-front-1")
    grew = wider["bbox"][2] - wider["bbox"][0] - (front["bbox"][2] - front["bbox"][0])
    assert grew == pytest.approx(2 * 42.0)
    assert wide["values"]["units_x"] == 6
    assert wide["params"][0]["default"] == 4


def test_an_int_parameter_stays_an_int_when_the_browser_sends_a_number() -> None:
    scene = _ok(run(_source(), {"drawers": 3.0, "units_y": "2"}))
    assert scene["values"]["drawers"] == 3
    assert isinstance(scene["values"]["drawers"], int)
    assert scene["values"]["units_y"] == 2


def test_an_override_that_is_not_a_number_fails_at_the_show_line_naming_the_setting() -> None:
    error = _error(run(SETTINGS, {"w": "wide"}))
    assert error["message"] == "ValueError: w must be a number, not 'wide'"
    assert error["line"] == SHOW_LINE


def test_a_flag_that_says_neither_yes_nor_no_fails_at_the_show_line() -> None:
    """A flag reads the words a form sends as well as the thing itself, but "maybe" is
    neither."""
    error = _error(run(SETTINGS, {"holes": "maybe"}))
    assert error["message"] == "ValueError: holes must be true or false, not 'maybe'"
    assert error["line"] == SHOW_LINE


def test_a_comma_separated_str_parameter_engraves_one_label_per_drawer() -> None:
    scene = _ok(run(_source(), {"drawers": 3, "labels": "bits, taps , dies"}))
    labels = [one["label"] for one in scene["parts"]]
    assert labels[:3] == ["drawer-front-bits", "drawer-front-taps", "drawer-front-dies"]
    front = scene["parts"][0]
    assert [one["text"] for one in front["lettering"]] == ["bits"]


# ---- settings: one dataclass, and a build function over it --------------------------


SETTINGS = """\
from dataclasses import dataclass
from typing import Literal

from bench import *


@dataclass(frozen=True, slots=True, kw_only=True)
class Panel:
    w: float = knob(80.0, min=10.0, max=200.0, step=0.5, label="Width")
    h: float = 40.0
    holes: bool = True
    finish: Literal["oil", "wax", "none"] = "oil"
    title: str = "panel"


def build(p: Panel) -> Part:
    shape = fill(rect(p.w, p.h, label=Label("outline")))
    if p.holes:
        shape = cut(shape, circle(4.0, Point(p.w / 2, p.h / 2)), label=Label("hole"))
    print(f"building {p.title} at {p.w} x {p.h}")
    return part(Label(p.title), shape, Stock(3.0, p.finish, 0.25), Process.LASER)


show(build)
"""
"""The panel script again, written as settings and a build; ``show(build)`` is line 24."""

SHOW_LINE = 24

SMALL = (
    "from dataclasses import dataclass\n"
    "from bench import *\n"
    "\n"
    "@dataclass(frozen=True)\n"
    "class S:\n"
    "    n: int = 1\n"
    "\n"
)
"""Seven lines of settings for the scripts that are about ``show`` rather than a part; what
follows it starts on line 8."""


def test_the_settings_class_is_the_panel_in_the_order_it_declares() -> None:
    scene = _ok(run(SETTINGS))
    assert [one["name"] for one in scene["params"]] == ["w", "h", "holes", "finish", "title"]
    assert scene["params"][0] == {
        "name": "w",
        "label": "Width",
        "kind": "float",
        "default": 80.0,
        "min": 10.0,
        "max": 200.0,
        "step": 0.5,
        "choices": None,
    }
    assert scene["params"][3]["choices"] == ["oil", "wax", "none"]
    assert scene["values"] == {
        "w": 80.0,
        "h": 40.0,
        "holes": True,
        "finish": "oil",
        "title": "panel",
    }


def test_an_override_reaches_the_build_as_its_settings() -> None:
    scene = _ok(run(SETTINGS, {"w": "120", "holes": "false", "title": 7}))
    made = scene["parts"][0]
    assert made["label"] == "7"
    assert made["bbox"][2] - made["bbox"][0] == pytest.approx(120.0)
    holed = _ok(run(SETTINGS, {"w": "120", "title": 7}))["parts"][0]["mesh"]
    assert made["mesh"] is not None and holed is not None
    assert len(made["mesh"]["ref_index"]) < len(holed["ref_index"]), "no holes, fewer walls"
    assert scene["values"]["w"] == pytest.approx(120.0)
    assert "building 7 at 120.0 x 40.0" in scene["stdout"]


def test_a_setting_outside_its_range_is_built_at_the_nearer_end() -> None:
    """Held, not refused: the run goes on with the nearest value the script allows, and
    ``values`` says which one was built."""
    scene = _ok(run(SETTINGS, {"w": 5}))
    assert scene["values"]["w"] == pytest.approx(10.0)
    made = scene["parts"][0]
    assert made["bbox"][2] - made["bbox"][0] == pytest.approx(10.0)


def test_an_emptied_field_is_refused_rather_than_built_at_zero() -> None:
    """``""`` is what the panel sends while a number is being retyped."""
    error = _error(run(SETTINGS, {"w": ""}))
    assert error["message"] == "ValueError: w must be a number, not ''"


def test_an_override_the_settings_do_not_declare_is_ignored() -> None:
    assert _ok(run(SETTINGS, {"gone": 3}))["values"]["w"] == pytest.approx(80.0)


def test_an_exception_inside_the_build_is_reported_at_the_build_s_own_line() -> None:
    error = _error(
        run(SMALL + "def build(p: S) -> Part:\n    raise ValueError('boom')\n\nshow(build)\n")
    )
    assert error["message"] == "ValueError: boom"
    assert error["line"] == 9


def test_showing_the_settings_class_itself_names_the_mistake() -> None:
    error = _error(run(SMALL + "show(S)\n"))
    assert "give it the function that builds from it" in error["message"]
    assert error["line"] == 8


def test_a_build_whose_argument_has_no_annotation_says_how_to_write_one() -> None:
    error = _error(run(SMALL + "def build(p):\n    return None\n\nshow(build)\n"))
    assert "write def build(p: Settings)" in error["message"]
    assert error["line"] == 11


def test_a_build_that_takes_two_arguments_is_refused() -> None:
    error = _error(
        run(
            SMALL + "def build(p: S, q: S) -> Part:\n    raise ValueError('never')\n\nshow(build)\n"
        )
    )
    assert "it takes 2" in error["message"]
    assert error["line"] == 11


def test_two_runs_never_see_each_other_s_declarations() -> None:
    first = _ok(run(SETTINGS))
    second = _ok(run(SETTINGS, {"w": 150}))
    assert first["params"] == second["params"]
    assert first["values"]["w"] == pytest.approx(80.0)
    assert second["values"]["w"] == pytest.approx(150.0)


def test_show_belongs_to_a_run_and_knob_to_the_package() -> None:
    """``show`` is a per-run closure injected into the script's namespace, so there is
    nothing to call outside a run and ``from bench import *`` cannot replace it. ``knob``
    touches no run, so it is the package's own."""
    assert "show" not in bench.__all__
    assert not hasattr(bench, "show")
    assert "knob" in bench.__all__
    assert "param" not in bench.__all__
    assert not hasattr(bench, "param")


def test_a_script_that_still_calls_param_is_told_plainly_that_it_is_gone() -> None:
    error = _error(run("from bench import *\nw = param('w', 7)\n"))
    assert error["message"] == "NameError: name 'param' is not defined"
    assert error["line"] == 2


def test_a_star_import_does_not_take_the_injected_name_away() -> None:
    """``SETTINGS`` itself says ``from bench import *`` before calling ``show``; this is the
    same thing said out loud, with the name read out of the script's own globals."""
    source = (
        "from bench import *\n"
        "print(show.__module__)\n"
        "show(part(Label('p'), fill(rect(7, 7)), Stock(3.0, 'ply', 0.25), Process.LASER))\n"
    )
    scene = _ok(run(source))
    assert scene["stdout"] == "bench.script\n"


# ---- what can be shown ---------------------------------------------------------------


def test_a_lone_part_can_be_shown_and_keeps_its_own_ref() -> None:
    source = (
        "from bench import *\n"
        "show(part(Label('lid'), fill(rect(40, 20, label=Label('outline'))),"
        " Stock(3.0, 'ply', 0.25), Process.LASER))\n"
    )
    scene = _ok(run(source))
    assert [one["ref"] for one in scene["parts"]] == ["lid"]
    assert scene["refs"] == ["lid", "lid/outline"]
    assert scene["parts"][0]["qty"] == 1


def test_a_sequence_of_parts_can_be_shown() -> None:
    source = (
        "from bench import *\n"
        "panels = [part(Label(f'panel-{i}'), fill(rect(40, 20)), Stock(3.0, 'ply', 0.25),"
        " Process.LASER) for i in range(3)]\n"
        "show(panels)\n"
    )
    scene = _ok(run(source))
    assert [one["ref"] for one in scene["parts"]] == ["panel-0", "panel-1", "panel-2"]
    assert len(scene["sheets"]) == 1


def test_a_raw_assembly_can_be_shown() -> None:
    """``show`` takes an ``Assembly`` as readily as the ``Part`` it usually wraps one
    around - a script that already built its own assembly does not need to unwrap it."""
    source = (
        "from bench import *\n"
        "front = part(Label('lid'), fill(rect(40, 20)), Stock(3.0, 'ply', 0.25), Process.LASER)\n"
        "show(assembly(Label('box'), (Placed(front, XY),)))\n"
    )
    scene = _ok(run(source))
    assert [one["ref"] for one in scene["parts"]] == ["lid"]
    assert scene["refs"] == ["lid"]


def test_showing_an_empty_sequence_is_an_error() -> None:
    error = _error(run("from bench import *\nshow(())\n"))
    assert error["line"] == 2
    assert "empty sequence" in error["message"]


def test_showing_a_sequence_holding_something_that_is_not_a_part_is_an_error() -> None:
    error = _error(run("from bench import *\nshow((1, 2))\n"))
    assert error["line"] == 2
    assert "not a part" in error["message"]


def test_showing_something_that_is_not_geometry_is_an_error() -> None:
    error = _error(run("from bench import *\nshow(42)\n"))
    assert error["line"] == 2
    assert "cannot show" in error["message"]


def test_a_build_with_a_bad_quantities_value_is_an_error() -> None:
    """``Build.quantities`` maps a ref to how many to cut; a value that is not a count at
    all (a string, here) is not caught at ``show()`` - the call just records it - but once
    the run tries to nest it, a quantity multiplies the blanks and a non-int breaks there.
    That happens after the script's own code has finished, so no frame of it is on the
    traceback and the error has no line - but it is still an error scene, not an exception
    out of ``run`` itself."""
    source = (
        "from bench import *\n"
        "front = part(Label('lid'), fill(rect(40, 20)), Stock(3.0, 'ply', 0.25), Process.LASER)\n"
        "root = assembly(Label('box'), (Placed(front, XY),))\n"
        "show(Build(root, frozendict({Ref('lid'): 'many'})))\n"
    )
    error = _error(run(source))
    assert error["line"] is None
    assert "TypeError" in error["message"]


def test_ref_names_the_path_it_was_given() -> None:
    assert ref("drawer-front-1/pull") == "drawer-front-1/pull"


def test_the_script_runs_as_its_own_module_with_the_real_builtins() -> None:
    scene = _ok(
        run(
            "from bench import *\n"
            "print(__name__, len(dir(__builtins__)) > 20)\n"
            "show(part(Label('p'), fill(rect(10, 10)), Stock(3.0, 'ply', 0.25), Process.LASER))\n"
        )
    )
    assert scene["stdout"] == "__script__ True\n"


# ---- failure -------------------------------------------------------------------------


def test_a_syntax_error_comes_back_as_the_line_it_is_on() -> None:
    error = _error(run("from bench import *\nx = (1\nshow(x)\n"))
    assert error["line"] == 2
    assert error["message"].startswith("SyntaxError: ")
    assert "line 2" in error["traceback"]


def test_an_exception_comes_back_as_the_script_line_that_raised_it() -> None:
    error = _error(run("from bench import *\nx = 1\ny = 1 / 0\nshow(x)\n"))
    assert error["line"] == 3
    assert error["message"] == "ZeroDivisionError: division by zero"
    assert "y = 1 / 0" in error["traceback"]
    assert "bench" not in error["traceback"]


def test_a_failure_deep_in_bench_is_reported_where_the_script_called_in() -> None:
    source = (
        "from bench import *\n"
        "from bench.library import gridfinity\n"
        "n = 0\n"
        "show(gridfinity.cabinet(gridfinity.Spec(drawers=n)))\n"
    )
    error = _error(run(source))
    assert error["line"] == 4
    assert error["message"] == "ValueError: drawers must be at least one, not 0"
    assert error["traceback"].count("File ") == 1


def test_a_setting_that_is_not_a_scalar_is_an_error_at_the_show_line() -> None:
    source = SMALL.replace("n: int = 1", "sizes: tuple[int, ...] = (1, 2)") + (
        "def build(p: S) -> Part:\n    raise ValueError('never')\n\nshow(build)\n"
    )
    error = _error(run(source))
    assert error["line"] == 11
    assert error["message"].startswith("TypeError: S.sizes is tuple[int, ...]")


def test_a_script_that_never_shows_anything_is_an_error_with_no_line() -> None:
    error = _error(run("from bench import *\nx = 1\n"))
    assert error["line"] is None
    assert "never called show" in error["message"]
    assert error["traceback"] == ""


def test_showing_twice_is_an_error_on_the_second_call() -> None:
    source = (
        "from bench import *\n"
        "p = part(Label('p'), fill(rect(10, 10)), Stock(3.0, 'ply', 0.25), Process.LASER)\n"
        "show(p)\n"
        "show(p)\n"
    )
    error = _error(run(source))
    assert error["line"] == 4
    assert "already called" in error["message"]


def test_a_script_that_exits_comes_back_as_an_error_scene_not_an_exception() -> None:
    error = _error(run("import sys\nsys.exit('enough')\n"))
    assert error["line"] == 2
    assert error["message"] == "SystemExit: enough"


def test_a_failed_run_is_still_json() -> None:
    again = json.loads(scene_json(run("from bench import *\nx = (1\n")))
    assert again["ok"] is False
    assert again["error"]["line"] == 2
    assert set(again["error"]) == {"message", "line", "traceback"}


# ---- the bed -------------------------------------------------------------------------


def test_a_smaller_bed_warns_about_what_will_not_fit_rather_than_dropping_it() -> None:
    scene = _ok(run(_source(), bed=Bed(200.0, 200.0)))
    assert scene["warnings"]
    assert any("cabinet-side-left" in warning for warning in scene["warnings"])
    assert all("does not fit" in warning for warning in scene["warnings"])
    assert scene["sheets"]


def test_a_bed_carries_the_margin_and_the_gap_a_maker_wants() -> None:
    """The knobs used to be unreachable: ``run`` took a bare ``(w, h)`` pair, so nothing
    outside :mod:`bench.nest` could say how far in from the edge to stay."""
    source = _source()
    tight = _ok(run(source, bed=Bed(320.0, 320.0, margin=1.0, gap=1.0)))
    roomy = _ok(run(source, bed=Bed(320.0, 320.0, margin=20.0, gap=12.0)))
    assert len(roomy["sheets"]) > len(tight["sheets"])
    assert tight["warnings"] == []


def test_a_bigger_bed_needs_fewer_sheets() -> None:
    source = _source()
    small = _ok(run(source, bed=Bed(320.0, 320.0)))
    big = _ok(run(source, bed=Bed(600.0, 400.0)))
    assert len(big["sheets"]) < len(small["sheets"])
    assert big["warnings"] == []


def test_the_parts_themselves_are_not_kerf_compensated() -> None:
    source = (
        "from bench import *\n"
        "show(part(Label('p'), fill(rect(40, 20)), Stock(3.0, 'ply', 1.0), Process.LASER))\n"
    )
    scene = _ok(run(source))
    x0, y0, x1, y1 = scene["parts"][0]["bbox"]
    assert (x1 - x0, y1 - y0) == (40.0, 20.0)
    placed = scene["sheets"][0]["parts"]
    assert placed == ["p"]


def test_a_sheet_is_named_for_its_stock_and_its_place_in_that_series() -> None:
    scene = _ok(run(_source()))
    names = [sheet["name"] for sheet in scene["sheets"]]
    assert names[0] == "sheet-3mm-01"
    assert "sheet-6mm-01" in names
    assert len(set(names)) == len(names)


def test_a_nested_sheet_is_titled_and_keeps_the_refs_of_the_wires_that_have_them() -> None:
    scene = _ok(run(_source()))
    for sheet in scene["sheets"]:
        assert f"<title>{sheet['name']}</title>" in sheet["svg"]
    assert any('data-ref="drawer-front-1/pull"' in sheet["svg"] for sheet in scene["sheets"])


def test_a_script_imports_the_library_it_reaches_for() -> None:
    source = (
        "from bench import *\n"
        "from bench.library import gridfinity\n"
        "print(gridfinity.GRID, bench.library.gridfinity is gridfinity)\n"
        "show(gridfinity.cabinet(gridfinity.Spec(drawers=1, height_u=1, units_x=1, units_y=1)))\n"
    )
    scene = _ok(run(source))
    assert scene["stdout"] == "42.0 True\n"


def test_a_library_is_not_in_the_namespace_unless_the_host_puts_it_there() -> None:
    """The runtime binds no library by name. A host with scripts already written can
    pre-bind one through ``extras``, which is what the browser worker does."""
    source = (
        "from bench import *\n"
        "print(gridfinity.GRID)\n"
        "show(gridfinity.cabinet(gridfinity.Spec(drawers=1, height_u=1, units_x=1, units_y=1)))\n"
    )
    error = _error(run(source))
    assert error["line"] == 2
    assert error["message"] == "NameError: name 'gridfinity' is not defined"
    scene = _ok(run(source, extras={"gridfinity": gridfinity}))
    assert scene["stdout"] == "42.0\n"


# ---- a body somebody else made ----------------------------------------------------------

TRIANGLE = bench.Mesh((0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 4.0, 0.0), (0, 1, 2), (None,))
"""One triangle, which is enough to be handed over and measured."""

SURVEYS = """\
from bench import *

print(reference is None, survey(reference).triangles)
show(part("plate", fill(rect(10, 10)), Stock(3, "ply")))
"""


def test_a_reference_is_bound_for_the_script_to_measure() -> None:
    """A host hands over a body somebody else made; the script surveys what it is copying."""
    scene = _ok(run(SURVEYS, reference=TRIANGLE))
    assert scene["stdout"] == "False 1\n"


def test_a_reference_is_none_when_the_host_has_nothing_to_offer() -> None:
    """The name is always there, so a script tests it rather than guarding an import."""
    source = (
        "from bench import *\n\n"
        "print(reference)\n"
        "show(part('p', fill(rect(4, 4)), Stock(3, 'ply')))\n"
    )
    assert _ok(run(source))["stdout"] == "None\n"


def test_a_reference_reaches_the_scene_as_a_body_to_draw_and_nothing_else() -> None:
    """It is something to look at and to measure, not something to make: it is drawn, and it
    is not a part, is nested onto no sheet and reaches no file."""
    with_one = _ok(run(SURVEYS, reference=TRIANGLE))
    without = _ok(run(SURVEYS.replace("survey(reference).triangles", "0")))

    assert [view["ref"] for view in with_one["parts"]] == ["plate"]
    assert with_one["parts"] == without["parts"]
    assert with_one["sheets"] == without["sheets"]
    assert with_one["files"] == without["files"]
    assert without["reference"] is None

    drawn = with_one["reference"]
    assert drawn is not None
    assert len(drawn["positions"]) == 9, "one triangle, three corners, three numbers each"


def test_a_drawn_reference_answers_to_no_name_so_a_click_cannot_land_on_it() -> None:
    """Every triangle indexes nothing and the table is empty, which is how the viewer is told
    this body is scenery rather than something to select."""
    drawn = _ok(run(SURVEYS, reference=TRIANGLE))["reference"]

    assert drawn is not None
    assert drawn["refs"] == []
    assert set(drawn["ref_index"]) == {0}


# ---- a body through the runtime ---------------------------------------------------------

SOLID = """\
from dataclasses import dataclass

from bench import *


@dataclass(frozen=True)
class Plate:
    depth: float = 2.0


def build(p: Plate) -> Part:
    plate = extrude(fill(rect(60.0, 40.0, label="outline")), 5.0)
    top = plane_of(plate, "top")
    plate = pocket(plate, fill(rect(20.0, 10.0, Point(20.0, 15.0)), on=top),
                   p.depth, label="pocket")
    return part("plate", plate, Stock(0.0, "PLA"), Process.PRINT)


show(build)
"""


def test_a_part_holding_a_body_comes_back_as_a_scene_of_refs_and_no_paths() -> None:
    """The acceptance bar for a tree with no kernel behind it: the scene lists every face
    the body will have and draws nothing at all, because a recipe cannot be flattened onto
    a sheet."""
    scene = _ok(run(SOLID))
    assert scene["refs"] == [
        "plate",
        "plate/top",
        "plate/bottom",
        "plate/side-0",
        "plate/side-1",
        "plate/side-2",
        "plate/side-3",
        "plate/pocket",
        "plate/pocket/top",
        "plate/pocket/bottom",
        "plate/pocket/side-0",
        "plate/pocket/side-1",
        "plate/pocket/side-2",
        "plate/pocket/side-3",
    ]
    only = scene["parts"][0]
    assert (only["mesh"], only["marks"], only["lettering"]) == (None, None, [])
    assert only["bbox"] == pytest.approx([0.0, 0.0, 60.0, 40.0])
    assert scene["sheets"] == []
    assert any("plate" in warning for warning in scene["warnings"])
    json.loads(scene_json(scene))


# ---- the kernel that builds a body --------------------------------------------------------


def test_a_flat_part_is_drawn_as_the_plate_it_is_cut_from() -> None:
    """A face is swept into a plate as thick as its stock with no kernel at all, so a laser
    part is drawn whether or not a modeller loaded."""
    mesh = _ok(run(SETTINGS))["parts"][0]["mesh"]
    assert mesh is not None
    assert mesh["positions"]


def test_a_run_without_a_kernel_still_produces_everything_that_does_not_need_one() -> None:
    """The whole point of injecting the kernel: refs, parameters and the cut sheets are the
    tree's own answers, and only ``mesh`` and the STL wait for a modeller."""
    scene = _ok(run(SOLID))
    only = scene["parts"][0]
    assert only["mesh"] is None
    assert not [name for name in scene["files"] if name.endswith(".stl")]
    assert scene["refs"] and scene["params"]


def test_which_files_of_a_scene_are_bytes_is_answerable_from_the_name() -> None:
    """A scene is JSON, so every file is a string; this is the one place that says which
    strings have to be decoded before they are written to disk."""
    assert bench.transport.binary("plate.stl") is True
    assert bench.transport.binary("sheet-3mm-01.svg") is False
    assert bench.transport.binary("baseplate.scad") is False
