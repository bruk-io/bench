"""Functional: the wall a survey reports is the wall the wall check fails on.

Criterion #4 of the survey: the two measurements agree on the same object. They agree because
they are one function, :func:`bench.facets.thinnest`, and this is the check that nothing
between it and either caller changes the number. The kernel here is a hand-written fake that
answers with a mesh built in the test - a stand-in for a boundary, exactly as the README allows
for the modeller, and not a mock: nothing is patched, and it asserts on nothing.
"""

import math

import pytest

from bench import Mesh, Solid, Violation, cuboid, survey
from bench.checks import wall

pytestmark = pytest.mark.functional


class _Handed:
    """A kernel that hands back the one mesh it was given, whatever solid it is asked about."""

    def __init__(self, mesh: Mesh) -> None:
        self._mesh = mesh

    def mesh(self, solid: Solid) -> Mesh:
        return self._mesh

    def volume(self, solid: Solid) -> float:
        return 0.0

    def min_gap(self, a: Solid, b: Solid, *, upto: float) -> float:
        return upto


def _tube(outer: float, inner: float, sides: int, h: float) -> Mesh:
    """A closed tube on the origin, as in the unit tests: the shape whose thinnest wall is
    the gap between its skins rather than any dimension of its box."""

    def ring(radius: float, z: float) -> list[tuple[float, float, float]]:
        return [
            (
                radius * math.cos(2 * math.pi * k / sides),
                radius * math.sin(2 * math.pi * k / sides),
                z,
            )
            for k in range(sides)
        ]

    corners = (*ring(outer, 0.0), *ring(outer, h), *ring(inner, 0.0), *ring(inner, h))
    faces: list[tuple[int, int, int]] = []
    for k in range(sides):
        j = (k + 1) % sides
        faces.append((k, j, sides + j))
        faces.append((k, sides + j, sides + k))
        a, b, c, d = 2 * sides + k, 2 * sides + j, 3 * sides + j, 3 * sides + k
        faces.append((a, c, b))
        faces.append((a, d, c))
        faces.append((sides + k, sides + j, 3 * sides + j))
        faces.append((sides + k, 3 * sides + j, 3 * sides + k))
        faces.append((k, 2 * sides + j, j))
        faces.append((k, 2 * sides + k, 2 * sides + j))
    return Mesh(
        tuple(v for corner in corners for v in corner),
        tuple(i for face in faces for i in face),
        (None,) * len(faces),
    )


def test_the_survey_and_the_wall_check_report_the_same_thinnest_wall() -> None:
    mesh = _tube(10.0, 6.0, 36, 8.0)

    walls = survey(mesh).walls
    found = wall(cuboid(1, 1, 1), 100.0, kernel=_Handed(mesh))

    assert walls is not None
    assert isinstance(found, Violation)
    assert f"the thinnest wall is {walls.thinnest:.2f} mm" in found.message
    assert walls.thinnest == pytest.approx(4.0, abs=0.05)


def test_a_wall_check_that_passes_is_a_survey_wall_at_least_that_thick() -> None:
    mesh = _tube(10.0, 6.0, 36, 8.0)

    walls = survey(mesh).walls
    assert walls is not None
    assert wall(cuboid(1, 1, 1), walls.thinnest, kernel=_Handed(mesh)) is None
    assert wall(cuboid(1, 1, 1), walls.thinnest + 0.01, kernel=_Handed(mesh)) is not None


def test_the_survey_names_where_the_thinnest_wall_was_measured() -> None:
    """A plain box: the thinnest wall is the height, measured from the top or the bottom."""
    mesh = _box(30.0, 20.0, 10.0)

    walls = survey(mesh).walls
    assert walls is not None
    assert walls.at.z in (0.0, 10.0)
    assert walls.at.x == pytest.approx(10.0) or walls.at.x == pytest.approx(20.0)


def _box(w: float, d: float, h: float) -> Mesh:
    corners = (
        (0.0, 0.0, 0.0),
        (w, 0.0, 0.0),
        (w, d, 0.0),
        (0.0, d, 0.0),
        (0.0, 0.0, h),
        (w, 0.0, h),
        (w, d, h),
        (0.0, d, h),
    )
    faces = (
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    )
    return Mesh(
        tuple(v for corner in corners for v in corner),
        tuple(i for face in faces for i in face),
        (None,) * len(faces),
    )
