"""The built app, served: one build when its sources have changed, one `vite preview`.

Both things that drive the app in a browser start here - the ``e2e`` layer in
:mod:`tests.e2e.conftest` and :mod:`tools.qa`, the one a person runs by hand - because what
either of them wants is the same and is worth getting right once: the app a user gets,
built from ``web/dist`` rather than a dev server, rebuilt when and only when something it
is made from has changed, and served on whatever port vite picked for itself.

Nothing here is pure: it builds, it spawns, it waits. That is the point of it being a tool
rather than a module of the package - the layer graph in ``pyproject.toml`` governs
``src/bench``, and none of this belongs anywhere near it.
"""

import contextlib
import hashlib
import os
import re
import select
import signal
import subprocess
import threading
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import IO

ROOT = Path(__file__).resolve().parent.parent
"""The repository root."""

WEB = ROOT / "web"
"""The app: its sources, its build, its screenshots."""

DIST = WEB / "dist" / "index.html"
"""The built entry point."""

HASH_FILE = WEB / "dist" / ".bench-hash"
"""Where the hash of the sources the current build was made from is written, next to the
build itself so a ``rm -rf web/dist`` forgets it along with everything else."""

WATCHED = ("web/src", "src/bench")
"""What the build is made from; a changed hash of this means rebuild."""

BUILD_SECONDS = 900
"""How long ``npm run build`` may take - it type-checks and bundles Pyodide's copy."""

PREVIEW_BOOT_SECONDS = 30.0
"""How long ``vite preview`` may take to print the URL it picked before this gives up."""

_LOCAL_URL = re.compile(r"Local:\s+(http://\S+)")
"""What ``vite preview`` prints once it is listening, e.g. ``Local:   http://localhost:4173/``."""


def _files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            yield path


def sources_hash(roots: tuple[str, ...] = WATCHED) -> str:
    """A hash of every watched file's path and content, so a rebuild is only skipped when
    nothing that feeds the build has changed - unlike an mtime, this cannot be fooled by a
    checkout or a copy that preserves timestamps but not content, and does not force a
    rebuild when a file is only touched, not edited."""
    digest = hashlib.sha256()
    paths = sorted(
        (path for root in roots for path in _files(ROOT / root)), key=lambda p: p.as_posix()
    )
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def build() -> None:
    """``npm run build``, which generates the Python bundle and Pyodide's copy first.

    Raises:
        RuntimeError: if the build fails, with its own output as the reason.
    """
    done = subprocess.run(
        ("npm", "run", "build"),
        cwd=WEB,
        capture_output=True,
        text=True,
        timeout=BUILD_SECONDS,
        check=False,
    )
    if done.returncode != 0:
        msg = (
            f"npm run build exited {done.returncode}:\n{done.stdout[-4000:]}\n{done.stderr[-4000:]}"
        )
        raise RuntimeError(msg)


def built() -> Path:
    """``web/dist``, rebuilt when the hash of its sources has changed since the build
    written there last - :data:`HASH_FILE`, next to the build it describes."""
    current = sources_hash()
    stale = not DIST.exists() or not HASH_FILE.exists() or HASH_FILE.read_text().strip() != current
    if stale:
        build()
        HASH_FILE.write_text(current)
    return DIST.parent


def _drained(stream: IO[bytes]) -> None:
    """Read and discard ``stream`` until it closes, so a process writing to a pipe nobody
    is reading from cannot block on a full buffer once this stops looking for its URL."""
    with contextlib.suppress(ValueError, OSError):
        while stream.read(4096):
            pass


def _preview_url(server: subprocess.Popen[bytes], timeout: float) -> str:
    """The URL ``vite preview`` announced on its own stdout - whatever port it picked,
    since nothing here asks for a particular one.

    ``select`` bounds each read by what is left of ``timeout``, so a process that never
    prints anything and never exits cannot block this past it - a plain blocking
    ``read1`` would wait on the pipe forever regardless of any deadline checked around it.

    Raises:
        RuntimeError: if it exits, or prints nothing recognisable within ``timeout`` seconds.
    """
    assert server.stdout is not None
    deadline = time.monotonic() + timeout
    seen = b""
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        if server.poll() is not None:
            msg = f"vite preview exited {server.returncode} before printing a URL:\n{seen!r}"
            raise RuntimeError(msg)
        ready, _, _ = select.select([server.stdout], [], [], min(remaining, 0.5))
        if not ready:
            continue
        chunk = os.read(server.stdout.fileno(), 4096)
        if not chunk:
            break
        seen += chunk
        found = _LOCAL_URL.search(seen.decode("utf-8", errors="replace"))
        if found is not None:
            return found.group(1).rstrip("/") + "/"
    msg = f"vite preview printed no URL within {timeout:.0f}s:\n{seen!r}"
    raise RuntimeError(msg)


def _answering(url: str, server: subprocess.Popen[bytes]) -> None:
    """Wait until ``server`` serves ``url``.

    Raises:
        RuntimeError: if it exits, or never answers.
    """
    for _ in range(120):
        if server.poll() is not None:
            msg = f"vite preview exited {server.returncode} before serving {url}"
            raise RuntimeError(msg)
        try:
            with urllib.request.urlopen(url, timeout=2) as answer:
                if answer.status == 200:
                    return
        except OSError:
            # urllib.error.URLError, TimeoutError and ConnectionError are all OSError, and
            # the connection is refused for as long as the server has not opened its socket.
            time.sleep(0.5)
    msg = f"vite preview never answered on {url}"
    raise RuntimeError(msg)


def _stopped(server: subprocess.Popen[bytes]) -> None:
    """Stop the whole process group, politely and then not, so nothing outlives the run."""
    with contextlib.suppress(OSError):
        os.killpg(os.getpgid(server.pid), signal.SIGTERM)
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(OSError):
            os.killpg(os.getpgid(server.pid), signal.SIGKILL)
        server.wait(timeout=10)


@contextlib.contextmanager
def served() -> Iterator[str]:
    """The built app, up for as long as the block runs, at the URL this yields.

    No ``--port`` is given, so vite is free to fall back to the next free one when its
    default is taken - the port this run gets is read back off its own announcement rather
    than chosen up front, which is what a fixed port and ``--strictPort`` used to need a
    free-port probe for, with a window between the probe and the bind that another process
    could win.
    """
    # Plain text, whatever the caller's terminal asked for: the announcement is read, not
    # shown, and a FORCE_COLOR in the environment has vite wrap "Local" and the port in escape
    # codes that no URL pattern sees through. NO_COLOR wins over FORCE_COLOR in vite's colours.
    plain = {name: value for name, value in os.environ.items() if name != "FORCE_COLOR"}
    server = subprocess.Popen(
        ("npx", "vite", "preview"),
        cwd=WEB,
        env={**plain, "NO_COLOR": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        url = _preview_url(server, PREVIEW_BOOT_SECONDS)
        threading.Thread(target=_drained, args=(server.stdout,), daemon=True).start()
        _answering(url, server)
        yield url
    finally:
        _stopped(server)
