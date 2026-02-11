#!/usr/bin/env bash
set -euo pipefail
# Run Python tests
python -m pytest -x -q
# Build frontend (only if node is available)
if command -v node &>/dev/null; then
    python build_frontend.py
else
    echo 'WARNING: node not found, skipping frontend build'
fi
