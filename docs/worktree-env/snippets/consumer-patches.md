# The in-app patches: make every port a variable

Nothing reads `.env.worktree` directly. It is always exported into the
environment (by `tmux-dev.sh` for every pane, or by hand with
`set -a; . .env.worktree; set +a`), and each consumer reads plain env vars.

So the app itself needs a few small changes. This is the part people forget,
and the failure mode is nasty: two worktrees quietly talk to each other's
backend and it looks like an application bug, not a setup bug.

**The rule: every port a service uses to find another one becomes a variable
with the old value as the default.** That includes vite proxy targets,
`VITE_*_URL` values, CORS origins, and OAuth redirect URIs. Grep the repo for
the port numbers (`grep -rn "8000\|5173" --exclude-dir=node_modules`) and fix
every hit before you call the port done.

Below are the three patches from resslab-hub.

## 1. Backend: the port the server listens on

`backend/Makefile`, top of the file:

```make
# Per-checkout overrides (git worktrees export these from .env.worktree, see
# docs/worktree-dev-environment.md); the main checkout keeps the defaults.
BACKEND_PORT ?= 8000
RESSLAB_DATA_DIR ?= ../../resslab-hub-data
```

and in the `dev` target:

```make
dev:
	DOTENV_PATH_FOR_DYNACONF="../secrets/.env" uv run uvicorn resslab_hub.main:app --reload --log-level info --port $(BACKEND_PORT)
```

`?=` matters: the variable only takes the default when the environment does not
already set it, so the main checkout keeps 8000 and a worktree gets its own.

The second variable (`RESSLAB_DATA_DIR`) is the resslab-specific case of a
general problem: any relative path to a sibling repo breaks in a worktree,
because a worktree sits deeper in the tree (`.claude/worktrees/<branch>/`).
`wt-setup.sh` writes the resolved absolute path into `.env.worktree`. If the
target repo has no sibling repo, drop this.

## 2. Frontend: the port vite serves on, and how it finds the backend

`frontend/vite.config.ts`, in the `server` block:

```ts
  server: {
    // Git worktrees run one Vite per branch; wt-setup.sh puts the branch's port in
    // .env.worktree and tmux-dev.sh exports it. The main checkout keeps 5173.
    port: Number(process.env.FRONTEND_PORT) || 5173,
  },
```

For the backend URL, resslab-hub uses an env file: `wt-setup.sh` writes
`VITE_APP_BACKEND_URL=http://127.0.0.1:<port>` into the gitignored
`frontend/.env.development.local` (see `set_env_var` in `wt-lib.sh`).

If the project uses a **vite proxy** instead of a `VITE_*` URL, the target is a
hardcoded string in `vite.config.ts` and it must become a variable too:

```ts
  server: {
    port: Number(process.env.FRONTEND_PORT) || 5173,
    proxy: {
      '^/data.*': {
        target: `http://127.0.0.1:${process.env.BACKEND_PORT || 8000}/data`,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/data/, '')
      }
    }
  },
```

A proxy is actually easier than a `VITE_*` URL: `vite.config.ts` runs in Node,
so it reads `process.env` straight from the exported `.env.worktree`, and
`wt-setup.sh` has nothing to write into an env file at all.

## 3. Tests: a throwaway database per worktree

`backend/tests/conftest.py`, before any application import:

```python
os.environ.setdefault("DOTENV_PATH_FOR_DYNACONF", str(_REPO_DIR / "secrets" / ".env"))
TEST_DB = os.environ.get("POSTGRES_TEST_DB", "resslab_hub_test")
os.environ["POSTGRES_DB"] = TEST_DB
os.environ["DATABASE_UPGRADE"] = "false"
```

Two reasons this sits at the top of the file, not in a fixture. The settings
object is built at import time, so it has to be set before the first
`import <app>`. And it reads the **process environment**, not the dotenv file,
which is exactly why the tmux panes export `.env.worktree` instead of relying on
`secrets/.env`.

Without this, two worktrees running pytest at the same time create and drop the
same `..._test` database under each other.
