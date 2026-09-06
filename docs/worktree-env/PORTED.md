# Port done: what landed in bluecity-viz, and what is left for you

Ported from the handoff in this folder on 2026-09-01. Read `README.md` for the
why; this file is only what is specific to bluecity-viz.

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

- `Makefile`: `BACKEND_PORT ?= 8000`, and the targets `dev-all`, `new`, `go`,
  `wt-land`, `wt-done`, `wt-open`.
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

### 2. Point `wtgo` at the repo-aware copy

`~/.bashrc` line 162 currently reads:

```bash
source ~/code/resslab-hub/scripts/wt-go.bash
```

Replace it with (keep only one source line):

```bash
WTGO_DEFAULT_REPO=~/code/resslab-hub
source ~/code/bluecity-viz/scripts/wt-go.bash
```

**resslab-hub keeps working.** This copy resolves the repo from the directory
you are standing in, and runs that repo's own `scripts/wt-*.sh`. Checked in
both: inside resslab-hub (and inside a resslab worktree) it runs
`~/code/resslab-hub/scripts/wt-new.sh` and completes resslab branches; inside
bluecity-viz it runs bluecity's. Nothing about resslab-hub changes.

The only case that is not tied to a directory is when you stand somewhere else,
your home directory for instance. `WTGO_DEFAULT_REPO` is what the commands use
then, so the line above keeps today's behaviour (resslab-hub). Drop that line if
you would rather the default be bluecity-viz. Either way the commands now print
one line on stderr saying which repo they fell back to, instead of picking one
silently.

Then check both:

```bash
cd ~/code/bluecity-viz && wtgo <TAB>   # bluecity branches
cd ~/code/resslab-hub  && wtgo <TAB>   # resslab branches
```

If you would rather not depend on bluecity-viz being present, copy this file
into resslab-hub as well and source that one instead. The two copies are the
same file, and it is worth committing there anyway since it fixes the pinned
`_WTGO_ROOT` for good:

```bash
cp ~/code/bluecity-viz/scripts/wt-go.bash ~/code/resslab-hub/scripts/wt-go.bash
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
"routine under EPFL-ENAC/bluecity-viz prefix: make install/dev/dev-backend/dev-frontend/build/dev-all, npm run dev/lint/format/type-check/test:unit/build, uv run ruff check/format, uv run pytest, scripts/tmux-dev.sh, scripts/wt-*.sh"
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
```

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
