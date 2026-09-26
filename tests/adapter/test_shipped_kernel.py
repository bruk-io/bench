"""Adapter: the shipped kernel behind the :class:`bench.kernel.Kernel` seam.

A real boundary with nothing standing in for it. The tree is built by the ordinary
vocabulary and handed to the kernel the app ships - :class:`bench.adapters.browser.JsKernel`
driving Manifold's WASM through ``web/src/modeller.ts``, inside Pyodide under Node, on
:mod:`tools.stack` - and what comes back is checked here against arithmetic done by hand,
not against another run of the same code.

Two of these checks are the ones the whole kernel exists for. **The tagged face matches the
geometric one exactly**: every triangle the kernel calls ``plate/top`` is a triangle lying on
the plate's top plane and facing out of it, and every such triangle is called that - zero
mismatches, after a union, a difference and a bore. And **a hull names nothing under it**,
because identity does not survive one and the naming rule already says so.

One boot answers the whole module: the bodies are built in :mod:`kernel_cases` inside the
runtime, and every test reads what came back.
"""

import math
import struct
from pathlib import Path
from typing import Any, assert_never, get_args

import pytest

from bench import (
    XY,
    Mesh,
    Process,
    Ref,
    Severity,
    Stock,
    circle,
    faces_of,
    part,
    refs,
    run,
    stl,
)
from bench.topology import (
    CHORD,
    Difference,
    Extrude,
    Hull,
    Imported,
    Intersection,
    Moved,
    Node,
    Revolve,
    Swept,
    Union,
    chord_step,
    flat_ring,
)
from tests.adapter import kernel_cases
from tests.adapter.kernel_cases import BORE, BOSS, PLATE, POCKET, SUNK, WALLED
from tools import stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)

CASES = Path(__file__).with_name("kernel_cases.py")

PROGRAM = """\
import json

from pyodide.ffi import JsException

import kernel_cases
from bench.adapters.browser import JsKernel


def main(js, given):
    return json.dumps(kernel_cases.measured(JsKernel(js, JsException)))
"""


@pytest.fixture(scope="module")
def built() -> dict[str, Any]:
    """Every body, measurement and check this module reads, built once by the shipped
    kernel."""
    found: dict[str, Any] = stack.run(PROGRAM, {}, modules={"kernel_cases.py": CASES.read_text()})
    return found


# ---- the arithmetic these checks are made of -------------------------------------------


def _facets(radius: float) -> int:
    """How many straight steps a circle of that radius is cut into - the package's one chord
    rule, restated here so the expected numbers below are worked out rather than read off
    the code under test."""
    return math.ceil(math.tau / (2.0 * math.acos(1.0 - CHORD / radius)))


def _polygon_area(radius: float) -> float:
    """The area of the regular polygon a circle of that radius actually becomes. A mesh
    kernel has no circles, so a boss footprint is this and not ``pi r squared`` - it is
    about a quarter of a percent under at the sizes here, which is far more than float
    noise and has to be in the expected value rather than in the tolerance."""
    sides = _facets(radius)
    return 0.5 * sides * radius * radius * math.sin(math.tau / sides)


def _ring_area(points: tuple[tuple[float, float], ...]) -> float:
    """A closed polygon's own area, by the shoelace formula - the same arithmetic a kernel's
    cross-section is built from, so a footprint with arcs in it can be worked out here rather
    than read off a formula for a circle it never fully is."""
    pairs = tuple(zip(points, points[1:] + points[:1], strict=True))
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in pairs)) / 2


def _large_plate_footprint_area() -> float:
    """The area one large plate's flange actually meshes as: the outer rounded square, less
    the rounded-square window, less its four round clearance holes - every wire chorded the
    one rule the package uses everywhere, :func:`~bench.topology.flat_ring`, so this is the
    same arithmetic the kernel's own cross-section is built from and not a second guess at
    it."""
    outer = kernel_cases.large_outline()
    window = kernel_cases.large_window()
    hole = circle(kernel_cases.FLANGE_HOLE_D / 2)
    outer_area = _ring_area(flat_ring(outer, XY, (0,) * len(outer.edges)).points)
    window_area = _ring_area(flat_ring(window, XY, (0,) * len(window.edges)).points)
    hole_area = _ring_area(flat_ring(hole, XY, (0,) * len(hole.edges)).points)
    return outer_area - window_area - 4 * hole_area


