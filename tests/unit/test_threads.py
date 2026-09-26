"""Unit: :mod:`bench.threads`, and the twist and taper an extrusion takes that it is built on.

What a thread is before anything builds it: the faces it will have and what they are called,
where its top frame points, how far out it reaches, the number its internal half is opened
by, and what it refuses and warns about. Beside it, the two halves of a twisted extrusion
that need no modeller - the recipe's own names and bounds (:mod:`bench.topology`) and which
named face a hand-written triangle of a twisted mesh lies on (:mod:`bench.meshing`). Whether
a built bolt goes into a built nut is ``tests/adapter/test_threads_measured.py``'s question.
"""

import logging
import math
from array import array

import pytest

from bench import (
    CHORD,
    ROUND_DEPTH,
    Fit,
    Point,
    Thread,
    Vector,
    axis_of,
    bounds,
    extrude,
    faces_of,
    fill,
    plane_of,
    rect,
    thread,
    thread_opening,
)
from bench.library.print import PLA
from bench.meshing import divisions, extruded_faces
from bench.telemetry import CHECK, FIELDS
from bench.threads import FINEST, FLANK, SMALLEST, drawn_clear, too_small
from bench.topology import Extrude, chord_step, profile_rings

pytestmark = pytest.mark.unit

_SQUARE = fill(rect(4, 4, Point(-2, -2)))
"""A square centred on its own axis, so a twist turns it about its middle."""


# ---- a twisted extrusion, before anything builds it -----------------------------------


def test_a_plain_extrusion_is_the_record_it_always_was() -> None:
    """Twist and scale are additive: left alone they are the plain prism, equal as a value to
    an extrusion written before either existed, with the same faces."""
    plain = extrude(_SQUARE, 5.0)
    assert plain.node == Extrude(_SQUARE, 5.0)
    assert faces_of(plain) == faces_of(extrude(_SQUARE, 5.0, twist=0.0, scale=1.0))


def test_a_twisted_extrusion_is_named_by_the_same_rule_as_a_plain_one() -> None:
    """One side per profile edge however many turns it makes - the names do not change."""
    plain = tuple(f.label for f in faces_of(extrude(_SQUARE, 5.0)))
    twisted = tuple(f.label for f in faces_of(extrude(_SQUARE, 5.0, twist=7 * math.pi)))
    assert twisted == plain == ("top", "bottom", "side-0", "side-1", "side-2", "side-3")


@pytest.mark.parametrize(("twist", "scale"), [(math.pi, 1.0), (0.0, 0.5)])
def test_a_twisted_or_tapered_side_has_no_plane_and_no_axis(twist: float, scale: float) -> None:
    body = extrude(_SQUARE, 5.0, twist=twist, scale=scale)
    sides = [f for f in faces_of(body) if f.label.startswith("side-")]
    assert all(f.plane is None and f.curved is None for f in sides)
    with pytest.raises(ValueError, match="no single plane"):
        plane_of(body, "side-0")
    with pytest.raises(ValueError, match="only a round face has an axis"):
        axis_of(body, "side-0")


def test_a_round_side_twisted_is_no_longer_round() -> None:
    """A circle's side is a :class:`~bench.topology.Curved` until it twists; an offset
    circle twisted is a helix, and has no one axis and radius to offer."""
    thread_side = faces_of(thread(Thread.EXTERNAL, 12.0, 2.0, 10.0))[2]
    assert (thread_side.label, thread_side.plane, thread_side.curved) == ("side-0", None, None)


@pytest.mark.parametrize(
    ("distance", "x_dir"), [(10.0, Vector(0, 1, 0)), (-10.0, Vector(0, -1, 0))]
)
def test_a_twisted_top_is_the_profile_frame_turned_right_handed_about_the_sweep(
    distance: float, x_dir: Vector
) -> None:
    """A quarter turn about +Z carries X to +Y; about -Z, the way a negative sweep runs, to -Y."""
    top = plane_of(extrude(_SQUARE, distance, twist=math.pi / 2), "top")
    assert abs(top.x_dir - x_dir) < 1e-12
    assert top.origin.z == pytest.approx(distance)


def test_a_twisted_extrusion_is_bounded_by_its_furthest_reach_turned_every_way() -> None:
    """A square's corners turned an eighth stick out past the square itself, so a twisted
    body's bound is its reach from the axis, every way round."""
    reach = math.hypot(2, 2)
    box = bounds(extrude(_SQUARE, 6.0, twist=math.pi / 4))
    assert box == pytest.approx((-reach, -reach, 0.0, reach, reach, 6.0))


def test_a_tapered_extrusion_is_bounded_by_its_larger_end() -> None:
    grown = bounds(extrude(_SQUARE, 6.0, scale=1.5))
    shrunk = bounds(extrude(_SQUARE, 6.0, scale=0.5))
    assert grown == pytest.approx((-3.0, -3.0, 0.0, 3.0, 3.0, 6.0))
    assert shrunk == pytest.approx((-2.0, -2.0, 0.0, 2.0, 2.0, 6.0))


