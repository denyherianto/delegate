#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKTREE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/setup.sh"
cd "$WORKTREE_ROOT"

pytest tests/ -x -q
