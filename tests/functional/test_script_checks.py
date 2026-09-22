"""Functional: the checks a script runs, and how a violation reaches the scene.

Through the public API and with no kernel, which is the browser's case: a check that cannot
be measured says ``unchecked``, a check that fails records a violation *and lets the run
finish*, and ``require`` is the one way a script turns a violation into a stopped run. The
measurement itself is the adapter layer's.
"""

import pytest

from bench import Severity, run
from bench.scene import ErrorView, OkScene, Scene

pytestmark = pytest.mark.functional

TOO_BIG = """\
from bench import *
from bench.library.print import PLA, H2D

block = cuboid(400, 100, 60)
check_fits(block, H2D)
show(part("block", block, Printed(PLA)))
"""

STOPPED = """\
from bench import *
from bench.library.print import PLA, H2D

block = cuboid(400, 100, 60)
require(check_fits(block, H2D))
show(part("block", block, Printed(PLA)))
"""

UNMEASURED = """\
from bench import *
from bench.library.print import PLA, H2D

block = cuboid(40, 40, 40)
require(check_wall(block, 1.2))
check_overhangs(block, Orient(), PLA)
check_clearance(block, move(block, Vector(60, 0, 0)), 0.3)
check_contact(block, move(block, Vector(40, 0, 0)))
show(part("block", block, Printed(PLA)))
"""

CLEAN = """\
from bench import *
from bench.library.print import PLA, H2D

block = cuboid(40, 40, 40)
check_fits(block, H2D)
show(part("block", block, Printed(PLA)))
"""

CHECKED_BEFORE_IT_WAS_A_PART = """\
from bench import *
from bench.library.print import PLA, H2D

blank = cuboid(400, 100, 60)
check_fits(blank, H2D)
block = move(blank, Vector(10, 0, 0))
show(part("block", block, Printed(PLA)))
"""

TWO_TOO_BIG = """\
from bench import *
from bench.library.print import PLA, H2D

a = cuboid(400, 100, 60)
b = cuboid(400, 100, 60)
check_fits(b, H2D)
show((part("a", a, Printed(PLA)), part("b", b, Printed(PLA))))
"""


STACK = """\
from bench import *
from bench.library.print import PLA

pla = Printed(PLA)
parts = tuple(
    Placed(part(f"block-{{n}}", move(cuboid(10, 10, 10), Vector(20 * n, 0, 0)), pla), XY)
    for n in range(4)
)
stack = assembly("stack", parts, posed=True)
found = check_clearance_within(stack, 0.3{extra})
print(f"{{len(found)}} findings")
show(stack)
"""
"""Four posed bodies - six pairs - with whatever ``exclude`` the case under test wants."""

FLAT_IN_THE_ASSEMBLY = """\
from bench import *

panel = part("panel", fill(rect(40, 30)), Stock(3.0, "ply"), Process.LASER)
stack = assembly("frame", (Placed(panel, XY),), posed=True)
check_clearance_within(stack, 0.3)
show(stack)
"""


def _ok(scene: Scene) -> OkScene:
    if not scene["ok"]:
        pytest.fail(f"{scene['error']['message']}\n{scene['error']['traceback']}")
    return scene


def _error(scene: Scene) -> ErrorView:
    if scene["ok"]:
        pytest.fail("that script was meant to fail")
    return scene["error"]


def test_a_failed_check_is_a_violation_and_the_run_still_produces_geometry() -> None:
    """The whole point of a record rather than a raise: the part is still there to look at,
    with its refs, and the violation sits beside it - exactly how ``nest`` already reports a
    part too big for the bed."""
    scene = _ok(run(TOO_BIG))
    assert len(scene["violations"]) == 1
    found = scene["violations"][0]
    assert found["check"] == "fits"
    assert found["severity"] == Severity.ERROR
    assert "400.0 mm against 350.0 mm" in found["message"]
    assert scene["parts"], "the geometry came back anyway"
    assert scene["refs"]


