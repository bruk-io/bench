"""Functional: the build's hash watches everything the build is made from.

:func:`tools.preview.sources_hash` decides whether ``web/dist`` is rebuilt. Whatever
``web/scripts/bundle-py.mjs`` reads from the repository ends up inside the app, so a directory
it reads and the hash does not watch is a change the e2e suite and ``tools.qa`` never see.
"""

import re

import pytest

from tools.preview import ROOT, WATCHED

pytestmark = pytest.mark.functional

_READ = re.compile(r'join\(ROOT, "([^"]+)"')
"""A top-level directory the bundling script reads, as it names it: ``join(ROOT, "examples")``."""


def test_every_directory_the_python_bundle_reads_is_watched() -> None:
    script = (ROOT / "web" / "scripts" / "bundle-py.mjs").read_text()
    read = set(_READ.findall(script))
    assert read, "found none - has bundle-py.mjs stopped naming its sources as join(ROOT, ...)?"
    watched = {w.split("/")[0] for w in WATCHED}
    missing = {r for r in read if r not in watched and not any(w.startswith(r) for w in WATCHED)}
    assert not missing, f"bundle-py.mjs reads {sorted(missing)}, which the build hash ignores"
