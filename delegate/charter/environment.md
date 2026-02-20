# Environment Setup

Every repo worktree has auto-generated `.delegate/setup.sh` and `.delegate/premerge.sh` scripts. The daemon creates these when it provisions the worktree, detecting the project's tooling (Python, Node, Rust, Go, Ruby, Nix) and generating correct install/test commands.

Your job is to **source** the setup script, verify it works, and fix it if needed — not to write it from scratch.

## Step 1: Source .delegate/setup.sh — MANDATORY

This is your FIRST action on every task, before writing any code or running any command. No exceptions.

```
. .delegate/setup.sh
```

If it exits non-zero, investigate and fix it before proceeding. Common issues:
- Missing system tool (nix, uv, cargo, etc.) — check error message, report to manager
- Stale lockfile — run the appropriate sync command, update setup.sh if needed
- Wrong install command for the project — see the reference templates below and fix

## Step 2: If scripts are missing (rare)

The daemon should have already created the scripts. If they're missing (legacy worktree, daemon failure), regenerate them:

```
python -m delegate.env "$WORKTREE_ROOT"
```

This auto-detects the stack and writes `.delegate/setup.sh` and `.delegate/premerge.sh` with a git commit. Use `--force` to overwrite existing scripts, `--no-commit` to skip the commit, or `--print` to preview without writing.

If `python -m delegate.env` is not available, create the scripts manually using the templates below.

## What the auto-generated scripts detect

The generator scans the repo root and all top-level subdirectories, detecting:

| Signal | Stack |
|---|---|
| `poetry.lock` | Python (Poetry) |
| `uv.lock` | Python (uv sync) |
| `pyproject.toml` or `requirements.txt` (no lockfile) | Python (uv/pip fallback) |
| `pnpm-lock.yaml` / `yarn.lock` / `package-lock.json` / `package.json` | Node |
| `Cargo.toml` | Rust |
| `go.mod` | Go |
| `Gemfile` | Ruby |
| `shell.nix` / `flake.nix` | Nix (wraps the inner stack) |
| `.envrc` with `use nix`, `layout python`, etc. | direnv hints (fallback) |

For multi-language repos (e.g. Rust backend + Python server + Node frontend), all detected stacks are composed into a single pair of scripts. Workspace configurations (Cargo workspaces, npm workspaces, Go workspaces, uv workspaces) are detected to avoid redundant setup for sub-modules.

## Isolation requirement — CRITICAL

Every worktree MUST have its own isolated environment (`.venv`, `node_modules`, `vendor/bundle`, etc.) created INSIDE the worktree directory. NEVER reuse or symlink to the main repo's environment, another worktree's environment, or any absolute path outside the worktree.

Forbidden patterns — if you catch yourself writing any of these, stop and fix it:
- `VENV_DIR="$REPO_ROOT/.venv"` — links to the main repo's venv
- `VENV_DIR="/Users/.../some-project/.venv"` — hardcoded absolute path to another location
- `source "$REPO_ROOT/.venv/bin/activate"` — activating a shared venv
- "reuse the pre-existing venv" / "shared across worktrees" — this reasoning is always wrong

The correct pattern is always: `VENV_DIR="$WORKTREE_ROOT/.venv"` — the venv lives inside the worktree. If creating the venv fails, exit with a clear error — do NOT fall back to sharing another environment.

**Network is restricted.** The sandbox allows outbound connections only to curated package-manager registries and git forges (see `delegate network show`). The auto-generated `setup.sh` uses a 3-tier install strategy to minimise network dependence:

1. **Copy from main repo** — for Python, copies `site-packages` from the main repo's `.venv`; for Node, copies `node_modules`. Instant, zero network.
2. **Install from system cache** — runs the package manager in offline/cache-only mode (e.g. `uv pip install --offline`, `npm ci --prefer-offline`). Works when the user has previously installed the same packages.
3. **Full network install** — standard `pip install` / `npm ci` / etc. Used in CI, first checkout, or cold machines.

Each tier is tried in order; the first success short-circuits. Do not create `.pth` files, symlinks, or any other mechanism to borrow packages from outside the worktree — the copy in tier 1 is a full, independent copy into the worktree's own environment.

