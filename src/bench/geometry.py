"""Geometry: where things are. Pure maths, never named, millimetres, one tolerance.

``Point`` is a place; ``Vector`` is a displacement or direction. They share three
floats but not an algebra, and the operators below let the type checker enforce
the difference: place + move = place, place - place = move, place + place is an
error. ``Transform`` applies to both and treats them differently - a vector
ignores translation.
"""

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import assert_never, overload

TOL = 1e-6


@dataclass(frozen=True, slots=True)
class Vector:
    x: float
    y: float
    z: float = 0.0

    def __add__(self, other: Vector) -> Vector:
        if not isinstance(other, Vector):
            return NotImplemented
        return Vector(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vector) -> Vector:
        if not isinstance(other, Vector):
            return NotImplemented
        return Vector(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, k: float) -> Vector:
        return Vector(self.x * k, self.y * k, self.z * k)

    def __rmul__(self, k: float) -> Vector:
        return self * k

    def __truediv__(self, k: float) -> Vector:
        return Vector(self.x / k, self.y / k, self.z / k)

    def __neg__(self) -> Vector:
        return Vector(-self.x, -self.y, -self.z)

    def __abs__(self) -> float:
        """Length."""
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def __matmul__(self, other: Vector) -> float:
        """Dot product, the NumPy reading of ``@`` between two vectors."""
        return self.x * other.x + self.y * other.y + self.z * other.z

    def __iter__(self) -> Iterator[float]:
        yield from (self.x, self.y, self.z)


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float
    z: float = 0.0

    def __add__(self, other: Vector) -> Point:
        if not isinstance(other, Vector):
            return NotImplemented  # place + place has no meaning; Python raises TypeError
        return Point(self.x + other.x, self.y + other.y, self.z + other.z)

    @overload
    def __sub__(self, other: Point) -> Vector: ...
    @overload
    def __sub__(self, other: Vector) -> Point: ...
    def __sub__(self, other: Point | Vector) -> Point | Vector:
        match other:
            case Point():
                return Vector(self.x - other.x, self.y - other.y, self.z - other.z)
            case Vector():
                return Point(self.x - other.x, self.y - other.y, self.z - other.z)
            case _:
                return NotImplemented

    def __iter__(self) -> Iterator[float]:
        yield from (self.x, self.y, self.z)


ORIGIN = Point(0.0, 0.0, 0.0)
X = Vector(1.0, 0.0, 0.0)
Y = Vector(0.0, 1.0, 0.0)
Z = Vector(0.0, 0.0, 1.0)


# ---- vector functions ----------------------------------------------------------


def unit(v: Vector) -> Vector:
    """The direction of ``v`` with length 1.

    Raises:
        ValueError: if ``v`` is the zero vector, which has no direction.
    """
    length = abs(v)
    if length < TOL:
        msg = "zero vector has no direction"
        raise ValueError(msg)
    return v / length


def cross(a: Vector, b: Vector) -> Vector:
    return Vector(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)


def angle(a: Vector, b: Vector) -> float:
    """Unsigned angle between two vectors, in radians."""
    c = max(-1.0, min(1.0, unit(a) @ unit(b)))
    return math.acos(c)


def project(a: Vector, onto: Vector) -> Vector:
    """The component of ``a`` along ``onto``."""
    d = unit(onto)
    return d * (a @ d)


def perpendicular(v: Vector) -> Vector:
    """``v`` turned a quarter turn counter-clockwise in the XY plane."""
    return Vector(-v.y, v.x, v.z)


# ---- point functions -----------------------------------------------------------


def distance(p: Point, q: Point) -> float:
    return abs(q - p)


def lerp(p: Point, q: Point, t: float) -> Point:
    return p + (q - p) * t


def midpoint(p: Point, q: Point) -> Point:
    return lerp(p, q, 0.5)


def near(a: Point | Vector, b: Point | Vector, tol: float = TOL) -> bool:
    """Equality within tolerance; ``==`` stays exact so hashing keeps its promise."""
    return abs(a.x - b.x) <= tol and abs(a.y - b.y) <= tol and abs(a.z - b.z) <= tol


# ---- transforms ----------------------------------------------------------------

