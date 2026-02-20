# Environment Setup

Every repo worktree may need an environment activated before you can run code or tests. Your job is to detect, create, and use the right setup for each repo.

## Step 1: Check for .delegate/setup.sh — MANDATORY

This is your FIRST action on every task, before writing any code or running any command. No exceptions.

```
ls .delegate/setup.sh 2>/dev/null && echo EXISTS || echo MISSING
```

- **If EXISTS**: source it before doing anything else: `. .delegate/setup.sh`
- **If MISSING**: you MUST create both `.delegate/setup.sh` AND `.delegate/premerge.sh` (see templates below), commit them (`git add .delegate/ && git commit -m "chore: add delegate env scripts"`), then source setup.sh.

Do NOT skip this step. Do NOT start coding without an active environment. If you find yourself writing application code before running this check, stop and do it first.

## Step 2: Creating .delegate/setup.sh (if missing)

Look at the repo root for existing environment tooling and use it — do not duplicate what already exists. Detection order matters — check in this order:

1. **`shell.nix` or `flake.nix`** → Nix environment. See "Nix" guide below.
2. **`Dockerfile` or `docker-compose.yml`** → Containerized. Note this in setup.sh; most setup/test steps may need to run inside the container.
3. **`mise.toml` or `.tool-versions`** → mise/asdf manages runtimes. Use `mise install && mise activate`.
4. **`Makefile`** with `install` or `setup` targets → call `make install` or `make setup`.
5. **`pyproject.toml` or `requirements.txt`** → Python. See "Python" guide below.
6. **`package.json`** → Node. See "Node" guide below.
7. **`Cargo.toml`** → Rust. See "Rust" guide below.
8. **`go.mod`** → Go. See "Go" guide below.
9. **`Gemfile`** → Ruby. See "Ruby" guide below.
10. **Nothing found** → write a placeholder with a comment asking the user to fill it in.

**Isolation requirement — CRITICAL**: every worktree MUST have its own isolated environment (`.venv`, `node_modules`, `vendor/bundle`, etc.) created INSIDE the worktree directory. NEVER reuse or symlink to the main repo's environment, another worktree's environment, or any absolute path outside the worktree.

Forbidden patterns — if you catch yourself writing any of these, stop and fix it:
- `VENV_DIR="$REPO_ROOT/.venv"` — links to the main repo's venv
- `VENV_DIR="/Users/.../some-project/.venv"` — hardcoded absolute path to another location
- `source "$REPO_ROOT/.venv/bin/activate"` — activating a shared venv
- "reuse the pre-existing venv" / "shared across worktrees" — this reasoning is always wrong

The correct pattern is always: `VENV_DIR="$WORKTREE_ROOT/.venv"` — the venv lives inside the worktree. If creating the venv fails, exit with a clear error — do NOT fall back to sharing another environment.

**Network IS available.** You can run `pip install`, `uv sync`, `npm install`, etc. normally. Do not assume network is unavailable — it is not. Do not create `.pth` files, symlinks, or any other mechanism to borrow packages from outside the worktree.

---

## Nix

When `shell.nix` or `flake.nix` is present, the repo defines its own hermetic environment. Use nix machinery — do not bypass it with ad-hoc tool discovery.

### Key principle

For nix repos, setup.sh and premerge.sh should run all install and test commands **inside** the nix shell. This guarantees the exact toolchain the repo declares. The pattern is:

```bash
nix-shell /path/to/shell.nix --run "bash -c 'cd $WORKTREE_ROOT && <install command>'"
```

Use `bash -c` inside `--run` so the shellHook's PATH exports are inherited by the inner commands. `cd` to the worktree explicitly, since `nix-shell` may start in a different directory.

For flake-based repos (`flake.nix` + `nix` >= 2.4):
```bash
nix develop /path/to/repo --command bash -c 'cd $WORKTREE_ROOT && <install command>'
```

### Finding the repo root from a linked worktree

Worktrees are linked git directories. `git rev-parse --show-toplevel` returns the worktree path, not the main repo root. Use `git rev-parse --git-common-dir` instead:

```bash
WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GIT_COMMON="$(git -C "$WORKTREE_ROOT" rev-parse --git-common-dir)"
REPO_ROOT="$(cd "$GIT_COMMON/.." && pwd)"
```

`REPO_ROOT` is where `shell.nix`/`flake.nix` live. Use `REPO_ROOT` ONLY for locating nix files — never use it to share environments. The venv/node_modules must still live inside `$WORKTREE_ROOT`.

### Nix setup.sh template

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

if [ -f "$REPO_ROOT/shell.nix" ] && command -v nix-shell >/dev/null 2>&1; then
  # Run install inside the nix shell so the shellHook environment is active.
  # Adapt the install command to the project's language/tooling.
  nix-shell "$REPO_ROOT/shell.nix" --run \
    "bash -c 'cd $WORKTREE_ROOT && <install command --quiet>'"
elif [ -f "$REPO_ROOT/flake.nix" ] && command -v nix >/dev/null 2>&1; then
  nix develop "$REPO_ROOT" --command bash -c \
    "cd $WORKTREE_ROOT && <install command --quiet>"
