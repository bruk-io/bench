"""Adapter: *Open in slicer* (task-86), on a real Vite server, launching a real program.

``/__bench/prints/<project>/<file>`` writes a file a run made into the project's ``prints/`` and
opens it in the host's slicer with ``execFile`` and a fixed argument list. Nothing here stands in
for that: the slicer each server is pointed at (``BENCH_SLICER``, or a project's own
``[print] slicer``) is a small program of its own - a Python script that writes the arguments it
was started with to a file and exits - so the test reads back exactly what a slicer would have
been handed. The real Bambu Studio is never started here: every server this module runs names
its slicer, so the host's own default is never reached (``web/src/slicer.test.ts`` has that
choice, as data).

Every refusal is driven the way an attacker or an accident would drive it, with the path sent
byte for byte (:func:`test_projects_route.ask`'s reason), and each one checked twice: the answer
refuses, and the recording program was never started and nothing landed where it should not.
"""

import json
import shutil
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

import pytest

from tests.adapter.test_projects_route import Answer, Server, ask
from tools import preview
from tools.projects import VARIABLE

pytestmark = pytest.mark.adapter

_VITE = preview.WEB / "node_modules" / ".bin" / "vite"
if shutil.which("node") is None or not _VITE.is_file():
    pytest.skip("node or web/node_modules missing - run npm ci in web/", allow_module_level=True)

OPEN = "/__bench/prints"
SLICER = "BENCH_SLICER"

PACKAGE = b"PK\x03\x04 a 3MF's bytes, as the page posts them"


def _recorder(path: Path, record: Path, status: int = 0) -> Path:
    """A program at ``path`` that appends the arguments it was started with to ``record``, one
    JSON list a line, then exits ``status`` - saying why on stderr when that is not 0."""
    complaint = "" if status == 0 else "sys.stderr.write('cannot read that file\\n')\n"
    path.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        f"with open({str(record)!r}, 'a') as out:\n"
        "    out.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        f"{complaint}"
        f"sys.exit({status})\n"
    )
    path.chmod(0o755)
    return path


class Slicers(NamedTuple):
    """What each of the module's slicers recorded, by where it records."""

    host: Path
    project: Path
    grumpy: Path


class Hosted(NamedTuple):
    """A running server, and where each of its slicers records what it was started with."""

    server: Server
    records: Slicers


def _launches(record: Path) -> list[list[str]]:
    """Every argument list the recorder at ``record`` was started with, oldest first."""
    if not record.exists():
        return []
    return [json.loads(line) for line in record.read_text().splitlines()]


def _laid_out(base: Path) -> tuple[Path, Path, Slicers, Path]:
    """A root with a plain project, projects that name their own slicer, and every trap."""
    root = base / "projects"
    outside = base / "projects-evil"
    bin_ = base / "bin"
    for one in (root / "cabinet", outside, bin_):
        one.mkdir(parents=True)
    records = Slicers(base / "host.jsonl", base / "project.jsonl", base / "grumpy.jsonl")
    host = _recorder(bin_ / "host-slicer", records.host)
    own = _recorder(bin_ / "own slicer", records.project)
    grumpy = _recorder(bin_ / "grumpy-slicer", records.grumpy, status=3)
    (root / "cabinet" / "cabinet.py").write_text("x = 1\n")
    for name, slicer in (("named", own), ("grumpy", grumpy), ("missing", bin_ / "no-such-slicer")):
        (root / name).mkdir()
        (root / name / "bench.toml").write_text(
            f'[values]\nx = 1\n\n[print]\nslicer = "{slicer}"\n'
        )
    # prints/ a symlink out of the project, and a file in prints/ that is a symlink out.
    (root / "linked").mkdir()
    (root / "linked" / "prints").symlink_to(outside, target_is_directory=True)
    (root / "trap" / "prints").mkdir(parents=True)
    (outside / "secret.3mf").write_bytes(b"theirs")
    (root / "trap" / "prints" / "trap.3mf").symlink_to(outside / "secret.3mf")
    (root / "escape").symlink_to(outside, target_is_directory=True)
    return root, outside, records, host


