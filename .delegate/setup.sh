#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.

WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$WORKTREE_ROOT/.venv"

# Re-entrance guard
[[ -n "$_DELEGATE_SETUP_DONE" ]] && { source "$VENV_DIR/bin/activate"; return 0 2>/dev/null || exit 0; }
_DELEGATE_SETUP_DONE=1

if ! "$VENV_DIR/bin/python" -c "import pytest" 2>/dev/null; then
  rm -rf "$VENV_DIR"
  cd "$WORKTREE_ROOT"
  if command -v uv >/dev/null 2>&1; then
    uv sync --group dev --quiet
  else
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install ".[dev]" --quiet
  fi
fi

source "$VENV_DIR/bin/activate"

# Frontend deps
if [ -f "$WORKTREE_ROOT/frontend/package-lock.json" ] && [ ! -d "$WORKTREE_ROOT/frontend/node_modules" ]; then
  (cd "$WORKTREE_ROOT/frontend" && npm ci --silent)
fi