else
  echo "ERROR: shell.nix/flake.nix found but nix-shell/nix not on PATH" >&2
  exit 1
fi
```

Replace `<install command --quiet>` with whatever the project needs (e.g. `uv sync --group dev --quiet`, `npm ci --silent`, `cargo build --quiet`). The nix shell provides all declared tools via its `packages` and `shellHook`.

### Nix premerge.sh template

For nix repos, premerge.sh must be **self-contained** — it runs install + test inside its own `nix-shell` invocation. Do NOT source setup.sh from a nix premerge.sh (the nix environment from setup.sh doesn't persist into the parent shell).

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

## Python

### Choosing the right install command

Before writing setup.sh, inspect the project to pick the correct install command:

| Condition | Install command |
|---|---|
| `poetry.lock` present (Poetry project) | `poetry install` (or `poetry install --with dev` if dev group exists) |
| `uv.lock` present + `[dependency-groups]` in pyproject.toml (PEP 735) | `uv sync --group dev` |
| `uv.lock` present + `[project.optional-dependencies]` in pyproject.toml | `uv sync --extra dev` |
| `uv.lock` present, no extras/groups | `uv sync` |
| No lockfile, uv available, extras defined | `uv pip install -e ".[dev]"` |
| No lockfile, uv available, no extras | `uv pip install -e .` |
| No uv available | `pip install ".[dev]"` (non-editable — safer across pip versions) |

Key rules:
- **Check for `poetry.lock` first** — if present, the project uses Poetry. Do not mix `uv` or `pip` into a Poetry project; use `poetry install` exclusively. Poetry manages its own venv (at `$(poetry env info --path)`); activate with `source "$(poetry env info --path)/bin/activate"`.
- **Check for `uv.lock` next** — if present, always prefer `uv sync` over `uv pip install`. `uv sync` reads the lockfile and ensures reproducible installs.
- **`uv sync` creates the venv itself** — no separate `uv venv` call needed. The venv lands at `.venv/` in the current directory.
- **`uv pip install -e ".[dev]"` silently skips `[dependency-groups]`** — use it only when there is no `uv.lock`. It works for `[project.optional-dependencies]` but not PEP 735 groups.
- **pip fallback**: use non-editable install (`pip install ".[dev]"` not `-e`) — editable installs require pip >= 21.3 + a PEP 660 build backend. Older pip + hatchling combinations fail silently.
- **Detect dependency format**: `grep -q '^\[dependency-groups\]' pyproject.toml` for PEP 735; `grep -q '^\[tool.poetry\]' pyproject.toml` for Poetry.
- **Use the global uv cache** — never pass `--no-cache` routinely. uv's shared cache (`~/.cache/uv`) is a major speed advantage over pip; reusing compiled wheels across worktrees makes installs fast. Only pass `--no-cache` if you have diagnosed a specific cache corruption (e.g. `uv cache clean` after an interrupted download). Same principle for Node: prefer `pnpm` (shared content-addressable store) or `npm ci` with its local cache over `--prefer-offline` flags that skip caching entirely.

### Poetry setup.sh template

```bash
#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.

WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKTREE_ROOT"

# Re-entrance guard
[[ -n "$_DELEGATE_SETUP_DONE" ]] && { source "$WORKTREE_ROOT/.venv/bin/activate"; return 0 2>/dev/null || exit 0; }
_DELEGATE_SETUP_DONE=1

# Force venv inside the worktree (not in ~/.cache/pypoetry/virtualenvs/)
export POETRY_VIRTUALENVS_IN_PROJECT=true

# Install deps (creates/updates .venv/ in the worktree)
poetry install --with dev --quiet 2>/dev/null || poetry install --quiet

source "$WORKTREE_ROOT/.venv/bin/activate"
```

Premerge: `poetry run pytest tests/ -x -q` (or `source` the venv first and run `pytest` directly).

### Python setup.sh template

Adjust the install command using the decision table above. If the repo also has `shell.nix`/`flake.nix`, use the Nix template instead and run the Python install command inside `nix-shell --run`.

```bash
#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.

WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$WORKTREE_ROOT/.venv"

# Re-entrance guard — skip if already sourced (premerge.sh sources us too)
[[ -n "$_DELEGATE_SETUP_DONE" ]] && { source "$VENV_DIR/bin/activate"; return 0 2>/dev/null || exit 0; }
_DELEGATE_SETUP_DONE=1

if ! "$VENV_DIR/bin/python" -c "import pytest" 2>/dev/null; then
  rm -rf "$VENV_DIR"
  cd "$WORKTREE_ROOT"
  if command -v uv >/dev/null 2>&1; then
    # CHOOSE one based on the decision table:
    #   uv.lock + [dependency-groups]:             uv sync --group dev
    #   uv.lock + [project.optional-dependencies]: uv sync --extra dev
    #   no lockfile:                               uv pip install -e ".[dev]"
    uv sync --group dev --quiet
  else
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install ".[dev]" --quiet
  fi
fi

