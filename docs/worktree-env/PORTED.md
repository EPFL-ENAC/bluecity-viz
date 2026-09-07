# Port done: what landed in bluecity-viz, and what is left for you

Ported from the handoff in this folder on 2026-09-01, committed on the branch
`chore/improve-worktree-config` on 2026-09-06 with the fixes listed at the end.
Read `README.md` for the why; this file is only what is specific to bluecity-viz.

## Choices made

- Base branch `dev`, protected branches `dev` and `main` (no `stage` here).
- No database half at all: no `wt-db.sh`, no `db-*` targets, no compose.
- The frontend reaches the backend through vite's own `/api` proxy, so nothing
  per-worktree has to be written into an env file.
- The push guard is a plain `pre-push` hook, installed by `wt-setup.sh` (this
  repo has no lefthook).
- A worktree installs `frontend/` and `backend/` only, not `processing/`.

## Files added

```
.wt.toml                        wt hooks (post_create, post_checkout, pre_remove)
scripts/wt-lib.sh               constants and shared helpers
scripts/wt-setup.sh             make a worktree runnable (idempotent)
scripts/wt-teardown.sh          kill the session, free the ports
scripts/wt-new.sh               wtgo / make new
scripts/wt-done.sh              wtdone
scripts/wt-land.sh              rebase, PR, squash-merge into dev
scripts/wt-open.sh              print and open a branch's URL
scripts/tmux-dev.sh             the 4-pane session
scripts/git-push-guard.sh       a worktree may push only its own branch
scripts/wt-go.bash              wtgo / wtdone shell functions, repo-aware
scripts/claude-worktree-settings.json   template for each worktree's settings.local.json
```

## Files changed

- `Makefile`: `BACKEND_PORT ?= 8000`, and the targets `tmux-dev-all` (the tmux
  session), `dev-all` (alias of `dev`, same name as in resslab-hub), `new`,
  `go`, `wt-land`, `wt-done`, `wt-open`.
- `backend/Makefile`: same `BACKEND_PORT ?= 8000`.
- `frontend/vite.config.ts`: `port` from `FRONTEND_PORT`, a new `^/api/.*` proxy
  and the existing `/data` proxy both targeting `127.0.0.1:$BACKEND_PORT`.
- `frontend/src/services/trafficAnalysis.ts`, `services/cvrp.ts`,
  `config/biodiversity.ts`: the API base URL is now the relative `/api/v1/...`
  in dev too (it already was in prod), so each checkout hits its own backend.
- `backend/test_api.py`, `backend/test_with_data.py`: `BASE_URL` reads
  `BACKEND_PORT`.
- `.gitignore`: `.env.worktree`, `.wt-logs/`, `PROMPT.md`, `.claude/worktrees/`,
  `.claude/settings.local.json`.
- `CLAUDE.md`: the "Dev servers and worktrees" section.

## Two changes made on purpose, different from resslab-hub

1. **The dev data is symlinked, not copied.** `frontend/public/geodata` is
   103 MB of PMTiles and the `backend/data/*.csv` centroids are untracked, so
   `wt-setup.sh` links them to the main checkout. Deleting a worktree removes
   the links, never the targets (checked).
2. **The pre-push hook is chained, not overwritten.** This repo already had a
   git-lfs `pre-push` hook (and a `.lfsconfig` pointing at the EPFL LFS server).
   Setup moves it to `pre-push.before-wt` and the installed hook runs it after
   the guard, with the same refs on its stdin. Setup also follows
   `core.hooksPath` if husky is ever installed, so the guard cannot end up in a
   directory git ignores.

## What you have to do by hand

An agent cannot write these (they are outside the repo, or inside `.git`).

### 1. Finish removing the test worktree

The smoke test left metadata behind, the sandbox could not delete it:

```bash
git worktree prune
git branch -D test/smoke
```

### 2. `wtgo` from one source line

`~/.bashrc` sources `~/code/resslab-hub/scripts/wt-go.bash`. That copy is
repo-aware since 2026-09-06 (branch `chore/improve-worktree-config` there): it
resolves the repo from the directory you stand in and runs that repo's own
`scripts/wt-*.sh`, so one source line serves both repos. Nothing to change
once that branch is in resslab's `dev`. Until then, source that worktree's
copy, or use `make go BRANCH=...` from `~/code/bluecity-viz`.

Standing outside any repo with the tooling (your home directory), the commands
fall back to `WTGO_DEFAULT_REPO` if set, else the repo the sourced file lives
in, and say so on stderr.

Check both:

```bash
cd ~/code/bluecity-viz && wtgo <TAB>   # bluecity branches
cd ~/code/resslab-hub  && wtgo <TAB>   # resslab branches
```

### 3. Add the auto mode entry for this repo

`~/.claude/settings.json`, in `autoMode.environment`, after the `### resslab-hub`
block. The easy way is to run `/auto-mode-setup` from this repo. To paste it by
hand, these five strings match the shape of the resslab-hub ones:

