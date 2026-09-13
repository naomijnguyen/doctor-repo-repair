#!/usr/bin/env bash
set -euo pipefail
python3 -m unittest discover -s tests -v
python3 -m compileall -q fieldnotes
# Frontend checks will be added after beta.
