"""End to end: the projects route answers under ``vite preview`` - the built app, served the
way ``tools/preview.py`` serves it to the rest of this layer and to ``tools.qa``.

What the route does and refuses is driven in full a layer down, against ``vite`` in dev
(``tests/adapter/test_projects_route.py``); the middleware is the same one registered in the
other hook. What this adds is that the other hook *is* registered - task-45's AC#7, "the route
answers in both" - with its own host rule in force, and that a server started with nothing
set lands on the root :mod:`tools.projects` says it will.
"""

import http.client
import json
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tools import preview
from tools.projects import DEFAULT, VARIABLE, projects_root

pytestmark = pytest.mark.e2e

ROUTE = "/__bench/projects"


def _ask(
    url: str,
    method: str,
    path: str,
    body: bytes = b"",
    headers: Mapping[str, str] | None = None,
) -> tuple[int, dict[str, object] | bytes]:
    """One request to the server at ``url``, and its status and body - JSON where it is."""
    port = urlsplit(url).port
    assert port is not None
    conn = http.client.HTTPConnection("localhost", port, timeout=10)
    try:
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for name, value in {"Host": f"localhost:{port}", **(headers or {})}.items():
            conn.putheader(name, value)
        conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body)
        response = conn.getresponse()
        raw = response.read()
        is_json = response.getheader("content-type") == "application/json"
        return response.status, json.loads(raw) if is_json else raw
    finally:
        conn.close()


def test_the_route_answers_under_preview(built_app: Path, tmp_path: Path) -> None:
    root = tmp_path / "projects"
    (root / "cabinet").mkdir(parents=True)
    with preview.served(env={VARIABLE: str(root)}) as url:
        status, listed = _ask(url, "GET", ROUTE)
        made = _ask(url, "PUT", f"{ROUTE}/cabinet/cabinet.py", b"x = 1\n", {"If-None-Match": "*"})
        status_read, read = _ask(url, "GET", f"{ROUTE}/cabinet/cabinet.py")
        forged = _ask(
            url,
            "PUT",
            f"{ROUTE}/cabinet/forged.py",
            b"x = 1\n",
            {"Origin": "http://evil.example", "If-None-Match": "*"},
        )
        rebound = _ask(url, "GET", ROUTE, headers={"Host": "evil.example"})
    assert status == 200
    assert listed == {"root": str(root.resolve()), "projects": ["cabinet"]}
    assert made[0] == 201
    assert (status_read, read) == (200, b"x = 1\n")
    assert forged[0] == 403
    assert isinstance(forged[1], dict)
    assert forged[1]["refused"] == "origin"
    assert rebound[0] == 403
    assert isinstance(rebound[1], dict)
    assert rebound[1]["refused"] == "host"
    assert not (root / "cabinet" / "forged.py").exists()


def test_with_nothing_set_the_app_and_the_command_line_land_on_the_same_root(
    built_app: Path,
) -> None:
    with preview.served(env={VARIABLE: ""}) as url:
        status, listed = _ask(url, "GET", ROUTE)
    assert status == 200
    assert isinstance(listed, dict)
    assert Path(str(listed["root"])) == projects_root({}).resolve() == DEFAULT.resolve()
