#!/usr/bin/env bash
set -euo pipefail
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/field-notes-pycache"

python3 -m compileall -q fieldnotes

if command -v node >/dev/null 2>&1; then
  node --check web/api.js
  node --check web/app.js
else
  echo "warning: node is unavailable; skipped frontend syntax checks" >&2
fi

python3 -m unittest discover -s tests -v
