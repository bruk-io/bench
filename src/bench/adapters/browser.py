"""The :class:`bench.kernel.Kernel` on Manifold's WASM build, called from Pyodide.

The browser has no ``manifold3d`` wheel and will not get one: there is no emscripten build
on PyPI, upstream turns the Python bindings off under emscripten, and a build of one would
have to be redone against every Pyodide bump. What the browser does have is Manifold's own
WASM build, ``manifold-3d`` on npm, loaded in the same worker as Pyodide - and Pyodide's
Python calls into that worker's JavaScript *synchronously*.

**This module is the kernel.** It walks a :class:`~bench.topology.Solid`'s tree, asks the
modeller for each sweep and boolean by handle, and makes every decision about names with
:mod:`bench.meshing`: which face each triangle of a fresh primitive lies on, what every face
is called, and what each triangle of the result answers to. The modeller on the other side -
``web/src/modeller.ts`` - holds Manifold's objects and forwards calls, and does no geometry.

**What crosses.** Handles and single numbers, and bulk numbers as buffers: an
:class:`array.array` goes out as a view onto Python's memory, and a mesh comes back as the
typed arrays Manifold made, read with ``to_py``. The number of calls grows with the tree,
never with the triangles - every per-triangle loop runs here, on one side of the bridge.

**Nothing Pyodide-only is imported.** A JavaScript call that throws raises Pyodide's
``JsException`` in here, and the host hands that type in as ``refused`` - so this runs, and
is tested, anywhere, against anything with the modeller's calls.

**Failure and memory.** A refusal becomes a :class:`ValueError` naming the call, which
:func:`bench.script.run` turns into an error scene on the script's own line. Every call ends
with the modeller told to free what it made, refused or not, because WASM memory is not
garbage-collected.
"""

import logging
import math
from array import array
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, assert_never

from .. import meshing
from ..geometry import TOL, Transform, Vector, identity, translation
from ..kernel import Mesh
from ..model import Ref
from ..telemetry import SILENT, Tracer, fields, timed
from ..topology import (
    Difference,
    Extrude,
    Hull,
    Imported,
    Intersection,
    Moved,
    Node,
    Revolve,
    Ring,
    Solid,
    Swept,
    Union,
    profile_rings,
    straight,
    under,
)

_Tags = dict[tuple[int, int], Ref | None]
"""What a triangle's ``(run_original_id, face_id)`` pair means, filled in as the tree is
walked and read once the result is meshed."""


class Buffer(Protocol):
    """A typed array from JavaScript. ``to_py`` is Pyodide's copy of it as a memoryview."""

    def to_py(self) -> memoryview: ...


class MeshBuffers(Protocol):
    """A body's boundary as Manifold made it: ``num_prop`` numbers per vertex, the first
    three its position, and the runs a triangle's original and face ids are read through."""

    @property
    def num_prop(self) -> int: ...
    @property
    def vertices(self) -> Buffer: ...
    @property
    def triangles(self) -> Buffer: ...
    @property
    def run_index(self) -> Buffer: ...
    @property
    def run_original_id(self) -> Buffer: ...
    @property
    def face_id(self) -> Buffer: ...


class Tagged(Protocol):
    """A body rebuilt with a face id on every triangle, and the original id marking it."""

    @property
    def body(self) -> int: ...
    @property
    def mark(self) -> int: ...


class Modeller(Protocol):
    """The calls ``web/src/modeller.ts`` answers: handles in, handles and buffers out.

    Written down because it is the whole of the contract with the JavaScript, and a mistyped
    call across a foreign-function boundary is otherwise found by a browser at run time and
    nowhere else. Positional arguments only: a JavaScript function has no keywords.
    """

    def section(self, rings: array[float], lengths: array[int], /) -> int: ...
    def extrude(
        self,
        section: int,
        height: float,
        divisions: int = 0,
        twist: float = 0.0,
        scale: float = 1.0,
        /,
    ) -> int: ...
    def revolve(self, section: int, segments: int, degrees: float, /) -> int: ...
    def transform(self, body: int, columns: array[float], /) -> int: ...
    def union(self, a: int, b: int, /) -> int: ...
    def difference(self, a: int, b: int, /) -> int: ...
    def intersection(self, a: int, b: int, /) -> int: ...
    def hull(self, points: array[float], /) -> int: ...
    def imported(self, vertices: array[float], triangles: array[int], /) -> int: ...
    def tagged(self, body: int, faces: array[int], /) -> Tagged: ...
    def mesh(self, body: int, /) -> MeshBuffers: ...
    def num_tri(self, body: int, /) -> int: ...
    def is_empty(self, body: int, /) -> bool: ...
    def volume(self, body: int, /) -> float: ...
    def min_gap(self, a: int, b: int, upto: float, /) -> float: ...
    def release(self) -> None: ...