@pytest.fixture(scope="module")
def hosted(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Hosted]:
    """``vite`` with the route pointed at a fresh root and the host's slicer at a recorder."""
    root, outside, records, host = _laid_out(tmp_path_factory.mktemp("slicer"))
    with preview.served(dev=True, env={VARIABLE: str(root), SLICER: str(host)}) as url:
        port = urlsplit(url).port
        assert port is not None
        yield Hosted(Server(port, root, outside), records)


def _open(
    hosted: Hosted, path: str, body: bytes = PACKAGE, headers: Mapping[str, str] | None = None
) -> Answer:
    return ask(hosted.server, "POST", path, body, headers)


# ---- AC#1: the file lands in prints/ and the slicer is started with it ---------------------


def test_the_file_lands_in_prints_and_the_hosts_slicer_is_started_with_it(hosted: Hosted) -> None:
    before = len(_launches(hosted.records.host))
    answer = _open(hosted, f"{OPEN}/cabinet/cabinet.3mf")
    assert answer.status == 200, answer
    assert answer.json() == {
        "file": "prints/cabinet.3mf",
        "slicer": "host-slicer",
        "said": "environment",
    }
    landed = hosted.server.root / "cabinet" / "prints" / "cabinet.3mf"
    assert landed.read_bytes() == PACKAGE
    # The server resolves the root through every symlink - /var is /private/var on macOS.
    launches = _launches(hosted.records.host)
    assert launches[before:] == [[str(landed.resolve())]]
    assert (hosted.server.root / "cabinet" / "prints" / ".gitignore").read_text() == "*\n"


def test_a_parts_stl_opens_too_and_a_second_click_replaces_the_first(hosted: Hosted) -> None:
    first = _open(hosted, f"{OPEN}/cabinet/Knob.STL", b"solid one\n")
    again = _open(hosted, f"{OPEN}/cabinet/Knob.STL", b"solid two\n")
    assert (first.status, again.status) == (200, 200)
    landed = hosted.server.root / "cabinet" / "prints" / "Knob.STL"
    assert landed.read_bytes() == b"solid two\n"
    assert _launches(hosted.records.host)[-2:] == [[str(landed.resolve())]] * 2


def test_the_projects_own_slicer_wins_over_the_hosts(hosted: Hosted) -> None:
    before = len(_launches(hosted.records.host))
    answer = _open(hosted, f"{OPEN}/named/named.3mf")
    assert answer.status == 200, answer
    assert answer.json()["said"] == "project"
    landed = hosted.server.root / "named" / "prints" / "named.3mf"
    # A path with a space in it is still one argument - the program, never a shell's words.
    assert _launches(hosted.records.project) == [[str(landed.resolve())]]
    assert len(_launches(hosted.records.host)) == before


def test_no_slicer_where_it_was_looked_for_is_said_plainly(hosted: Hosted) -> None:
    answer = _open(hosted, f"{OPEN}/missing/missing.3mf")
    assert answer.status == 502
    said = answer.json()
    assert said["refused"] == "slicer"
    assert str(said["message"]).startswith("No slicer was found: ")
    assert "no-such-slicer" in str(said["message"])
    assert "[print] slicer" in str(said["message"])
    # The file is written either way: it is the slicer, not the file, that was missing.
    assert (hosted.server.root / "missing" / "prints" / "missing.3mf").read_bytes() == PACKAGE


def test_a_slicer_that_says_no_is_reported_with_what_it_said(hosted: Hosted) -> None:
    answer = _open(hosted, f"{OPEN}/grumpy/grumpy.3mf")
    assert answer.status == 502
    said = answer.json()
    assert said["refused"] == "slicer"
    assert "exited 3 - cannot read that file" in str(said["message"])
    assert len(_launches(hosted.records.grumpy)) == 1


# ---- AC#2: confined to prints/, localhost only --------------------------------------------