---

## Reference Templates

These show what the auto-generated scripts look like and how to modify them when the project has unusual needs.

### Nix

When `shell.nix` or `flake.nix` is present (or `.envrc` contains `use nix`/`use flake`), all install and test commands run **inside** the nix shell. This guarantees the exact toolchain the repo declares.

#### Finding the repo root from a linked worktree

Worktrees are linked git directories. `git rev-parse --show-toplevel` returns the worktree path, not the main repo root. The generated scripts use:

```bash
WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GIT_COMMON="$(git -C "$WORKTREE_ROOT" rev-parse --git-common-dir)"
REPO_ROOT="$(cd "$GIT_COMMON/.." && pwd)"
```

`REPO_ROOT` is where `shell.nix`/`flake.nix` live. Use `REPO_ROOT` ONLY for locating nix files — never use it to share environments.

#### Nix setup.sh

```bash
#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.

WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GIT_COMMON="$(git -C "$WORKTREE_ROOT" rev-parse --git-common-dir)"
REPO_ROOT="$(cd "$GIT_COMMON/.." && pwd)"

# Re-entrance guard
[[ -n "$_DELEGATE_SETUP_DONE" ]] && return 0 2>/dev/null || true
_DELEGATE_SETUP_DONE=1

if [ -f "$REPO_ROOT/flake.nix" ] && command -v nix >/dev/null 2>&1; then
  nix develop "$REPO_ROOT" --command bash -c \
    "cd $WORKTREE_ROOT && <install command --quiet>"
elif [ -f "$REPO_ROOT/shell.nix" ] && command -v nix-shell >/dev/null 2>&1; then
  nix-shell "$REPO_ROOT/shell.nix" --run \
    "bash -c 'cd $WORKTREE_ROOT && <install command --quiet>'"
else
  echo "ERROR: shell.nix/flake.nix found but nix-shell/nix not on PATH" >&2
  exit 1
fi
```

#### Nix premerge.sh

