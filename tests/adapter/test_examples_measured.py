"""Adapter: the five parts a maker builds, run through the shipped kernel and measured.

Every script under ``examples/`` is run the way the app runs it - :func:`bench.script.run`
inside Pyodide, with :class:`~bench.adapters.browser.JsKernel` driving Manifold's WASM, on
:mod:`tools.stack` - and then the mesh that comes back is measured against arithmetic done
here by hand. Nothing stands in for the kernel and nothing is read off the code under test: a
number below is either the standard's own, a figure out of the fastener or material tables,
or one of those plus :data:`~bench.topology.CHORD`, which is the sag a mesh's flat chords
leave where a drawing had a circle.

The measurements are taken **through the refs**. A triangle knows the name of the face it
lies on, so "the set screw's bore" is the triangles whose ref starts ``collar/set-screw``,
and its diameter is how far those corners reach across. That is the whole product in one
assertion: a name a script wrote, still attached to geometry a printer will make. A scene's
corners are placed on the stage, which moves a body and so changes no span.

One boot answers the whole module: :mod:`example_cases` runs every example and makes the
direct kernel calls inside the runtime, and every test reads what came back.
"""

import math
from pathlib import Path
from typing import Any

import pytest

from bench import (
    INSERT_M3,
    M4,
    ORIGIN,
    Fit,
    Point,
    Severity,
    Vector,
    bore,
)
from bench.library import ducts
from bench.library import gridfinity3d as g3
from bench.library.print import PLA, clearance
from bench.scene import MeshView, OkScene
from bench.topology import CHORD
from tools import stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)

_EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
_CASES = Path(__file__).with_name("example_cases.py")

NAMES = (
    "gridfinity_bin.py",
    "pipe_bracket.py",
    "enclosure_lid.py",
    "depth_stop_collar.py",
    "hinge.py",
    "fulcrum_hinge.py",
    "wall_vent.py",
    "jar_lid.py",
    "duct_offset.py",
    "dust_line.py",
)

PROGRAM = """\
import json

from pyodide.ffi import JsException

import example_cases
from bench.adapters.browser import JsKernel


def main(js, given):
    kernel = JsKernel(js, JsException)
    return json.dumps(example_cases.measured(kernel, json.loads(given)))
"""


@pytest.fixture(scope="module")
def measured() -> dict[str, Any]:
    """Every example run and every direct measurement taken, once, by the shipped kernel."""
    sources = {name: (_EXAMPLES / name).read_text() for name in NAMES}
    found: dict[str, Any] = stack.run(
        PROGRAM, sources, modules={"example_cases.py": _CASES.read_text()}
    )
    return found


# ---- reading the scenes that came back -------------------------------------------------


def _scene(measured: dict[str, Any], name: str) -> OkScene:
    """One example's scene, or the failure it reported."""
    return _ok(measured["scenes"][name], name)


def _ok(scene: Any, name: str) -> OkScene:
    if not scene["ok"]:
        error = scene["error"]
        pytest.fail(f"{name} line {error['line']}: {error['message']}\n{error['traceback']}")
    ok: OkScene = scene
    return ok


def _mesh(scene: OkScene, label: str) -> MeshView:
    for view in scene["parts"]:
        if view["label"] == label:
            mesh = view["mesh"]
            assert mesh is not None, f"{label} came back without a mesh"
            return mesh
    raise AssertionError(f"no part called {label}")


def _points(mesh: MeshView, under: str) -> tuple[Point, ...]:
    """Every corner of every triangle whose ref starts with ``under`` - one named feature's
    own geometry, pulled out of the mesh by the name the script gave it."""
    found: set[tuple[float, float, float]] = set()
    corners = mesh["positions"]
    for i, place in enumerate(mesh["ref_index"]):
        if place == 0 or not mesh["refs"][place - 1].startswith(under):
            continue
        for k in range(3):
            at = 9 * i + 3 * k
            found.add((corners[at], corners[at + 1], corners[at + 2]))
    assert found, f"nothing in the mesh answers to {under}"
    return tuple(Point(*one) for one in sorted(found))


