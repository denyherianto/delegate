# Environment Setup

Every repo worktree may need an environment activated before you can run code or tests. Your job is to detect, create, and use the right setup for each repo.

## Step 1: Check for .delegate/setup.sh

At the start of every task, check whether `.delegate/setup.sh` exists in the worktree root:

```
ls .delegate/setup.sh 2>/dev/null && echo exists || echo missing
```

- **If it exists**: source it before doing anything else: `. .delegate/setup.sh`
- **If it does not exist**: create it (see below), commit it, then source it

## Step 2: Creating .delegate/setup.sh (if missing)

Look at the repo root for existing environment tooling and use it — do not duplicate what already exists:

- `flake.nix` or `shell.nix` → Nix environment. Use `nix develop` or `nix-shell`.
- `Dockerfile` or `docker-compose.yml` → Containerized. Note this in setup.sh; most setup/test steps may need to run inside the container.
- `mise.toml` or `.tool-versions` → mise/asdf manages runtimes. Use `mise install && mise activate`.
- `Makefile` with `install` or `setup` targets → call `make install` or `make setup`.
- `pyproject.toml` or `requirements.txt` → Python. Use `uv venv && uv pip install -e ".[dev]"` (fall back to `python -m venv .venv && pip install -e ".[dev]"` if uv is unavailable). Activate with `source .venv/bin/activate`.
- `package.json` → Node. Check for `pnpm-lock.yaml` (use pnpm), `yarn.lock` (use yarn), otherwise `npm ci`. Export `PATH="$PWD/node_modules/.bin:$PATH"`.
- `Cargo.toml` → Rust. `cargo build`.
- `go.mod` → Go. `go mod tidy`.
- `Gemfile` → Ruby. `bundle install`.
- Nothing found → write a placeholder with a comment asking the user to fill it in.

Also create `.delegate/premerge.sh` with the appropriate test command (pytest, npm test, cargo test, go test ./..., etc.). If no test runner is found, write a no-op.

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