@pytest.mark.parametrize("scale", [0.0, -1.0])
def test_an_extrusion_refuses_a_far_end_of_no_size(scale: float) -> None:
    with pytest.raises(ValueError, match="positive scale"):
        extrude(_SQUARE, 5.0, scale=scale)


# ---- a twisted mesh, named ------------------------------------------------------------


def _twisted() -> Extrude:
    node = extrude(_SQUARE, 10.0, twist=math.pi / 2).node
    assert isinstance(node, Extrude)
    return node


def _turned(u: float, v: float, angle: float, z: float) -> tuple[float, float, float]:
    return (u * math.cos(angle) - v * math.sin(angle), u * math.sin(angle) + v * math.cos(angle), z)


def _faces(twist: float, *corners: tuple[float, float, float], distance: float = 10.0) -> int:
    vertices = array("f", (value for corner in corners for value in corner))
    rings = profile_rings(_twisted())
    (face,) = extruded_faces(vertices, 3, array("I", (0, 1, 2)), distance, rings, twist, 1.0)
    return face


def test_a_twisted_cap_is_named_by_where_it_is() -> None:
    assert _faces(math.pi / 2, (0, 0, 10), (1, 0, 10), (0, 1, 10)) == 0
    assert _faces(math.pi / 2, (0, 0, 0), (0, 1, 0), (1, 0, 0)) == 1


def test_a_steep_twisted_side_is_still_a_side() -> None:
    """A thread's flank can face further up than any side a normal test would allow. This
    triangle's normal is more than half up, and it is still the south side it was swept
    from: position decides a twisted cap, not the normal."""
    lean = math.tau * 0.05
    corners = ((-2.0, -2.0, 0.0), (2.0, -2.0, 0.0), _turned(2.0, -2.0, lean, 0.5))
    (a, b, c) = corners
    u = [b[k] - a[k] for k in range(3)]
    v = [c[k] - a[k] for k in range(3)]
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    assert n[2] > 0.5 * math.hypot(*n)
    assert _faces(math.tau, *corners) == 2


def test_a_twisted_side_is_the_edge_it_was_swept_from_turned_back() -> None:
    """Half way up a quarter turn, the east edge has turned an eighth: turned back, a
    triangle there lies on the east edge and nowhere else."""
    half = math.pi / 4
    corners = (
        _turned(2.0, -2.0, half, 5.0),
        _turned(2.0, 2.0, half, 5.0),
        _turned(2.0, 2.0, math.pi / 2, 10.0 - 1.0e-2),
    )
    assert _faces(math.pi / 2, *corners) == 3


def test_a_twist_needs_copies_of_its_section_by_the_chord_rule_and_a_prism_none() -> None:
    """The corner furthest out runs a helix, and the turn between copies keeps its straight
    run within a chord of it - at the larger end's reach, for a taper that grows."""
    rings = profile_rings(_twisted())
    reach = math.hypot(2, 2)
    assert divisions(rings, 0.0, 0.5) == 0
    assert divisions(rings, math.pi, 1.0) == math.ceil(math.pi / chord_step(reach)) - 1
    assert divisions(rings, -math.pi, 2.0) == math.ceil(math.pi / chord_step(2 * reach)) - 1


# ---- a thread -------------------------------------------------------------------------


def test_a_thread_is_three_faces_and_its_flank_is_one() -> None:
    bolt = thread(Thread.EXTERNAL, 12.0, 2.0, 20.0, label="bolt")
    assert tuple(f.label for f in faces_of(bolt)) == ("top", "bottom", "side-0")


def test_an_external_thread_reaches_its_nominal_diameter_and_no_further() -> None:
    """The offset and the radius together are the crest: a twisted body is bounded by its
    reach, so an M12's bound is 12 across."""
    box = bounds(thread(Thread.EXTERNAL, 12.0, 2.0, 20.0, at=Point(0, 0, 5)))
    assert box == pytest.approx((-6.0, -6.0, 5.0, 6.0, 6.0, 25.0))


def test_an_internal_thread_is_opened_by_the_clearance_and_grown_by_the_compensation() -> None:
    """The nut's section is the bolt's plus :func:`thread_opening` of the per-side gap PLA
    asks at a slide, plus half PLA's ``hole_compensation`` on its radius as any printed hole
    grows by - drawn wider, never the bolt drawn smaller, and the compensation added once."""
    depth = 2.0 * ROUND_DEPTH
    wide = thread_opening(PLA.clearances[Fit.SLIDE], 2.0, depth) + PLA.hole_compensation / 2
    box = bounds(thread(Thread.INTERNAL, 12.0, 2.0, 20.0, material=PLA, fit=Fit.SLIDE))
    assert box.x1 == pytest.approx(6.0 + wide)
    bolt = bounds(thread(Thread.EXTERNAL, 12.0, 2.0, 20.0))
    assert bolt.x1 == pytest.approx(6.0)


