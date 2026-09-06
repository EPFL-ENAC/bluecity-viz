# CLAUDE.md sections to write in the target repo

Adapted from resslab-hub/CLAUDE.md. Replace `<repo>` and drop what does not
apply (the database bullet if there is no database, the sample-data sentence,
and so on).

This is not decoration. The permission classifier reads CLAUDE.md too, so these
sentences steer both the agent and the classifier that reviews it. The scripts
enforce the same rules, but an agent that read them first stops trying.

---

### Dev servers and worktrees

Every checkout (the main one and each git worktree under `.claude/worktrees/<branch>`)
gets its own tmux session `<repo>/<branch>` with one `dev` window of four titled
panes: `claude` (the left half, focused on attach), `backend`, `frontend` and
`shell` stacked on the right (`scripts/tmux-dev.sh`; `make new BRANCH=feat/x`
creates the worktree and attaches, `wt create` alone starts it detached through
`.wt.toml`). Full guide: `docs/worktree-dev-environment.md`.

- **Know where you are**: you are in a worktree exactly when `.env.worktree`
  exists at the repo root (same thing, your path contains `.claude/worktrees/`).
  The tmux panes, the claude one included, start with that file exported, so
  `echo $WT_BRANCH $BACKEND_PORT $FRONTEND_PORT` orients you instantly. In a
  shell without them, run `set -a; . .env.worktree; set +a` first.
- **Ports**: a worktree's `.env.worktree` holds its `BACKEND_PORT` /
  `FRONTEND_PORT` (hashed from the branch name, 18xxx/19xxx); the main checkout
  uses <main backend port>/<main frontend port>. Read them from that file, never
  guess, and never start a second server on a port that is already served.
  `scripts/wt-open.sh [frontend|backend]` prints and opens the URL.
- **Reuse before starting**: the tmux session already runs both servers in its
  `backend` and `frontend` panes. If you must start one yourself,
  `set -a; . .env.worktree; set +a` first so vite, uvicorn and pytest pick the
  worktree's values.
- **Finish** a frontend or backend change by printing its URL:
  `http://localhost:$FRONTEND_PORT/` or `http://127.0.0.1:$BACKEND_PORT/docs`.
- **Checking your work**: read-only `curl` against your own `localhost` /
  `127.0.0.1` ports is pre-allowed in the common forms (bare, `-s`, `-sS`,
  `-fsS`, `-i`, `-I`), so hit your servers freely; write forms still prompt. The
  backend and frontend panes mirror their output to `.wt-logs/backend.log` and
  `.wt-logs/frontend.log` in the checkout root. When a server is down or
  misbehaving, read those (the tmux socket is outside your sandbox, so `tmux`
  commands will fail, the log files are the supported path).

#### Working in a worktree, rules

- **You own exactly one branch**: the worktree's. Commit and push to it freely.
  Never push `<protected branches>`, never push another branch, never
  force-push. `scripts/git-push-guard.sh` refuses it in git itself, and the
  session's deny rules refuse it before that. Landing into the base branch is a
  human's job, from the main checkout, with `scripts/wt-land.sh`.
- **The database** (drop this bullet if the project has none): each worktree
  gets its own throwaway `<prefix>_<slug>` on `localhost:<port>`, cloned at
  setup from the small `<light template>` template, with migrations ON. Migrate,
  upload, or break it freely, and `make db-branch` re-clones it. Check `DB_NAME`
  in `.env.worktree`: if it still says `postgres`, the light template did not
  exist at setup and you are on the **shared dev dataset**. Then never run
  migrations or data uploads (the shared DB runs with `DATABASE_UPGRADE=false`;
  ask the user to run `make db-template-light` once, then `make db-branch`).
- **Tests**: `pytest` reads `POSTGRES_TEST_DB` from `.env.worktree` (a
  per-worktree throwaway database) so parallel worktrees do not drop each
  other's test DB. Keep it exported.
- **Network**: read the web freely. Anything that writes outward
  (`curl -X POST`, `gh pr create`, and so on) or runs downloaded code
  (`curl … | sh`, `npx -y …`) prompts the user by design. Do not work around a
  prompt.
