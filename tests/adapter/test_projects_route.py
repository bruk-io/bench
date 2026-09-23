"""Adapter: the projects route, on a real Vite server, against a real directory.

decision-9's route reads and writes files on somebody's machine, so what it refuses is the
point of it, and every refusal is driven here the way an attacker or an accident would drive
it: raw HTTP to ``vite`` (the dev server - the route is the same middleware in dev and preview,
and dev needs no build), pointed by ``BENCH_PROJECTS`` at a temporary root laid out with the
traps in it - a sibling directory whose name starts with the root's, a file and a project
that are symlinks out of the root, a symlink that stays inside it. The e2e layer checks the
same route answers under ``vite preview`` (``tests/e2e/test_projects_route.py``).

Requests go through :mod:`http.client` with the path written exactly as given: ``urllib`` and
anything built on WHATWG URL parsing collapse ``..`` before it is sent, and a traversal test
that never sends a traversal proves nothing.

The client the app will use (``web/src/host.ts``) is bundled with the app's own esbuild and
run under Node against the same server, so its half of the protocol is checked for real too.
"""

import hashlib
import http.client
import json
import os
import shutil
import subprocess
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

import pytest

from tools import preview
from tools.projects import VARIABLE, projects_root

pytestmark = pytest.mark.adapter

_VITE = preview.WEB / "node_modules" / ".bin" / "vite"
_ESBUILD = preview.WEB / "node_modules" / ".bin" / "esbuild"
if shutil.which("node") is None or not _VITE.is_file():
    pytest.skip("node or web/node_modules missing - run npm ci in web/", allow_module_level=True)

ROUTE = "/__bench/projects"

SCRIPT = b"units_x = 4\n"
VALUES = b"[values]\nunits_x = 4\n"


class Answer(NamedTuple):
    """What the server said."""

    status: int
    headers: Mapping[str, str]
    body: bytes

    def json(self) -> dict[str, object]:
        """The body, as the JSON object every answer but a read is."""
        found = json.loads(self.body)
        assert isinstance(found, dict)
        return found


class Server(NamedTuple):
    """A running server and the directory it was pointed at."""

    port: int
    root: Path
    outside: Path


def ask(
    server: Server,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: Mapping[str, str] | None = None,
) -> Answer:
    """One request, with ``path`` sent byte for byte and ``Host`` set by hand."""
    given = {"Host": f"localhost:{server.port}", **(headers or {})}
    conn = http.client.HTTPConnection("localhost", server.port, timeout=10)
    try:
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for name, value in given.items():
            conn.putheader(name, value)
        conn.putheader("Content-Length", str(len(body or b"")))
        conn.endheaders(body or b"")
        response = conn.getresponse()
        return Answer(
            response.status,
            {name.lower(): value for name, value in response.getheaders()},
            response.read(),
        )
    finally:
        conn.close()


def _laid_out(base: Path) -> tuple[Path, Path]:
    """A root with one real project and every trap the route has to refuse."""
    root = base / "projects"
    # Named so a bare ``startswith(root)`` would take it for part of the root.
    outside = base / "projects-evil"
    (root / "cabinet").mkdir(parents=True)
    outside.mkdir()
    (root / "cabinet" / "cabinet.py").write_bytes(SCRIPT)
    (root / "cabinet" / "cabinet.toml").write_bytes(VALUES)
    (root / "cabinet" / "notes.txt").write_text("not a kind the route writes\n")
    (root / "cabinet" / ".env").write_text("SECRET=1\n")
    (outside / "secret.py").write_text("password = 'hunter2'\n")
    (root / "cabinet" / "leak.py").symlink_to(outside / "secret.py")
    (root / "cabinet" / "alias.py").symlink_to(root / "cabinet" / "cabinet.py")
    (root / "escape").symlink_to(outside, target_is_directory=True)
    return root, outside


@pytest.fixture(scope="module")
def server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Server]:
    """``vite`` with the route pointed at a fresh root, for the whole module."""
    root, outside = _laid_out(tmp_path_factory.mktemp("route"))
    with preview.served(dev=True, env={VARIABLE: str(root)}) as url:
        port = urlsplit(url).port
        assert port is not None
        yield Server(port, root, outside)