def test_a_violation_carries_the_line_of_the_script_that_asked_for_it() -> None:
    """Which is what lets the editor point at it, the way an error scene's line does."""
    assert _ok(run(TOO_BIG))["violations"][0]["line"] == 5


def test_a_check_that_found_nothing_records_nothing() -> None:
    """``violations`` is what went wrong, not a transcript of what was asked."""
    assert _ok(run(CLEAN))["violations"] == []


# ---- the assembly-shaped clearance ------------------------------------------------------


def test_check_clearance_within_walks_every_pair_of_the_assembly() -> None:
    """Four parts are six pairs, and the script gets one finding per pair without writing a
    loop over ``combinations`` or holding on to a single loose body."""
    scene = _ok(run(STACK.format(extra="")))
    assert [one["check"] for one in scene["violations"]] == ["clearance"] * 6
    assert scene["stdout"].strip() == "6 findings"


def test_an_excluded_pair_is_named_by_its_parts_labels_and_is_not_walked() -> None:
    """The seam task-34's ``check_contact`` needs: the pair it declares is the pair this
    leaves out, named by the labels the parts already carry rather than by which object is
    which. Either way round is the same pair - a script writes the one that reads better."""
    scene = _ok(
        run(STACK.format(extra=', exclude=(("block-0", "block-1"), ("block-3", "block-2"))'))
    )
    assert [one["check"] for one in scene["violations"]] == ["clearance"] * 4


def test_excluding_a_pair_the_assembly_does_not_hold_stops_the_run() -> None:
    """A typo here is a pair a maker believes was declared and nothing declared. Silently
    checking everything would hide it, so it is refused, naming the label that is not there."""
    error = _error(run(STACK.format(extra=', exclude=(("block-0", "blcok-1"),)')))
    assert "'blcok-1'" in error["message"]
    assert "not a part of stack" in error["message"]


def test_a_flat_part_in_the_assembly_stops_the_run_rather_than_being_passed_over() -> None:
    """``min_gap`` measures bodies. A panel cut from sheet has none, and dropping its pairs
    out of the walk would read as a pass for pairs nothing measured."""
    error = _error(run(FLAT_IN_THE_ASSEMBLY))
    assert "panel" in error["message"] and "cut from sheet" in error["message"]


# ---- the same question asked of a whole motion -------------------------------------------


MOTION = """\
from bench import *
from bench.library.print import PLA

pla = Printed(PLA)


def at(t):
    return assembly(
        "swing",
        (
            Placed(part("post", cuboid(10, 10, 10), pla), XY),
            Placed(part("arm", move(cuboid(10, 10, 10), Vector(12 - 3 * t, 0, 0)), pla), XY),
        ),
        posed=True,
    )


print(check_clearance_through(at, 0.5{extra}))
show(at(0.0))
"""
"""An arm that swings in toward a post, asked about across the whole travel with whatever
``samples`` and ``contacts`` the case under test wants."""


def test_a_motion_with_no_kernel_is_unchecked_once_rather_than_once_a_pose() -> None:
    """The browser before the modeller loads, and every run of these pure layers. Nothing was
    measured, so nothing is claimed, and the answer says so in the same words every other
    check uses - once, not twenty-one times over, because it is one question that went
    unanswered and not twenty-one."""
    scene = _ok(run(MOTION.format(extra=", samples=21")))
    assert [one["check"] for one in scene["violations"]] == ["clearance-through"]
    assert scene["violations"][0]["severity"] == Severity.UNCHECKED
    assert "the motion was not measured" in scene["stdout"]
    assert "sampled at" not in scene["stdout"]


def test_a_motion_is_sampled_at_both_ends_and_so_needs_two_poses() -> None:
    """One pose is a picture, not a motion. Asking for fewer than two stops the run rather
    than quietly measuring one end, which is the check the task exists to be better than."""
    error = _error(run(MOTION.format(extra=", samples=1")))
    assert "at least twice, not 1" in error["message"]