@dataclass(frozen=True, slots=True)
class JsKernel:
    """:class:`bench.kernel.Kernel` on a Manifold living in JavaScript.

    ``js`` is the modeller; ``refused`` is the exception a failed call to it raises -
    Pyodide's ``JsException`` in the browser; ``tracer`` is handed a ``bench.kernel.<call>``
    span for every call. No state beyond those three: a kernel is handed a tree and answers
    about it.
    """

    js: Modeller
    refused: type[Exception]
    tracer: Tracer = SILENT

    def mesh(self, solid: Solid) -> Mesh:
        """``solid`` evaluated to triangles, each carrying the ref of the face it lies on. A
        modeller that refused is the :class:`ValueError` :meth:`_answer` raises."""
        tags: _Tags = {}
        return self._answer("mesh", lambda: _meshed(self.js, _body(self.js, solid, "", tags), tags))

    def volume(self, solid: Solid) -> float:
        """How much material ``solid`` encloses, in cubic millimetres."""
        return self._answer("volume", lambda: float(self.js.volume(_body(self.js, solid, "", {}))))

    def min_gap(self, a: Solid, b: Solid, *, upto: float) -> float:
        """The smallest distance between the surfaces of ``a`` and ``b``, stopping at
        ``upto``."""
        js = self.js
        return self._answer(
            "min_gap", lambda: float(js.min_gap(_body(js, a, "", {}), _body(js, b, "", {}), upto))
        )

    def _answer[T](self, call: str, work: Callable[[], T]) -> T:
        """``work``'s answer, timed as ``bench.kernel.<call>``, with everything the modeller
        made for it freed afterwards.

        Raises:
            ValueError: if the modeller refused, naming the call and its reason.
        """
        try:
            with timed(self.tracer, f"bench.kernel.{call}") as attributes:
                answer = work()
                if isinstance(answer, Mesh):
                    attributes["bench.mesh.triangles"] = len(answer.refs)
                return answer
        except self.refused as exc:
            _log.warning(
                "the modeller refused %s: %s",
                call,
                exc,
                extra=fields(**{"bench.kernel.call": call}),
            )
            msg = f"the modeller could not answer {call}: {exc}"
            raise ValueError(msg) from exc
        finally:
            self.js.release()


_log = logging.getLogger(__name__)
"""This module's log records: a refusal from the modeller, which is also an error scene."""


# ---- the tree, evaluated ---------------------------------------------------------------


def _body(js: Modeller, solid: Solid, prefix: str, tags: _Tags) -> int:
    """``solid`` built, everything under it named beneath ``prefix``: a bare solid's faces
    answer to ``top``, and the same solid inside a part to ``plate/top`` once the part's label
    is put in front."""
    return _node(js, solid.node, under(prefix, solid.label), tags)


def _node(js: Modeller, node: Node, under: str, tags: _Tags) -> int:
    """One node built. ``under`` is the ref path its named faces hang from."""
    match node:
        case Extrude() | Revolve():
            return _swept(js, node, under, tags)
        case Union(a, b):
            return js.union(_body(js, a, under, tags), _body(js, b, under, tags))
        case Difference(base, tool):
            return js.difference(_body(js, base, under, tags), _body(js, tool, under, tags))
        case Intersection(a, b):
            return js.intersection(_body(js, a, under, tags), _body(js, b, under, tags))
        case Hull(parts):
            return _hulled(js, parts, under, tags)
        case Imported(vertices, triangles):
            return _imported(js, vertices, triangles, under, tags)
        case Moved(inner, at):
            # A move of a move is one move: the modeller rounds what it moves onto 32-bit
            # floats (``web/src/modeller.ts``, task-77), so a body turned, shifted and mated
            # back is rounded once, where it ends, and lands where one move there puts it.
            while isinstance(inner, Moved):
                at, inner = at @ inner.at, inner.node
            return js.transform(_node(js, inner, under, tags), meshing.column_major(at))
        case Swept():
            return _carried(js, node, under, tags)
        case _:
            assert_never(node)


def _swept(js: Modeller, node: Extrude | Revolve, under: str, tags: _Tags) -> int:
    """A profile swept: built flat in its own frame, every triangle given the face it lies on
    while it is still the only thing in the mesh, then put where it belongs.

    Manifold sweeps a cross-section up ``+Z`` from the origin and knows nothing of planes,
    which is why the frame is applied last - after the marking.
    """
    rings = profile_rings(node)
    refs = meshing.face_refs(node, under)
    profile = js.section(*meshing.section(rings))
    match node:
        case Extrude(_, distance) if straight(node):
            body = js.extrude(profile, abs(distance))
            if distance < 0.0:
                body = js.transform(body, meshing.column_major(_lifted(distance)))
            built = js.mesh(body)
            faces = meshing.extruded_faces(
                built.vertices.to_py(), built.num_prop, built.triangles.to_py(), distance, rings
            )
        case Extrude(_, distance, twist, scale):
            body = _twisted(js, profile, rings, distance, twist, scale)
            built = js.mesh(body)
            faces = meshing.extruded_faces(
                built.vertices.to_py(),
                built.num_prop,
                built.triangles.to_py(),
                distance,
                rings,
                twist,
                scale,
            )
        case Revolve(_, _, angle):
            turn = math.degrees(min(angle, math.tau))
            body = js.revolve(profile, meshing.segments(rings), turn)
            built = js.mesh(body)
            faces = meshing.revolved_faces(
                built.vertices.to_py(),
                built.num_prop,
                built.triangles.to_py(),
                angle,
                rings,
                len(refs),
            )
        case _:
            assert_never(node)
    marked = js.tagged(body, faces)
    for face, ref in enumerate(refs):
        tags[marked.mark, face] = ref
    return js.transform(marked.body, meshing.column_major(meshing.sweep_frame(node)))


