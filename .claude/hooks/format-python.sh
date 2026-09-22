#!/bin/bash
# After Claude writes or edits a Python file, format it and apply ruff's safe fixes, so the
# gate's `ruff format --check` and `ruff check` never fail on something a tool would fix.
#
# Reads the hook payload on stdin. Anything that is not a .py file inside this repo is left
# alone. Never blocks: whatever ruff cannot fix is the gate's to report, not this hook's.
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
FILE="$(jq -r '.tool_input.file_path // .tool_response.filePath // empty')"

case "$FILE" in
  "$ROOT"/*.py) ;;
  *) exit 0 ;;
esac
[ -f "$FILE" ] || exit 0

cd "$ROOT"
# --no-sync: the file's edit is not a reason to rebuild the environment on every save.
uv run --no-sync ruff format --quiet "$FILE"
uv run --no-sync ruff check --fix --quiet --exit-zero "$FILE"
exit 0
