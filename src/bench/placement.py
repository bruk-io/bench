"""Placement: where a dropped mesh's own datum sits, read from a fact somebody wrote down.

A mesh arrives in its exporter's space, and none of its numbers are typeable. A `[reference]`
table beside a project's script says which point of the mesh is the origin, which direction is
up and which is along - :func:`placement` reads that untrusted table into a
:class:`~bench.geometry.Plane`, resolving the two words the survey's own numbers answer
(`"low"`, `"high"`, `"centre"` of the box; `"+X"` .. `"-Z"` of the world) against the mesh it is
handed. :func:`placed` is the move itself: every vertex through the plane's local frame,
triangles and refs untouched.

No table, no call: a project with nothing to place calls neither function, and its mesh stays
exactly as exported. That is a rule for the host, not for this module - :func:`placement` reads
whatever table it is handed, and reads nothing when there is none to read.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace

from .geometry import ORIGIN, TOL, Plane, Point, Vector, X, Y, Z, midpoint, plane, to_local
from .kernel import Mesh

_AXES: dict[str, Vector] = {
    "+X": X,
    "-X": -X,
    "+Y": Y,
    "-Y": -Y,
    "+Z": Z,
    "-Z": -Z,
}
"""The signed world axes a `[reference]` table may name ``up`` or ``along`` by."""


def placement(table: Mapping[str, object], mesh: Mesh) -> Plane:
    """The plane a `[reference]` table describes, resolved against ``mesh``'s own box.

    ``table`` is the untrusted `[reference]` mapping read from a project's TOML: ``origin`` is
    `"low"`, `"high"`, `"centre"` or a triple; ``up`` and ``along`` are `"+X"` .. `"-Z"` or a
    triple. Every number is in ``mesh``'s own coordinates, as exported - one frame in the file,
    never two. ``along`` need only be roughly along the edge: :func:`~bench.geometry.plane`
    projects it onto the plane perpendicular to ``up`` before it is used, and what came out of
    that projection is the plane this returns.

    Raises:
        ValueError: if ``origin``, ``up`` or ``along`` is missing, or is not one of the words
            or triple of numbers each allows, naming the key that failed to read - or if
            ``along`` is parallel to ``up``, which no projection can fix.
    """
    low, high = _box(mesh)
    origin = _origin(table, low, high)
    up = _direction(table, "up")
    along = _direction(table, "along")
    try:
        return plane(origin, up, along)
    except ValueError as exc:
        msg = f"along is parallel to up, so no plane has both: {exc}"
        raise ValueError(msg) from exc


def named_origins(mesh: Mesh) -> tuple[tuple[str, Point], ...]:
    """The points `[reference]`'s three ``origin`` words name for ``mesh``: `"low"`, `"high"`
    and `"centre"`, in that order.

    What a pick needs to say whether the point somebody clicked *is* one of the words this
    module already reads - read off the same box :func:`placement` resolves them against, so a
    pick that writes the word can never mean a different point than the word does.
    """
    low, high = _box(mesh)
    return (("low", low), ("high", high), ("centre", midpoint(low, high)))


def placed(mesh: Mesh, at: Plane) -> Mesh:
    """``mesh`` moved so that ``at``'s origin lands on the world origin, its normal on +Z and
    its ``x_dir`` on +X - the rigid move :func:`placement`'s plane describes, applied to
    triangles a kernel already built.

    Only the vertices move; ``triangles`` and ``refs`` ride along unchanged, so a click on a
    placed mesh still answers exactly as it did before the move.
    """
    t = to_local(at)
    vertices = mesh.vertices
    moved: list[float] = []
    for i in range(0, len(vertices), 3):
        p = t @ Point(vertices[i], vertices[i + 1], vertices[i + 2])
        moved.extend((p.x, p.y, p.z))
    return replace(mesh, vertices=tuple(moved))


def _box(mesh: Mesh) -> tuple[Point, Point]:
    """The low and high corners of the box ``mesh`` fills, or both at the origin for a mesh
    with no vertices."""
    if not mesh.vertices:
        return ORIGIN, ORIGIN
    xs = mesh.vertices[0::3]
    ys = mesh.vertices[1::3]
    zs = mesh.vertices[2::3]
    return Point(min(xs), min(ys), min(zs)), Point(max(xs), max(ys), max(zs))


def _origin(table: Mapping[str, object], low: Point, high: Point) -> Point:
    if "origin" not in table:
        msg = "reference table has no 'origin'"
        raise ValueError(msg)
    value = table["origin"]
    if value == "low":
        return low
    if value == "high":
        return high
    if value == "centre":
        return midpoint(low, high)
    triple = _triple(value)
    if triple is None:
        msg = f"origin must be 'low', 'high', 'centre' or a triple of numbers, not {value!r}"
        raise ValueError(msg)
    return Point(*triple)


def _direction(table: Mapping[str, object], key: str) -> Vector:
    if key not in table:
        msg = f"reference table has no {key!r}"
        raise ValueError(msg)
    value = table[key]
    if isinstance(value, str):
        found = _AXES.get(value)
        if found is None:
            msg = (
                f"{key} must be a signed axis ('+X' .. '-Z') or a triple of numbers, not {value!r}"
            )
            raise ValueError(msg)
        return found
    triple = _triple(value)
    if triple is None:
        msg = f"{key} must be a signed axis ('+X' .. '-Z') or a triple of numbers, not {value!r}"
        raise ValueError(msg)
    vector = Vector(*triple)
    if abs(vector) < TOL:
        msg = f"{key} must not be the zero vector"
        raise ValueError(msg)
    return vector


def _triple(value: object) -> tuple[float, float, float] | None:
    """``value`` as three numbers, or ``None`` if it is not a sequence of exactly three."""
    if isinstance(value, str) or not isinstance(value, Sequence) or len(value) != 3:
        return None
    if not all(isinstance(one, (int, float)) and not isinstance(one, bool) for one in value):
        return None
    a, b, c = value
    return (float(a), float(b), float(c))