def _twisted(
    js: Modeller, profile: int, rings: tuple[Ring, ...], distance: float, twist: float, scale: float
) -> int:
    """A twisted or tapered extrusion, built from ``z = 0`` to ``z = distance``.

    Manifold sweeps up ``+Z`` and turns counter-clockwise about it, so a sweep the other way
    is built upwards with the turn reversed and then reflected through its own profile's
    plane: the profile stays where it was drawn, unturned and full size, and the far end
    comes out below it, turned the right way about the sweep.
    """
    turn = twist if distance >= 0.0 else -twist
    body = js.extrude(
        profile,
        abs(distance),
        meshing.divisions(rings, twist, scale),
        math.degrees(turn),
        scale,
    )
    if distance >= 0.0:
        return body
    return js.transform(body, meshing.column_major(_REFLECTED))


_REFLECTED = Transform(((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, -1.0, 0.0)))
"""The reflection through ``z = 0`` that turns a sweep built upwards into one hanging below
its profile."""


def _carried(js: Modeller, node: Swept, under: str, tags: _Tags) -> int:
    """A profile carried along its path, meshed here and handed over whole, every triangle
    given the face it was laid for.

    The modeller has no sweep, so :func:`bench.meshing.swept` lays the rings and caps and says
    which face each triangle is, and the modeller only takes the mesh in. Taking it in
    reorders the triangles, but each one comes back with the index of a triangle it was made
    from - one of its own coplanar neighbours, all of which lie on the same face - so the face
    it lies on is read through that index before it is marked.
    """
    vertices, triangles, faces = meshing.swept(node)
    body = js.imported(vertices, triangles)
    made_from = js.mesh(body).face_id.to_py()
    marked = js.tagged(body, array("I", (faces[one] for one in made_from)))
    for face, ref in enumerate(meshing.face_refs(node, under)):
        tags[marked.mark, face] = ref
    return marked.body


def _lifted(distance: float) -> Transform:
    """The move that puts an extrusion swept the wrong way back under its own profile."""
    return translation(Vector(0.0, 0.0, distance))


def _hulled(js: Modeller, parts: tuple[Solid, ...], under: str, tags: _Tags) -> int:
    """The convex hull of its parts, as one unnamed surface answering to the enclosing solid."""
    cloud = array("d")
    for one in parts:
        cloud.extend(_cloud(js, one.node, identity()))
    body = js.hull(cloud)
    marked = js.tagged(body, array("I", bytes(4 * js.num_tri(body))))
    tags[marked.mark, 0] = Ref(under) if under else None
    return marked.body


def _imported(
    js: Modeller,
    vertices: tuple[float, ...],
    triangles: tuple[int, ...],
    under: str,
    tags: _Tags,
) -> int:
    """A body somebody else made, built from its own triangles.

    The bulk numbers cross as buffers, the way a hull's point cloud already does; the body
    that comes back is marked as one unnamed surface answering to the enclosing solid, for
    the same reason a hull is - a file has no names in it, so there is nothing under it to
    name. Marking costs an extra mesh-and-rebuild on a body that can be tens of thousands
    of triangles, which is what makes an imported solid's own label mean anything.

    A mesh Manifold will not take - an open boundary, a non-finite vertex, an index past the
    end - throws in there and becomes the same :class:`ValueError` every other refused call
    does. Nothing is checked on this side.
    """
    body = js.imported(array("d", vertices), array("I", triangles))
    marked = js.tagged(body, array("I", bytes(4 * js.num_tri(body))))
    tags[marked.mark, 0] = Ref(under) if under else None
    return marked.body


def _cloud(js: Modeller, node: Node, at: Transform) -> array[float]:
    """Every point of a subtree that a hull could stand on, ``x, y, z`` in turn."""
    match node:
        case Moved(inner, t):
            return _cloud(js, inner, at @ t)
        case Extrude(_, distance) if abs(distance) <= TOL:
            return meshing.flat_points(node, at)
        case _:
            built = js.mesh(_node(js, node, "", {}))
            return meshing.placed(built.vertices.to_py(), built.num_prop, at)


def _meshed(js: Modeller, body: int, tags: _Tags) -> Mesh:
    """The evaluated body as a :class:`~bench.kernel.Mesh`, every triangle mapped back to a
    ref through its ``(run_original_id, face_id)`` pair."""
    if js.is_empty(body):
        return Mesh((), (), ())
    built = js.mesh(body)
    refs = meshing.triangle_refs(
        built.run_index.to_py(), built.run_original_id.to_py(), built.face_id.to_py(), tags
    )
    return meshing.mesh(built.vertices.to_py(), built.num_prop, built.triangles.to_py(), refs)