def _mesh(built: dict[str, Any], key: str) -> Mesh:
    """One body's mesh as the kernel built it, back as the transport record."""
    data = built["meshes"][key]
    return Mesh(
        tuple(float(one) for one in data["vertices"]),
        tuple(int(one) for one in data["triangles"]),
        tuple(None if one is None else Ref(one) for one in data["refs"]),
    )


def _triangles(mesh: Mesh) -> int:
    return len(mesh.triangles) // 3


def _corners(mesh: Mesh, at: int) -> tuple[tuple[float, float, float], ...]:
    return tuple(
        (
            mesh.vertices[3 * mesh.triangles[3 * at + k]],
            mesh.vertices[3 * mesh.triangles[3 * at + k] + 1],
            mesh.vertices[3 * mesh.triangles[3 * at + k] + 2],
        )
        for k in range(3)
    )


def _cross(mesh: Mesh, at: int) -> tuple[float, float, float]:
    """Twice the triangle's area vector: its normal's direction, its length its own area
    doubled."""
    a, b, c = _corners(mesh, at)
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def _area(mesh: Mesh, at: int) -> float:
    x, y, z = _cross(mesh, at)
    return math.sqrt(x * x + y * y + z * z) / 2


def _tagged(mesh: Mesh, ref: str) -> set[int]:
    return {at for at in range(_triangles(mesh)) if mesh.refs[at] == Ref(ref)}


def _names(mesh: Mesh) -> set[str]:
    return {str(one) for one in mesh.refs if one is not None}


def _on_top(mesh: Mesh, height: float) -> set[int]:
    """The geometric predicate the tags are checked against: every triangle whose three
    corners sit on the plane at ``height`` and whose winding faces ``+Z``.

    Mesh vertices are single precision, so the tolerance is a tenth of a micron rather than
    :data:`~bench.geometry.TOL`.
    """
    found: set[int] = set()
    for at in range(_triangles(mesh)):
        area = _area(mesh, at)
        if area <= 0.0 or _cross(mesh, at)[2] / (2 * area) < 0.99:
            continue
        if all(abs(corner[2] - height) < 1e-4 for corner in _corners(mesh, at)):
            found.add(at)
    return found


def _stl_volume(written: bytes) -> float:
    """The volume a binary STL encloses, by the divergence theorem: a sixth of the sum of
    each facet's ``a . (b x c)``. It reads the file back rather than the mesh, so a wrong
    byte order or a dropped triangle shows up as a wrong number."""
    count = struct.unpack("<I", written[80:84])[0]
    total = 0.0
    for at in range(count):
        start = 84 + 50 * at + 12
        a, b, c = (
            struct.unpack("<3f", written[start + 12 * k : start + 12 * k + 12]) for k in range(3)
        )
        cross = (b[1] * c[2] - b[2] * c[1], b[2] * c[0] - b[0] * c[2], b[0] * c[1] - b[1] * c[0])
        total += sum(a[k] * cross[k] for k in range(3)) / 6
    return total


def _kinds(node: Node) -> frozenset[type[Node]]:
    """Every arm of :data:`~bench.topology.Node` that appears anywhere under ``node``.

    A walk of its own rather than :func:`~bench.topology.node_children`, which stops at a
    hull because refs do: what is under a hull has no name, but it is still built, and this
    is about what gets built.
    """
    match node:
        case Extrude() | Revolve():
            return frozenset({type(node)})
        case Union(a, b) | Intersection(a, b) | Difference(a, b):
            return frozenset({type(node)}) | _kinds(a.node) | _kinds(b.node)
        case Hull(parts):
            return frozenset({Hull}).union(*(_kinds(one.node) for one in parts))
        case Imported():
            return frozenset({Imported})
        case Moved(inner, _):
            return frozenset({Moved}) | _kinds(inner)
        case Swept():
            return frozenset({Swept})
        case _:
            assert_never(node)


# ---- what gets built -------------------------------------------------------------------