def _version(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---- AC#1: one root ----------------------------------------------------------------------


def test_the_route_and_the_command_line_agree_on_the_root(server: Server) -> None:
    answer = ask(server, "GET", ROUTE)
    assert answer.status == 200
    said = answer.json()["root"]
    assert isinstance(said, str)
    assert Path(said) == projects_root({VARIABLE: str(server.root)}).resolve()


def test_a_root_that_is_not_there_is_reported_not_made(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-projects"
    with preview.served(dev=True, env={VARIABLE: str(missing)}) as url:
        port = urlsplit(url).port
        assert port is not None
        answer = ask(Server(port, missing, tmp_path), "GET", ROUTE)
    assert answer.status == 503
    assert answer.json()["refused"] == "no-root"
    assert not missing.exists()


def test_a_relative_root_stops_the_server_rather_than_guessing_where_it_is() -> None:
    with (
        pytest.raises(RuntimeError, match="must be an absolute path"),
        preview.served(dev=True, env={VARIABLE: "projects"}),
    ):
        pass
    with pytest.raises(ValueError, match="absolute"):
        projects_root({VARIABLE: "projects"})


# ---- AC#2: the operations ----------------------------------------------------------------


def test_lists_the_projects_and_nothing_that_leads_out(server: Server) -> None:
    projects = ask(server, "GET", ROUTE).json()["projects"]
    assert isinstance(projects, list)
    assert "cabinet" in projects
    assert "escape" not in projects


def test_lists_a_projects_files_without_hidden_ones_or_links_out(server: Server) -> None:
    files = ask(server, "GET", f"{ROUTE}/cabinet").json()["files"]
    assert isinstance(files, list)
    names = [one["name"] for one in files]
    assert "cabinet.py" in names
    assert "cabinet.toml" in names
    assert "alias.py" in names
    assert ".env" not in names
    assert "leak.py" not in names


def test_a_read_carries_the_bytes_their_version_and_their_modification_time(server: Server) -> None:
    at = server.root / "cabinet" / "cabinet.toml"
    answer = ask(server, "GET", f"{ROUTE}/cabinet/cabinet.toml")
    assert answer.status == 200
    assert answer.body == at.read_bytes()
    assert answer.headers["etag"] == f'"{_version(at)}"'
    assert float(answer.headers["x-bench-mtime"]) == pytest.approx(at.stat().st_mtime * 1000, abs=1)
    assert int(answer.headers["x-bench-size"]) == at.stat().st_size


def test_write_create_rename_and_delete_round_trip(server: Server) -> None:
    project = server.root / "shelf"
    made = ask(server, "PUT", f"{ROUTE}/shelf/shelf.py", b"w = 1\n", {"If-None-Match": "*"})
    assert made.status == 201
    assert (project / "shelf.py").read_bytes() == b"w = 1\n"
    assert made.json()["version"] == _version(project / "shelf.py")

    base = ask(server, "GET", f"{ROUTE}/shelf/shelf.py").headers["etag"]
    written = ask(server, "PUT", f"{ROUTE}/shelf/shelf.py", b"w = 2\n", {"If-Match": base})
    assert written.status == 200
    assert (project / "shelf.py").read_bytes() == b"w = 2\n"
    assert not [p for p in project.iterdir() if p.name.startswith(".")], "a staged write was left"

    moved = ask(server, "POST", f"{ROUTE}/shelf/shelf.py?to=rack.py")
    assert moved.status == 200
    assert not (project / "shelf.py").exists()
    assert (project / "rack.py").read_bytes() == b"w = 2\n"

    base = ask(server, "GET", f"{ROUTE}/shelf/rack.py").headers["etag"]
    gone = ask(server, "DELETE", f"{ROUTE}/shelf/rack.py", headers={"If-Match": base})
    assert gone.status == 204
    assert not (project / "rack.py").exists()


# ---- AC#3: confined to the root ----------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        f"{ROUTE}/../etc",
        f"{ROUTE}/cabinet/../../projects-evil/secret.py",
        f"{ROUTE}/%2e%2e/projects-evil",
        f"{ROUTE}/cabinet/..%2F..%2Fprojects-evil%2Fsecret.py",
        f"{ROUTE}/%2Fetc%2Fpasswd",
        f"{ROUTE}//etc/passwd",
        f"{ROUTE}/cabinet/cabinet.py%00.txt",
        f"{ROUTE}/cabinet/.env",
    ],
)
def test_a_path_that_is_not_a_project_and_a_file_is_refused(server: Server, path: str) -> None:
    for method, headers in (("GET", {}), ("PUT", {"If-None-Match": "*"})):
        answer = ask(server, method, path, b"x = 1\n", headers)
        assert answer.status == 400, (method, path, answer)
        assert answer.json()["refused"] == "name"
    assert sorted(p.name for p in server.outside.iterdir()) == ["secret.py"]


def test_a_file_that_is_a_symlink_out_is_refused(server: Server) -> None:
    answer = ask(server, "GET", f"{ROUTE}/cabinet/leak.py")
    assert answer.status == 403
    assert answer.json()["refused"] == "outside"
    assert b"hunter2" not in answer.body
    base = f'"{_version(server.outside / "secret.py")}"'
    written = ask(server, "PUT", f"{ROUTE}/cabinet/leak.py", b"owned\n", {"If-Match": base})
    assert written.status == 403
    assert written.json()["refused"] == "link"
    assert (server.outside / "secret.py").read_text() == "password = 'hunter2'\n"


