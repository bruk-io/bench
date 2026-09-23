"""Functional: :mod:`tools.qa`'s own output hygiene.

A look round writes screenshots as it walks and a log beside them - see :func:`tools.qa._said`
and :data:`tools.qa.LOG`. A walk that raises before it finishes never reaches a line that
rewrites that log, so without :func:`tools.qa._reset` an old, unrelated walk's log stays behind
next to this walk's fresh screenshots - two runs that look like one and do not agree, which is
`task-53`'s own bug: a stale ``qa-log.txt`` from an earlier walk of `systainer_tote.py` sitting
beside a fresh, unrelated screenshot of `gridfinity_bin.py`, misread as one run.
"""

from pathlib import Path

import pytest

from tools.qa import _reset

pytestmark = pytest.mark.functional


def test_a_stale_log_does_not_survive_a_fresh_walk(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    stale_log = out / "qa-log.txt"
    stale_log.write_text("violations     warning overhangs: ... (tote/socket-1, line 257)\n")
    stale_shot = out / "qa-01-systainer_tote.png"
    stale_shot.write_bytes(b"stale")

    _reset(out)

    assert list(out.iterdir()) == []


def test_a_look_round_with_nothing_behind_it_is_left_alone(tmp_path: Path) -> None:
    """A fresh :data:`tools.qa.OUT` - the common case - is not a failure to clear."""
    out = tmp_path / "out"

    _reset(out)  # does not raise on a directory that does not exist yet

    assert not out.exists()