def test_every_arm_of_the_node_union_is_built_by_the_kernel(built: dict[str, Any]) -> None:
    """A :data:`~bench.topology.Node` kind the kernel cannot build must fail loudly and by
    name, so the arms are derived from the union itself rather than from a list somebody
    keeps, and an arm added to ``topology.py`` fails here until a case builds it."""
    claimed = frozenset[type[Node]]().union(
        *(_kinds(build().node) for build in kernel_cases.CASES.values())
    )
    assert frozenset(get_args(Node)) - claimed == frozenset()
    for key in kernel_cases.CASES:
        assert _triangles(_mesh(built, key)) > 0, f"{key} came back with no triangles"


# ---- the example ------------------------------------------------------------------------


def test_the_plate_volume_is_what_the_arithmetic_says(built: dict[str, Any]) -> None:
    """Slab, plus the boss's prism, less the pocket's box, less the bore - with the round
    features counted as the polygons a mesh kernel actually makes them."""
    expected = (
        PLATE[0] * PLATE[1] * PLATE[2]
        + _polygon_area(BOSS[0]) * BOSS[1]
        - POCKET[0] * POCKET[1] * POCKET[2]
        - _polygon_area(BORE[0]) * BORE[1]
    )
    assert built["volumes"]["plate"] == pytest.approx(expected, rel=1e-9)


def test_the_plates_top_face_is_recovered_after_the_booleans_with_no_mismatches(
    built: dict[str, Any],
) -> None:
    """The check this whole kernel exists for. After a union, a difference and a bore, the
    set of triangles tagged ``top`` is *exactly* the set of triangles lying on the top plane
    and facing out of it - not a superset, not a subset - and their area is the slab's top
    less the three features that broke it."""
    mesh = _mesh(built, "plate")
    tagged = _tagged(mesh, "top")
    geometric = _on_top(mesh, PLATE[2])
    assert tagged == geometric, f"{len(tagged ^ geometric)} triangles disagree"
    assert tagged, "the top face survived nothing at all"
    expected = (
        PLATE[0] * PLATE[1]
        - _polygon_area(BOSS[0])
        - POCKET[0] * POCKET[1]
        - _polygon_area(BORE[0])
    )
    assert sum(_area(mesh, at) for at in tagged) == pytest.approx(expected, rel=1e-5)


def test_every_face_the_tree_names_and_survives_the_cuts_is_on_a_triangle(
    built: dict[str, Any],
) -> None:
    """The mesh's refs are the ref table's own, so a click lands on a name a script can
    write, and the kernel never invents one the tree did not promise.

    What is missing is exactly what the booleans consumed. The three bodies themselves name
    no surface of their own - a solid's faces are what carry names, not the solid. And four
    faces are eaten: the boss's underside, buried in the plate; the bore's two caps, flush
    with the plate's own top and bottom; and the pocket's opening, flush with the top. A
    face that lands exactly on another is not a face of the result, which is the honest
    answer and the reason a name is promised by the tree and *found* by the kernel.
    """
    found = _names(_mesh(built, "plate"))
    named = {str(one) for one in refs(kernel_cases.plate())}
    assert found <= named, f"the kernel invented {sorted(found - named)}"
    assert named - found == {
        "boss",
        "pocket",
        "bore",
        "boss/bottom",
        "bore/top",
        "bore/bottom",
        "pocket/top",
    }


def test_the_pocket_floor_answers_to_the_tools_own_bottom(built: dict[str, Any]) -> None:
    """``plate/pocket/bottom`` is not a rule about pockets, it is the naming rule falling
    out: the tool's own ``bottom`` is the face that survived the cut, and here it is, at the
    depth the pocket was sunk to and facing down."""
    mesh = _mesh(built, "plate")
    floor = _tagged(mesh, "pocket/bottom")
    assert floor
    assert sum(_area(mesh, at) for at in floor) == pytest.approx(POCKET[0] * POCKET[1])
    for at in floor:
        assert all(abs(corner[2] - (PLATE[2] - POCKET[2])) < 1e-4 for corner in _corners(mesh, at))


