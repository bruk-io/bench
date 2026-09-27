"""Functional: a body hollowed by making it again, through the public vocabulary.

Nothing is built here. What the tree alone can answer is asserted: what every inner face is
called, where the named inner planes stand and which way they face, where the cavity's
recipe reaches, and what :func:`bench.shell` refuses. What the modeller makes of it - the
volume, the openings, the wall it measures - is ``tests/adapter/test_shell_measured.py``'s.
"""

import math

import pytest

from bench import (
    ORIGIN,
    XY,
    Axis,
    Bend,
    Plane,
    Point,
    Printed,
    Solid,
    Straight,
    Thread,
    Vector,
    X,
    Y,
    Z,
    bounds,
    circle,
    cuboid,
    cylinder,
    extrude,
    fill,
    hull,
    loft,
    move,
    near,
    part,
    path,
    plane_of,
    raised,
    rect,
    refs,
    revolve,
    shell,
    sweep,
    thread,
    union,
)
from bench.library.print import PLA
from bench.shell import PAST
from bench.topology import Difference, Moved, Revolve, Swept, curve_start

pytestmark = pytest.mark.functional

UP = Vector(0.0, 0.0, 1.0)


def _cavity(shelled: Solid) -> Solid:
    """The body a shell took out: the tool of the cut it is."""
    assert isinstance(shelled.node, Difference)
    return shelled.node.tool


def _at(got: Plane, origin: Point, normal: Vector) -> None:
    assert near(got.origin, origin), got
    assert near(got.normal, normal), got


# ---- an extrusion ------------------------------------------------------------------------


def test_a_box_shelled_open_at_the_top_names_its_inner_floor_and_walls_after_the_outer_ones() -> (
    None
):
    """The cavity is the box's own recipe run again, so its faces carry the box's names under
    ``inside``: the floor is ``inside/bottom`` and each inner wall the outer wall it follows."""
    box = part("box", shell(cuboid(40, 30, 20), 2.0, open=("top",)), Printed(PLA))
    named = {str(r) for r in refs(box)}
    for face in ("bottom", "side-front", "side-right", "side-back", "side-left"):
        assert f"inside/{face}" in named, face
    assert "top" in named


def test_a_boxs_inner_floor_and_walls_face_into_the_hollow() -> None:
    """Every face a cut leaves points out of the material that is left, so a part mated onto
    the inner floor sits in the box: the floor faces up at the wall's height, and the front
    wall's inside faces back into the box from a wall's thickness in."""
    box = shell(cuboid(40, 30, 20), 2.0, open=("top",))
    _at(plane_of(box, "inside/bottom"), Point(0.0, 0.0, 2.0), UP)
    front = plane_of(box, "inside/side-front")
    assert near(front.normal, Vector(0.0, 1.0, 0.0)), front
    assert front.origin.y == pytest.approx(2.0)


def test_a_boxs_cavity_runs_from_the_floor_through_the_open_top() -> None:
    """Inset by the wall across, standing a wall's height off the bottom, and running on past
    the open top so the opening is a cut and not a face lying on the rim."""
    cavity = bounds(_cavity(shell(cuboid(40, 30, 20), 2.0, open=("top",))))
    assert (cavity.x0, cavity.y0, cavity.z0) == pytest.approx((2.0, 2.0, 2.0))
    assert (cavity.x1, cavity.y1) == pytest.approx((38.0, 28.0))
    assert cavity.z1 > 20.0


def test_a_closed_box_keeps_a_floor_and_a_roof() -> None:
    cavity = bounds(_cavity(shell(cuboid(40, 30, 20), 2.0)))
    assert (cavity.z0, cavity.z1) == pytest.approx((2.0, 18.0))


def test_a_tube_open_at_both_ends_is_cut_through() -> None:
    cavity = bounds(_cavity(shell(cylinder(10.0, 20.0), 2.0, open=("top", "bottom"))))
    assert cavity.z0 < 0.0
    assert cavity.z1 > 20.0
    assert cavity.x1 - cavity.x0 == pytest.approx(16.0)


def test_an_extrusion_swept_downward_keeps_its_floor_on_the_side_it_hangs_from() -> None:
    """A negative distance sweeps the other way, and so does the cavity: the floor stands a
    wall below the profile's plane and faces down into the hollow."""
    hanging = shell(extrude(fill(rect(20, 20)), -10.0), 1.0, open=("top",))
    _at(plane_of(hanging, "inside/bottom"), Point(0.0, 0.0, -1.0), -UP)
    cavity = bounds(_cavity(hanging))
    assert cavity.z1 == pytest.approx(-1.0)
    assert cavity.z0 < -10.0


def test_a_moved_body_is_shelled_where_it_stands() -> None:
    box = shell(move(cuboid(20, 20, 10), Vector(5.0, 0.0, 3.0)), 1.0, open=("top",))
    _at(plane_of(box, "inside/bottom"), Point(5.0, 0.0, 4.0), UP)


