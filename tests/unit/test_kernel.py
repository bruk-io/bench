"""Unit: :mod:`bench.kernel` alone - the seam, and the fact that it is only a seam.

There is nothing to compute here: the module is a Protocol and a transport record. What is
worth pinning is that the record says what it claims to say and that the Protocol is
structural, so a kernel can be written without importing anything of ours.
"""

from typing import get_type_hints

import pytest

from bench import Kernel, Mesh, Ref, Solid, cuboid

pytestmark = pytest.mark.unit


def test_a_mesh_is_flat_frozen_and_one_ref_per_triangle() -> None:
    """Three flat tuples, because that is what a renderer, an STL writer and a JSON scene
    all want. ``refs`` runs per triangle, not per vertex or per index."""
    mesh = Mesh(
        vertices=(0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
        triangles=(0, 1, 2),
        refs=(Ref("plate/top"),),
    )
    assert len(mesh.vertices) % 3 == 0
    assert len(mesh.refs) == len(mesh.triangles) // 3
    with pytest.raises(AttributeError):
        mesh.vertices = ()  # type: ignore[misc]


def test_the_kernel_protocol_is_exactly_three_methods() -> None:
    """Three, and no more: what the package asks a solid modeller for is what is drawn, what
    is measured, and how close two things come. Everything else a body can be asked is
    answered from the tree."""
    named = {
        name
        for name in vars(Kernel)
        if not name.startswith("_") and callable(getattr(Kernel, name, None))
    }
    assert named == {"mesh", "volume", "min_gap"}


def test_anything_with_the_three_methods_is_a_kernel() -> None:
    """Structural, not inherited: nothing has to import :class:`~bench.kernel.Kernel` to be
    one, which is what lets the browser bind a kernel written in another language."""

    class Counting:
        """A kernel that only counts what it is asked - enough to be one, and no geometry."""

        def __init__(self) -> None:
            self.asked: list[str] = []

        def mesh(self, solid: Solid) -> Mesh:
            self.asked.append("mesh")
            return Mesh((), (), ())

        def volume(self, solid: Solid) -> float:
            self.asked.append("volume")
            return 1.0

        def min_gap(self, a: Solid, b: Solid, *, upto: float) -> float:
            self.asked.append("min_gap")
            return upto

    def measured(kernel: Kernel, solid: Solid) -> float:
        return kernel.volume(solid)

    counting = Counting()
    assert measured(counting, cuboid(1, 1, 1)) == pytest.approx(1.0)
    assert counting.asked == ["volume"]


def test_the_mesh_record_is_what_the_protocol_promises() -> None:
    hints = get_type_hints(Mesh)
    assert set(hints) == {"vertices", "triangles", "refs"}
    assert get_type_hints(Kernel.mesh)["return"] is Mesh