def test_a_hull_names_itself_and_nothing_under_it(built: dict[str, Any]) -> None:
    """Identity does not survive a hull: a mesh kernel builds one from a point cloud and
    hands back surfaces belonging to nothing that went in. So the whole body answers to the
    hull's own label, the profiles that made it are unreachable, and the tree said so before
    anything was built."""
    taper = kernel_cases.taper()
    assert {str(one) for one in _mesh(built, "taper").refs} == {"t"}
    # the tree said so first: a hull has no faces of its own to name, and the profiles that
    # went into it are unreachable
    assert faces_of(taper) == ()
    assert refs(part("block", taper, Stock(0.0, "PLA"), Process.PRINT)) == (Ref("t"),)
    assert built["volumes"]["taper"] == pytest.approx(8 * (400 + 100 + math.sqrt(400 * 100)) / 3)


def test_a_hull_inside_a_part_still_names_only_itself(built: dict[str, Any]) -> None:
    """And the same under a boolean, where a tagged neighbour could have lent it a name."""
    # the bore's top cap lands exactly on the hull's own top surface, so the cut leaves it
    # nothing; what is left of the tool is its wall
    assert {str(one) for one in _mesh(built, "capped").refs} == {"cap", "bore/side-0"}


# ---- a mesh somebody else made ----------------------------------------------------------


def test_a_dropped_mesh_builds_as_a_body_and_weighs_what_it_should(built: dict[str, Any]) -> None:
    """The leaf on its own: a hand-written cube of ten millimetres, handed to the kernel as
    a mesh and measured as a body. A thousand cubic millimetres exactly - not approximately,
    because a box has no round features to be cut into chords - and the twelve triangles it
    went in as."""
    side = kernel_cases.DROPPED_SIDE
    assert built["volumes"]["dropped"] == pytest.approx(side**3, rel=1e-9)
    assert _triangles(_mesh(built, "dropped")) == 12


def test_an_import_names_itself_and_nothing_under_it(built: dict[str, Any]) -> None:
    """The same rule a hull is under, for the same reason: a file somebody else wrote has no
    names in it to keep, so the whole body answers to the label the script gave it and there
    is nothing beneath it to reach. The tree says so before anything is built."""
    assert {str(one) for one in _mesh(built, "dropped").refs} == {"dropped"}
    assert faces_of(kernel_cases.dropped()) == ()


def test_an_import_composes_with_the_verbs_nobody_wrote_a_case_for(
    built: dict[str, Any],
) -> None:
    """``_cloud`` in the adapter has no ``Imported`` case and needs none: it falls back to
    building the node and reading its own vertices, and an import lands there exactly as any
    node that catch-all has never heard of does. Run rather than reasoned about, because it
    is the claim decision-8 rests its "the design already composes" argument on. A cube is
    its own convex hull, so the hull weighs what the import weighs; and a move carries it
    without touching the leaf at all."""
    side = kernel_cases.DROPPED_SIDE
    assert built["volumes"]["import-hulled"] == pytest.approx(side**3, rel=1e-9)
    assert built["volumes"]["import-moved"] == pytest.approx(side**3, rel=1e-9)
    # the hull renames what is under it, the move renames nothing
    assert {str(one) for one in _mesh(built, "import-hulled").refs} == {"wrapped"}
    assert {str(one) for one in _mesh(built, "import-moved").refs} == {"dropped"}


def test_how_much_of_a_candidate_lies_inside_a_dropped_reference(built: dict[str, Any]) -> None:
    """The measure the whole leaf exists for, and the one a survey diff cannot give: a
    candidate box slid half its width along X shares exactly half its volume with the
    reference, makes one and a half of them together, and stands a half proud. Every figure
    is a multiplication of the cube's own edge, done here rather than read back."""
    side = kernel_cases.DROPPED_SIDE
    whole = side**3
    fit = built["fit"]
    assert fit["reference"] == pytest.approx(whole, rel=1e-9)
    assert fit["candidate"] == pytest.approx(whole, rel=1e-9)
    assert fit["overlap"] == pytest.approx(whole / 2, rel=1e-9)
    assert fit["both"] == pytest.approx(whole * 1.5, rel=1e-9)
    assert fit["proud"] == pytest.approx(whole / 2, rel=1e-9)
    assert fit["fraction"] == pytest.approx(0.5, rel=1e-9)
    # and min_gap reads an import as readily as it reads anything else: a box standing at
    # x = 15 is five millimetres clear of a cube reaching x = 10
    assert fit["gap"] == pytest.approx(5.0, rel=1e-9)


