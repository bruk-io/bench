"""Functional: ``mated`` and ``check_fit`` as a script reaches them, with no kernel.

What a mate records, where its part ends up in the scene, and which pairs of an assembly
``check_clearance_within`` still walks once a pair has been mated - the browser's case, in
which nothing is measured and every measurement says so. The measuring itself, and a finding
landing on the mated part, are the adapter layer's.
"""

import pytest

from bench import Severity, run
from bench.scene import ErrorView, OkScene, Scene

pytestmark = pytest.mark.functional

MATED = """\
from bench import *
from bench.library.print import PLA

pla = Printed(PLA)
base = part("base", cuboid(40, 40, 5), pla)
plate = part("plate", cuboid(20, 20, 4), pla)
fitted = mated(base, "base/top", plate, "plate/bottom", offset=Vector(10, 10))
print(fitted)
print(fitted.part.stock.orient.up)
show(assembly("pair", (Placed(base, XY), Placed(fitted.part, XY)), posed=True))
"""

UPSIDE_DOWN = """\
from bench import *
from bench.library.print import PLA

base = part("base", cuboid(40, 40, 5), Printed(PLA))
plate = part("plate", cuboid(20, 20, 4), Printed(PLA))
fitted = mated(base, "base/top", plate, "plate/top")
print(fitted.part.stock.orient.up)
show(assembly("pair", (Placed(base, XY), Placed(fitted.part, XY)), posed=True))
"""

THREE = """\
from bench import *
from bench.library.print import PLA

pla = Printed(PLA)
base = part("base", cuboid(40, 40, 5), pla)
far = part("far", move(cuboid(10, 10, 10), Vector(100, 0, 0)), pla)
{before}
fitted = mated(base, "base/top", part("plate", cuboid(20, 20, 4), pla), "plate/bottom")
stack = assembly("stack", (Placed(base, XY), Placed(fitted.part, XY), Placed(far, XY)), posed=True)
{after}
show(stack)
"""
"""Three parts, one pair of them mated: three pairs in all, and the mated one is not the
clearance walk's to ask about. ``before`` and ``after`` are where the walk is called."""

WALK = 'print(len(check_clearance_within(stack, 0.3)), "findings")'

NO_MATERIAL = """\
from bench import *

check_fit(cuboid(10, 10, 10), move(cuboid(10, 10, 10), Vector(20, 0, 0)), Fit.SLIDE)
show(part("panel", fill(rect(10, 10)), Stock(3.0, "ply")))
"""

FIT = """\
from bench import *
from bench.library.print import PLA

a = cuboid(10, 10, 10)
print(check_fit(a, move(a, Vector(10.2, 0, 0)), Fit.SLIDE, PLA))
show(part("a", a, Printed(PLA)))
"""

PINNED = """\
from bench import *
from bench.library.print import PLA

pla = Printed(PLA)
profile = cut(fill(rect(20, 20)), circle(2.25, Point(10, 10)), label="bore")
plate = part("plate", extrude(profile, 5.0), pla)
pin = part("pin", cylinder(2.0, 12.0), pla)
fitted = mated(plate, "plate/bore", pin, "pin/side-0", fit=Fit.SLIDE, along=-3.0)
print(fitted)
show(assembly("pinned", (Placed(plate, XY), Placed(fitted.part, XY)), posed=True))
"""
"""A pin put into a bore drawn in its plate's profile, three millimetres short of the bore's
mouth: the round pair a script writes."""


def _ok(scene: Scene) -> OkScene:
    if not scene["ok"]:
        pytest.fail(f"{scene['error']['message']}\n{scene['error']['traceback']}")
    return scene


def _error(scene: Scene) -> ErrorView:
    if scene["ok"]:
        pytest.fail("that script was meant to fail")
    return scene["error"]


def test_a_mate_is_one_call_that_places_the_part_and_asks_about_the_pair() -> None:
    """The pair is declared by the call that put it together: with no kernel the question is
    still recorded - once, as unmeasured, on the line that asked - and the sentence the script
    prints says what was asked."""
    scene = _ok(run(MATED))
    [found] = scene["violations"]
    assert found["check"] == "fit"
    assert found["severity"] == Severity.UNCHECKED
    assert found["line"] == 7
    said = scene["stdout"].splitlines()
    assert said[0].startswith("plate/bottom on base/top: asked contact, not measured")


