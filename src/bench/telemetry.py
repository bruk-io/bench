"""Telemetry: what a run says to whoever is listening - its log records and its timed spans.

Both are the standards a collector already reads, so an OpenTelemetry exporter, Datadog or
Grafana can be attached by a host without anything here naming one.

**Logs** are the standard library's :mod:`logging`: one logger per module, under ``bench``.
Importing the package configures nothing - no handler, no level - because a library's records
are the host's to route: the app's worker attaches a handler to ``bench``, and a host that
attaches none gets :mod:`logging`'s own default, warnings on stderr. Structured fields ride
in ``extra`` under the one key :data:`FIELDS`; :func:`fields` builds that.

**Spans** are timed stretches of work, named the OpenTelemetry way - lowercase and dotted,
``bench.`` first - with attributes to match: ``bench.part.ref``, ``bench.mesh.triangles``, and
``error.type`` on a span whose work raised. A :class:`Tracer` is handed in at the edge the way a
kernel is, and :data:`SILENT`, which keeps nothing, is the default - so a run nobody is timing
pays for two clock reads a span and nothing else.
"""

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import NamedTuple, Protocol

Attribute = str | int | float | bool
"""What a span attribute or a log field may hold: the scalar kinds OpenTelemetry carries."""

FIELDS = "bench"
"""The ``extra`` key a log record's structured fields are kept under."""


class Span(NamedTuple):
    """One stretch of work: what it was, when it began (seconds since the epoch), how long it
    took (seconds), and what is worth knowing about it."""

    name: str
    start: float
    duration: float
    attributes: Mapping[str, Attribute]


class Tracer(Protocol):
    """Where finished spans go."""

    def record(self, span: Span, /) -> None: ...


@dataclass(frozen=True, slots=True)
class _Silent:
    """The tracer that keeps nothing."""

    def record(self, span: Span, /) -> None:
        return None


SILENT: Tracer = _Silent()
"""The default tracer: timing is on only when a host hands in one of its own."""


def fields(**values: Attribute) -> dict[str, dict[str, Attribute]]:
    """Structured fields for a log record, as ``extra`` carries them:
    ``log.info("built", extra=fields(parts=3))``."""
    return {FIELDS: values}


@contextmanager
def timed(tracer: Tracer, name: str, **attributes: Attribute) -> Iterator[dict[str, Attribute]]:
    """Time the block as one span called ``name``.

    The block is handed the span's attributes to add to - a count is often known only at the
    end. A block that raises is recorded all the same, with ``error.type`` naming what it
    raised, and the exception goes on its way untouched.
    """
    found: dict[str, Attribute] = dict(attributes)
    start = time.time()
    began = time.perf_counter()
    try:
        yield found
    except BaseException as exc:
        found["error.type"] = type(exc).__name__
        raise
    finally:
        tracer.record(Span(name, start, time.perf_counter() - began, found))