def test_the_checks_take_an_imported_body_exactly_as_they_take_any_other(
    built: dict[str, Any],
) -> None:
    """Neither ``clearance_between`` nor ``contact_between`` was touched to make this true -
    an import is a ``Solid``, so they already worked on one. A reference and a body five
    millimetres clear of it pass a 0.15 mm clearance and fail an 8 mm one; and the candidate
    driven halfway into the reference is named as the overlap it is, with the shared volume
    measured off the imported cube itself - half of it, which is the same figure the fit
    measure answers with and the strongest evidence the check really read the import."""
    side = kernel_cases.DROPPED_SIDE
    assert built["checks"]["clearance-imported"] is None
    tight = built["checks"]["clearance-imported-tight"]
    assert tight is not None
    assert tight["severity"] == Severity.ERROR
    overlapping = built["checks"]["contact-imported"]
    assert overlapping is not None
    assert overlapping["severity"] == Severity.ERROR
    assert f"share {side**3 / 2:.3f} mm3" in overlapping["message"]


def test_a_mesh_that_is_no_body_is_refused_the_way_every_bad_call_is(
    built: dict[str, Any],
) -> None:
    """One lone triangle bounds nothing, and Manifold's own constructor is what says so.
    There is no check on bench's side of the bridge: the refusal crosses as the exception a
    failed call already raises and comes out as the ``ValueError`` naming the call, exactly
    as a boolean the kernel cannot complete does."""
    refusal = built["refusal"]
    assert refusal is not None, "a torn mesh measured as though it were a body"
    assert "the modeller could not answer volume" in refusal
    assert "manifold" in refusal.lower()


def test_a_partial_turn_shows_two_ends_a_whole_turn_does_not(built: dict[str, Any]) -> None:
    """A revolve's caps are found by position and its sides by the profile step under them:
    the same profile turned part way names every face the whole turn does, and the two ends
    it leaves showing."""
    part_turn = _names(_mesh(built, "part-turn"))
    whole_turn = _names(_mesh(built, "whole-turn"))
    assert whole_turn < part_turn
    assert len(part_turn - whole_turn) == 2


def test_an_intersection_is_what_two_boxes_share(built: dict[str, Any]) -> None:
    """Two 20 mm boxes, one moved 10 mm along every axis: they share a 10 mm cube, and each
    lends it the three faces of its own that bound the overlap - named under the shared
    solid's label, since a bare solid's faces answer beneath its own name."""
    assert built["volumes"]["shared"] == pytest.approx(1000.0, rel=1e-9)
    names = _names(_mesh(built, "shared"))
    assert len({one for one in names if one.startswith("shared/left/")}) == 3, names
    assert len({one for one in names if one.startswith("shared/right/")}) == 3, names
    assert len(names) == 6, names


def test_two_bodies_that_are_known_to_be_apart_measure_apart(built: dict[str, Any]) -> None:
    """``min_gap`` searches only as far as it is asked to, which is what keeps it cheap: two
    blocks five millimetres apart answer five when there is room to look and the limit when
    there is not."""
    gaps = built["gaps"]
    assert gaps["apart"] == pytest.approx(5.0)
    assert gaps["limited"] == pytest.approx(2.0)
    assert gaps["touching"] == pytest.approx(0.0)


def test_an_stl_says_the_same_thing_the_kernel_does(built: dict[str, Any]) -> None:
    """The file is the model: header, count and length agree, and the closed volume the
    facets enclose - by the divergence theorem, read back out of the bytes - is the volume
    the kernel measured."""
    mesh = _mesh(built, "plate")
    written = stl(mesh)
    count = struct.unpack("<I", written[80:84])[0]
    assert count == _triangles(mesh)
    assert len(written) == 84 + 50 * count
    assert _stl_volume(written) == pytest.approx(built["volumes"]["plate"], rel=1e-6)


def test_a_body_moved_keeps_every_name_it_had(built: dict[str, Any]) -> None:
    """A ``Moved`` renames nothing, and a transform applied after tagging carries the tags
    with it - so the same cuboid answers the same six faces wherever it is put."""
    assert _names(_mesh(built, "block")) == _names(_mesh(built, "block-moved"))
    assert built["volumes"]["block-moved"] == pytest.approx(8.0)


