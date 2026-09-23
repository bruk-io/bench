"""Adapter: the write lease on a project, on a real Vite server (task-47).

decision-9: "The host grants a write lease on a project, and holds it for one client." What
the lease decides is ``web/src/lease.ts`` and is tested beside it; what only a running server
can show is here - that the route refuses a write from anybody but the holder (not only the
page's own controls), that a lease lapses on the server's own clock, and that the leases are
the server's memory and nothing else: a restart voids every one and leaves nothing on the disk
(AC#8). The lease is shortened with ``BENCH_LEASE_MS`` so a lapse takes seconds, not a minute.

Requests go through :mod:`http.client`, as the route's own adapter checks do. The page's side
of it - two browsers, a reload, a closed tab - is ``tests/e2e/test_write_lease.py``.
"""

import http.client
import json
import shutil
import subprocess
import time
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

import pytest

from tools import preview
from tools.projects import VARIABLE

pytestmark = pytest.mark.adapter

_VITE = preview.WEB / "node_modules" / ".bin" / "vite"
_ESBUILD = preview.WEB / "node_modules" / ".bin" / "esbuild"
if shutil.which("node") is None or not _VITE.is_file():
    pytest.skip("node or web/node_modules missing - run npm ci in web/", allow_module_level=True)

LEASE_VARIABLE = "BENCH_LEASE_MS"
"""How long a lease lasts unheard, in milliseconds - ``web/server/projects.ts``'s variable."""

EXPIRY_MS = 2000
"""Short enough to watch a lease lapse; long enough that one request after another is not."""

LEASES = "/__bench/leases"
ROUTE = "/__bench/projects"


DESK = "desk-0123456789abcdef"
TABLET = "tablet-0123456789abcdef"


class Answer(NamedTuple):
    """What the server said."""

    status: int
    body: bytes

    def json(self) -> dict[str, object]:
        """The body, as the JSON object every answer here is."""
        found = json.loads(self.body)
        assert isinstance(found, dict)
        return found


def ask(
    port: int,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: Mapping[str, str] | None = None,
) -> Answer:
    """One request to the server on ``port``."""
    conn = http.client.HTTPConnection("localhost", port, timeout=10)
    try:
        conn.request(method, path, body=body or b"", headers={**(headers or {})})
        response = conn.getresponse()
        return Answer(response.status, response.read())
    finally:
        conn.close()


def as_holder(holder: str, label: str = "a test") -> dict[str, str]:
    """The headers a client holding leases as ``holder`` sends."""
    return {"X-Bench-Holder": holder, "X-Bench-Client": label}


def take(port: int, project: str, holder: str, act: str = "take") -> dict[str, object]:
    """``act`` on ``project``'s lease as ``holder``, and what the server said about it."""
    answer = ask(port, "POST", f"{LEASES}/{project}?act={act}", headers=as_holder(holder))
    assert answer.status == 200, answer.body
    return answer.json()


def put(port: int, project: str, file: str, body: bytes, holder: str | None) -> Answer:
    """Create ``project/file`` as ``holder``, or as a client holding nothing."""
    headers = {"If-None-Match": "*", **(as_holder(holder) if holder is not None else {})}
    return ask(port, "PUT", f"{ROUTE}/{project}/{file}", body, headers)


def everything(root: Path) -> set[str]:
    """Every file and directory under ``root``, hidden ones included."""
    return {str(one.relative_to(root)) for one in root.rglob("*")}


class Server(NamedTuple):
    """A running server and the directory it was pointed at."""

    port: int
    root: Path


@pytest.fixture
def server(tmp_path: Path) -> Iterator[Server]:
    """``vite`` over a root holding one project, with a lease that lapses in two seconds."""
    root = tmp_path / "projects"
    (root / "cabinet").mkdir(parents=True)
    (root / "cabinet" / "cabinet.py").write_text("w = 1\n")
    env = {VARIABLE: str(root), LEASE_VARIABLE: str(EXPIRY_MS)}
    with preview.served(dev=True, env=env) as url:
        port = urlsplit(url).port
        assert port is not None
        yield Server(port, root)


# ---- AC#1, AC#2: one writer, and everybody else told who -----------------------------------


