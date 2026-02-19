#!/usr/bin/env bash
# Created by delegate. Edit as needed.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKTREE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/setup.sh"
cd "$WORKTREE_ROOT"
pytest tests/ -x -q
