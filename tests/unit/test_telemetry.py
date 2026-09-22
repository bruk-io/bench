"""Unit: :mod:`bench.telemetry`, spans timed and handed to a tracer, and the logging defaults.

The tracer here is a hand-written list of what it was given, which is the whole of what a
tracer is.
"""

import logging
from dataclasses import dataclass, field

import pytest

from bench.telemetry import FIELDS, SILENT, Span, fields, timed

pytestmark = pytest.mark.unit


@dataclass
class _Kept:
    spans: list[Span] = field(default_factory=list)

    def record(self, span: Span, /) -> None:
        self.spans.append(span)


def test_a_block_is_recorded_as_one_span_with_its_name_and_attributes() -> None:
    kept = _Kept()
    with timed(kept, "bench.work", **{"bench.part.ref": "lid"}):
        pass
    [span] = kept.spans
    assert span.name == "bench.work"
    assert span.attributes == {"bench.part.ref": "lid"}
    assert span.duration >= 0.0
    assert span.start > 1_600_000_000, "the start is a wall-clock time, not a counter"


def test_a_block_can_add_what_it_learned_by_the_end() -> None:
    kept = _Kept()
    with timed(kept, "bench.work") as attributes:
        attributes["bench.mesh.triangles"] = 482
    assert kept.spans[0].attributes == {"bench.mesh.triangles": 482}


def test_a_block_that_raises_is_recorded_with_its_error_type_and_still_raises() -> None:
    kept = _Kept()
    with pytest.raises(KeyError), timed(kept, "bench.work"):
        raise KeyError("nope")
    assert kept.spans[0].attributes == {"error.type": "KeyError"}


def test_the_silent_tracer_takes_a_span_and_keeps_nothing() -> None:
    with timed(SILENT, "bench.work"):
        pass


def test_structured_fields_ride_under_one_key() -> None:
    assert fields(parts=3, ok=True) == {FIELDS: {"parts": 3, "ok": True}}


def test_importing_the_package_configures_no_logging() -> None:
    """A library's records are the host's to route, so importing it touches nothing."""
    assert logging.getLogger("bench").handlers == []