def test_a_scripted_part_is_meshed_through_the_seam_and_not_around_it(
    built: dict[str, Any],
) -> None:
    """The seam as the rest of the package uses it: a part, a kernel, and refs that read the
    same in the mesh as in the ref table - part label and all."""
    scene = built["scripted"]
    assert scene["ok"] is True, scene
    mesh = scene["parts"][0]["mesh"]
    assert mesh is not None
    assert set(mesh["refs"]) <= set(scene["refs"])
    assert "tray/well/bottom" in mesh["refs"]
    assert "tray.stl" in scene["files"]


def test_a_round_feature_is_cut_into_the_steps_the_one_chord_rule_asks_for(
    built: dict[str, Any],
) -> None:
    """The kernel flattens with the package's rule and not with Manifold's own default, so
    a bore is the same polygon in the mesh, in the DXF and in the browser."""
    wall = _tagged(_mesh(built, "bore"), "bore/side-0")
    assert len(wall) == 2 * _facets(BORE[0])
    assert chord_step(BORE[0]) == pytest.approx(2.0 * math.acos(1.0 - CHORD / BORE[0]))


def test_a_loft_between_two_profiles_on_one_plane_encloses_nothing(built: dict[str, Any]) -> None:
    """The degenerate hull: two profiles drawn on the same plane have no height between
    them, so the convex hull of their points is flat and a flat thing is not a body. It
    comes back as an empty mesh and a volume of zero rather than as a crash out of the
    modeller, because nothing here can say what the script meant."""
    assert built["volumes"]["flat"] == pytest.approx(0.0)
    assert _mesh(built, "flat") == Mesh((), (), ())


# ---- the print domain, measured on real triangles ---------------------------------------


def test_a_printed_bore_measures_the_diameter_the_material_asked_for(
    built: dict[str, Any],
) -> None:
    """What the whole compensation story is for, measured rather than asserted: the table's
    M3 clearance hole is 3.4 mm, PLA takes 0.2 mm back off a printed one, and what the
    kernel actually leaves behind is the polygon those 3.6 mm are cut into.

    A mesh kernel has no circles, so the hole a printer sees is the inscribed polygon of the
    circle we asked for; both numbers are worked out here rather than read off the code.
    """
    from bench import M3, Fit, bore
    from bench.library.print import PLA

    asked = bore(M3, Fit.CLEARANCE) + PLA.hole_compensation
    mesh = _mesh(built, "drilled")
    wall = [p for at in _tagged(mesh, "m3/side-0") for p in _corners(mesh, at)]
    across = max(math.hypot(x - 10.0, y - 10.0) for x, y, _ in wall) * 2
    assert across == pytest.approx(asked, abs=1e-3), "the circle the chords stand in"
    lost = built["volumes"]["drilled-plate"] - built["volumes"]["drilled"]
    assert lost == pytest.approx(_polygon_area(asked / 2) * 4.0, rel=1e-6)


@pytest.mark.parametrize(
    ("key", "degrees"), [("sunk-m3", 90.0), ("sunk-wood-8", 82.0), ("sunk-drywall-8", 61.5)]
)
def test_a_countersink_is_cut_at_the_screws_own_angle(
    built: dict[str, Any], key: str, degrees: float
) -> None:
    """``hole(countersink=True)`` with no ``angle`` cuts the cone the screw's own
    ``countersink_angle`` asks for: ISO 90 for an M3, 82 for an inch flat head, the bugle's
    estimate for a drywall screw. Read off the cone's own triangles: how far it widens
    between its narrowest ring, down where it meets the bore, and its widest, at the plate's
    top, over how far apart the two rings stand."""
    mesh = _mesh(built, key)
    cone = [p for at in _tagged(mesh, "sunk/head") for p in _corners(mesh, at)]
    reach = [(math.hypot(x - 10.0, y - 10.0), z) for x, y, z in cone]
    (r0, z0), (r1, z1) = min(reach, key=lambda p: p[1]), max(reach)
    assert z1 == pytest.approx(SUNK, abs=1e-3)
    assert math.degrees(2 * math.atan((r1 - r0) / (z1 - z0))) == pytest.approx(degrees, abs=0.05)