Row = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class Transform:
    """An affine map as three rows of a 4x4 matrix; the fourth row is implied."""

    rows: tuple[Row, Row, Row]

    @overload
    def __matmul__(self, other: Point) -> Point: ...
    @overload
    def __matmul__(self, other: Vector) -> Vector: ...
    @overload
    def __matmul__(self, other: Transform) -> Transform: ...
    def __matmul__(self, other: Point | Vector | Transform) -> Point | Vector | Transform:
        r0, r1, r2 = self.rows
        match other:
            case Point(x, y, z):
                return Point(
                    r0[0] * x + r0[1] * y + r0[2] * z + r0[3],
                    r1[0] * x + r1[1] * y + r1[2] * z + r1[3],
                    r2[0] * x + r2[1] * y + r2[2] * z + r2[3],
                )
            case Vector(x, y, z):
                return Vector(
                    r0[0] * x + r0[1] * y + r0[2] * z,
                    r1[0] * x + r1[1] * y + r1[2] * z,
                    r2[0] * x + r2[1] * y + r2[2] * z,
                )
            case Transform(rows):
                b = (*rows, (0.0, 0.0, 0.0, 1.0))
                out = tuple(
                    tuple(sum(a[k] * b[k][j] for k in range(4)) for j in range(4))
                    for a in self.rows
                )
                return Transform((_row(out[0]), _row(out[1]), _row(out[2])))
            case _:
                assert_never(other)


def _row(values: tuple[float, ...]) -> Row:
    a, b, c, d = values
    return (a, b, c, d)


def identity() -> Transform:
    return Transform(((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0)))


def translation(v: Vector) -> Transform:
    return Transform(((1.0, 0.0, 0.0, v.x), (0.0, 1.0, 0.0, v.y), (0.0, 0.0, 1.0, v.z)))


def rotation(axis: Axis, radians: float) -> Transform:
    """Rotation about an axis through a point (Rodrigues' formula)."""
    kx, ky, kz = unit(axis.direction)
    c, s = math.cos(radians), math.sin(radians)
    t = 1.0 - c
    linear = Transform(
        (
            (c + kx * kx * t, kx * ky * t - kz * s, kx * kz * t + ky * s, 0.0),
            (ky * kx * t + kz * s, c + ky * ky * t, ky * kz * t - kx * s, 0.0),
            (kz * kx * t - ky * s, kz * ky * t + kx * s, c + kz * kz * t, 0.0),
        )
    )
    o = axis.origin - ORIGIN
    return translation(o) @ linear @ translation(-o)


def inverse(t: Transform) -> Transform:
    """Inverse of an affine transform.

    Raises:
        ValueError: if the transform is singular (collapses space).
    """
    (a, b, c, tx), (d, e, f, ty), (g, h, i, tz) = t.rows
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < TOL:
        msg = "singular transform has no inverse"
        raise ValueError(msg)
    m = (
        ((e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det),
        ((f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det),
        ((d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det),
    )
    rows = tuple((r[0], r[1], r[2], -(r[0] * tx + r[1] * ty + r[2] * tz)) for r in m)
    return Transform((rows[0], rows[1], rows[2]))


# ---- planes and axes -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Axis:
    origin: Point
    direction: Vector


@dataclass(frozen=True, slots=True)
class Plane:
    """A local frame. Build with :func:`plane` so the directions are unit and orthogonal."""

    origin: Point
    normal: Vector
    x_dir: Vector

    @property
    def y_dir(self) -> Vector:
        return cross(self.normal, self.x_dir)


def plane(origin: Point, normal: Vector, x_dir: Vector | None = None) -> Plane:
    """A plane with unit, mutually perpendicular ``normal`` and ``x_dir``.

    When ``x_dir`` is omitted an arbitrary perpendicular is chosen; when given it
    is projected onto the plane and normalised.

    Raises:
        ValueError: if ``normal`` is zero or ``x_dir`` is parallel to it.
    """
    n = unit(normal)
    seed = (X if abs(n @ X) < 0.9 else Y) if x_dir is None else x_dir
    x = seed - n * (seed @ n)
    if abs(x) < TOL:
        msg = "x_dir is parallel to the normal"
        raise ValueError(msg)
    return Plane(origin, n, unit(x))


XY = plane(ORIGIN, Z, X)


def raised(on: Plane, d: float) -> Plane:
    """``on`` moved ``d`` millimetres along its own normal, pointing the same way.

    The sketch plane every maker script wanted: ``raised(XY, 5)`` is the flat world plane at
    ``z = 5``, and a wire drawn on it keeps the numbers it was drawn with, because a wire is
    read in the frame of the plane it is put on. A negative ``d`` drops the plane instead.
    """
    return Plane(on.origin + on.normal * d, on.normal, on.x_dir)


def to_world(p: Plane) -> Transform:
    """Map the plane's local coordinates into the enclosing frame."""
    x, y, n, o = p.x_dir, p.y_dir, p.normal, p.origin
    return Transform(((x.x, y.x, n.x, o.x), (x.y, y.y, n.y, o.y), (x.z, y.z, n.z, o.z)))


def to_local(p: Plane) -> Transform:
    """Map enclosing-frame coordinates into the plane's own."""
    return inverse(to_world(p))
