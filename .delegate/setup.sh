#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.

WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$WORKTREE_ROOT/.venv"

# Re-entrance guard — skip if already sourced (premerge.sh sources us too)
[[ -n "$_DELEGATE_SETUP_DONE" ]] && { source "$VENV_DIR/bin/activate"; return 0 2>/dev/null || exit 0; }
_DELEGATE_SETUP_DONE=1

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

if ! "$VENV_DIR/bin/python" -c "import pytest" 2>/dev/null; then
  rm -rf "$VENV_DIR"
  cd "$WORKTREE_ROOT"
  if [ -n "$UV" ]; then
    # uv sync reads [dependency-groups] (PEP 735) and uv.lock for reproducible installs.
    # uv reuses its global cache (~/.cache/uv) — do NOT pass --no-cache routinely.
    "$UV" sync --group dev --quiet
  else
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install ".[dev]" --quiet
  fi
fi

source "$VENV_DIR/bin/activate"