def test_the_opening_stands_the_gap_square_across_the_steepest_flank() -> None:
    """The steepest flank of a round thread leans ``atan(pi * depth / pitch)`` off the axis,
    and two sections ``g`` apart in their own plane stand ``g`` times its cosine apart across
    it - so the section is opened by the gap over that cosine, and a chord's sag on top."""
    gap, pitch, depth = 0.2, 2.0, 0.5
    lean = math.atan(math.pi * depth / pitch)
    assert (thread_opening(gap, pitch, depth) - CHORD) * math.cos(lean) == pytest.approx(gap)


def test_the_default_depth_leans_its_steepest_flank_at_the_default_angle() -> None:
    assert math.atan(math.pi * ROUND_DEPTH) == pytest.approx(FLANK)
    assert math.degrees(FLANK) == pytest.approx(40.0)


def test_a_thread_turns_right_handed_a_whole_turn_per_pitch() -> None:
    """A pitch and a quarter up, the top's frame has turned a quarter counter-clockwise."""
    top = plane_of(thread(Thread.EXTERNAL, 12.0, 2.0, 2.5), "top")
    assert abs(top.x_dir - Vector(0, 1, 0)) < 1e-9


@pytest.mark.parametrize(
    ("args", "said"),
    [
        ((12.0, 0.0, 10.0), "positive diameter, pitch, length and depth"),
        ((12.0, 2.0, -1.0), "positive diameter, pitch, length and depth"),
        ((4.0, 2.0, 10.0, 2.0), "no core left"),
    ],
)
def test_a_thread_refuses_sizes_that_sweep_no_rod(args: tuple[float, ...], said: str) -> None:
    diameter, pitch, length, *rest = args
    with pytest.raises(ValueError, match=said):
        thread(Thread.EXTERNAL, diameter, pitch, length, depth=rest[0] if rest else None)


def test_an_internal_thread_needs_a_material_to_read_its_clearance_from() -> None:
    with pytest.raises(ValueError, match="fit table"):
        thread(Thread.INTERNAL, 12.0, 2.0, 10.0)


def test_a_small_thread_is_warned_about_as_an_unmeasured_default() -> None:
    assert too_small(40.0, 0.8) == ()
    (diameter,) = too_small(3.0, 0.5)
    assert f"{SMALLEST:g} mm" in diameter and "unmeasured default" in diameter
    (depth,) = too_small(8.0, 0.3)
    assert f"{FINEST:g} mm" in depth and "unmeasured default" in depth
    assert len(too_small(2.0, 0.2)) == 2


def test_a_small_thread_is_built_and_logged_never_refused(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="bench.threads"):
        bolt = thread(Thread.EXTERNAL, 3.0, 0.5, 6.0)
    assert faces_of(bolt)
    assert any("unmeasured default" in r.getMessage() for r in caplog.records)
    assert all(getattr(r, FIELDS)[CHECK] == "thread" for r in caplog.records), (
        "each warning names the check a run records it under"
    )


def test_an_internal_thread_drawn_clear_of_its_bolt_is_warned_about() -> None:
    """An M8 x 1.25 in PLA at a slide is opened 0.41 mm on a thread 0.33 deep: the model's
    nut clears its bolt, and the sentence says so, naming the thread, the material and the
    fit. An M12 x 2 is opened less than it is deep, and engages."""
    (said,) = drawn_clear(8.0, 1.25, 1.25 * ROUND_DEPTH, PLA, Fit.SLIDE)
    assert "8 x 1.25 internal thread in PLA at SLIDE is drawn clear of its bolt" in said
    assert "opened 0.41 mm on a thread 0.33 mm deep" in said
    assert "coarser pitch or a deeper thread" in said
    assert drawn_clear(12.0, 2.0, 2.0 * ROUND_DEPTH, PLA, Fit.SLIDE) == ()


def test_the_pitch_a_thread_stops_engaging_in_the_model_below() -> None:
    """In PLA at a slide, at the default depth, the drawn thread engages from a pitch of
    about 1.54 mm up - found here by bisection on :func:`drawn_clear` itself."""
    low, high = 0.5, 3.0
    for _ in range(40):
        pitch = (low + high) / 2
        if drawn_clear(20.0, pitch, pitch * ROUND_DEPTH, PLA, Fit.SLIDE):
            low = pitch
        else:
            high = pitch
    assert high == pytest.approx(1.54, abs=0.01)


def test_an_external_thread_is_never_warned_as_drawn_clear(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only the cavity is opened, so only the nut can be drawn clear of its bolt."""
    with caplog.at_level(logging.WARNING, logger="bench.threads"):
        thread(Thread.EXTERNAL, 8.0, 1.25, 10.0, depth=0.5, material=PLA)
        thread(Thread.INTERNAL, 8.0, 1.25, 10.0, depth=0.5, material=PLA)
    assert not caplog.records, "0.5 deep engages in the model, and 8 mm is no small thread"
    with caplog.at_level(logging.WARNING, logger="bench.threads"):
        thread(Thread.INTERNAL, 8.0, 1.25, 10.0, material=PLA)
    assert any("drawn clear" in r.getMessage() for r in caplog.records)
