# Handoff: the parallel worktree dev environment

One branch, one git worktree, one tmux session, one Claude Code agent, its own
servers and its own database. This folder is a snapshot of that setup in
resslab-hub, packaged so you can port it to another FastAPI + Vue project.

- Source repo: `resslab-hub`, commit `da02c61`, taken on 2026-09-01. The port
  landed here on 2026-09-06 with the fixes resslab-hub made in between, see
  `PORTED.md`.
- Originals live in `resslab-hub/scripts/`, `resslab-hub/.wt.toml` and
  `resslab-hub/docs/worktree-dev-environment.md`. If something here looks stale,
  that repo wins.
- The full guide is `~/code/resslab-hub/docs/worktree-dev-environment.md`
  (this folder used to carry a copy under `files/`, dropped because it went
  stale). This README is the short version plus the porting work. Read the
  guide when you need the why behind a detail.

You are probably a Claude Code session in the target repo. Read this file top to
bottom before touching anything, then work through section 4.

---

## 1. What the setup does

You run several branches at the same time. Each one is a full, isolated dev
environment. Nothing is shared except the git object store and the one Postgres
container.

```
wt create feat/123-thing origin/dev
  └─ .wt.toml → scripts/wt-setup.sh                (idempotent)
       ├─ seeds the gitignored dev files from the main checkout
       ├─ hashes the branch name → .env.worktree  (BACKEND_PORT 18xxx, FRONTEND_PORT 19xxx, DB, test DB)
       ├─ points this frontend at this backend, this backend at its own DB
       ├─ writes .claude/settings.local.json      (sandbox + ask/deny rules for the agent)
       ├─ make install && make hooks
       └─ scripts/tmux-dev.sh --no-attach          → tmux session "<repo>/feat/123-thing"
                                                      one window: claude (left half) | backend / frontend / shell (right)
wt remove feat/123-thing
  └─ .wt.toml → scripts/wt-teardown.sh   (kills the session, frees the ports, drops the branch DB)
```

Daily use:

```bash
wtgo feat/x              # go to that branch's session, creating branch + worktree + session if missing
wtgo all                 # after a reboot: start every worktree's session, then the picker
wtgo feat/x --prompt brief.md   # brief that branch's agent, it starts on the brief in plan mode
make wt-open BRANCH=feat/x      # open the frontend of that branch
wtdone feat/x            # kill the session, remove the worktree, keep the branch
make wt-land BRANCH=feat/x      # from the main checkout: rebase, PR, squash-merge, clean up
```

## 2. The pieces

