#!/usr/bin/env bash
set -euo pipefail

python3 -c 'import sys; assert sys.version_info[:2] >= (3, 11), f"need Python 3.11+, got {sys.version}"'
command -v node >/dev/null

# Catch syntax errors early; runtime uses stdlib only (no pip install).
python3 -m compileall -q radar