def test_a_wall_check_measures_the_thinnest_wall_of_a_real_body(built: dict[str, Any]) -> None:
    """Straight through the material from the middle of every triangle: a 4 mm plate is
    4 mm thick, and the wall left beside a bore is what the arithmetic says."""
    found = built["checks"]
    assert found["wall-thick"] is None
    thin = found["wall-thin"]
    assert thin is not None
    assert thin["severity"] == Severity.ERROR
    assert "4.00 mm" in thin["message"]
    assert thin["refs"] and thin["refs"][0] in {"top", "bottom"}


def test_a_wall_check_sees_the_material_a_bore_left_behind(built: dict[str, Any]) -> None:
    """A 10 mm bore in the middle of a 20 mm block leaves 5 mm either side; move it to
    1.5 mm from the edge and the check says so and names the face it measured from."""
    found = built["checks"]
    assert found["wall-centred"] is None
    near_edge = found["wall-near-edge"]
    assert near_edge is not None
    assert near_edge["message"].startswith("the thinnest wall is 1.0")


def test_an_overhang_check_classifies_real_triangles_against_the_build_direction(
    built: dict[str, Any],
) -> None:
    """A box standing on the bed overhangs nothing; the same box with a bore drilled across
    it has an arch that PLA cannot hold up, and the check names the face."""
    from bench.library.print import PLA

    found = built["checks"]
    assert found["overhang-block"] is None
    sideways = found["overhang-sideways"]
    assert sideways is not None
    assert sideways["severity"] == Severity.WARNING
    leans = float(sideways["message"].split(" leans ")[1].split(" degrees")[0])
    assert leans > math.degrees(PLA.max_overhang)
    assert leans > 80.0, "the top of a horizontal bore is all but a ceiling"
    assert sideways["refs"] and sideways["refs"][0] == "bore/side-0"


def test_a_teardrop_bore_passes_the_overhang_check_a_round_one_fails(built: dict[str, Any]) -> None:
    """The two halves of the print domain meeting on a real mesh: the shape ``hole`` builds
    for a leaning bore is exactly the shape the overhang check asks for."""
    assert built["checks"]["overhang-round"] is not None
    assert built["checks"]["overhang-teardrop"] is None


def test_a_clearance_check_measures_the_gap_between_two_real_bodies(
    built: dict[str, Any],
) -> None:
    """``min_gap`` through the seam: two knuckles a fifth of a millimetre apart do not
    print as two parts, and the check says the number it measured."""
    assert built["checks"]["clearance-loose"] is None
    tight = built["checks"]["clearance-tight"]
    assert tight is not None
    assert tight["severity"] == Severity.ERROR
    assert "0.20 mm" in tight["message"]


def test_a_declared_contact_passes_exactly_where_an_undeclared_pair_fails(
    built: dict[str, Any],
) -> None:
    """The whole point of the check, on one pair of bodies. A boss seated flat on a disc is
    what a shoulder is; ``min_gap`` reads it as zero, so asking for a fifth of a millimetre
    fails it. Declaring the contact does not skip the pair - it asks the other question, and
    the other question is the one a seat can answer."""
    assert built["checks"]["contact-seated"] is None
    undeclared = built["checks"]["contact-seated-undeclared"]
    assert undeclared is not None
    assert undeclared["severity"] == Severity.ERROR
    assert "0.00 mm" in undeclared["message"]


def test_a_declared_contact_that_is_really_an_overlap_is_still_reported(
    built: dict[str, Any],
) -> None:
    """Declared is not exempt. The same boss driven 0.2 mm into the same disc reads zero to
    ``min_gap`` exactly as the seated one does - the two are indistinguishable by distance -
    and the shared material is what tells them apart, so the collision is named and the seat
    is not."""
    driven = built["checks"]["contact-driven"]
    assert driven is not None
    assert driven["severity"] == Severity.ERROR
    # Worked out rather than read off: the boss is sunk 0.2 mm into the disc, so what the two
    # share is that depth of the polygon a 4 mm circle actually meshes as - not of the circle,
    # which is a quarter of a percent bigger and would miss by far more than float noise.
    assert f"share {_polygon_area(4.0) * 0.2:.3f} mm3" in driven["message"]
    # and the gap reads the same zero for the seat and for the collision, which is why the
    # check cannot be built on a distance at all
    assert "0.00 mm" in built["checks"]["contact-driven-undeclared"]["message"]


