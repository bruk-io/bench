"""Unit: :mod:`bench.adapters.browser`, the kernel that walks a tree over the bridge.

The modeller on the far side is JavaScript, and is built for real in the adapter layer. What
is left for this one is the walk itself: what is asked for, in what order, with what numbers,
and what happens to an answer the modeller refuses to give.

The stand-in is a hand-written fake, not a double of Manifold: it hands out handles, writes
down every call, and meshes every body as the same one triangle facing up - which is enough
for the adapter's own decisions, face naming included, to be read off what comes back.
"""

import logging
import math
from array import array
from dataclasses import dataclass, field

import pytest

from bench import Point, Ref, Vector, cuboid, cut, cylinder, extrude, fill, move, name, rect
from bench.adapters.browser import JsKernel
from bench.telemetry import Span
from bench.topology import CHORD, Solid

pytestmark = pytest.mark.unit


class _Refused(Exception):
    """What the fake modeller raises for a call it will not answer."""


@dataclass(frozen=True, slots=True)
class _Buffer:
    data: memoryview

    def to_py(self) -> memoryview:
        return self.data


@dataclass(frozen=True, slots=True)
class _Built:
    num_prop: int
    vertices: _Buffer
    triangles: _Buffer
    run_index: _Buffer
    run_original_id: _Buffer
    face_id: _Buffer


@dataclass(frozen=True, slots=True)
class _Marked:
    body: int
    mark: int


@dataclass
class _Modeller:
    """A Manifold that is not there: every body is one upward triangle at ``z = 4``, marked
    with the last original id handed out, and every call is written down."""

    refuse: str | None = None
    asked: list[tuple[object, ...]] = field(default_factory=list)
    handles: int = 0
    marks: int = 100
    released: int = 0

    def _call(self, call: str, *args: object) -> int:
        self.asked.append((call, *args))
        if call == self.refuse:
            raise _Refused(f"no {call} today")
        self.handles += 1
        return self.handles

    def section(self, rings: array[float], lengths: array[int], /) -> int:
        return self._call("section", list(lengths))

    def extrude(self, section: int, height: float, /, *twisted: float) -> int:
        return self._call("extrude", height, *twisted)

    def revolve(self, section: int, segments: int, degrees: float, /) -> int:
        return self._call("revolve", segments, degrees)

    def transform(self, body: int, columns: array[float], /) -> int:
        return self._call("transform", list(columns))

    def union(self, a: int, b: int, /) -> int:
        return self._call("union")

    def difference(self, a: int, b: int, /) -> int:
        return self._call("difference")

    def intersection(self, a: int, b: int, /) -> int:
        return self._call("intersection")

    def hull(self, points: array[float], /) -> int:
        return self._call("hull")

    def imported(self, vertices: array[float], triangles: array[int], /) -> int:
        return self._call("imported", len(vertices), len(triangles))

    def tagged(self, body: int, faces: array[int], /) -> _Marked:
        self.marks += 1
        return _Marked(self._call("tagged", list(faces)), self.marks)

    def mesh(self, body: int, /) -> _Built:
        self._call("mesh")
        return _Built(
            3,
            _Buffer(memoryview(array("f", (0, 0, 4, 1, 0, 4, 0, 1, 4)))),
            _Buffer(memoryview(array("I", (0, 1, 2)))),
            _Buffer(memoryview(array("I", (0, 3)))),
            _Buffer(memoryview(array("I", (self.marks,)))),
            _Buffer(memoryview(array("I", (0,)))),
        )

    def num_tri(self, body: int, /) -> int:
        return 1

    def is_empty(self, body: int, /) -> bool:
        return False

    def volume(self, body: int, /) -> float:
        self._call("volume")
        return 800

    def min_gap(self, a: int, b: int, upto: float, /) -> float:
        self._call("min_gap", upto)
        return 1.5

    def release(self) -> None:
        self.released += 1


def _plate() -> Solid:
    return name(cuboid(20, 10, 4), "plate")


def _bored() -> Solid:
    return cut(_plate(), move(cylinder(2, 20), Vector(0, 0, -5)), label="bore")


def _calls(modeller: _Modeller) -> list[object]:
    return [one[0] for one in modeller.asked]


def test_a_primitive_is_built_meshed_marked_and_placed_in_that_order() -> None:
    modeller = _Modeller()
    JsKernel(modeller, _Refused).mesh(_plate())
    assert _calls(modeller) == ["section", "extrude", "mesh", "tagged", "transform", "mesh"]


def test_a_triangle_comes_back_named_by_the_face_it_was_marked_with() -> None:
    """The fake's triangle faces up, so the adapter marks it ``top`` and the result reads it
    back through the pair it wrote - the whole naming mechanism, on one triangle."""
    mesh = JsKernel(_Modeller(), _Refused).mesh(_plate())
    assert mesh.refs == (Ref("plate/top"),)
    assert mesh.vertices == (0, 0, 4, 1, 0, 4, 0, 1, 4)
    assert mesh.triangles == (0, 1, 2)


def test_a_plain_extrusion_is_asked_for_with_its_height_and_nothing_else() -> None:
    """Twist and scale are additive: an extrusion with neither crosses exactly as every
    extrusion did before they existed."""
    modeller = _Modeller()
    JsKernel(modeller, _Refused).mesh(_plate())
    assert [one for one in modeller.asked if one[0] == "extrude"] == [("extrude", 4.0)]


