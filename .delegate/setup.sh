#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.

WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$WORKTREE_ROOT/.venv"

# Find uv — check PATH first, then in the main repo root (via git-common-dir)
UV=""
if command -v uv >/dev/null 2>&1; then
  UV="$(command -v uv)"
else
  # git-common-dir gives the shared .git dir; its parent is the main repo root
  GIT_COMMON="$(git -C "$WORKTREE_ROOT" rev-parse --git-common-dir 2>/dev/null || true)"
  if [ -n "$GIT_COMMON" ]; then
    MAIN_REPO="$(cd "$GIT_COMMON/.." && pwd)"
    if [ -x "$MAIN_REPO/.nix-uv/bin/uv" ]; then
      UV="$MAIN_REPO/.nix-uv/bin/uv"
    fi
  fi
fi

if [ ! -f "$VENV_DIR/bin/pytest" ]; then
  rm -rf "$VENV_DIR"
  if [ -n "$UV" ]; then
    # Try normally first; fall back to --no-cache if uv cache is corrupted
    if ! "$UV" venv "$VENV_DIR" 2>/dev/null; then
      "$UV" venv "$VENV_DIR" --no-cache
    fi
    cd "$WORKTREE_ROOT"
    if ! "$UV" pip install --python "$VENV_DIR/bin/python" -e ".[dev]" 2>/dev/null; then
      "$UV" pip install --python "$VENV_DIR/bin/python" -e ".[dev]" --no-cache
    fi
  else
    python3 -m venv "$VENV_DIR"
    cd "$WORKTREE_ROOT"
    "$VENV_DIR/bin/pip" install ".[dev]"
  fi
fi

source "$VENV_DIR/bin/activate"
