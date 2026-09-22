"""The app's Python and its modeller, together, outside a browser.

The worker runs ``bench`` in Pyodide and hands it Manifold's WASM as its kernel. This does
the same under Node, with the same pieces and no stand-ins: the pinned runtime in
``web/node_modules/pyodide``, every module of ``src/bench`` written into ``/lib`` the way
``web/src/worker.ts`` writes them, and the app's own modeller module bundled by the app's
own esbuild and loaded against the Manifold WASM in ``web/node_modules``.

:func:`run` takes a Python program that defines ``main(kernel, payload)`` - ``kernel`` is the
object the modeller module's ``bind`` made, ``payload`` a JSON string - and gives back the
JSON ``main`` returned. One call is one boot, which takes seconds, so a caller asks for
everything it needs in one program rather than one call per question. Modules of the
caller's own - the cases a test builds, say - are written into ``/lib`` beside ``bench`` and
imported by name.

A tool rather than a module of the package, for the same reason :mod:`tools.preview` is: it
spawns, writes files and waits. Both :mod:`tools.kernel_timing` and the adapter tests stand
on it.
"""

import json
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
"""The repository root."""

SOURCES = ROOT / "src"
"""What ``/lib`` is filled from, keyed the way the worker keys it: ``bench/script.py``."""

WEB = ROOT / "web"
RUNTIME = WEB / "node_modules" / "pyodide"
MANIFOLD = WEB / "node_modules" / "manifold-3d"
ESBUILD = WEB / "node_modules" / ".bin" / "esbuild"

MODELLER = WEB / "src" / "modeller.ts"
"""The module whose ``load`` and ``bind`` make the modeller handed to ``main``."""

BUILD_SECONDS = 120
"""How long bundling the modeller may take."""

RUN_SECONDS = 600
"""How long one boot and one program may take together."""

DRIVER = """\
// Mirrors web/src/worker.ts: the modeller loaded and bound, Pyodide booted, the bench
// sources written into /lib, and one Python program handed both.
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { bind, load } from "./modeller.mjs";

const payload = JSON.parse(await readFile(process.argv[2], "utf8"));
const kernel = bind(await load(payload.manifold));
const runtime = await import(pathToFileURL(join(payload.runtime, "pyodide.mjs")).href);
const pyodide = await runtime.loadPyodide({
  indexURL: `${payload.runtime}/`,
  stdout: (text) => process.stderr.write(`${text}\\n`),
  stderr: (text) => process.stderr.write(`${text}\\n`),
});

function mkdirp(dir) {
  let walked = "";
  for (const segment of dir.split("/")) {
    if (segment === "") continue;
    walked += `/${segment}`;
    try {
      pyodide.FS.mkdir(walked);
    } catch {
      // already there, which is the common case
    }
  }
}

for (const [path, text] of Object.entries(payload.sources)) {
  const full = `/lib/${path}`;
  mkdirp(full.slice(0, full.lastIndexOf("/")));
  pyodide.FS.writeFile(full, text, { encoding: "utf8" });
}

pyodide.runPython(`import sys\\nsys.path.insert(0, "/lib")`);
const main = pyodide.runPython(`${payload.program}\\nmain`);
console.log(main(kernel, JSON.stringify(payload.given)));
"""


def missing() -> str | None:
    """Why the stack cannot run here, or ``None`` when it can."""
    if shutil.which("node") is None:
        return "node not on PATH"
    for needed in (RUNTIME / "pyodide.mjs", MANIFOLD / "manifold.wasm", ESBUILD):
        if not needed.is_file():
            return f"{needed.relative_to(ROOT)} missing - run npm install in web/"
    return None


def _mounted() -> dict[str, str]:
    """Every module of the package, keyed by its path relative to ``src``."""
    return {
        str(path.relative_to(SOURCES)): path.read_text()
        for path in sorted((SOURCES / "bench").rglob("*.py"))
        if "__pycache__" not in path.parts
    }


def _bundled(into: Path, modeller: Path) -> None:
    """``modeller`` as one ES module named ``modeller.mjs`` beside the driver.

    Raises:
        RuntimeError: if esbuild fails, with its complaint as the reason.
    """
    done = subprocess.run(
        (
            str(ESBUILD),
            str(modeller),
            "--bundle",
            "--format=esm",
            "--platform=neutral",
            f"--outfile={into / 'modeller.mjs'}",
        ),
        capture_output=True,
        text=True,
        timeout=BUILD_SECONDS,
        check=False,
    )
    if done.returncode != 0:
        msg = f"esbuild exited {done.returncode}:\n{done.stderr[-4000:]}"
        raise RuntimeError(msg)


def run(
    program: str,
    given: object,
    *,
    modeller: Path = MODELLER,
    modules: Mapping[str, str] | None = None,
) -> Any:
    """Boot the stack once, call ``main(kernel, json.dumps(given))`` in it, and return the
    JSON that ``main`` returned, parsed.

    ``modules`` maps a file name to its source; each is written into ``/lib`` beside
    ``bench``, so ``{"cases.py": text}`` is ``import cases`` inside the program.

    Raises:
        RuntimeError: if the stack cannot run here, the bundle fails, Node exits badly, or
            the program prints no answer.
    """
    reason = missing()
    node = shutil.which("node")
    if reason is not None or node is None:
        msg = f"the stack cannot run: {reason}"
        raise RuntimeError(msg)
    with tempfile.TemporaryDirectory() as scratch:
        where = Path(scratch)
        _bundled(where, modeller)
        (where / "drive.mjs").write_text(DRIVER)
        payload = where / "payload.json"
        payload.write_text(
            json.dumps(
                {
                    "manifold": f"{MANIFOLD.as_uri()}/",
                    "runtime": str(RUNTIME),
                    "sources": {**_mounted(), **(modules or {})},
                    "program": program,
                    "given": given,
                }
            )
        )
        done = subprocess.run(
            (node, str(where / "drive.mjs"), str(payload)),
            capture_output=True,
            text=True,
            timeout=RUN_SECONDS,
            check=False,
        )
    if done.returncode != 0:
        msg = f"node exited {done.returncode}:\n{done.stderr[-4000:]}"
        raise RuntimeError(msg)
    lines = done.stdout.splitlines()
    if not lines:
        msg = f"the program printed nothing:\n{done.stderr[-4000:]}"
        raise RuntimeError(msg)
    return json.loads(lines[-1])