def _untouched(hosted: Hosted, before: int) -> None:
    """Nothing was launched since ``before`` launches, and nothing landed outside the root."""
    assert len(_launches(hosted.records.host)) == before
    assert sorted(one.name for one in hosted.server.outside.iterdir()) == ["secret.3mf"]
    assert (hosted.server.outside / "secret.3mf").read_bytes() == b"theirs"


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        (f"{OPEN}/../projects-evil/planted.3mf", "name"),
        (f"{OPEN}/cabinet/..%2F..%2Fprojects-evil%2Fplanted.3mf", "name"),
        (f"{OPEN}/%2e%2e/planted.3mf", "name"),
        (f"{OPEN}/cabinet/%2Ftmp%2Fplanted.3mf", "name"),
        (f"{OPEN}//tmp/planted.3mf", "name"),
        (f"{OPEN}/cabinet/prints/planted.3mf", "name"),
        (f"{OPEN}/cabinet/.planted.3mf", "name"),
        (f"{OPEN}/cabinet/run.sh", "type"),
        (f"{OPEN}/cabinet/cabinet.py", "type"),
        (f"{OPEN}/nobody/planted.3mf", "missing"),
        (f"{OPEN}/escape/planted.3mf", "outside"),
        (f"{OPEN}/linked/planted.3mf", "link"),
        (f"{OPEN}/trap/trap.3mf", "link"),
    ],
)
def test_a_file_that_would_land_anywhere_but_the_projects_prints_is_refused(
    hosted: Hosted, path: str, reason: str
) -> None:
    before = len(_launches(hosted.records.host))
    answer = _open(hosted, path)
    assert answer.json()["refused"] == reason, (path, answer)
    _untouched(hosted, before)
    assert not (hosted.server.root / "cabinet" / "planted.3mf").exists()
    assert not (hosted.server.root / "cabinet" / "prints" / "planted.3mf").exists()
    assert not (hosted.server.root / "nobody").exists()


def test_only_a_post_opens_anything(hosted: Hosted) -> None:
    before = len(_launches(hosted.records.host))
    for method in ("GET", "PUT", "DELETE"):
        answer = ask(hosted.server, method, f"{OPEN}/cabinet/cabinet.3mf", PACKAGE)
        assert answer.json()["refused"] == "method", method
    _untouched(hosted, before)


def test_a_page_that_reached_the_host_by_its_lan_address_cannot_start_a_program(
    hosted: Hosted,
) -> None:
    """The tablet the projects route lets write (``test_projects_route``) may not open a
    slicer: a window would open on a desk nobody is at. Sent from this machine, so what is
    refused is the ``Host`` it was sent to; a socket from another machine is refused by its
    address as well, which ``web/src/route.test.ts`` has as data."""
    host = f"192.168.1.20:{hosted.server.port}"
    before = len(_launches(hosted.records.host))
    answer = _open(
        hosted,
        f"{OPEN}/cabinet/tablet.3mf",
        headers={"Host": host, "Origin": f"http://{host}", "Sec-Fetch-Site": "same-origin"},
    )
    assert answer.status == 403
    assert answer.json()["refused"] == "remote"
    _untouched(hosted, before)
    assert not (hosted.server.root / "cabinet" / "prints" / "tablet.3mf").exists()


@pytest.mark.parametrize(
    "headers",
    [{"Origin": "http://evil.example"}, {"Sec-Fetch-Site": "cross-site"}, {"Host": "evil.example"}],
)
def test_another_origin_or_a_rebound_name_cannot_start_a_program(
    hosted: Hosted, headers: Mapping[str, str]
) -> None:
    before = len(_launches(hosted.records.host))
    answer = _open(hosted, f"{OPEN}/cabinet/forged.3mf", headers=headers)
    assert answer.status == 403
    assert answer.json()["refused"] in {"origin", "host"}
    _untouched(hosted, before)
    assert not (hosted.server.root / "cabinet" / "prints" / "forged.3mf").exists()