def test_a_free_lease_is_taken_and_a_second_client_is_told_whose_it_is(server: Server) -> None:
    mine = take(server.port, "cabinet", DESK)
    assert mine["yours"] is True
    assert mine["holder"] is None
    assert mine["expiryMs"] == EXPIRY_MS
    assert mine["renewMs"] == EXPIRY_MS // 4

    answer = ask(
        server.port,
        "POST",
        f"{LEASES}/cabinet?act=take",
        headers=as_holder(TABLET, "Safari on an iPad"),
    )
    theirs = answer.json()
    assert theirs["yours"] is False
    holder = theirs["holder"]
    assert isinstance(holder, dict)
    assert holder["label"] == "a test"
    # Where the holder asked from, as a person would say it - not ``::1``, whichever stack the
    # request came over.
    assert holder["address"] == "localhost"
    # The holder id is what lets a client write, so it is never handed to another one.
    assert DESK.encode() not in answer.body


def test_the_route_refuses_a_write_to_a_leased_project_from_anybody_but_its_holder(
    server: Server,
) -> None:
    take(server.port, "cabinet", DESK)

    refused = put(server.port, "cabinet", "tablet.py", b"x = 1\n", TABLET)
    assert refused.status == 423
    said = refused.json()
    assert said["refused"] == "leased"
    assert "a test at localhost" in str(said["message"])
    assert said["file"] == "cabinet/tablet.py"
    # A client that says nothing about a lease is somebody else too.
    assert put(server.port, "cabinet", "curl.py", b"x = 1\n", None).json()["refused"] == "leased"
    assert not (server.root / "cabinet" / "tablet.py").exists()
    assert not (server.root / "cabinet" / "curl.py").exists()

    assert put(server.port, "cabinet", "desk.py", b"x = 1\n", DESK).status == 201
    # Another project, which nobody holds, is anybody's to write.
    assert put(server.port, "shelf", "shelf.py", b"x = 1\n", TABLET).status == 201


def test_a_rename_and_a_delete_are_refused_to_a_non_holder_too(server: Server) -> None:
    take(server.port, "cabinet", DESK)
    renamed = ask(
        server.port, "POST", f"{ROUTE}/cabinet/cabinet.py?to=moved.py", headers=as_holder(TABLET)
    )
    assert renamed.json()["refused"] == "leased"
    read = ask(server.port, "GET", f"{ROUTE}/cabinet/cabinet.py")
    assert read.status == 200
    deleted = ask(
        server.port,
        "DELETE",
        f"{ROUTE}/cabinet/cabinet.py",
        headers={**as_holder(TABLET), "If-Match": '"anything"'},
    )
    assert deleted.json()["refused"] == "leased"
    assert (server.root / "cabinet" / "cabinet.py").read_text() == "w = 1\n"


def test_a_project_with_no_directory_yet_can_be_leased_and_none_is_made(server: Server) -> None:
    assert take(server.port, "not-yet", DESK)["yours"] is True
    assert not (server.root / "not-yet").exists()


# ---- AC#3, AC#5: a lease lapses, and is let go ----------------------------------------------


def test_a_lease_whose_holder_stops_renewing_lapses_and_the_next_client_takes_it(
    server: Server,
) -> None:
    take(server.port, "cabinet", DESK)
    assert take(server.port, "cabinet", TABLET)["yours"] is False
    time.sleep(EXPIRY_MS / 1000 + 0.3)
    assert take(server.port, "cabinet", TABLET)["yours"] is True
    assert put(server.port, "cabinet", "desk.py", b"x = 1\n", DESK).json()["refused"] == "leased"


def test_a_renewing_holder_keeps_its_lease_past_the_expiry(server: Server) -> None:
    take(server.port, "cabinet", DESK)
    for _ in range(4):
        time.sleep(EXPIRY_MS / 1000 / 2)
        assert take(server.port, "cabinet", DESK)["yours"] is True
    assert take(server.port, "cabinet", TABLET)["yours"] is False


def test_a_released_lease_is_free_at_once_and_only_its_holder_can_release_it(
    server: Server,
) -> None:
    take(server.port, "cabinet", DESK)
    take(server.port, "cabinet", TABLET, "release")
    assert take(server.port, "cabinet", TABLET)["yours"] is False
    take(server.port, "cabinet", DESK, "release")
    assert take(server.port, "cabinet", TABLET)["yours"] is True


# ---- AC#6: a lease can be taken over ------------------------------------------------------