def test_a_declared_contact_says_nothing_about_whether_the_two_actually_meet(
    built: dict[str, Any],
) -> None:
    """The limit, asserted rather than left to the docstring. A declared pair standing well
    clear of each other shares no material and passes: declaring a contact names the pair
    that is *allowed* to touch, never the pair that must."""
    assert built["checks"]["contact-apart"] is None


def test_a_small_face_sunk_one_micron_still_fails(built: dict[str, Any]) -> None:
    """The figure :data:`~bench.checks._SHARED_SLACK`'s own docstring cites: the same disc
    and boss as :func:`test_a_declared_contact_passes_exactly_where_an_undeclared_pair_fails`,
    sunk a single micron rather than a fifth of a millimetre. A mean-penetration-depth test
    has to fail this exactly as a fixed-volume one already did, so it is measured here and
    not assumed."""
    sunk = built["checks"]["contact-sunk-one-micron"]
    assert sunk is not None
    assert sunk["severity"] == Severity.ERROR
    assert f"share {_polygon_area(4.0) * 0.001:.3f} mm3" in sunk["message"]


def test_two_large_coincident_faces_pass_a_declared_contact(built: dict[str, Any]) -> None:
    """task-57: two 317.5 mm rounded-square plates, each with a 266.7 mm rounded-square
    window and four clearance holes, the second extruded from the exact plane the first's
    top face is on. A fixed-volume test failed this - the rounding two large faces pick up
    just from being large reads as more shared material than a real one-micron overlap on a
    small pair ever did - so this is the check the fix exists to pass."""
    assert built["checks"]["contact-large-plates"] is None


def test_a_one_micron_sink_of_the_large_plates_still_fails(built: dict[str, Any]) -> None:
    """The other half of task-57's evidence: the same two large plates, the upper one sunk
    one micron into the lower, still have to fail. The shared volume a one-micron overlap
    that size leaves behind is the footprint - a rounded square less a rounded-square window
    less four round holes, chorded the one rule the kernel's own cross-section uses - times
    the sink, so the expected share is worked out from that footprint rather than read off a
    second run of the modeller - within a few ten-thousandths, since a footprint this large is
    single-precision mesh vertices summed a hundred thousand times over."""
    expected = _large_plate_footprint_area() * 0.001
    sunk = built["checks"]["contact-large-plates-sunk-one-micron"]
    assert sunk is not None
    assert sunk["severity"] == Severity.ERROR
    reported = float(sunk["message"].split("share ")[1].split(" mm3")[0])
    assert reported == pytest.approx(expected, rel=1e-3)


def test_two_islands_of_overlap_far_apart_on_one_large_face_still_fail(
    built: dict[str, Any],
) -> None:
    """Why the contact area is read off the shared shape's own surface rather than off a
    bounding box: two small bosses seated at opposite corners of the same large flange pass
    exactly as the boss and disc do on their own, and sunk a micron into it still fail, even
    though the two overlaps sit 260-odd millimetres apart and a box around both of them would
    be most of the plate. A bounding box read that large would have driven the mean
    penetration depth down by orders of magnitude and passed this as if it were rounding
    noise; it is not, and the check has to catch it."""
    assert built["checks"]["contact-scattered"] is None
    sunk = built["checks"]["contact-scattered-sunk-one-micron"]
    assert sunk is not None
    assert sunk["severity"] == Severity.ERROR
    # two 4 mm bosses, each sunk the same micron the small disc and boss above were
    assert f"share {2 * _polygon_area(4.0) * 0.001:.3f} mm3" in sunk["message"]


def test_a_run_with_a_kernel_measures_what_a_run_without_one_leaves_unchecked(
    built: dict[str, Any],
) -> None:
    """The same script, the same checks, the same scene shape - and the only difference is
    whether the answer is a measurement or ``unchecked``."""
    without = run(WALLED)
    assert without["ok"] is True, without
    assert without["violations"][0]["severity"] == Severity.UNCHECKED
    with_one = built["walled"]
    assert with_one["ok"] is True, with_one
    assert with_one["violations"][0]["severity"] == Severity.ERROR
    assert "1.00 mm" in with_one["violations"][0]["message"]
    assert with_one["violations"][0]["line"] == 4