def _span(points: tuple[Point, ...], along: Vector) -> float:
    """How far a set of corners reaches along one direction."""
    reach = tuple((p - ORIGIN) @ along for p in points)
    return max(reach) - min(reach)


def _facets(radius: float) -> int:
    """How many straight steps a circle of that radius is cut into - the package's one chord
    rule, restated here so the tolerances below are worked out rather than read off the code
    under test."""
    return math.ceil(math.tau / (2.0 * math.acos(1.0 - CHORD / radius)))


def _shortfall(diameter: float) -> float:
    """How far under its drawn diameter a printed-and-meshed circle can measure.

    A mesh kernel has no circles: a bore is a polygon *inscribed* in the circle it was drawn
    as, so a span across it is never over the diameter and is under it by at most the sag of
    one facet. That is a quantity, not a fudge factor, and it is what the assertions below
    allow rather than a round tolerance.
    """
    radius = diameter / 2.0
    return diameter * (1.0 - math.cos(math.pi / _facets(radius)))


_TINY = 1e-3
"""Float noise on a single-precision mesh vertex, in millimetres."""


def _measures(measured: float, drawn: float) -> bool:
    """Whether a span across a round feature measures what it was drawn as."""
    return drawn - _shortfall(drawn) - _TINY <= measured <= drawn + _TINY


def _errors(scene: OkScene) -> list[str]:
    return [one["check"] for one in scene["violations"] if one["severity"] == Severity.ERROR]


# ---- every example, with a modeller behind it ------------------------------------------


@pytest.mark.parametrize("name", NAMES)
def test_an_example_builds_a_body_and_breaks_no_check_it_asked_for(
    measured: dict[str, Any], name: str
) -> None:
    """The checks that answer ``unchecked`` without a kernel are answered here, on the real
    mesh: a clearance measured with ``min_gap``, an overhang measured off the triangles."""
    scene = _scene(measured, name)
    assert _errors(scene) == []
    assert scene["warnings"] == []
    for view in scene["parts"]:
        mesh = view["mesh"]
        assert mesh is not None and len(mesh["ref_index"]) >= 1
        assert f"{view['label']}.stl" in scene["files"]


# ---- (a) the bin -----------------------------------------------------------------------


def test_the_bins_footprint_is_the_standards_own_and_it_stacks(measured: dict[str, Any]) -> None:
    """83.5 by 41.5: two grids of 42 less the half millimetre that lets it drop into a
    baseplate. And it stacks, measured rather than asserted - a second bin one body height
    up clears this one's lip everywhere, because the lip is the base profile with the fit
    round it."""
    scene = _scene(measured, "gridfinity_bin.py")
    x0, y0, x1, y1 = scene["parts"][0]["bbox"]
    assert (x1 - x0, y1 - y0) == pytest.approx((83.5, 41.5))

    spec = g3.Spec(units_x=2, units_y=1, height=g3.Units(3), scoop=0.5, label_tab=g3.Tab.FULL)
    dims = g3.derive(spec)
    gap = measured["stack_gap"]
    # the flanks of the profile are at 45 degrees, so a fit of `stack` a side reads as
    # stack / sqrt(2) across them, less a chord's sag at each of the two rounded corners
    # that face each other.
    across = dims.stack / math.sqrt(2.0)
    assert across - 2 * CHORD <= gap <= across + CHORD
    assert gap > 0.0, "a bin that touches the bin below it is not stacking, it is jamming"


def test_the_bins_lip_is_the_base_profile_grown_by_the_fit(measured: dict[str, Any]) -> None:
    """Measured on the tree rather than the mesh, because this is the rule the module is
    built on: the void the bin above drops into is this bin's own foot with the fit round
    it, which is why the two were never two tables."""
    dims = g3.derive(g3.Spec())
    assert dims.total - dims.height == pytest.approx(g3.BASE_HEIGHT - dims.stack)
    assert measured["lip"]["triangles"] > 100
    assert measured["lip"]["named"]