def test_the_mated_part_is_the_one_the_scene_shows_where_the_mate_put_it() -> None:
    """The plate's box in the scene is where the mate put it - slid by the offset onto the
    base's top - not where it was drawn."""
    scene = _ok(run(MATED))
    plate = next(view for view in scene["parts"] if view["label"] == "plate")
    assert plate["bbox"] == pytest.approx([10.0, 10.0, 30.0, 30.0])
    assert "plate/bottom" in scene["refs"]


def test_a_part_that_moves_without_turning_keeps_its_way_up() -> None:
    assert _ok(run(MATED))["stdout"].splitlines()[1] == "Vector(x=0.0, y=0.0, z=1.0)"


def test_a_part_mated_upside_down_prints_the_way_it_was_drawn_to() -> None:
    """Its top on the base's top turns it over, and its way up turns with it: it still
    prints standing on the face it was drawn standing on."""
    up = _ok(run(UPSIDE_DOWN))["stdout"].strip()
    assert up.startswith("Vector(x=0.0, y=") and up.endswith("z=-1.0)")


def test_the_clearance_walk_leaves_a_mated_pair_out() -> None:
    """Three parts are three pairs; the mated one was measured by the mate, so the walk asks
    only the other two. Unmeasured, a finding names no part, so what is counted is how many
    pairs the walk asked about."""
    scene = _ok(run(THREE.format(before="", after=WALK)))
    checks = sorted(one["check"] for one in scene["violations"])
    assert checks == ["clearance", "clearance", "fit"]
    assert scene["stdout"].strip() == "2 findings"


def test_a_walk_over_the_parts_as_they_were_before_the_mate_asks_about_every_pair() -> None:
    """The walk leaves out the bodies the mate handed back, by identity, so an assembly of
    the parts as they were before the mate is walked in full - it holds none of them."""
    before = (
        'loose = part("plate", cuboid(20, 20, 4), pla)\n'
        'print(len(check_clearance_within(assembly("was", (Placed(base, XY), Placed(loose, XY),'
        ' Placed(far, XY)), posed=True), 0.3)), "findings")'
    )
    scene = _ok(run(THREE.format(before=before, after="")))
    assert scene["stdout"].strip() == "3 findings"


def test_a_mated_pair_the_walk_leaves_out_is_still_named_by_the_mates_own_finding() -> None:
    """Nothing about the pair goes unasked: the finding the walk does not make is the one the
    mate made, on the line of the mate."""
    scene = _ok(run(THREE.format(before="", after=WALK)))
    [mate] = [one for one in scene["violations"] if one["check"] == "fit"]
    assert mate["severity"] == Severity.UNCHECKED
    assert mate["line"] == 8


def test_a_fit_with_no_material_to_read_its_gap_from_stops_the_run() -> None:
    error = _error(run(NO_MATERIAL))
    assert "slide fit is a gap in some plastic" in error["message"]
    assert error["line"] == 3


def test_check_fit_says_what_it_asked_even_when_nothing_measured_it() -> None:
    scene = _ok(run(FIT))
    assert scene["stdout"].startswith("asked 0.200 (slide), not measured")
    assert [one["check"] for one in scene["violations"]] == ["fit"]


def test_a_pin_mated_into_its_bore_is_shown_on_the_bores_axis_and_asks_the_fits_gap() -> None:
    """The pin's box in the scene is centred on the bore, slid ``along`` its axis; with no
    kernel the gap round it is asked and not measured, on the line of the mate."""
    scene = _ok(run(PINNED))
    pin = next(view for view in scene["parts"] if view["label"] == "pin")
    assert pin["bbox"] == pytest.approx([8.0, 8.0, 12.0, 12.0])
    said = scene["stdout"].strip()
    assert said.startswith("pin/side-0 on plate/bore: asked 0.200 (slide), not measured")
    [found] = scene["violations"]
    assert (found["check"], found["severity"], found["line"]) == ("fit", Severity.UNCHECKED, 8)


def test_a_round_face_put_on_a_flat_one_stops_the_run_naming_both() -> None:
    error = _error(run(PINNED.replace('"plate/bore"', '"plate/top"')))
    assert "pin/side-0 is round and plate/top is not" in error["message"]
    assert error["line"] == 8
