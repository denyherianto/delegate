#!/usr/bin/env python3
"""Build the boss frontend assets.

Runs esbuild to bundle JS/CSS from frontend/src/ into boss/static/.
Automatically runs ``npm install`` in frontend/ if node_modules is missing.

Usage:
    python build_frontend.py            # production build (minified)
    python build_frontend.py --watch    # watch mode for development
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
BUILD_JS = FRONTEND / "build.js"


def ensure_node() -> str:
    """Return the path to the node binary, or exit with a helpful message."""
    node = shutil.which("node")
    if node is None:
        print("Error: 'node' not found on PATH. Install Node.js >= 18.", file=sys.stderr)
        sys.exit(1)
    return node


def ensure_npm() -> str:
    npm = shutil.which("npm")
    if npm is None:
        print("Error: 'npm' not found on PATH. Install Node.js >= 18.", file=sys.stderr)
        sys.exit(1)
    return npm


def main() -> None:
    node = ensure_node()

    # npm install if node_modules is missing
    if not (FRONTEND / "node_modules").is_dir():
        npm = ensure_npm()
        print("Installing frontend dependencies …")
        subprocess.run([npm, "install"], cwd=str(FRONTEND), check=True)

    # Run the esbuild build script
    cmd = [node, str(BUILD_JS)]
    if "--watch" in sys.argv:
        cmd.append("--watch")

    print(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=str(FRONTEND), check=True)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