# ---- (b) the bracket --------------------------------------------------------------------


def test_the_saddle_bore_is_the_pipe_plus_the_fit_the_table_says(measured: dict[str, Any]) -> None:
    """A 40 mm pipe drops through with ``clearance(Fit.CLEARANCE, PLA)`` a side, and the
    bore is cut that much wider again by half the printed-hole compensation, because a
    printed hole comes out under. Measured as the gap onto a 40 mm pipe standing in the
    bore."""
    mesh = _mesh(_scene(measured, "pipe_bracket.py"), "bracket")
    saddle = _points(mesh, "bracket/saddle")
    fit = clearance(Fit.CLEARANCE, PLA)
    drawn = 40.0 + 2 * fit + PLA.hole_compensation
    # the bore is a teardrop, so it is widest up the build direction; across the pipe's own
    # axis it is round, and that is the dimension a pipe cares about
    assert _measures(_span(saddle, Vector(0, 1, 0)), drawn)
    assert _span(saddle, Vector(0, 0, 1)) > _span(saddle, Vector(0, 1, 0)), "a teardrop, not a bore"


def test_the_bracket_has_two_m4_holes_and_a_gusset_that_is_no_fillet(
    measured: dict[str, Any],
) -> None:
    mesh = _mesh(_scene(measured, "pipe_bracket.py"), "bracket")
    for which in ("bracket/screw-1", "bracket/screw-2"):
        screw = _points(mesh, which)
        wide = bore(M4, Fit.CLEARANCE) + PLA.hole_compensation
        assert _measures(_span(screw, Vector(1, 0, 0)), wide)
        assert _measures(_span(screw, Vector(0, 1, 0)), wide)
    # the gusset is a hull, and a hull names nothing under it - so it is in the part and
    # none of its triangles answers to anything below its own label
    assert all(ref != "bracket/gusset/top" for ref in mesh["refs"])


# ---- (c) the lid -------------------------------------------------------------------------


def test_the_insert_bores_measure_the_inserts_own_hole(measured: dict[str, Any]) -> None:
    """4.2 mm, exactly: an insert bore is quoted as the hole to *print*, so it is the one
    hole on these five parts that is not compensated for the filament again."""
    mesh = _mesh(_scene(measured, "enclosure_lid.py"), "lid")
    for i in range(4):
        bore_points = _points(mesh, f"lid/insert-{i + 1}")
        assert _measures(_span(bore_points, Vector(1, 0, 0)), INSERT_M3.bore)
        assert _measures(_span(bore_points, Vector(0, 1, 0)), INSERT_M3.bore)
        assert INSERT_M3.bore == pytest.approx(4.2)


def test_the_lip_registers_in_the_box_at_a_snug_fit(measured: dict[str, Any]) -> None:
    """The check the script itself makes, measured here for the number: 0.10 mm a side in
    PLA, which is ``clearance(Fit.SNUG, PLA)`` and nothing anybody typed."""
    scene = _scene(measured, "enclosure_lid.py")
    assert _errors(scene) == []
    lip = _points(_mesh(scene, "lid"), "lid/lip")
    cavity = _points(_mesh(scene, "box"), "box/cavity")
    # both are square-cornered on purpose: flats measure the fit, arcs would measure the
    # chord rule as well
    gap = (_span(cavity, Vector(1, 0, 0)) - _span(lip, Vector(1, 0, 0))) / 2
    assert gap == pytest.approx(clearance(Fit.SNUG, PLA), abs=1e-3)


# ---- (d) the collar ----------------------------------------------------------------------