def test_a_held_lease_can_be_taken_over_and_the_old_holder_can_no_longer_write(
    server: Server,
) -> None:
    take(server.port, "cabinet", DESK)
    assert take(server.port, "cabinet", TABLET, "take-over")["yours"] is True
    assert put(server.port, "cabinet", "desk.py", b"x = 1\n", DESK).json()["refused"] == "leased"
    told = take(server.port, "cabinet", DESK)
    assert told["yours"] is False
    holder = told["holder"]
    assert isinstance(holder, dict)
    assert holder["label"] == "a test"


def test_acting_on_a_lease_needs_a_holder_and_a_page_from_elsewhere_cannot(
    server: Server,
) -> None:
    anonymous = ask(server.port, "POST", f"{LEASES}/cabinet?act=take-over")
    assert anonymous.json()["refused"] == "precondition"
    forged = ask(
        server.port,
        "POST",
        f"{LEASES}/cabinet?act=take-over",
        headers={
            **as_holder(TABLET),
            "Origin": "http://evil.example",
            "Sec-Fetch-Site": "cross-site",
        },
    )
    assert forged.json()["refused"] == "origin"
    looked = ask(server.port, "GET", f"{LEASES}/cabinet").json()
    assert looked["holder"] is None


# ---- AC#8: a restart voids every lease, and nothing is left behind -------------------------


def test_a_server_restart_voids_every_lease_and_leaves_nothing_on_disk(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    (root / "cabinet").mkdir(parents=True)
    (root / "cabinet" / "cabinet.py").write_text("w = 1\n")
    before = everything(root)
    # The default expiry: nothing here lapses on its own.
    env = {VARIABLE: str(root)}
    with preview.served(dev=True, env=env) as url:
        port = urlsplit(url).port
        assert port is not None
        assert take(port, "cabinet", DESK)["yours"] is True
        assert take(port, "cabinet", TABLET)["yours"] is False
    assert everything(root) == before, "a lease left something on the disk"
    with preview.served(dev=True, env=env) as url:
        port = urlsplit(url).port
        assert port is not None
        assert take(port, "cabinet", TABLET)["yours"] is True
    assert everything(root) == before


def test_a_lease_expiry_that_is_not_one_stops_the_server() -> None:
    with (
        pytest.raises(RuntimeError, match="BENCH_LEASE_MS must be a whole number"),
        preview.served(dev=True, env={LEASE_VARIABLE: "soon"}),
    ):
        pass


# ---- the client --------------------------------------------------------------------------

DRIVER = """\
import { host } from "./host.mjs";

const at = process.argv[2];
const desk = host(at, fetch, { id: "desk-0123456789abcdef", label: "Chrome on a Mac" });
const tablet = host(at, fetch, { id: "tablet-0123456789abcdef", label: "Safari on an iPad" });
const said = {};
said.taken = await desk.lease("client", "take");
said.told = await tablet.lease("client", "take");
said.refused = await tablet.create("client", "part.py", "a = 1\\n");
said.written = await desk.create("client", "part.py", "a = 1\\n");
said.over = await tablet.lease("client", "take-over");
said.looked = await desk.lease("client", "look");
said.released = await tablet.lease("client", "release", true);
said.free = await desk.lease("client", "look");
console.log(JSON.stringify(said));
"""


@pytest.mark.skipif(not _ESBUILD.is_file(), reason="web/node_modules/.bin/esbuild missing")
def test_the_apps_client_takes_and_is_refused_as_the_tab_it_is(
    server: Server, tmp_path: Path
) -> None:
    node = shutil.which("node")
    assert node is not None
    subprocess.run(
        (
            str(_ESBUILD),
            str(preview.WEB / "src" / "host.ts"),
            "--bundle",
            "--format=esm",
            "--platform=neutral",
            f"--outfile={tmp_path / 'host.mjs'}",
        ),
        check=True,
        capture_output=True,
        timeout=120,
    )
    (tmp_path / "drive.mjs").write_text(DRIVER)
    done = subprocess.run(
        (node, str(tmp_path / "drive.mjs"), f"http://localhost:{server.port}"),
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    said = json.loads(done.stdout.splitlines()[-1])

    assert said["taken"]["value"]["yours"] is True
    assert said["told"]["value"]["yours"] is False
    assert said["told"]["value"]["holder"]["label"] == "Chrome on a Mac"
    assert said["refused"]["refusal"]["refused"] == "leased"
    assert said["written"]["ok"]
    assert said["over"]["value"]["yours"] is True
    assert said["looked"]["value"]["holder"]["label"] == "Safari on an iPad"
    assert said["released"]["ok"]
    assert said["free"]["value"]["holder"] is None
