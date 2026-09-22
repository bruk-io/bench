"""Kernel: the seam a solid modeller is plugged into, and nothing behind it.

A :class:`~bench.topology.Solid` holds a recipe. Turning that recipe into triangles, a
volume or a distance is the one job in this package that needs a real solid modeller, and
the modeller is not part of the package: this module says what one has to be able to do, and
:mod:`bench.adapters` holds the implementations. Nothing here imports one, and no module
under ``src/bench`` outside ``adapters`` may - a pypeeker row says so and
``tests/unit/test_layer_graph.py`` enforces it - so ``import bench`` never needs a kernel
and a run without one still yields every ref, parameter and cut sheet.

Three methods, because three are what the rest of the package asks for: :meth:`Kernel.mesh`
for what is drawn and printed, :meth:`Kernel.volume` for what is measured, and
:meth:`Kernel.min_gap` for the clearance checks. A kernel is handed to
:func:`bench.script.run` the way ``show`` is - injected at the edge, never
imported in the middle.
"""

from dataclasses import dataclass
from typing import Protocol

from .model import Ref
from .topology import Solid


@dataclass(frozen=True, slots=True)
class Mesh:
    """A body's boundary as triangles, with the ref each one answers to.

    A transport record rather than a piece of topology: flat tuples of floats and ints
    because that is what a renderer, an STL writer and a JSON scene all want, and because a
    mesh crosses the wire to a browser whole. It is *built* from lists inside one function -
    a kernel fills three lists as it walks a result and freezes them once at the end, the
    same exception ``script._Recorder`` is - and it is frozen everywhere else.

    ``vertices`` is x, y, z per vertex, so vertex ``i`` is at ``vertices[3 * i : 3 * i + 3]``.
    ``triangles`` is three vertex indices per triangle, wound counter-clockwise seen from
    outside. ``refs`` has one entry per *triangle* - a third of ``triangles``'s length - and
    is the whole reason a mesh is worth building here rather than in the viewer: a click on
    a triangle is a click on ``plate/top``. It is ``None`` for a triangle belonging to no
    named face, which is what a hull leaves behind.
    """

    vertices: tuple[float, ...]
    triangles: tuple[int, ...]
    refs: tuple[Ref | None, ...]


class Kernel(Protocol):
    """What a solid modeller must be able to do for :mod:`bench`.

    Three methods and no state: a kernel is handed a tree and answers about it. An
    implementation lives under :mod:`bench.adapters` and is injected at the edge -
    ``run(..., kernel=...)`` - so the package itself never imports one.
    """

    def mesh(self, solid: Solid) -> Mesh:
        """``solid`` evaluated to triangles, each carrying the ref of the face it lies on.

        The refs are the ones :func:`bench.model.refs` hands out for the same bare solid, so
        a triangle of a plate's top face answers to ``top`` and one of its boss's crown to
        ``boss/top`` - the part's label is the caller's to add, exactly as it is for the ref
        table.
        """
        ...

    def volume(self, solid: Solid) -> float:
        """How much material ``solid`` encloses, in cubic millimetres."""
        ...

    def min_gap(self, a: Solid, b: Solid, *, upto: float) -> float:
        """The smallest distance between the surfaces of ``a`` and ``b``, in millimetres.

        Searching stops at ``upto``, which is what keeps it fast: two bodies further apart
        than that answer ``upto`` rather than their true distance, and a check asking
        whether a wall is thick enough never needs more. Bodies that touch or overlap
        answer zero.
        """
        ...