def test_a_twisted_extrusion_sends_its_divisions_degrees_and_scale() -> None:
    """The twist crosses in degrees, the way Manifold reads it, over enough copies of the
    section that no straight run between two strays further than the chord rule allows."""
    modeller = _Modeller()
    square = fill(rect(4, 4, Point(-2, -2)))
    JsKernel(modeller, _Refused).mesh(extrude(square, 10.0, twist=math.pi, scale=0.5))
    ((_, height, divisions, degrees, scale),) = [o for o in modeller.asked if o[0] == "extrude"]
    reach = math.hypot(2, 2)
    assert (height, degrees, scale) == (10.0, pytest.approx(180.0), 0.5)
    assert divisions == math.ceil(math.pi / (2 * math.acos(1 - CHORD / reach))) - 1


def test_a_twist_hanging_below_its_profile_is_built_upwards_turned_back_and_reflected() -> None:
    """Manifold only sweeps up, so a negative sweep is built up with the turn reversed and
    reflected through the profile's plane - the far end below it, turned the asked way."""
    modeller = _Modeller()
    JsKernel(modeller, _Refused).mesh(extrude(fill(rect(4, 4)), -10.0, twist=math.pi))
    ((_, height, _, degrees, _),) = [o for o in modeller.asked if o[0] == "extrude"]
    assert (height, degrees) == (10.0, pytest.approx(-180.0))
    reflection = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1]
    assert ("transform", reflection) in modeller.asked


def test_a_boolean_is_asked_for_after_both_of_its_operands() -> None:
    modeller = _Modeller()
    JsKernel(modeller, _Refused).mesh(_bored())
    calls = _calls(modeller)
    assert calls.count("extrude") == 2
    assert calls.index("difference") > max(i for i, call in enumerate(calls) if call == "extrude")


def test_a_move_crosses_as_a_column_major_matrix() -> None:
    modeller = _Modeller()
    JsKernel(modeller, _Refused).mesh(_bored())
    moves = [one[1] for one in modeller.asked if one[0] == "transform"]
    assert any(
        isinstance(columns, list) and columns[12:16] == [0, 0, -5, 1] for columns in moves
    ), moves


def test_upto_crosses_positionally_and_both_bodies_are_built_first() -> None:
    modeller = _Modeller()
    gap = JsKernel(modeller, _Refused).min_gap(_plate(), _bored(), upto=3.0)
    assert gap == pytest.approx(1.5)
    assert modeller.asked[-1] == ("min_gap", 3.0)


def test_a_volume_comes_back_as_a_float() -> None:
    volume = JsKernel(_Modeller(), _Refused).volume(_plate())
    assert isinstance(volume, float)
    assert volume == pytest.approx(800.0)


def test_a_refusal_is_a_value_error_naming_the_call_and_the_reason() -> None:
    """Never a crash and never a silent empty body: a modeller that refused becomes an error
    scene on the line of the script that asked."""
    with pytest.raises(ValueError, match="could not answer mesh: no difference today"):
        JsKernel(_Modeller(refuse="difference"), _Refused).mesh(_bored())


def test_everything_made_is_freed_whether_the_call_succeeded_or_not() -> None:
    fine = _Modeller()
    JsKernel(fine, _Refused).volume(_plate())
    refused = _Modeller(refuse="extrude")
    with pytest.raises(ValueError, match="could not answer mesh"):
        JsKernel(refused, _Refused).mesh(_plate())
    assert (fine.released, refused.released) == (1, 1)


def test_a_mistake_on_this_side_is_not_dressed_up_as_a_refusal() -> None:
    """Only the modeller's own exception becomes a :class:`ValueError`; anything else is a
    bug here and surfaces as itself - after the modeller is still told to free its memory."""

    class _Broken(_Modeller):
        def mesh(self, body: int, /) -> _Built:
            raise KeyError("a bug, not a refusal")

    broken = _Broken()
    with pytest.raises(KeyError):
        JsKernel(broken, _Refused).mesh(_plate())
    assert broken.released == 1


@dataclass
class _Kept:
    spans: list[Span] = field(default_factory=list)

    def record(self, span: Span, /) -> None:
        self.spans.append(span)


def test_every_kernel_call_is_timed_by_its_name() -> None:
    kept = _Kept()
    kernel = JsKernel(_Modeller(), _Refused, kept)
    kernel.mesh(_plate())
    kernel.volume(_plate())
    kernel.min_gap(_plate(), _bored(), upto=1.0)
    assert [one.name for one in kept.spans] == [
        "bench.kernel.mesh",
        "bench.kernel.volume",
        "bench.kernel.min_gap",
    ]
    assert kept.spans[0].attributes["bench.mesh.triangles"] == 1


def test_a_refusal_is_timed_with_its_error_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    kept = _Kept()
    with caplog.at_level(logging.WARNING, logger="bench"), pytest.raises(ValueError):
        JsKernel(_Modeller(refuse="extrude"), _Refused, kept).mesh(_plate())
    assert kept.spans[0].attributes["error.type"] == "_Refused"
    [record] = caplog.records
    assert record.name == "bench.adapters.browser"
    assert "refused mesh" in record.getMessage()