def test_the_set_screw_bore_is_radial_and_a_teardrop(measured: dict[str, Any]) -> None:
    """The part the review called blocked. The bore runs across the collar rather than up
    it - that is what ``plane_of(..., around=, along=)`` bought - and it is 3.6 mm across
    the way a screw measures it, with an apex above that a round hole does not have."""
    mesh = _mesh(_scene(measured, "depth_stop_collar.py"), "collar")
    screw = _points(mesh, "collar/set-screw")
    wide = bore(M4, Fit.PRESS) + PLA.hole_compensation
    assert _span(screw, Vector(1, 0, 0)) > 2 * _span(screw, Vector(0, 1, 0)), "it runs across"
    assert _measures(_span(screw, Vector(0, 1, 0)), wide)
    # a teardrop stands r * sqrt(2) above the centre and r below it, so it is taller than
    # it is wide by exactly that much
    tall = wide / 2 * (1.0 + math.sqrt(2.0))
    assert _span(screw, Vector(0, 0, 1)) == pytest.approx(tall, abs=_shortfall(wide))


def test_a_round_bore_in_the_same_collar_fails_the_overhang_check(
    measured: dict[str, Any],
) -> None:
    """The other half of the sentence, and the reason the teardrop is not decoration: the
    same script with ``Top.ROUND`` in it reports a ceiling that leans 90 degrees."""
    assert measured["round"]["edited"]
    scene = _ok(measured["round"]["scene"], "depth_stop_collar.py with a round bore")
    found = [one for one in scene["violations"] if one["check"] == "overhangs"]
    assert found and "90 degrees" in found[0]["message"]
    assert _errors(_scene(measured, "depth_stop_collar.py")) == []
    # The face it leans on is named the way the scene names it - under the part the collar
    # became, and among the refs the scene's own table holds - so the finding can be lined up
    # with the geometry it is about rather than read as a bare `set-screw/...`.
    named = found[0]["refs"]
    assert named, "the overhang finding names no face"
    assert all(one.startswith("collar/") for one in named), named
    assert set(named) <= set(scene["refs"]), set(named) - set(scene["refs"])


# ---- (e) the hinge ------------------------------------------------------------------------


def test_the_pin_turns_in_a_bore_a_slide_fit_wider_than_itself(measured: dict[str, Any]) -> None:
    """``min_gap`` between a 4 mm pin and the bore drawn for it: the fit the table says,
    plus half of what the filament takes back off a printed hole, because the bore is cut
    with that compensation and the pin is not."""
    gap = measured["pin_gap"]
    want = clearance(Fit.SLIDE, PLA) + PLA.hole_compensation / 2
    assert want - _shortfall(4.6) <= gap <= want + _TINY


def test_the_hinges_own_clearance_check_holds_on_the_real_mesh(measured: dict[str, Any]) -> None:
    """The script asks for the same thing on the parts it actually made - the pin against a
    leaf, and the two leaves against each other - and with a modeller behind it those are
    ``min_gap`` calls rather than ``unchecked``."""
    scene = _scene(measured, "hinge.py")
    assert _errors(scene) == []
    assert [one["check"] for one in scene["violations"]] == []
    bore_points = _points(_mesh(scene, "leaf-a"), "leaf-a/bore")
    drawn = 4.0 + 2 * clearance(Fit.SLIDE, PLA) + PLA.hole_compensation
    assert _measures(_span(bore_points, Vector(0, 1, 0)), drawn)
    pin = _mesh(scene, "pin")
    assert _span(_points(pin, "pin"), Vector(0, 1, 0)) <= 4.0 + 1e-3


def test_which_way_up_a_pin_prints_is_the_difference_between_a_pass_and_a_fail(
    measured: dict[str, Any],
) -> None:
    """Why the pin carries ``Orient(up=X)`` rather than taking the default. The same body,
    measured against two build directions: along its own axis nothing leans at all, and
    across it the whole underside of the cylinder does."""
    assert measured["pin_along"] is None
    assert measured["pin_flat"] == Severity.WARNING
    scene = _scene(measured, "hinge.py")
    assert [view["stock"]["material"] for view in scene["parts"]] == [PLA.name] * 3


# ---- (f) the fulcrum hinge -----------------------------------------------------------------


