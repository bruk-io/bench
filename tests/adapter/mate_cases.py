"""What ``test_mate_measured.py`` asks of the shipped kernel, answered inside Pyodide.

:mod:`tools.stack` writes this file beside ``bench`` in the runtime the app ships, and
:func:`measured` puts parts together with :func:`bench.mate.mating` and through a script's
own ``mated``, and measures what came of it with the real kernel - answering with plain
JSON-able data. It imports nothing but ``bench`` and the standard library, and decides
nothing: every assertion is in the test module.
"""

from collections.abc import Mapping

from bench import (
    ORIGIN,
    Axis,
    Orient,
    Part,
    Point,
    Printed,
    Solid,
    Vector,
    X,
    common,
    cuboid,
    extrude,
    face,
    mating,
    move,
    overhangs,
    part,
    plane,
    polygon,
    rotate,
    run,
)
from bench.kernel import Kernel, Mesh
from bench.library.print import PLA

PRINTED = Printed(PLA)
"""What every part here is made of: PLA, printed the way it is drawn."""

PEGGED = """\
from bench import *
from bench.library.print import PLA

pla = Printed(PLA)
base = part("base", cuboid(40, 40, 5), pla)
plate = cuboid(20, 20, 4)
plate = union(plate, extrude(fill(rect(4, 4, Point(8, 8)), on=raised(XY, -1.0)), 1.0, label="peg"))
fitted = mated(base, "base/top", part("plate", plate, pla), "plate/bottom", offset=Vector(10, 10))
print(fitted)
show(assembly("pegged", (Placed(base, XY), Placed(fitted.part, XY)), posed=True))
"""
"""A plate with a peg standing a millimetre proud of its back face, mated flat onto a base:
the peg is sunk into the base, so the contact the mate declares is an overlap."""

SLID = """\
from bench import *
from bench.library.print import PLA

pla = Printed(PLA)
base = part("base", cuboid(40, 40, 5), pla)
plate = part("plate", cuboid(20, 20, 4), pla)
fitted = mated(base, "base/top", plate, "plate/bottom", fit=Fit.SLIDE, offset=Vector(10, 10))
print(fitted)
show(assembly("slid", (Placed(base, XY), Placed(fitted.part, XY)), posed=True))
"""
"""A plate mated onto a base at a slide fit, with nothing else between them: the gap the
mate measures is the table's own, exactly."""


def _vent(source: str) -> Mapping[str, object]:
    """The example vent's own functions, read out of its source with ``show`` stubbed - the
    script is data here, and its geometry is what is measured."""
    names: dict[str, object] = {"show": lambda _: None, "__name__": "wall_vent"}
    exec(source, names)
    return names


def _bounds(mesh: Mesh) -> list[float]:
    """The axis-aligned box of a built mesh: low corner, then high."""
    xs, ys, zs = mesh.vertices[0::3], mesh.vertices[1::3], mesh.vertices[2::3]
    return [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]


def _placed(kernel: Kernel, one: Solid, other: Solid) -> dict[str, object]:
    """Two placements of one body measured against each other: each one's box and volume, and
    how much of the two the kernel finds they share - all of it, when they are the same."""
    return {
        "bounds": [_bounds(kernel.mesh(one)), _bounds(kernel.mesh(other))],
        "volumes": [kernel.volume(one), kernel.volume(other)],
        "shared": kernel.volume(common(one, other)),
    }


def _vent_cases(kernel: Kernel, source: str) -> dict[str, object]:
    """The vent's attachment put on its frame by the mate, against the same attachment put
    there by hand - moved up by the flange - and against one that wandered off first, turned
    and shifted, and was mated back."""
    vent = _vent(source)
    p = vent["Vent"]()  # type: ignore[operator]
    body, _ = vent["frame"](p)  # type: ignore[operator]
    drawn = vent["attachment"](p)  # type: ignore[operator]
    held = part("frame", body, PRINTED)
    by_hand = move(drawn, Vector(0.0, 0.0, p.flange))
    mate = mating(
        held, "frame/flange/top", part("attachment", drawn, PRINTED), "attachment/base/bottom"
    )
    wandered = move(
        rotate(rotate(drawn, 1.1, about=Axis(Point(3, -7, 2), Vector(1, 2, 3))), 0.4),
        Vector(40.0, -25.0, 17.0),
    )
    back = mating(held, "frame/flange/top", part("attachment", wandered, PRINTED), "base/bottom")
    return {
        "mated": _placed(kernel, _body(mate.part), by_hand),
        "wandered": _placed(kernel, _body(back.part), by_hand),
    }


def _body(one: Part) -> Solid:
    shape = one.shape
    assert isinstance(shape, Solid)
    return shape


def _ridge() -> Solid:
    """A squat ridge, wide at the bottom: a trapezoid 30 across its foot and 10 across its
    crown, 5 high, swept 20 along Y. Its two flanks lean 63 degrees off the vertical, so it
    prints standing on its foot (``side-0``) and not on its crown (``side-2``)."""
    profile = polygon((Point(0, 0), Point(30, 0), Point(20, 5), Point(10, 5)))
    return extrude(face(profile, on=plane(ORIGIN, Vector(0, -1, 0), X)), 20.0)


def _turned_over(kernel: Kernel) -> dict[str, object]:
    """A part that prints on its foot, mated crown down onto a shelf - upside down: its
    overhangs measured as authored, as mated with its way up carried along, and as mated with
    the authored way up left behind, and which of its faces lies lowest along the way up it
    carried."""
    authored = part("ridge", _ridge(), PRINTED)
    shelf = cuboid(60, 60, 5)
    mate = mating(shelf, "top", authored, "ridge/side-2")
    carried = mate.part.stock
    assert isinstance(carried, Printed)
    moved = _body(mate.part)
    return {
        "up": list(carried.orient.up),
        "authored": _found(overhangs(_body(authored), PRINTED.orient, PLA, kernel=kernel)),
        "carried": _found(overhangs(moved, carried.orient, PLA, kernel=kernel)),
        "left_behind": _found(overhangs(moved, Orient(), PLA, kernel=kernel)),
        "bed": _bed(kernel.mesh(moved), carried.orient.up),
    }


def _found(violation: object) -> str | None:
    return None if violation is None else str(getattr(violation, "message", violation))


def _bed(mesh: Mesh, up: Vector) -> list[str]:
    """The refs of every triangle lying flat at the lowest height along ``up`` - what
    stands on the bed when the part is printed that way up."""
    heights = [
        sum(v * c for v, c in zip(mesh.vertices[3 * i : 3 * i + 3], up, strict=True))
        for i in range(len(mesh.vertices) // 3)
    ]
    low = min(heights)
    return sorted(
        {
            str(ref)
            for t, ref in enumerate(mesh.refs)
            if all(abs(heights[mesh.triangles[3 * t + k]] - low) <= 1e-4 for k in range(3))
        }
    )


def measured(kernel: Kernel, vent: str) -> dict[str, object]:
    """Everything ``test_mate_measured.py`` reads, built by ``kernel``; ``vent`` is the
    example's source."""
    return {
        "vent": _vent_cases(kernel, vent),
        "pegged": run(PEGGED, kernel=kernel),
        "slid": run(SLID, kernel=kernel),
        "turned": _turned_over(kernel),
    }
