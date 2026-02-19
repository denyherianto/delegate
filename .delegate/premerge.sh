#!/usr/bin/env bash
# Created by delegate. Edit as needed.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/setup.sh"
pytest tests/ -x -q