def test_a_project_that_is_a_symlink_out_is_refused(server: Server) -> None:
    listed = ask(server, "GET", f"{ROUTE}/escape")
    assert listed.status == 403
    assert listed.json()["refused"] == "outside"
    read = ask(server, "GET", f"{ROUTE}/escape/secret.py")
    assert read.json()["refused"] == "outside"
    made = ask(server, "PUT", f"{ROUTE}/escape/planted.py", b"x = 1\n", {"If-None-Match": "*"})
    assert made.status == 403
    assert made.json()["refused"] == "outside"
    assert not (server.outside / "planted.py").exists()


def test_a_symlink_inside_the_root_is_read_through_and_never_written_through(
    server: Server,
) -> None:
    read = ask(server, "GET", f"{ROUTE}/cabinet/alias.py")
    assert read.status == 200
    assert read.body == (server.root / "cabinet" / "cabinet.py").read_bytes()
    written = ask(
        server, "PUT", f"{ROUTE}/cabinet/alias.py", b"x = 9\n", {"If-Match": read.headers["etag"]}
    )
    assert written.json()["refused"] == "link"
    gone = ask(server, "DELETE", f"{ROUTE}/cabinet/alias.py", headers={"If-Match": '"x"'})
    assert gone.json()["refused"] == "link"
    assert (server.root / "cabinet" / "alias.py").is_symlink()


# ---- AC#4: only .py, .toml and .stl ------------------------------------------------------


def test_only_scripts_values_and_meshes_can_be_written(server: Server) -> None:
    for name in ("run.sh", "notes.txt", "index.html"):
        answer = ask(server, "PUT", f"{ROUTE}/cabinet/{name}", b"x", {"If-None-Match": "*"})
        assert answer.status == 403
        assert answer.json()["refused"] == "type"
    assert (server.root / "cabinet" / "notes.txt").read_text() == "not a kind the route writes\n"
    assert not (server.root / "cabinet" / "run.sh").exists()
    mesh = ask(server, "PUT", f"{ROUTE}/cabinet/slide.STL", b"solid\n", {"If-None-Match": "*"})
    assert mesh.status == 201


def test_a_traversal_wearing_an_allowed_extension_is_still_a_traversal(server: Server) -> None:
    for path in (
        f"{ROUTE}/cabinet/..%2F..%2Fprojects-evil%2Fplanted.py",
        f"{ROUTE}/../projects-evil/planted.py",
    ):
        answer = ask(server, "PUT", path, b"x = 1\n", {"If-None-Match": "*"})
        assert answer.json()["refused"] == "name"
    renamed = ask(server, "POST", f"{ROUTE}/cabinet/cabinet.py?to=..%2F..%2Fplanted.py")
    assert renamed.json()["refused"] == "name"
    assert not (server.outside / "planted.py").exists()
    assert not (server.root.parent / "planted.py").exists()


# ---- AC#5: same origin only --------------------------------------------------------------


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "http://evil.example"},
        {"Origin": "http://localhost:3000"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},
    ],
)
def test_a_request_from_another_origin_is_refused(
    server: Server, headers: Mapping[str, str]
) -> None:
    answer = ask(
        server, "PUT", f"{ROUTE}/cabinet/forged.py", b"x = 1\n", {"If-None-Match": "*", **headers}
    )
    assert answer.status == 403
    assert answer.json()["refused"] == "origin"
    assert not (server.root / "cabinet" / "forged.py").exists()


def test_a_tablet_that_reached_the_host_by_address_may_write(server: Server) -> None:
    host = f"192.168.1.20:{server.port}"
    answer = ask(
        server,
        "PUT",
        f"{ROUTE}/cabinet/tablet.py",
        b"x = 1\n",
        {
            "Host": host,
            "Origin": f"http://{host}",
            "Sec-Fetch-Site": "same-origin",
            "If-None-Match": "*",
        },
    )
    assert answer.status == 201


def test_a_request_with_no_origin_is_a_client_that_is_not_a_page_and_is_let_through(
    server: Server,
) -> None:
    answer = ask(server, "PUT", f"{ROUTE}/cabinet/curl.py", b"x = 1\n", {"If-None-Match": "*"})
    assert answer.status == 201


def test_a_name_the_server_was_not_told_to_answer_to_is_refused(server: Server) -> None:
    # DNS rebinding: a hostile name resolved to this machine. The Origin matches the Host, so
    # only the host check can see it - and Vite's own runs after the route, not before.
    rebound = "evil.example:" + str(server.port)
    answer = ask(
        server,
        "PUT",
        f"{ROUTE}/cabinet/rebound.py",
        b"x = 1\n",
        {"Host": rebound, "Origin": f"http://{rebound}", "If-None-Match": "*"},
    )
    assert answer.status == 403
    assert answer.json()["refused"] == "host"
    assert not (server.root / "cabinet" / "rebound.py").exists()
    assert ask(server, "GET", ROUTE, headers={"Host": rebound}).json()["refused"] == "host"