def test_the_cavity_can_be_named_and_the_shell_labelled() -> None:
    shelled = shell(cuboid(20, 20, 10), 1.0, open=("top",), inside="bore", label="cup")
    assert shelled.label == "cup"
    assert "cup/bore/bottom" in {str(r) for r in refs(part("x", shelled, Printed(PLA)))}


# ---- a revolve ---------------------------------------------------------------------------


def _cup() -> Solid:
    """A cup turned about Y: a 20 by 30 section standing on the axis, its edges the bottom
    (``side-0``), the outside (``side-1``), the rim (``side-2``) and the axis (``side-3``)."""
    return revolve(fill(rect(20, 30)), Axis(ORIGIN, Y))


def test_a_turned_cup_opens_at_its_rim_and_keeps_its_axis_where_it_was() -> None:
    """Every edge moves in by the wall except the one on the axis, which stays on it - a
    uniform inset would leave a pillar up the middle - and the rim, which moves out past
    itself so the cup is open there."""
    cavity = _cavity(shell(_cup(), 2.0, open=("side-2",)))
    assert isinstance(cavity.node, Revolve)
    on = cavity.node.profile.plane
    corners = [
        value
        for p in (curve_start(e.curve) for e in cavity.node.profile.outer.edges)
        for value in ((p - on.origin) @ on.x_dir, (p - on.origin) @ on.y_dir)
    ]
    assert corners == pytest.approx([0.0, 2.0, 18.0, 2.0, 18.0, 31.0, 0.0, 31.0])


def test_a_turned_cups_inner_faces_are_named_after_the_outer_ones() -> None:
    cup = part("cup", shell(_cup(), 2.0, open=("side-2",)), Printed(PLA))
    named = {str(r) for r in refs(cup)}
    assert {"inside/side-0", "inside/side-1", "inside/side-2"} <= named


def test_a_half_turn_is_shelled_open_at_its_start_and_end() -> None:
    """A partial turn's cavity turns a little further than the body at both ends, so both
    ends are cut through."""
    ring = revolve(fill(rect(10, 10, Point(10, 0))), Axis(ORIGIN, Y), angle=math.pi)
    shelled = shell(ring, 2.0, open=("start", "end"))
    cavity = _cavity(shelled).node
    assert isinstance(cavity, Moved)
    assert isinstance(cavity.node, Revolve)
    assert cavity.node.angle == pytest.approx(math.pi + 2 * PAST / 20.0)
    named = {str(r) for r in refs(part("r", shelled, Printed(PLA)))}
    assert {"inside/start", "inside/end", "inside/side-1"} <= named


# ---- a loft ------------------------------------------------------------------------------


def _funnel() -> Solid:
    return loft(fill(circle(30)), fill(circle(15), on=raised(XY, 40)))


def test_a_loft_walled_at_its_bottom_has_a_floor_named_like_an_extrusions() -> None:
    """The loft's own wall is a hull and keeps no names, so it all answers to ``inside``; the
    floor is cut level a wall above the bottom profile, and is ``inside/bottom``, facing up."""
    funnel = shell(_funnel(), 2.0, open=("top",))
    _at(plane_of(funnel, "inside/bottom"), Point(0.0, 0.0, 2.0), UP)
    named = {str(r) for r in refs(part("f", funnel, Printed(PLA)))}
    assert "inside/bottom" in named


def test_a_loft_open_at_both_ends_is_its_two_profiles_inset_and_run_past_each_end() -> None:
    cavity = bounds(_cavity(shell(_funnel(), 2.0, open=("bottom", "top"))))
    assert cavity.z0 < 0.0
    assert cavity.z1 > 40.0
    assert cavity.x1 == pytest.approx(28.0)


# ---- a run swept in pieces ----------------------------------------------------------------


def _elbow_and_spigot(radius: float = 20.0, spigot: float = 20.0) -> tuple[Solid, Solid]:
    """An elbow turned 30 degrees and a spigot of ``spigot`` radius swept on from its end."""
    elbow = sweep(
        fill(circle(radius)),
        path(ORIGIN, Z, Straight(20.0), Bend(60.0, math.radians(30.0), X)),
    )
    end = plane_of(elbow, "end")
    tail = sweep(
        fill(circle(spigot), on=end), path(end.origin, end.normal, Straight(30.0)), label="spigot"
    )
    return elbow, tail