source "$VENV_DIR/bin/activate"
```

---

## Node

### Choosing the right package manager

| Condition | Command |
|---|---|
| `pnpm-lock.yaml` present | `pnpm install --frozen-lockfile` |
| `yarn.lock` present | `yarn install --frozen-lockfile` |
| `package-lock.json` present | `npm ci` |
| No lockfile | `npm install` |

Key rules:
- **Always use the lockfile command** (`--frozen-lockfile` / `npm ci`) when a lockfile exists — this guarantees reproducible installs.
- **Install into the worktree** — `node_modules/` must be local to each worktree, not shared.
- **Export PATH**: add `export PATH="$PWD/node_modules/.bin:$PATH"` so local binaries (jest, eslint, etc.) are found without `npx`.
- **Never use `npm install -g`** — global installs pollute the shared environment.

### Node setup.sh template

```bash
#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.

WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKTREE_ROOT"

# Re-entrance guard
[[ -n "$_DELEGATE_SETUP_DONE" ]] && { export PATH="$WORKTREE_ROOT/node_modules/.bin:$PATH"; return 0 2>/dev/null || exit 0; }
_DELEGATE_SETUP_DONE=1

if [ ! -d node_modules ]; then
  # Use the lockfile-aware install for the detected package manager
  if [ -f pnpm-lock.yaml ]; then
    pnpm install --frozen-lockfile --silent
  elif [ -f yarn.lock ]; then
    yarn install --frozen-lockfile --silent
  else
    npm ci --silent
  fi
fi

export PATH="$WORKTREE_ROOT/node_modules/.bin:$PATH"
```

Premerge: `npm test`, `npm run test`, or whichever script the project defines (check `package.json` → `scripts`).

---

## Rust

### Install command

```bash
cargo build
```

Key rules:
- `target/` is local to each worktree by default — no isolation steps needed.
- Use `cargo test` for running tests in premerge.sh.
- If the project has a `Cargo.lock`, it is committed and `cargo build` will use it automatically.
- Never run `cargo install` for project dependencies — use `cargo build`/`cargo test` only.

### Rust setup.sh template

```bash
#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.

WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKTREE_ROOT"

# Re-entrance guard
[[ -n "$_DELEGATE_SETUP_DONE" ]] && return 0 2>/dev/null || true
_DELEGATE_SETUP_DONE=1

cargo build --quiet
```

Premerge: `cargo test`.

---

## Go

### Install command

```bash
go mod tidy
```

Key rules:
- The Go module cache (`$GOPATH/pkg/mod`) is shared across worktrees — this is safe and expected.
- `go mod tidy` ensures `go.sum` is up to date.
- Use `go test ./...` for running tests in premerge.sh.
- Never use `go get` to add dependencies without updating `go.mod` and `go.sum`.

### Go setup.sh template

```bash
#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.

WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKTREE_ROOT"

# Re-entrance guard
[[ -n "$_DELEGATE_SETUP_DONE" ]] && return 0 2>/dev/null || true
_DELEGATE_SETUP_DONE=1

go mod tidy
```

Premerge: `go test ./...`.

---

## Ruby

### Install command

```bash
bundle install --path vendor/bundle
```

Key rules:
- `--path vendor/bundle` keeps gems local to the worktree — never install to the system gem dir.
- If a `Gemfile.lock` exists, `bundle install` will use it automatically (reproducible install).
- Use `bundle exec rspec` or `bundle exec rake test` for tests (check the project's Rakefile/Gemfile).
- Set `BUNDLE_PATH=vendor/bundle` in the environment if bundle commands can't find gems.

### Ruby setup.sh template

```bash
#!/usr/bin/env bash
set -e
# Created by delegate. Edit as needed.

WORKTREE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKTREE_ROOT"

export BUNDLE_PATH="$WORKTREE_ROOT/vendor/bundle"

# Re-entrance guard
[[ -n "$_DELEGATE_SETUP_DONE" ]] && return 0 2>/dev/null || true
_DELEGATE_SETUP_DONE=1

if [ ! -d vendor/bundle ]; then
  bundle install --path vendor/bundle --quiet
fi
```

Premerge: `bundle exec rspec` or `bundle exec rake test` (check the project).

---

## premerge.sh template (non-Nix stacks)

The premerge.sh pattern is the same regardless of stack — source setup.sh (the re-entrance guard makes this cheap if the merge worker already sourced it), `cd` to the worktree root, then run tests:

> **Nix repos**: use the self-contained Nix premerge.sh template above instead — do NOT source setup.sh, since the nix environment doesn't persist into the parent shell.

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

Both files must start with `#!/usr/bin/env bash` and `set -e`. Add a comment: `# Created by delegate. Edit as needed.`

Create the `.delegate/` directory if it doesn't exist. Commit both files:
```
git add .delegate/
git commit -m "chore: add delegate env scripts"
```

## Step 3: Keeping scripts up to date

When you install new packages or change dependencies:
1. Update `.delegate/setup.sh` to include the install step
2. Update `.delegate/premerge.sh` if test commands change
3. Commit both changes alongside your code changes

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