# ---- AC#6: a write whose base has moved --------------------------------------------------


def test_a_write_made_from_a_version_that_moved_is_refused_and_names_the_file(
    server: Server,
) -> None:
    at = server.root / "cabinet" / "cabinet.py"
    base = ask(server, "GET", f"{ROUTE}/cabinet/cabinet.py").headers["etag"]
    stamp = at.stat()
    # The maker's editor changes one digit - the same size - and keeps the modification time,
    # which is what a coarse filesystem does inside the same second. Only the bytes moved.
    at.write_bytes(SCRIPT.replace(b"4", b"5"))
    os.utime(at, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    answer = ask(server, "PUT", f"{ROUTE}/cabinet/cabinet.py", b"units_x = 6\n", {"If-Match": base})
    assert answer.status == 409
    assert answer.json()["refused"] == "moved"
    assert answer.json()["file"] == "cabinet/cabinet.py"
    assert at.read_bytes() == b"units_x = 5\n"

    gone = ask(server, "DELETE", f"{ROUTE}/cabinet/cabinet.py", headers={"If-Match": base})
    assert gone.json()["refused"] == "moved"
    assert at.exists()


def test_a_write_that_does_not_say_what_it_was_made_from_is_refused(server: Server) -> None:
    answer = ask(server, "PUT", f"{ROUTE}/cabinet/cabinet.toml", b"[values]\n")
    assert answer.status == 428
    assert answer.json()["refused"] == "precondition"
    assert (server.root / "cabinet" / "cabinet.toml").read_bytes() == VALUES


def test_creating_or_renaming_onto_a_file_that_is_there_is_a_conflict(server: Server) -> None:
    made = ask(server, "PUT", f"{ROUTE}/cabinet/cabinet.toml", b"x", {"If-None-Match": "*"})
    assert made.status == 409
    assert made.json()["refused"] == "exists"
    assert made.json()["file"] == "cabinet/cabinet.toml"
    renamed = ask(server, "POST", f"{ROUTE}/cabinet/cabinet.toml?to=cabinet.py")
    assert renamed.status == 409
    assert renamed.json()["refused"] == "exists"
    assert (server.root / "cabinet" / "cabinet.toml").read_bytes() == VALUES


def test_a_file_that_is_not_there_is_missing(server: Server) -> None:
    assert ask(server, "GET", f"{ROUTE}/cabinet/nothing.py").json()["refused"] == "missing"
    assert ask(server, "GET", f"{ROUTE}/nothing").json()["refused"] == "missing"


# ---- the client --------------------------------------------------------------------------

DRIVER = """\
import { host } from "./host.mjs";

const route = host(process.argv[2]);
const said = {};
said.projects = await route.projects();
said.created = await route.create("client", "part.py", "a = 1\\n");
said.again = await route.create("client", "part.py", "a = 1\\n");
said.files = await route.files("client");
const read = await route.read("client", "part.py");
said.read = { ok: read.ok, text: read.ok ? new TextDecoder().decode(read.value.bytes) : null,
              version: read.ok ? read.value.version : null };
const base = read.ok ? read.value.version.version : "";
said.written = await route.write("client", "part.py", "a = 2\\n", base);
said.stale = await route.write("client", "part.py", "a = 3\\n", base);
said.type = await route.create("client", "notes.txt", "x");
said.renamed = await route.rename("client", "part.py", "piece.py");
const now = said.renamed.ok ? said.renamed.value.version : "";
said.removed = await route.remove("client", "piece.py", now);
console.log(JSON.stringify(said));
"""


@pytest.mark.skipif(not _ESBUILD.is_file(), reason="web/node_modules/.bin/esbuild missing")
def test_the_apps_client_speaks_the_route(server: Server, tmp_path: Path) -> None:
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

    assert said["projects"]["ok"]
    assert said["created"]["ok"]
    assert said["again"] == {"ok": False, "refusal": said["again"]["refusal"]}
    assert said["again"]["refusal"]["refused"] == "exists"
    assert [one["name"] for one in said["files"]["value"]] == ["part.py"]
    assert said["read"]["text"] == "a = 1\n"
    assert said["read"]["version"]["mtimeMs"] > 0
    assert said["read"]["version"]["size"] == len("a = 1\n")
    assert said["written"]["ok"]
    assert said["stale"]["refusal"]["refused"] == "moved"
    assert said["stale"]["refusal"]["file"] == "client/part.py"
    assert said["type"]["refusal"]["refused"] == "type"
    assert said["renamed"]["ok"]
    assert said["removed"] == {"ok": True, "value": None}
    assert not (server.root / "client" / "piece.py").exists()