def test_a_run_swept_in_pieces_is_hollowed_as_one_sweep_along_both_paths() -> None:
    """The cavity is the first profile, inset, swept once along the elbow's path and the
    spigot's joined - so there is no join inside it - and run on past both open ends."""
    elbow, tail = _elbow_and_spigot()
    hollow = shell(union(elbow, tail), 2.0, open=("start", "spigot/end"))
    cavity = _cavity(hollow)
    assert isinstance(cavity.node, Swept)
    assert len(cavity.node.path.edges) == 3, "the elbow's straight and bend, and the spigot's"
    found = refs(hollow)
    assert "inside/side-0" in {str(r) for r in found}
    assert "spigot/start" in {str(r) for r in found}, "the pieces keep their own faces"


def test_a_run_swept_in_pieces_opens_only_at_its_two_ends() -> None:
    """A join is no face of the hollowed body: naming one is refused, and the refusal names
    the two ends the run does have, each under its own piece's label."""
    elbow, tail = _elbow_and_spigot()
    with pytest.raises(ValueError, match="it opens at spigot/end, start"):
        shell(union(elbow, tail), 2.0, open=("start", "end"))


def test_a_run_whose_pieces_do_not_carry_on_from_each_other_is_refused() -> None:
    """A spigot narrower than the elbow, or one set off somewhere else, is not the same
    sweep carried on, and a cavity swept from the first profile would not fit it."""
    elbow, narrow = _elbow_and_spigot(spigot=15.0)
    with pytest.raises(ValueError, match="spigot does not"):
        shell(union(elbow, narrow), 2.0, open=("start", "spigot/end"))
    elbow, tail = _elbow_and_spigot()
    with pytest.raises(ValueError, match="spigot does not"):
        shell(union(elbow, move(tail, Vector(0.0, 1.0, 0.0))), 2.0)


def test_a_run_swept_in_pieces_is_hollowed_where_it_was_moved() -> None:
    """Moves above the union and above a piece are carried with it: the whole run moved is
    the same run, and hollowed there."""
    elbow, tail = _elbow_and_spigot()
    moved_run = move(union(elbow, tail), Vector(5.0, 0.0, 0.0))
    here = bounds(_cavity(shell(union(elbow, tail), 2.0)))
    there = bounds(_cavity(shell(moved_run, 2.0)))
    assert there.x0 == pytest.approx(here.x0 + 5.0)


# ---- what is refused -----------------------------------------------------------------------


@pytest.mark.parametrize("wall", [0.0, -1.0])
def test_a_shell_needs_a_wall(wall: float) -> None:
    with pytest.raises(ValueError, match="wall"):
        shell(cuboid(10, 10, 10), wall)


def test_a_body_with_no_one_recipe_is_refused() -> None:
    """A union is hollowed only as a run of sweeps set end to end; boxes are not one."""
    with pytest.raises(ValueError, match="union"):
        shell(union(cuboid(10, 10, 10), cuboid(5, 5, 20, label="post")), 1.0)


def test_a_hull_of_anything_but_two_profiles_is_refused() -> None:
    three = hull(fill(rect(10, 10)), fill(rect(8, 8), on=raised(XY, 5)), fill(circle(2)))
    with pytest.raises(ValueError, match="two profiles"):
        shell(three, 1.0)


def test_an_extrusion_does_not_open_at_a_side() -> None:
    with pytest.raises(ValueError, match="side-front"):
        shell(cuboid(10, 10, 10), 1.0, open=("side-front",))


def test_a_face_the_revolve_does_not_have_is_named_in_the_refusal() -> None:
    with pytest.raises(ValueError, match="side-9"):
        shell(_cup(), 2.0, open=("side-9",))


def test_a_revolve_with_a_curved_profile_is_refused() -> None:
    with pytest.raises(ValueError, match="straight"):
        shell(revolve(fill(circle(5, Point(20, 0))), Axis(ORIGIN, Y)), 1.0)


def test_a_partial_revolve_is_not_walled_at_its_ends() -> None:
    ring = revolve(fill(rect(10, 10, Point(10, 0))), Axis(ORIGIN, Y), angle=math.pi)
    with pytest.raises(ValueError, match="start and end"):
        shell(ring, 2.0)


def test_a_wall_too_thick_for_the_body_is_refused() -> None:
    with pytest.raises(ValueError, match="nothing"):
        shell(cuboid(20, 20, 4), 2.0)


@pytest.mark.parametrize(
    "body",
    [
        extrude(fill(rect(10, 10, Point(-5, -5))), 10.0, twist=math.pi / 2),
        extrude(fill(rect(10, 10, Point(-5, -5))), 10.0, scale=0.5),
        move(thread(Thread.EXTERNAL, 12.0, 2.0, 10.0), Vector(0.0, 0.0, 5.0)),
    ],
    ids=["twisted", "tapered", "thread"],
)
def test_a_twisted_or_tapered_extrusion_is_refused(body: Solid) -> None:
    """Its inset profile swept straight would neither turn nor narrow with it."""
    with pytest.raises(ValueError, match="twisted or tapered"):
        shell(body, 1.0)