def _stdout(scene: Any) -> str:
    text: str = _ok(scene, "fulcrum_hinge.py")["stdout"]
    return text


def test_the_fulcrum_stack_clears_itself_at_every_pose_of_the_sequence(
    measured: dict[str, Any],
) -> None:
    """Twelve bodies posed by the patent's order and every pair of them measured with
    ``min_gap`` at the fit: closed, at FIG. 9's positions two and three, open, and at a
    handover with the widest travel the panel offers. A pin in a pocket, a pin clearing the
    ring it must pass, a lug in its cutout, a shaft in its D - all of it is one answer here,
    that no check the script asked for came back at all. What this does not measure is
    whether a pin moves; the script's docstring says so and this test does not pretend
    otherwise."""
    poses = measured["poses"]
    assert len(poses) == 5
    for scene in (_ok(one, "fulcrum_hinge.py") for one in poses):
        assert [one["check"] for one in scene["violations"]] == []
    closed = [line for line in _stdout(poses[0]).splitlines() if "axes curled" in line]
    opened = [line for line in _stdout(poses[3]).splitlines() if "axes curled" in line]
    assert closed and "45, 45, 45, 45" in closed[0] and "fore, fore, fore" in closed[0]
    assert opened and "0, 0, 0, 0" in opened[0] and "aft, aft, aft" in opened[0]


def test_a_clearance_within_a_posed_assembly_says_which_two_parts_failed(
    measured: dict[str, Any],
) -> None:
    """What reading an assembly buys over a loop over loose bodies, and the one thing the
    fulcrum stack cannot show because it passes: a real failure, measured by a real modeller,
    naming both parts by the labels they already carried. Without a kernel this check answers
    ``unchecked`` and names nothing, so it can only be asked here."""
    scene = _ok(measured["colliding"], "colliding")
    assert [one["check"] for one in scene["violations"]] == ["clearance"]
    found = scene["violations"][0]
    assert found["severity"] == Severity.ERROR
    assert found["refs"] == ["left", "right"]


def test_a_pair_that_fouls_between_two_hand_picked_poses_is_found(
    measured: dict[str, Any],
) -> None:
    """Why a motion is not a handful of poses somebody picked. The arm swings out and back,
    so a maker checking the two ends - and this script checks them, with the same
    ``check_clearance_within`` the fulcrum stack uses - is told both are clear. The pose
    where it fouls the post is halfway between them, and sampling the range finds it and says
    where it is."""
    scene = _ok(measured["through"], "through")
    assert "0 findings at the two ends" in scene["stdout"]
    assert [one["check"] for one in scene["violations"]] == ["clearance"]
    message = scene["violations"][0]["message"]
    assert message.startswith("post and arm at 0.5000")
    assert "sample 3 of 5" in message


def test_a_sampled_motion_says_it_sampled_and_at_what_spacing(
    measured: dict[str, Any],
) -> None:
    """Criterion three of the task, and the reason the answer is a record and not a tuple of
    violations: "clear at five poses, one every 0.25" is a weaker claim than "clear
    throughout", and the weaker one is the only one that was earned. The sentence also says
    what it is not about, where a maker reads it rather than only in a docstring."""
    said = _ok(measured["through"], "through")["stdout"]
    assert "sampled at 5 poses from 0.000 to 1.000, one every 0.2500" in said
    assert "Sampled, not swept" in said
    assert "force, friction or binding" in said
    assert "throughout" not in said


def test_a_declared_contact_holds_at_every_pose_of_a_motion(
    measured: dict[str, Any],
) -> None:
    """Criterion four. A head seated on a ring turns with it, so its faces are coincident at
    every pose and ``min_gap`` reads zero at every pose: declared, that is measured as a
    contact each time and holds; undeclared, it is a failed clearance - which is what would
    drown every real finding in a moving assembly. Both answers come from the same geometry
    and the same four poses, so the difference is the declaration and nothing else."""
    scene = _ok(measured["seated"], "seated")
    declared, undeclared = scene["stdout"].splitlines()[:2]
    assert "every pair stayed 0.30 mm apart at every one of them" in declared
    assert "1 pair(s) came closer than 0.30 mm" in undeclared
    assert [one["check"] for one in scene["violations"]] == ["clearance"]
    assert scene["violations"][0]["message"].startswith("ring and head at 0.0000")