```json
"### bluecity-viz",
"**Trusted repo**: /home/pierre/code/bluecity-viz (EPFL-ENAC/bluecity-viz on github.com, PUBLIC) and its origin remote; git worktrees under /home/pierre/code/bluecity-viz/.claude/worktrees/<branch> are the same repo, and each worktree Claude session owns exactly one branch and may commit/push only to that branch",
"**Default / protected branches**: Default branch: main; work branches are cut from dev and land into dev. Protected branches: dev, main. A worktree session must never push to them; landing into dev happens from the main checkout via scripts/wt-land.sh (scripts/git-push-guard.sh enforces it in git)",
"**CI/CD deploy targets**: GitHub Actions deploy.yml on push to dev and main and on v*.*.* tags (release-please from main); quality-check.yml runs lint, type-check, build and the backend checks on PRs to main. Public site data comes from https://enacit4r-cdn.epfl.ch/bluecity",
"**Sensitive data locations & audiences**: frontend/public/geodata (103 MB of untracked PMTiles) and backend/data/*.csv are shared with worktrees by symlink (read them, never rewrite them in place); S3 upload targets (make upload-frontend-geodata) need BUCKET_NAME and are outward-facing",
"routine under EPFL-ENAC/bluecity-viz prefix: make install/dev/dev-backend/dev-frontend/build/dev-all/tmux-dev-all, npm run dev/lint/format/type-check/test:unit/build, uv run ruff check/format, uv run pytest, scripts/tmux-dev.sh, scripts/wt-*.sh"
```

## Smoke test, once the three steps above are done

```bash
wt create test/smoke origin/dev          # hooks run: setup, then a detached session
tmux ls                                  # "bluecity-viz/test/smoke" exists
cd .claude/worktrees/test-smoke && cat .env.worktree
curl -sI "http://localhost:$FRONTEND_PORT/"        # 200
curl -sI "http://127.0.0.1:$BACKEND_PORT/docs"     # 200
```

In the worktree's frontend, check the map draws (the geodata symlink) and that a
traffic analysis recalculation answers (the `/api` proxy hitting this
worktree's backend, not the main checkout's on 8000).

Then, from inside the worktree:

```bash
git commit --allow-empty -m "test: smoke" && git push   # must work
git push origin HEAD:dev                                # must be REFUSED
git branch -vv                                          # upstream is origin/test/smoke, never origin/dev
```

A second worktree must get a different port pair from the first one (the hash
steps past pairs in use).

Clean up:

```bash
wt remove test/smoke
tmux ls                      # session gone
lsof -i :$BACKEND_PORT       # nothing left
```

If the guard does not refuse, stop and fix it before using the setup for real
work. It is the one piece protecting dev and main from an agent.

## What was verified here, and what was not

Verified in this repo: the guard refuses `dev`, `main` and other branches while
allowing the worktree's own (all four cases run against a real worktree); the
chained hook still gets the refs; `vite.config.ts` gives 19217/18217 with the
worktree env and 5173/8000 without; both Makefiles honour `BACKEND_PORT`;
`wt-setup.sh` links the geodata and the CSVs, writes `.env.worktree` and the
Claude settings; the backend boots in a worktree and reads the symlinked CSVs;
deleting a worktree does not follow the symlinks.

Not verified, the sandbox blocks it: anything touching tmux (the socket is
outside), the real hook install (`.git/hooks` is read-only), `npm install` (the
npm cache is read-only) and therefore `npm run type-check` and a running vite.
Run `make install` then `npm run type-check` in `frontend/` once before trusting
the frontend edits.

## Fixes applied on 2026-09-06

The port was taken on 2026-09-01. resslab-hub fixed several things after that
(`HANDOFF-2026-09-06.md`, section 6); these are the ones that apply here.

- `scripts/claude-worktree-settings.json`: the `python -`, `python3 -`,
  `node -`, `perl -` ask rules are gone. Auto mode edits files through
  `python3 - <<EOF` heredocs, and an ask rule prompted on every one of them.
- `scripts/wt-setup.sh`: step 0 sets `branch.autoSetupMerge simple` and
  `push.autoSetupRemote true`, and repairs the branch's upstream (a branch cut
  from `origin/dev` used to track `origin/dev`, so `git pull` rebased it onto
  dev). Step 2 keeps the ports a previous run wrote in `.env.worktree`
  (delete the file to get a fresh pair). Step 4 reads the settings template
  from the main checkout only, so a branch forked before a template fix cannot
  write old rules back, and copies through a `.tmp` file.
- `scripts/wt-lib.sh`: `branch_ports` hashes `<repo>/<branch>` (the same
  branch name in resslab-hub and bluecity-viz got the same pair) and also
  steps past ports something is listening on (`ss`), not only pairs other
  worktrees of this repo hold. `ENV_WORKTREE_KEYS` lists the keys of
  `.env.worktree`, and `load_env_worktree` unsets them when there is no file.
  `set_env_var` removed (nothing here writes an env file).
- `scripts/tmux-dev.sh`: scrubs `ENV_WORKTREE_KEYS` from the tmux server like
  `ROOT`, the pane prefix unsets them in a checkout without `.env.worktree`
  (a server started from a worktree shell used to hand its ports to the main
  checkout's session), and `@wt_role` is set on all four panes.
- `scripts/wt-new.sh`: default base `origin/$BASE_BRANCH`, prints
  `==> <repo>: <branch>` so a `wtgo` typed in the wrong repo is visible.
- `scripts/wt-land.sh --local`: ran `make lint && make test`, targets this
  root Makefile does not have. Now runs `npm run lint`, `npm run type-check`
  in `frontend/` and, in `backend/`, ruff with CI's blocking selection only
  (`--select E9,F63,F7,F82`, `--no-fix`): a full `ruff check` reports 14 old
  errors and would block every landing.
- `Makefile`: `tmux-dev-all` is the tmux session, `dev-all` is an alias of
  `dev`, same names as resslab-hub.
- `docs/worktree-env/files/` (a snapshot of resslab-hub's scripts and guide)
  is gone; the guide is `~/code/resslab-hub/docs/worktree-dev-environment.md`.

Kept from bluecity's side, on purpose: `wt-done.sh` and the `prefix+X` binding
in `tmux-dev.sh` resolve the script from the pane's own repo (both repos share
one tmux server), `wt-go.bash` is the repo-aware copy, the push guard is a
plain pre-push hook chained with the git-lfs one.
