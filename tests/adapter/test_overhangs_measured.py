"""Adapter: every overhang on a part, and a part handed to the checks whole, on the shipped kernel.

task-78 found ``check_overhangs`` naming one face per part - the steepest, and at a tie the
first it met - so moving the vent onto ducts hid a side port lying on its side behind a
groove ledge. Each part here has more than one place that needs support, and every one of
them has to come back, steepest first and the larger first between two that lean alike.

task-81 found the same part passed two ways in one script - a ``Part`` to ``check_fits``, its
bare solid and its ``Orient`` again to ``check_overhangs``. The rod below is handed both ways
and must read the same, its own way up read off its ``Printed`` stock and an ``orient``
given still winning.

The numbers in each test's text were read off this kernel.
"""

from pathlib import Path
from typing import Any

import pytest

from tools import stack

pytestmark = pytest.mark.adapter

_MISSING = stack.missing()
if _MISSING is not None:
    pytest.skip(_MISSING, allow_module_level=True)

_CASES = Path(__file__).with_name("overhang_cases.py")
_TOTE = Path(__file__).resolve().parents[2] / "examples" / "systainer_tote.py"

PROGRAM = """\
import json

from pyodide.ffi import JsException

import overhang_cases
from bench.adapters.browser import JsKernel


def main(js, given):
    return json.dumps(overhang_cases.measured(JsKernel(js, JsException), json.loads(given)))
"""


@pytest.fixture(scope="module")
def measured() -> dict[str, Any]:
    """Every part this module reads, built and measured once by the shipped kernel."""
    found: dict[str, Any] = stack.run(
        PROGRAM, _TOTE.read_text(), modules={"overhang_cases.py": _CASES.read_text()}
    )
    return found


def _places(message: str) -> list[tuple[str, int]]:
    """Each place a finding's sentence names, as the face and the whole degrees it leans."""
    listed = message.split(": ", 1)[1].split("; ")
    named = [one.split(" over ")[0] for one in listed if " leans " in one]
    return [
        (face, int(lean.removesuffix(" degrees")))
        for face, lean in (one.split(" leans ") for one in named)
    ]


# ---- every place past the limit is found ----------------------------------------------------


def test_a_ledge_and_a_side_port_on_one_part_are_both_reported(measured: dict[str, Any]) -> None:
    """AC#3, the vent: a ledge run out from a post and a tube lying on its side run out from
    the other side. Before, one of them - the first 90 degree face met - was all it said.
    Read: the port's underside 90 degrees over 351 mm2, the ledge's 90 over 300, and the
    bore's crown 82 over 237 - three places on three faces, each with its size."""
    message, refs = measured["vent"]
    assert message.startswith("3 places lean further off the build direction")
    assert "PLA holds up 45" in message
    assert _places(message) == [("port/side-0", 90), ("ledge/bottom", 90), ("bore/side-0", 82)]
    assert refs == ["port/side-0", "ledge/bottom", "bore/side-0"]
    assert "351 mm2, 29.0 by 11.0 mm across" in message


def test_two_overhangs_of_the_same_lean_on_one_face_are_both_reported(
    measured: dict[str, Any],
) -> None:
    """AC#3: a bar across the top of a post hangs off both sides - one ``bottom``, two
    ceilings of the same lean and the same size, 150 mm2 each. Both are named; the face is
    one ref, once."""
    message, refs = measured["bar"]
    assert _places(message) == [("bar/bottom", 90), ("bar/bottom", 90)]
    assert message.count("150 mm2, 15.0 by 10.0 mm across") == 2
    assert refs == ["bar/bottom"]


def test_between_two_that_lean_alike_the_larger_comes_first(measured: dict[str, Any]) -> None:
    """Two caps, both ceilings: the 20 mm one is named before the 12 mm one though it was
    built second, because it is more to support."""
    message, refs = measured["caps"]
    assert _places(message) == [("cap-1/bottom", 90), ("cap-0/bottom", 90)]
    assert refs == ["cap-1/bottom", "cap-0/bottom"]