def test_the_fulcrum_stack_clears_itself_across_the_whole_travel_not_only_at_poses(
    measured: dict[str, Any],
) -> None:
    """What task-27's eleven hand-picked poses could not say. The stack is built again at
    each of twenty-one deployments from closed to open and all sixty-six pairs are measured
    at every one of them, with the four seats declared at every one of them - and it comes
    back clear. It is still sampling: 0.05 apart, and the script says so rather than claiming
    the travel between two samples. Nothing here is about force, friction or binding."""
    said = _stdout(measured["scenes"]["fulcrum_hinge.py"])
    assert "sampled at 21 poses from 0.000 to 1.000, one every 0.0500" in said
    assert "every pair stayed 0.20 mm apart at every one of them" in said
    assert [one["check"] for one in _scene(measured, "fulcrum_hinge.py")["violations"]] == []


def test_the_fulcrum_links_are_one_part_three_times_and_the_shaft_keys_in_a_d(
    measured: dict[str, Any],
) -> None:
    """The three links are the same body posed three ways, so their meshes are the same
    size; and the keyed passageway is the round one cut flat, so across the flat it is
    narrower than the round one is anywhere - which is the whole of the drive train."""
    scene = _scene(measured, "fulcrum_hinge.py")
    sizes = {len(_mesh(scene, f"link-{n}")["ref_index"]) for n in (1, 2, 3)}
    assert len(sizes) == 1
    link = _mesh(scene, "link-1")
    drawn = 6.0 + 2 * clearance(Fit.SLIDE, PLA) + PLA.hole_compensation
    assert _measures(_span(_points(link, "link-1/bore"), Vector(1, 0, 0)), drawn)
    # The link in the closed stack is turned 45 degrees, so the flat, drawn under the axis,
    # lies along a diagonal; across that diagonal the D reaches a radius one way and the
    # flat the other: a third of the shaft's radius less, plus the fit and the compensation.
    keyed = _points(link, "link-1/keyed-bore")
    diagonal = Vector(-1.0, 0.0, 1.0) / math.sqrt(2.0)
    flat = 2.0 + clearance(Fit.SLIDE, PLA) + PLA.hole_compensation / 2
    want = drawn / 2 + flat
    assert want - _shortfall(drawn) - _TINY <= _span(keyed, diagonal) <= want + _TINY
    assert _span(keyed, Vector(1.0, 0.0, 1.0) / math.sqrt(2.0)) > _span(keyed, diagonal)


# ---- (g) the wall vent -----------------------------------------------------------------


def test_the_vents_attachment_touches_the_flange_and_clears_the_collar_at_a_slide(
    measured: dict[str, Any],
) -> None:
    """The mate's own sentence says the back face touches the flange, which is what it was
    asked; the groove, checked where the mate put it, clears the collar by at least the slide
    the table asks - by the concave allowance more, because its corners are internal arcs
    and it is drawn at ``clearance(..., concave=True)`` - and no more than that."""
    said = _scene(measured, "wall_vent.py")["stdout"].splitlines()
    assert said[0] == "attachment/base/bottom on frame/flange/top: touch, asked contact"
    groove = said[1]
    assert groove.startswith("attachment/groove round frame/collar: clear by ")
    assert groove.endswith(", asked 0.200 (slide)")
    measured_gap = float(groove.split("clear by ")[1].split(" mm")[0])
    slide = clearance(Fit.SLIDE, PLA)
    assert slide <= measured_gap <= clearance(Fit.SLIDE, PLA, concave=True) + _TINY


# ---- (h) task-61: a picked face's frame sits under the face it names -------------------