For nix repos, premerge.sh is **self-contained** — it runs install + test inside its own `nix-shell` invocation. Do NOT source setup.sh (the nix environment doesn't persist into the parent shell).

```bash
#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKTREE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GIT_COMMON="$(git -C "$WORKTREE_ROOT" rev-parse --git-common-dir)"
REPO_ROOT="$(cd "$GIT_COMMON/.." && pwd)"

nix-shell "$REPO_ROOT/shell.nix" --run \
  "bash -c 'cd $WORKTREE_ROOT && <install command> && <test command>'"
```

---

### Python

#### Choosing the right install command

| Condition | Install command |
|---|---|
| `poetry.lock` present | `poetry install --with dev` (or `poetry install`) |
| `uv.lock` + `[dependency-groups]` in pyproject.toml | `uv sync --group dev` |
| `uv.lock` + `[project.optional-dependencies]` | `uv sync --extra dev` |
| `uv.lock`, no extras/groups | `uv sync` |
| No lockfile, uv available | `uv pip install -e ".[dev]"` |
| No lockfile, no uv | `pip install ".[dev]"` |

Key rules:
- **Check for `poetry.lock` first** — if present, use `poetry install` exclusively. Poetry manages its own venv; set `POETRY_VIRTUALENVS_IN_PROJECT=true` to keep it in the worktree.
- **Check for `uv.lock` next** — always prefer `uv sync` over `uv pip install`. No separate `uv venv` needed.
- **Never pass `--no-cache`** — the daemon sets team-level cache directories via `settings.env` so all worktrees share a common cache.

Anti-patterns — never write these:
- `uv pip install -r requirements.txt` when `uv.lock` exists — use `uv sync`
- `uv pip install --no-cache` or `uv sync --no-cache` — disables shared cache
- `pip install -r requirements.txt` when uv is available — always prefer uv

#### Python setup.sh (3-tier strategy)

```bash
#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.
_cp_tree() { cp -Rc "$@" 2>/dev/null || cp -r --reflink=auto "$@" 2>/dev/null || cp -r "$@"; }

WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$WORKTREE_ROOT/.venv"
MAIN_VENV="$(cd "$(git -C "$WORKTREE_ROOT" rev-parse --git-common-dir)/.." && pwd)/.venv"

# Re-entrance guard
[[ -n "$_DELEGATE_SETUP_DONE" ]] && { source "$VENV_DIR/bin/activate"; return 0 2>/dev/null || exit 0; }
_DELEGATE_SETUP_DONE=1

if ! "$VENV_DIR/bin/python" -c "import pytest" 2>/dev/null; then
  rm -rf "$VENV_DIR"
  cd "$WORKTREE_ROOT"
  python3 -m venv "$VENV_DIR"
  _installed=0

  # Strategy 1: copy site-packages from the main repo venv (no network)
  if [ "$_installed" -eq 0 ] && [ -d "$MAIN_VENV" ]; then
    MAIN_SITE="$(ls -d "$MAIN_VENV"/lib/python*/site-packages 2>/dev/null | head -1)"
    WORKTREE_SITE="$(ls -d "$VENV_DIR"/lib/python*/site-packages 2>/dev/null | head -1)"
    if [ -n "$MAIN_SITE" ] && [ -d "$MAIN_SITE" ]; then
      _cp_tree "$MAIN_SITE/." "$WORKTREE_SITE/"
      _installed=1
    fi
  fi

  # Strategy 2: install from system cache (no network)
  if [ "$_installed" -eq 0 ]; then
    _SYS_UV_CACHE="${HOME}/.cache/uv"
    _SYS_PIP_CACHE="${HOME}/.cache/pip"
    if command -v uv >/dev/null 2>&1 && [ -d "$_SYS_UV_CACHE" ]; then
      uv pip install --python "$VENV_DIR/bin/python" ".[dev]" --cache-dir "$_SYS_UV_CACHE" --offline --quiet 2>/dev/null && _installed=1 || true
    fi
    if [ "$_installed" -eq 0 ] && [ -d "$_SYS_PIP_CACHE" ]; then
      "$VENV_DIR/bin/pip" install ".[dev]" --cache-dir "$_SYS_PIP_CACHE" --no-index --quiet 2>/dev/null && _installed=1 || true
    fi
  fi

  # Strategy 3: full install (needs network — CI, first checkout)
  if [ "$_installed" -eq 0 ]; then
    if command -v uv >/dev/null 2>&1; then
      uv pip install --python "$VENV_DIR/bin/python" ".[dev]" --quiet 2>/dev/null && _installed=1 || true
    fi
    if [ "$_installed" -eq 0 ]; then
      "$VENV_DIR/bin/pip" install ".[dev]" --quiet 2>/dev/null && _installed=1 || true
    fi
  fi
fi

source "$VENV_DIR/bin/activate"
export PYTHONPATH="$WORKTREE_ROOT${PYTHONPATH:+:$PYTHONPATH}"
```

---

### Node

| Condition | Command |
|---|---|
| `pnpm-lock.yaml` | `pnpm install --frozen-lockfile` |
| `yarn.lock` | `yarn install --frozen-lockfile` |
| `package-lock.json` | `npm ci` |
| No lockfile | `npm install` |

Key rules:
- Always use the lockfile command when a lockfile exists.
- `node_modules/` must be local to each worktree.
- Export PATH: `export PATH="$WORKTREE_ROOT/node_modules/.bin:$PATH"`.
- Never use `npm install -g`.

#### Node setup.sh (3-tier strategy)

```bash
#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.
_cp_tree() { cp -Rc "$@" 2>/dev/null || cp -r --reflink=auto "$@" 2>/dev/null || cp -r "$@"; }

WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Re-entrance guard
[[ -n "$_DELEGATE_SETUP_DONE" ]] && { export PATH="$WORKTREE_ROOT/node_modules/.bin:$PATH"; return 0 2>/dev/null || true; }
_DELEGATE_SETUP_DONE=1

MAIN_REPO="$(cd "$(git -C "$WORKTREE_ROOT" rev-parse --git-common-dir)/.." && pwd)"
cd "$WORKTREE_ROOT"
if [ ! -d node_modules ]; then
  _nm_installed=0
  # Strategy 1: copy node_modules from main repo (no network)
  if [ -d "$MAIN_REPO/node_modules" ]; then
    _cp_tree "$MAIN_REPO/node_modules" node_modules && _nm_installed=1
  fi
  # Strategy 2: install from system cache (no network)
  if [ "$_nm_installed" -eq 0 ]; then
    npm ci --prefer-offline --silent 2>/dev/null && _nm_installed=1 || true
  fi
  # Strategy 3: full install (needs network)
  if [ "$_nm_installed" -eq 0 ]; then
    npm ci --silent 2>/dev/null || true      # adapt for pnpm/yarn
  fi
fi

export PATH="$WORKTREE_ROOT/node_modules/.bin:$PATH"
```

---

### Rust

```bash
#!/usr/bin/env bash
set -e
WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKTREE_ROOT"
[[ -n "$_DELEGATE_SETUP_DONE" ]] && return 0 2>/dev/null || true
_DELEGATE_SETUP_DONE=1
cargo build --quiet
```

Premerge: `cargo test`.

---

### Go

```bash
#!/usr/bin/env bash
set -e
WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKTREE_ROOT"
[[ -n "$_DELEGATE_SETUP_DONE" ]] && return 0 2>/dev/null || true
_DELEGATE_SETUP_DONE=1
go mod tidy
```

Premerge: `go test ./...`.

---

### Ruby

```bash
#!/usr/bin/env bash
set -e
WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKTREE_ROOT"
export BUNDLE_PATH="$WORKTREE_ROOT/vendor/bundle"
[[ -n "$_DELEGATE_SETUP_DONE" ]] && return 0 2>/dev/null || true
_DELEGATE_SETUP_DONE=1
if [ ! -d vendor/bundle ]; then
  bundle install --path vendor/bundle --quiet
fi
```

Premerge: `bundle exec rspec` or `bundle exec rake test`.

---

### premerge.sh (non-Nix stacks)

The premerge pattern is the same regardless of stack — source setup.sh (the re-entrance guard makes this cheap), then run tests:

> **Nix repos**: use the self-contained Nix premerge.sh template above — do NOT source setup.sh.

```bash
#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKTREE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/setup.sh"
cd "$WORKTREE_ROOT"

# Run the test suite — adapt for the stack:
pytest tests/ -x -q      # Python
# npm test                # Node
# cargo test              # Rust
# go test ./...           # Go
# bundle exec rspec       # Ruby
```

---

## Step 3: Keeping scripts up to date

When you install new packages or change dependencies:
1. Update `.delegate/setup.sh` to include the install step
2. Update `.delegate/premerge.sh` if test commands change
3. Commit both changes alongside your code changes

To regenerate from scratch (e.g., after adding a new sub-project): `python -m delegate.env --force "$WORKTREE_ROOT"`.

## Safety rules

These are hard constraints. Never violate them.

**Never:**
- `sudo` — do not use it under any circumstances
- Install system packages (`brew install`, `apt install`, `yum install`, etc.)
- Start system services (`postgres`, `redis`, `docker`, etc.)
- Change global tool versions (`nvm use --default`, `pyenv global`, etc.)
- Share a `.venv`, `node_modules`, or any environment with the main repo or other worktrees — every worktree gets its own

**Always:**
- Use project-local environments (`.venv`, `node_modules`, etc.)
- Use lockfiles when available (`uv.lock`, `package-lock.json`, `Cargo.lock`, etc.)
- Check that required tools exist and fail with clear messages if they don't
- Handle the common case, not every edge case

**If the project requires system dependencies** (Postgres, Redis, etc.): add checks at the top of `setup.sh` that verify they exist and print clear install instructions if missing. For example:

```bash
command -v psql >/dev/null 2>&1 || { echo "ERROR: PostgreSQL not found. Install with: brew install postgresql"; exit 1; }
```

Do not attempt to install the dependency yourself — that's the human's responsibility.

## Notes

- Always source `.delegate/setup.sh` before running `python`, `pytest`, `npm`, etc. — do NOT use system-level interpreters.
- If setup.sh fails (exits non-zero), investigate and fix it before proceeding.
- The merge worker will run `.delegate/premerge.sh` before merging — keep it passing.
