"""Unit: a flat laser part becomes a closed plate whose every triangle answers to a ref the
script already wrote.

"Closed" is checked by volume: the signed volume of a mesh is its true volume only when every
triangle is there and faces outwards, so area times thickness is a test of both. "A ref the
script wrote" is checked against the ref table and the cut paths the same part already has.
"""

import math

import pytest

from bench import (
    Label,
    Point,
    Process,
    Stock,
    Text,
    circle,
    cut,
    extrude,
    face,
    open_box,
    part,
    part_paths,
    polygon,
    rect,
    text_width,
)
from bench.kernel import Mesh
from bench.model import Part, index
from bench.plates import LIFT, plate

pytestmark = pytest.mark.unit

PLY = Stock(3.0, "ply", kerf=0.25)


def _volume(mesh: Mesh) -> float:
    v = mesh.vertices
    total = 0.0
    for k in range(0, len(mesh.triangles), 3):
        a, b, c = (mesh.triangles[k + n] * 3 for n in range(3))
        ax, ay, az = v[a : a + 3]
        bx, by, bz = v[b : b + 3]
        cx, cy, cz = v[c : c + 3]
        total += ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
    return total / 6.0


def _refs(mesh: Mesh) -> set[str | None]:
    return {None if ref is None else str(ref) for ref in mesh.refs}


def _built(shape: Part) -> Mesh:
    made = plate(shape)
    assert made is not None
    return made.mesh


def _template() -> Part:
    hole = circle(8.0, Point(50.0, 30.0), label=Label("hole"))
    return part(Label("plate"), face(rect(100.0, 60.0), holes=(hole,)), PLY, Process.LASER)


def test_a_plate_encloses_its_face_times_its_thickness() -> None:
    mesh = _built(_template())
    assert _volume(mesh) == pytest.approx((100.0 * 60.0 - math.pi * 8.0**2) * 3.0, rel=1e-3)


def test_an_outline_drawn_clockwise_still_makes_a_plate_facing_out() -> None:
    backwards = polygon((Point(0, 0), Point(0, 40), Point(40, 40), Point(40, 0)))
    mesh = _built(part(Label("p"), face(backwards), PLY, Process.LASER))
    assert _volume(mesh) == pytest.approx(40.0 * 40.0 * 3.0)


def test_the_hole_wall_answers_to_the_hole_and_the_rest_to_the_part() -> None:
    assert _refs(_built(_template())) == {None, "hole"}


def test_a_panel_answers_only_to_refs_the_part_already_has() -> None:
    box = open_box(w=120.0, d=80.0, h=50.0, t=3.0, finger=12.0)
    side = cut(box.side_left, circle(10.0, Point(40.0, 25.0)), label=Label("hole"))
    panel = part(Label("side-left"), side, PLY, Process.LASER)
    mesh = _built(panel)

    named = {str(ref) for ref in index(panel)}
    found = {str(ref) for ref in mesh.refs if ref is not None}
    assert found <= named, found - named
    assert _volume(mesh) > 0.0

    # Every cut path's ref is on the plate - on a wall itself, or on the walls of the edges
    # named under it - apart from the part's own, which is what an unnamed triangle means.
    prefix = f"{panel.label}/"
    for path in part_paths(panel):
        if path.ref is None or str(path.ref) == str(panel.label):
            continue
        own = str(path.ref).removeprefix(prefix)
        assert any(ref == own or ref.startswith(f"{own}/") for ref in found), own


def test_an_engraved_wire_is_drawn_just_above_the_top() -> None:
    mark = rect(20.0, 5.0, Point(10.0, 10.0), label=Label("score"))
    made = plate(part(Label("p"), face(rect(50.0, 30.0)), PLY, Process.LASER, engravings=(mark,)))
    assert made is not None
    segments = made.marks.segments
    assert len(segments) == 6 * 4, "a closed rectangle is four segments"
    assert all(z == pytest.approx(3.0 + LIFT) for z in segments[2::3])
    assert set(made.marks.refs) == {"score"}


def test_lettering_fills_its_estimated_box_on_the_top() -> None:
    words = Text("screws", Point(5.0, 8.0), 6.0, Label("label"))
    made = plate(part(Label("p"), face(rect(80.0, 30.0)), PLY, Process.LASER, engravings=(words,)))
    assert made is not None
    (only,) = made.lettering
    xs, ys, zs = only.corners[0::3], only.corners[1::3], only.corners[2::3]
    assert (min(xs), max(xs)) == pytest.approx((5.0, 5.0 + text_width("screws", 6.0)))
    assert (min(ys), max(ys)) == pytest.approx((8.0, 14.0))
    assert all(z == pytest.approx(3.0 + LIFT) for z in zs)
    assert (only.text, only.ref) == ("screws", "label")


def test_what_is_not_a_plate_is_none() -> None:
    flat = face(rect(10.0, 10.0))
    assert plate(part(Label("thin"), flat, Stock(0.0, "paper"), Process.LASER)) is None
    body = extrude(flat, 5.0)
    assert plate(part(Label("body"), body, PLY, Process.LASER)) is None