def test_the_steepest_comes_first_whatever_its_size(measured: dict[str, Any]) -> None:
    """A slab tilted to lean 60 degrees on top of a post, built first and 300 mm2 of it, and
    a ledge leaning 90 below it built after, 200 mm2: the ledge is named first. The post cuts
    the slab's underside in two, and both pieces are there."""
    message, refs = measured["tilted"]
    assert _places(message) == [("ledge/bottom", 90), ("slab/bottom", 60), ("slab/bottom", 60)]
    assert refs == ["ledge/bottom", "slab/bottom"]


def test_past_five_places_the_sentence_counts_the_rest_and_the_refs_name_them(
    measured: dict[str, Any],
) -> None:
    """AC#2: seven caps alike. The sentence names five and says how many more; the refs name
    all seven, in the same order - nothing past the cap is lost, only left unspelled."""
    message, refs = measured["many"]
    assert message.startswith("7 places lean")
    assert [face for face, _ in _places(message)] == [f"cap-{n}/bottom" for n in range(5)]
    assert message.endswith("; and 2 more")
    assert refs == [f"cap-{n}/bottom" for n in range(7)]


def test_the_totes_finding_names_only_the_bridges_once_the_lugs_and_ribs_are_fixed(
    measured: dict[str, Any],
) -> None:
    """AC#1 on a shipped example: before task-78's fix the tote read ``socket-1`` alone, and
    after it eighteen places - four socket ceilings, two grip tops, and the undersides of
    two latch lugs and ten ribs hanging off the wall with nothing under them. task-84 gave
    each lug a gusset and stood each rib on the bed, so six places are left - the same
    sockets and grip tops as before, 14.6 by 14.6 mm and 96.0 by 2.4 mm across, still one
    finding - and none of them a lug, a gusset or a rib."""
    scene = measured["tote"]
    assert scene["ok"], scene
    (found,) = [one for one in scene["violations"] if one["check"] == "overhangs"]
    assert found["message"].startswith("6 places lean")
    assert "14.6 by 14.6 mm across" in found["message"]
    assert "96.0 by 2.4 mm across" in found["message"]
    named = found["refs"]
    sockets = {f"tote/socket-{n}" for n in range(1, 5)}
    grips = {"tote/grip-left/top", "tote/grip-right/top"}
    assert set(named) == sockets | grips
    assert len(named) == 6
    assert not any("latch" in one or "gusset" in one or "rib-" in one for one in named)
    assert set(named) <= set(scene["refs"])


# ---- a part is handed whole -------------------------------------------------------------------


def test_a_printed_part_is_checked_the_way_its_stock_says_it_prints(
    measured: dict[str, Any],
) -> None:
    """task-81 AC#1 and #2: a rod lying along X leans past PLA's limit drawn as it is - both
    flanks of its underside, 54 degrees, the strip between them on the bed - and nothing
    stood on its end. Handed as a part, each way reads exactly what the bare rod with the
    same ``orient`` reads; an ``orient`` given overrides the part's own."""
    rod = measured["rod"]
    assert rod["bare_flat"] is not None
    assert _places(rod["bare_flat"][0]) == [("side-0", 54), ("side-0", 54)]
    assert rod["bare_on_end"] is None
    assert rod["part_flat"] == rod["bare_flat"]
    assert rod["part_on_end"] == rod["bare_on_end"]
    assert rod["overridden"] == rod["bare_flat"]


def test_a_wall_reads_the_same_on_the_part_as_on_its_body(measured: dict[str, Any]) -> None:
    """task-81: ``wall`` takes the part too, and reads its body - a wall is as thick lying
    down as standing up. A box hollowed to 0.5 mm reads 0.50 either way."""
    found = measured["wall"]
    assert found["part"] == found["bare"]
    assert found["part"][0].startswith("the thinnest wall is 0.50 mm")


def test_a_script_hands_check_overhangs_the_part_and_its_finding_names_the_part(
    measured: dict[str, Any],
) -> None:
    """``check_overhangs(tee)`` with nothing beside it: the ``Printed`` stock says the way up
    and the plastic, and the finding's refs come back under the part's label, the way the
    scene's ref table holds them - the run ties the finding to the part's own shape."""
    scene = measured["script"]
    assert scene["ok"], scene
    (found,) = scene["violations"]
    assert found["check"] == "overhangs"
    assert found["line"] == 6
    assert found["refs"] == ["tee/bar/bottom"]
    assert set(found["refs"]) <= set(scene["refs"])