_FRAME_TOL = 1e-3
"""Millimetres. Looser than :data:`bench.geometry.TOL`, which is for arithmetic done in
Python; a real kernel's own float noise is what this has to clear."""


def _framed_points(mesh: MeshView, ref: str) -> tuple[Point, ...]:
    """Every corner of every triangle answering to exactly ``ref`` - not a prefix match, the
    way :func:`_points` is, because a frame names one face and nothing under it."""
    found: set[tuple[float, float, float]] = set()
    corners = mesh["positions"]
    for i, place in enumerate(mesh["ref_index"]):
        if place == 0 or mesh["refs"][place - 1] != ref:
            continue
        for k in range(3):
            at = 9 * i + 3 * k
            found.add((corners[at], corners[at + 1], corners[at + 2]))
    return tuple(Point(*one) for one in sorted(found))


def test_every_face_frame_lies_on_its_own_triangles(measured: dict[str, Any]) -> None:
    """The frame :func:`bench.views._frames_view` sends for a ref is exactly what
    :func:`~bench.solids.plane_of` answers for it, moved by the same stage offset the mesh's
    own triangles were - so every corner of every triangle a frame names has to satisfy the
    plane it names: ``|normal . (corner - origin)| < tol``.

    Checked across every example with a printed part, not one shape picked to make it easy,
    and relationally against the frame's own numbers rather than a hard-coded coordinate - a
    posed assembly (the vent) and a laid-out one (everything else) put a body at a different
    offset, and this has to hold either way. Normal *direction* is not asserted - a cut
    face's own is task-65's open question - only that the plane itself is right.
    """
    checked = 0
    for name in NAMES:
        scene = _scene(measured, name)
        for view in scene["parts"]:
            mesh = view["mesh"]
            if mesh is None:
                continue
            for ref, frame in view["frames"].items():
                origin = Point(*frame["origin"])
                normal = Vector(*frame["normal"])
                for corner in _framed_points(mesh, ref):
                    off = abs((corner - origin) @ normal)
                    assert off < _FRAME_TOL, (
                        f"{name}: {ref}'s frame is {off:.4f} mm off its own face"
                    )
                    checked += 1
    assert checked > 0, "no example gave a face frame to check at all"


# ---- (i) the dust line -----------------------------------------------------------------


def test_the_dust_lines_fittings_all_print_standing_and_the_coupler_slides_on_at_a_slide(
    measured: dict[str, Any],
) -> None:
    """Every fitting's overhangs and walls, checked standing the way it prints, come back with
    nothing - a warning included, which the test above does not count. The coupler, checked
    seated on the wye's outlet, stands off it by the slide and no more than a chord past it,
    and slid on from clear above it keeps that at every pose."""
    scene = _scene(measured, "dust_line.py")
    assert [one["check"] for one in scene["violations"]] == []
    said = scene["stdout"].splitlines()
    seated = said[0]
    assert seated.startswith("coupler round the wye's outlet: clear by ")
    assert seated.endswith(", asked 0.200 (slide)")
    gap = float(seated.split("clear by ")[1].split(" mm")[0])
    assert clearance(Fit.SLIDE, PLA) <= gap <= clearance(Fit.SLIDE, PLA, concave=True) + _TINY
    assert "sampled at 5 poses" in said[1]
    assert "every pair stayed" in said[1]


def test_the_dust_lines_coupler_is_bored_to_the_ports_socket(measured: dict[str, Any]) -> None:
    """A 4 inch port is sold by its outside, so the socket that takes it is the port and the
    slide both sides - measured across the coupler's bore, found by its name."""
    mesh = _mesh(_scene(measured, "dust_line.py"), "coupler")
    bore = _points(mesh, "coupler/inside/side-inlet")
    wide = ducts.socket_diameter(ducts.PORT_4)
    assert wide == pytest.approx(101.6 + 2 * clearance(Fit.SLIDE, PLA, concave=True))
    assert _measures(_span(bore, Vector(1, 0, 0)), wide)
    assert _measures(_span(bore, Vector(0, 1, 0)), wide)
