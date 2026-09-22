"""Functional: what a run says about itself - the spans it times and the record it logs.

Real runs of real scripts, with a tracer that keeps what it is given and pytest's own log
capture, so every check reads what a host attached to a run would have received.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from bench import script
from bench.telemetry import FIELDS, Span

pytestmark = pytest.mark.functional

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "gridfinity_cabinet.py"

CHECKED = """\
from bench import *
from bench.library.print import H2D, PLA

block = cuboid(20, 20, 5)
check_fits(block, H2D)
show(part("block", block, Printed(PLA)))
"""


@dataclass
class _Kept:
    spans: list[Span] = field(default_factory=list)

    def record(self, span: Span, /) -> None:
        self.spans.append(span)

    def named(self, name: str) -> list[Span]:
        return [one for one in self.spans if one.name == name]


def test_a_run_is_one_span_with_its_stretches_inside_it() -> None:
    kept = _Kept()
    scene = script.run(EXAMPLE.read_text(), tracer=kept)
    assert scene["ok"], scene
    names = {one.name for one in kept.spans}
    assert {
        "bench.run",
        "bench.script.compile",
        "bench.script.exec",
        "bench.scene.nest",
        "bench.scene.mesh",
        "bench.stage.layout",
        "bench.scene.files",
    } <= names
    [whole] = kept.named("bench.run")
    assert kept.spans[-1] is whole, "the run is recorded when it ends, after everything in it"
    assert whole.attributes["bench.run.ok"] is True
    inside = sum(
        one.duration for one in kept.spans if one is not whole and one.name != "bench.scene.mesh"
    )
    assert inside <= whole.duration + 1e-3


def test_every_part_is_its_own_mesh_span() -> None:
    kept = _Kept()
    scene = script.run(EXAMPLE.read_text(), tracer=kept)
    assert scene["ok"], scene
    refs = [one.attributes["bench.part.ref"] for one in kept.named("bench.scene.mesh")]
    assert refs == [part["ref"] for part in scene["parts"]]


def test_a_check_is_timed_by_its_name() -> None:
    kept = _Kept()
    assert script.run(CHECKED, tracer=kept)["ok"]
    assert len(kept.named("bench.check.fits")) == 1


def test_a_run_whose_script_raised_says_so_on_its_spans() -> None:
    kept = _Kept()
    assert not script.run("from bench import *\n\nshow(1 / 0)\n", tracer=kept)["ok"]
    [whole] = kept.named("bench.run")
    assert whole.attributes["bench.run.ok"] is False
    [executed] = kept.named("bench.script.exec")
    assert executed.attributes["error.type"] == "ZeroDivisionError"


def test_a_run_logs_how_it_ended(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="bench"):
        script.run(EXAMPLE.read_text())
        script.run("from bench import *\n\nshow(1 / 0)\n")
    finished, failed = (one for one in caplog.records if one.name == "bench.script")
    assert (finished.levelno, finished.getMessage()) == (logging.INFO, "run finished")
    assert getattr(finished, FIELDS)["bench.parts"] > 0
    assert failed.levelno == logging.WARNING
    assert "ZeroDivisionError" in failed.getMessage()
    assert getattr(failed, FIELDS)["code.lineno"] == 3


def test_an_untimed_run_needs_no_tracer() -> None:
    assert script.run(EXAMPLE.read_text())["ok"]