def test_a_motion_runs_from_a_lower_value_to_a_higher_one() -> None:
    """A range with no width samples the same pose over and over and calls it a travel."""
    error = _error(run(MOTION.format(extra=", over=(1.0, 1.0), samples=5")))
    assert "1.0 to 1.0 does not" in error["message"]


def test_a_contact_a_motion_declares_must_be_a_part_of_the_assembly() -> None:
    """The same refusal ``exclude`` gets, for the same reason: a mistyped label is a seat a
    maker believes was declared at every pose and nothing declared at any of them.

    It is refused here, with no kernel at all, because the first pose is built whether or not
    anything can measure it. A typo that only surfaced on a machine with a modeller would
    surface last in the browser, which is the one place a script is written."""
    error = _error(run(MOTION.format(extra=', samples=3, contacts=(("post", "aarm"),)')))
    assert "'aarm'" in error["message"]
    assert "not a part of swing" in error["message"]


def test_require_is_how_a_script_stops_on_a_violation() -> None:
    """The run fails on the line that required it, and comes back as an error scene like
    any other exception - no new failure mode, no half-built scene."""
    error = _error(run(STOPPED))
    assert error["line"] == 5
    assert "bigger than the build volume" in error["message"]


def test_a_check_with_no_kernel_is_unchecked_and_does_not_stop_a_require() -> None:
    """A browser has no modeller. Saying ``unchecked`` keeps the honest answer in the scene
    without refusing to draw the part - and ``require`` reads it as "not measured" rather
    than as "failed", or a script would stop dead in the one place it most needs to run."""
    scene = _ok(run(UNMEASURED))
    assert [one["check"] for one in scene["violations"]] == [
        "wall",
        "overhangs",
        "clearance",
        "contact",
    ]
    assert {one["severity"] for one in scene["violations"]} == {Severity.UNCHECKED}
    assert all("no kernel in this run" in one["message"] for one in scene["violations"])
    assert [one["line"] for one in scene["violations"]] == [5, 6, 7, 8]
    # And it points at nothing: nothing was measured, so there is no finding about the block
    # to mark on its row, however surely the block is the shape each check was handed.
    assert all(one["refs"] == [] for one in scene["violations"])


# ---- which part a finding is about ------------------------------------------------------


def test_a_finding_about_a_whole_body_names_the_part_that_body_became() -> None:
    """``check_fits`` measures a bare solid, before the part exists, and reports no face.
    What the scene says is the part's own ref - the same name its ref table holds - because
    the run kept the shape the check was handed and the part's shape *is* that object."""
    scene = _ok(run(TOO_BIG))
    assert scene["violations"][0]["refs"] == ["block"]
    assert "block" in scene["refs"]


def test_a_shape_that_never_became_a_part_is_not_guessed_at() -> None:
    """The blank was checked and then moved, and the moved copy is what became the part. The
    finding stays about the blank, which nothing in the scene names, rather than being
    pinned on the nearest part that looks like it."""
    scene = _ok(run(CHECKED_BEFORE_IT_WAS_A_PART))
    assert scene["violations"][0]["check"] == "fits"
    assert scene["violations"][0]["refs"] == []


def test_two_parts_drawn_to_the_same_numbers_keep_their_own_findings() -> None:
    """``a`` and ``b`` are equal by value and are two parts; only ``b`` was checked, and
    only ``b`` is named. Identity, not equality, is what ties a finding to its part."""
    scene = _ok(run(TWO_TOO_BIG))
    assert [one["refs"] for one in scene["violations"]] == [["b"]]


def test_the_checks_are_injected_per_run_and_are_not_names_of_the_package() -> None:
    """Like ``show``: built around this run's notebook and its kernel, so
    ``from bench import *`` cannot replace them and two runs never share one."""
    import bench

    for name in (
        "check_fits",
        "check_wall",
        "check_overhangs",
        "check_clearance",
        "check_clearance_within",
        "check_clearance_through",
        "check_contact",
        "require",
    ):
        assert not hasattr(bench, name), f"{name} is a per-run closure, not an export"
    scene = _ok(run(CLEAN))
    assert scene["violations"] == []
