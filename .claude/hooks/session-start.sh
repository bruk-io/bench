#!/bin/bash
# Bring a fresh Claude Code on the web container up to where `uv run tools/check.py`
# passes: a Python 3.15 interpreter, the project's dependencies, and the web bundle - with
# the Manifold WASM modeller - that the adapter, component and e2e layers load.
#
# Every step is idempotent and safe to re-run. The web steps warn and carry on rather than
# failing the session, because the suite already skips those layers with a message when
# they are missing.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT"

note() { echo "session-start: $*"; }
warn() { echo "session-start: WARNING: $*" >&2; }

# 1. Python 3.15. The container's uv is too old to know about it (it lists 3.14 as the
#    newest download), so fetch a current uv from PyPI - reachable where GitHub is not -
#    and use that one only to install the interpreter. Everything after this runs on the
#    container's own uv, which finds the interpreter in the shared managed directory.
if ! uv python find 3.15 >/dev/null 2>&1; then
  note "installing Python 3.15"
  UV_NEW="$HOME/.cache/bench-session-start/uv"
  if [ ! -x "$UV_NEW/bin/uv" ]; then
    python3 -m pip install --quiet --target "$UV_NEW" uv
  fi
  "$UV_NEW/bin/uv" python install 3.15
else
  note "Python 3.15 already present"
fi

# 2. The Python dependencies. The modeller is Manifold's WASM build from npm, driven from
#    Python inside Pyodide, so there is no native extra to compile here.
note "syncing dependencies"
uv sync

# 3. The web bundle: the real-stack adapter tests (Node + Pyodide + Manifold WASM) and the
#    whole e2e layer read web/node_modules, and skip with a message saying so when absent.
note "installing web dependencies"
(cd web && npm install --no-audit --no-fund) ||
  warn "npm install failed - the browser and e2e layers will skip"

# 4. The chromium the component tests run in. Vitest drives it through the npm `playwright`,
#    which pins its own browser build, separate from the one Python's Playwright uses.
(cd web && npx playwright install chromium) ||
  warn "could not install chromium for the component tests - npm test will fail"

note "ready - run the gate with: uv run tools/check.py [--fast]"