| Piece | Scope | Role |
| --- | --- | --- |
| [`wt`](https://github.com/timvw/wt) | machine | creates, lists and removes worktrees, runs the hooks |
| `~/.config/wt/config.toml` | machine | where worktrees go: `<repo>/.claude/worktrees/<branch>` |
| `.wt.toml` | repo | three hooks (post_create, post_checkout, pre_remove) pointing at the scripts |
| `scripts/wt-lib.sh` | repo | shared helpers and all the repo constants. The one file you must edit |
| `scripts/wt-setup.sh` | repo | everything a worktree needs to run, in one idempotent script |
| `scripts/tmux-dev.sh` | repo | the 4-pane session, also `make tmux-dev-all` in any checkout |
| `scripts/wt-teardown.sh` | repo | mirror of setup, run by `wt remove` |
| `scripts/wt-new.sh` | repo | `wtgo` / `make new`: branch + worktree + session + optional brief |
| `scripts/wt-done.sh` | repo | `wtdone`: kill the session, remove the worktree, keep the branch |
| `scripts/wt-land.sh` | repo | rebase, PR, squash-merge into the base branch, clean up |
| `scripts/wt-open.sh` | repo | print and open a branch's frontend or backend URL |
| `scripts/wt-db.sh` | repo | per-branch Postgres databases cloned from a template |
| `scripts/git-push-guard.sh` | repo | a worktree may push only its own branch, never the protected ones |
| `scripts/claude-worktree-settings.json` | repo | template for each worktree's `.claude/settings.local.json` |
| `scripts/wt-go.bash` | machine | `wtgo` / `wtdone` shell functions and tab completion |
| `scripts/claude-notify*.sh` | machine | desktop notification when an agent needs you, click opens the session |

Three ideas hold it together.

**One file per worktree.** `.env.worktree` at the checkout root holds
`WT_BRANCH`, `WT_SLUG`, `BACKEND_PORT`, `FRONTEND_PORT` (resslab-hub adds
`DB_NAME` and `POSTGRES_TEST_DB`). Ports come from `cksum` of `<repo>/<branch>`
(`18000 + h % 500` and `19000 + h % 500`, same remainder so the two ports read
as one pair), stepping forward past a pair another worktree holds or something
is listening on. Nothing reads the file directly. `tmux-dev.sh` exports it into
every pane, and each tool reads plain env vars from there. A real one:

```
WT_BRANCH=feat/x
WT_SLUG=feat_x
BACKEND_PORT=18042
FRONTEND_PORT=19042
```

**The agent is fenced in by three layers.** The generated
`.claude/settings.local.json` denies pushes to protected branches and denies
force-push. `git-push-guard.sh` refuses the same thing inside git, where the
agent cannot argue with it. And CLAUDE.md explains the rules in prose, which the
permission classifier reads too.

**The agent can see its own servers.** The backend and frontend panes mirror
their output to `.wt-logs/*.log` with `tmux pipe-pane`, because the sandboxed
agent cannot reach the tmux socket. Read-only `curl` to localhost is pre-allowed
so "did my change work" costs nothing.

## 3. Machine setup

All of this is already done on Pierre's machine. Verify, do not redo.

```bash
wt --version                            # go install github.com/timvw/wt@latest
cat ~/.config/wt/config.toml            # strategy = "custom"
                                        # pattern  = "{.repo.Main}/.claude/worktrees/{.branch}"
                                        # separator = "-"
grep worktrees ~/.config/git/ignore     # **/.claude/worktrees/
grep wt-go ~/.bashrc                    # source .../scripts/wt-go.bash
grep choose-tree ~/.tmux.conf           # bind s choose-tree -wZ -O name
git config --global push.default        # current
which claude-notify                     # ~/.local/bin/claude-notify
```

Two things to change per repo:

- **`wtgo` is pinned to one repo, and this needs fixing.** `wt-go.bash` sets
  `_WTGO_ROOT` from its own path at source time (line 13), and every function
  and completion uses it. So `wtgo feat/x` typed inside bluecity-viz would
  create a worktree in **resslab-hub**, and tab completion would offer
  resslab-hub branches. Sourcing a second copy just overwrites the functions,
  whichever line comes last in `~/.bashrc` wins. See section 4.6 for the fix.
- `~/.claude/settings.json` has `autoMode.environment` entries per repo
  (trusted repo and remote, protected branches, sensitive paths). Add entries
  for the new repo. **You cannot edit this file yourself**, the classifier
  blocks an agent changing its own permissions. Write the entries out and ask
  Pierre to paste them, or point him at `/auto-mode-setup`.

## 4. Porting to a new repo

Work in this order. Copy from a checkout of resslab-hub (or from this repo's
`scripts/`, which is the same tooling without the database half), not from a
memory of what the scripts do.

### 4.1 Copy the files

```bash
src=~/code/resslab-hub
cp -r $src/scripts/*.sh $src/scripts/wt-go.bash $src/scripts/claude-worktree-settings.json scripts/
cp $src/.wt.toml .wt.toml
chmod +x scripts/*.sh
```

Skip `claude-notify.sh` and `claude-notify-install.sh` if the install already
exists in `~/.local/bin`. It is machine-wide and derives the session name from
any repo's origin and branch, so it needs no copy.

Skip `wt-db.sh` entirely if the project has no PostgreSQL dev database.

### 4.2 Edit the constants

`scripts/wt-lib.sh`, lines 7 to 14. This is the only file where names live:

```bash
BASE_BRANCH="${WT_BASE_BRANCH:-dev}"   # what wt-land.sh merges into
PROTECTED_BRANCHES="dev stage main"    # never pushed from a worktree
DB_CONTAINER="${DB_CONTAINER:-resslab-hub-database-1}"
SHARED_DB="postgres"
TEMPLATE_DB="resslab_hub_template"
LIGHT_TEMPLATE_DB="resslab_hub_light"
MAIN_BACKEND_PORT=8000
MAIN_FRONTEND_PORT=5173
```

The container name is the compose project (the main checkout directory name)
plus the service name plus `-1`. Check with `docker ps`.

The base and protected branches are unfortunately repeated in a few more places,
see wart 2 in section 6.

### 4.3 Files that need real adaptation

| File | What to change |
| --- | --- |
| `wt-setup.sh` | Step 1: the list of gitignored files to seed from the main checkout (resslab has `secrets/.env`, `docker-compose.override.yml`, `frontend/.env.development.local`). Step 1b: the sample-data block is resslab-only, delete it. Step 2: the extra env keys written into `.env.worktree`. Step 3: the `set_env_var` calls that wire frontend to backend and backend to its DB. Step 5: `make install` / `make hooks` if the target uses different commands. |
| `tmux-dev.sh` | Only the pane list and the commands they run (lines ~139 to 154), plus the `docker compose up -d database` line if there is no database. Everything else (session naming, `@wt_role`, the env-loading prefix, `pipe-pane`, `detach-on-destroy`, prefix+X, brief handling) is generic. |
| `claude-worktree-settings.json` | The `__RESSLAB_DATA_DIR__` placeholder and `additionalDirectories` (delete both if no sibling repo). The `allow` list: the project's own test and lint commands. The branch names in `deny`. `sandbox.network.allowedDomains` for the project's package registries. **Keep the `ask` list and the `curl *` exclusion as they are**, they were expensive to get right. |
| `wt-db.sh` | Postgres-specific throughout. The clone prefix, the `template-light` build commands (how this project loads dev data), the `status` filter. Drop the file if there is no database. |
| `wt-land.sh` | Generic, but assumes `gh` and `make lint && make test`. |
| `Makefile` | Add the targets from `snippets/Makefile-targets.mk`. |

### 4.4 Patch the app so ports are variables

This is the step people skip and then debug for an hour. See
`snippets/consumer-patches.md`. In short: the backend port, the vite port, the
vite proxy target or `VITE_*_URL`, CORS origins, OAuth redirects. Grep for the
port numbers and fix every hit:

```bash
grep -rn "8000\|5173" --exclude-dir=node_modules --exclude-dir=.git .
```

Miss one and two worktrees talk to each other's backend. It looks like an
application bug, not a setup bug.

### 4.5 Wire the guard and the ignores

- Add the pre-push job from `snippets/lefthook-push-guard.yml`, or install the
  plain git hook shown in the same file if the repo has no lefthook.
- Add the lines from `snippets/gitignore-lines.txt` to `.gitignore`.

### 4.6 Make `wtgo` repo-aware

Done since 2026-09-06 in both repos: `wt-go.bash` resolves the repo from the
directory you stand in. Kept for the record.

As shipped, `wt-go.bash` pins itself to the repo it was sourced from, so the
second repo to use this setup cannot get `wtgo` by sourcing its own copy. Patch
the copy that `~/.bashrc` sources (keep sourcing only one) so the functions
resolve the repo from the current directory and fall back to the sourced one:

```bash
_WTGO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The repo you are standing in, if it has the worktree tooling; else the repo
# this file was sourced from. Lets one source line serve every ported repo.
_wt_root() {
  local common root
  common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || {
    printf '%s' "$_WTGO_ROOT"; return; }
  root=$(dirname "$common")
  if [ -x "$root/scripts/wt-new.sh" ]; then printf '%s' "$root"
  else printf '%s' "$_WTGO_ROOT"; fi
}

wtgo() { "$(_wt_root)/scripts/wt-new.sh" "$@"; }
wtdone() { "$(_wt_root)/scripts/wt-done.sh" "$@"; }
```

Then replace `$_WTGO_ROOT` with `$(_wt_root)` in `_wt_worktrees` and `_wtgo` so
completion follows the same rule. Also widen the two hardcoded
`grep -Ev '^(dev|stage|main)$'` filters if the new repo has different protected
branches (see wart 2).

Test it: `cd` into each repo and check `wtgo <TAB>` offers that repo's branches.

If you would rather not touch the shared file, the cheap alternative is a second
pair of functions with a different name in `~/.bashrc`. It works, but you then
have two names to remember.

### 4.7 Write the CLAUDE.md section

Use `snippets/CLAUDE-md-worktree-section.md`. Not optional. The permission
classifier reads CLAUDE.md, so these sentences steer the agent and its reviewer.
An agent that has read them stops trying things the scripts would refuse.

## 5. Traps already paid for

Each of these cost a debugging session. Do not rediscover them.

- **`$WT_MAIN` lies.** wt exports it to hooks, but it points at whichever
  worktree has the *default branch* checked out (`cmd/repo.go`
  `getMainWorktreePath`). So `.wt.toml` and the scripts resolve the main
  checkout through `git rev-parse --path-format=absolute --git-common-dir`
  instead. Matching rule: **never check out the default branch in a worktree.**
- **Some wt builds run `post_checkout` on create too.** `wt-setup.sh` must stay
  idempotent. Both hooks point at it on purpose, so `wt co` and `wt pr` also set
  a worktree up.
- **The Claude sandbox cannot reach loopback.** A sandboxed
  `curl http://localhost:19234/` returns `000` even with `localhost` in
  `allowedDomains`, the proxy refuses loopback. That is why `curl *` is in
  `sandbox.excludedCommands`: it runs outside the sandbox and is governed by the
  classifier plus the allow/ask rules instead. Verified both ways.
- **A local ref makes a stale base.** `wt create x somebranch` resolves your
  *local* `somebranch` at whatever commit you last saw. `wt-new.sh` defaults to
  `origin/dev` and fetches first. Pass bases in the `origin/` form.
- **git omits non-fast-forward refs from pre-push stdin.** When testing the
  guard, use a ref git would actually push, or you test nothing.
- **Start the database from the main checkout.** Compose names its project after
  the directory, so `docker compose up` in a worktree creates a second project
  fighting for the same host port. `tmux-dev.sh` already does the right thing.
- **`ROOT` leaks into the tmux server.** If the run that starts the tmux server
  has `ROOT` exported, every pane of every future session inherits it and the
  scripts target the wrong checkout. `tmux-dev.sh` scrubs it (lines 19 to 20).
  Keep that.
- **lefthook refuses commits where it is not installed**
  (`assert_lefthook_installed`), which is why setup runs `make hooks`.
- **tmux session names** cannot contain `.` or `:`. `session_name()` maps them
  to `-`. `/` is fine.
- **`~/.claude/settings.json` cannot be edited by an agent.** Hand Pierre the
  text.
- **Disk.** Each worktree carries its own `node_modules` and `.venv`, about
  770 MB in resslab-hub. wt's `docs/examples.md` has shared-cache hooks if that
  hurts.

## 6. Known warts, fix them instead of copying them

Found while writing this handoff. All four are still in the source.

1. **`wt-db.sh` `restart_backend()` targets a window that no longer exists.** It
   sends keys to `"=$s:backend"`. In tmux that is a *window* named backend, and
   the layout has one window `dev` with *panes* named backend/frontend/shell
   (pane titles are not addressable as targets). So the call fails, and since
   `wt-db.sh` runs with `set -euo pipefail` and the call is not guarded, it
   aborts the script. `make db-branch` and `make db-branch-drop` should die at
   the very last step, after the database work is already done and committed to
   `.env.worktree`, so the state is fine but make reports an error and the
   backend is never restarted. Read from the source, not reproduced (tmux is not
   reachable from a sandboxed session). If you port `wt-db.sh`, look the pane up
   the way `tmux-dev.sh` does, by the `@wt_role` option, and guard the call with
   `|| true`.
2. **The branch names are hardcoded in four files**: `wt-lib.sh`
   (`BASE_BRANCH`, `PROTECTED_BRANCHES`), `wt-new.sh` line 39
   (`base="${base:-origin/dev}"`), `git-push-guard.sh` line 9
   (`PROTECTED="dev stage main"`), and `wt-go.bash` twice in its completion
   filters. The guard duplicates them on purpose, it must not depend on a
   sourced file that could be missing. The other two should read from
   `wt-lib.sh`. Change all four when you port, or you get a guard protecting
   branches that do not exist and completion hiding ones that do.
3. **Port space is 500 slots with no collision check.** Two branches whose
   `cksum % 500` collide fight for the same ports and nothing warns. Adding a
   "port already in `.env.worktree` of another worktree, bump by 1" loop in
   `branch_ports()` would fix it.
4. **`wt-setup.sh` dies if `$MAIN/secrets/.env` is missing.** That is the single
   hard prerequisite of the whole flow. In a repo with no such file, the seed
   step must change or setup never runs.

## 7. bluecity-viz checklist

Notes from looking at `~/code/bluecity-viz` on 2026-09-01. Confirm before
acting, the repo may have moved.

**What it looks like.** Root `Makefile` with `dev`, `dev-frontend`,
`dev-backend`. Backend is `uv run python -m uvicorn app.main:app --host 0.0.0.0
--port 8000 --reload`, run from `backend/`. Frontend is Vue + Vuetify + Vite in
`frontend/`, with a **hardcoded proxy** in `vite.config.ts`:
`target: 'http://127.0.0.1:8000/data'`. There is a `processing/` directory with
its own uv project. Branches are `dev` and `main`, `origin/HEAD` points at
`main`. No docker compose, **no PostgreSQL**, no lefthook (but
`commitlint.config.js` exists). `frontend/.env` is tracked and only holds
`VITE_PARAMETERS_URL` and `VITE_STYLE_URL`.

So the port is simpler than resslab-hub. Concretely:

- **Drop the whole database half.** No `wt-db.sh`, no `db-*` Makefile targets,
  no `docker-compose.override.yml`, no `DB_NAME` / `POSTGRES_TEST_DB` /
  `DATABASE_UPGRADE` in `.env.worktree`, no `docker compose up -d database` in
  `tmux-dev.sh`, and delete the database bullet from the CLAUDE.md section.
  `.env.worktree` shrinks to `WT_BRANCH`, `WT_SLUG`, `BACKEND_PORT`,
  `FRONTEND_PORT`.
- **Nothing to seed.** There is no `secrets/.env` and `frontend/.env` is
  tracked. So gut step 1 of `wt-setup.sh` (and remember wart 4: as copied, it
  dies without `secrets/.env`). If it turns out the backend needs a local env
  file or an API key file, seed that one instead.
- **Two ports to parameterize.** In the root `Makefile`, `--port 8000` becomes
  `--port $(BACKEND_PORT)` with `BACKEND_PORT ?= 8000` at the top. In
  `vite.config.ts`, add `port: Number(process.env.FRONTEND_PORT) || 5173` and
  make the proxy target
  `` `http://127.0.0.1:${process.env.BACKEND_PORT || 8000}/data` ``. The proxy
  is good news: `vite.config.ts` runs in Node and reads the exported
  `.env.worktree` directly, so `wt-setup.sh` has no env file to write at all.
  Grep for other hits of `8000` first, `frontend/src/services/*.ts` and
  `frontend/src/config/*.ts` mention `import.meta.env`, check what they read.
- **Constants**: `MAIN_BACKEND_PORT=8000`, `MAIN_FRONTEND_PORT=5173`,
  `DB_*` deleted. For `BASE_BRANCH` and `PROTECTED_BRANCHES`, `origin/HEAD` says
  `main` but a `dev` branch exists. **Ask Pierre which one branches are cut from
  and which ones must never be pushed** before setting them. A wrong guess here
  either blocks a normal push or lets an agent push `main`.
- **`wtgo` will point at the wrong repo.** bluecity-viz is the second repo to
  use this, so it is the one that hits the pinned `_WTGO_ROOT` problem. Do
  section 4.6, and test with `cd ~/code/bluecity-viz && wtgo <TAB>`: it must
  offer bluecity branches, not resslab-hub ones.
- **The push guard needs a home.** No lefthook. Either add lefthook (commitlint
  is already configured, so it would tidy that up too) or install the plain
  `pre-push` hook from `snippets/lefthook-push-guard.yml`.
- **tmux panes**: `claude`, `backend` (`make dev-backend`), `frontend`
  (`make dev-frontend`), `shell`. Note the backend binds `--host 0.0.0.0`, which
  is fine but means the port is exposed on the LAN, one more reason not to let
  two worktrees share it.
- **`processing/`** is a third uv project, and bluecity's `make install` already
  syncs it along with backend and frontend. So worktrees get it for free, but
  each worktree then carries three dependency trees. Watch the disk, and if
  `processing/` is not needed for normal branch work, consider a lighter install
  command in `wt-setup.sh`.

## 8. Smoke test

Do this before saying it works. It is the same test the original was verified
with.

```bash
wt create test/smoke origin/<base>     # hooks run: setup, then a detached session
tmux ls                                # "<repo>/test/smoke" exists
cd <worktree path> && cat .env.worktree
curl -sI http://localhost:$FRONTEND_PORT/    # 200
curl -sI http://127.0.0.1:$BACKEND_PORT/docs # 200 (or whatever the backend serves at /)
```

Then, from inside the worktree's claude pane:

```bash
git commit --allow-empty -m "test: smoke" && git push    # must work
git push origin HEAD:<protected branch>                  # must be REFUSED by the guard
```

And clean up:

```bash
wt remove test/smoke        # teardown runs
tmux ls                     # session gone
lsof -i :$BACKEND_PORT      # nothing left
```

If the guard does not refuse, stop and fix it before using the setup for real
work. It is the one piece protecting the shared branches from an agent.
