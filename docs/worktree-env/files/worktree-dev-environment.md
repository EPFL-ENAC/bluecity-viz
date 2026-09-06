# Parallel worktrees: one branch, one Claude, its own servers

How this repo runs several branches at once — each in its own git worktree, its
own tmux session, with its own Claude Code session and its own backend +
frontend dev servers — and how to replicate the setup in another repository.

```
wt create feat/123-thing origin/dev
  └─ .wt.toml → scripts/wt-setup.sh                (idempotent)
       ├─ seeds secrets/.env, docker-compose.override.yml, frontend/.env.development.local,
       │        sample-data/ batch folders (fieldGroups.spec.ts and the contribution flow need them)
       ├─ hashes the branch name → .env.worktree  (BACKEND_PORT 18xxx, FRONTEND_PORT 19xxx, DB, test DB, data dir)
       ├─ points this frontend at this backend, this backend at the right DB with migrations OFF
       ├─ writes .claude/settings.local.json     (sandbox + ask/deny rules for the Claude session)
       ├─ make install && make hooks
       └─ scripts/tmux-dev.sh --no-attach          → tmux session "resslab-hub/feat/123-thing"
                                                      one window: claude (left half) | backend / frontend / shell (right)
wt remove feat/123-thing
  └─ .wt.toml → scripts/wt-teardown.sh   (kills the session, frees the ports, drops a branch DB)
```

Nothing is shared between worktrees except the git object store and the one
Postgres container — and inside it each worktree gets its own throwaway ~20 MB
clone of the light template, falling back to the shared full dataset only when
no template exists yet ([Database](#database)).

## Moving parts

| Piece                                   | Lives at                                          | Scope   | Role                                                                    |
| --------------------------------------- | ------------------------------------------------- | ------- | ----------------------------------------------------------------------- |
| [`wt`](https://github.com/timvw/wt)     | `$PATH` (`go install github.com/timvw/wt@latest`) | machine | creates/lists/removes worktrees, runs the hooks                         |
| `wt init` shell integration             | `~/.bashrc`                                       | machine | `wt create` leaves you _inside_ the new worktree                        |
| `~/.config/wt/config.toml`              |                                                   | machine | where worktrees go: `<repo>/.claude/worktrees/<branch>`, `/`→`-`        |
| `~/.config/git/ignore`                  |                                                   | machine | `**/.claude/worktrees/` so nested worktrees never show as untracked     |
| `.wt.toml`                              | repo root, committed                              | repo    | three hooks → the two scripts below                                     |
| `scripts/wt-setup.sh`                   | committed                                         | repo    | everything a worktree needs to run, in one idempotent script            |
| `scripts/tmux-dev.sh`                   | committed                                         | repo    | the 4-pane session; also `make dev-all` in the main checkout          |
| `scripts/wt-teardown.sh`                | committed                                         | repo    | mirror of setup, run by `wt remove`                                     |
| `scripts/wt-db.sh`                      | committed                                         | repo    | `make db-template-light` / `db-template` / `db-branch[-full]` / `db-branch-drop` / `db-status` |
| `scripts/wt-open.sh`                    | committed                                         | repo    | `make wt-open [TARGET=backend] [BRANCH=…]` — prints and opens the URL   |
| `scripts/wt-land.sh`                    | committed                                         | repo    | `make wt-land BRANCH=…` — rebase, PR, squash-merge into `dev`, clean up |
| `scripts/git-push-guard.sh`             | committed, wired in `lefthook.yml`                | repo    | a worktree may push only its own branch, never `dev`/`stage`/`main`     |
| `scripts/claude-worktree-settings.json` | committed                                         | repo    | template for each worktree's `.claude/settings.local.json`              |
| `scripts/wt-lib.sh`                     | committed                                         | repo    | the shared helpers (ports, names, env file, psql)                       |
| `scripts/claude-notify.sh`              | committed → `~/.local/bin/claude-notify`          | machine | Claude Code hook → desktop notification, click opens the session        |
| `scripts/claude-notify-install.sh`      | committed, run by hand                            | machine | installs the above: `~/.local/bin` copy + `~/.claude/settings.json` hooks |
| `~/.claude/settings.json`               |                                                   | machine | auto mode default, sandbox on, `autoMode.environment` for this repo     |

`wt`'s own docs are the reference for anything about it: `docs/configuration.md`
(strategies, hook variables) and `docs/examples.md` (Claude Code + tmux,
per-worktree ports, shared build caches). Both are in the plugin checkout at
`~/.claude/plugins/marketplaces/wt/`.

## Machine setup (once)

```bash
go install github.com/timvw/wt@latest        # or brew install timvw/tap/wt
wt init                                       # shell function so `wt create` cd's for you
claude plugin marketplace add timvw/wt && claude plugin install wt@wt   # optional: /wt skill

git config --global push.default current      # a bare `git push` can only target the branch's own name
git config --global push.autoSetupRemote true

printf '**/.claude/worktrees/\n' >> ~/.config/git/ignore
echo 'source ~/code/resslab-hub/scripts/wt-go.bash' >> ~/.bashrc   # wtgo <branch> + tab completion
printf 'bind s choose-tree -wZ -O name\n' >> ~/.tmux.conf   # prefix+s: sessions sorted "<repo>/<branch>"; -w keeps each
                                                            # session's single dev window visible (-s would hide the four
                                                            # panes behind a second expand)
scripts/claude-notify-install.sh              # desktop notifications when an agent needs you (see below)
ln -s /mnt/data/Documents/Code/resslab-hub-data ~/code/resslab-hub-data   # the data repo, as the Makefile expects it
```

`~/.config/wt/config.toml`:

```toml
strategy = "custom"
pattern  = "{.repo.Main}/.claude/worktrees/{.branch}"   # same place Claude Code puts its own worktrees
separator = "-"                                         # feat/foo → feat-foo, no nested dirs
```

`~/.claude/settings.json` — the parts that matter (the classifier reads
`autoMode` from this file only, never from a repo):

- `"permissions": {"defaultMode": "auto"}` and `"sandbox": {"enabled": true, "autoAllowBashIfSandboxed": true}`.
- `permissions.ask` kept short — `rm`, `git reset`, `git clean`, force-push. An
  `ask` rule here prompts in _every_ session and no project-level `allow` can
  override it (deny → ask → allow, across all scopes), so a user-level
  `Bash(git commit:*)` ask is exactly what stops a worktree session from working
  on its own.
- `autoMode.environment` entries describing this repo: trusted repo + remote,
  protected branches, `secrets/` as sensitive, the shared Postgres, the data
  repo. `/auto-mode-setup` drafts them; `claude auto-mode config` shows the result.
- one `autoMode.soft_deny`: never migrate or `upload-data` the shared dev DB
  from a worktree unless the user named it.

## Daily workflow

```bash
wtgo all                             # after a reboot: every set-up worktree's session, detached, then the picker
wtgo feat/<TAB>                      # go to a branch's session: tab-completes worktrees and branches; creates
                                     # branch (from fetched origin/dev), worktree (~3 min first time) and session
                                     # only when missing. `make go BRANCH=…` / `make new BRANCH=…` do the same
                                     # without completion; prefix+d detaches, prefix+s switches
wtgo feat/x --no-attach              # spin the session up without entering it (chain several in one shell)
wtgo feat/x --prompt brief.md        # brief the branch's agent: brief.md (or literal text) becomes PROMPT.md and
                                     # the claude pane starts on it, on fable in plan mode, so you get a plan to
                                     # review. Works on a session that is already up (the pane restarts)
make wt-open BRANCH=feat/123-thing   # frontend in the browser; TARGET=backend for /docs
make db-status                       # which DB this worktree uses
make db-branch                       # re-clone the (light) template if setup couldn't; `db-branch-full` for the 3.4 GB copy
make wt-land BRANCH=feat/123-thing   # from the main checkout: rebase → PR → squash-merge → cleanup
wtdone feat/x                        # done with the branch (PR up, work merged, ...): kill the session and
                                     # remove the worktree + its database, keep the branch. --force when dirty.
                                     # Fine from inside the session itself; `make wt-done BRANCH=…` and the
                                     # prefix+X menu (below) do the same
```

Inside the session: the `backend` and `frontend` panes run `make dev` with the
worktree's ports; `claude` starts with the `PROMPT.md` brief when one is at the
checkout root (see below), otherwise resumes the checkout's last agent
conversation (`claude --continue`, falling back to a fresh one on a new
worktree); `shell` has `.env.worktree` exported.
Both URLs are printed when the session starts and by `wt-open`. The `backend`
and `frontend` panes also mirror their output to `.wt-logs/*.log` in the
checkout (`tmux pipe-pane`), so the sandboxed agent in the `claude` pane,
which cannot reach the tmux socket, can still read the server logs.

### Briefing the agent (`--prompt`)

A `PROMPT.md` at the checkout root is a one-shot brief for that worktree's
agent. `wtgo <branch> --prompt <file-or-text>` writes it, then the `claude` pane
runs `claude --model fable --permission-mode plan "$(cat PROMPT.sent.md)"`: the
agent reads the brief, looks around and comes back with a plan you approve or
send back, instead of editing straight away. Override the two flags with
`WT_BRIEF_MODEL` / `WT_BRIEF_PERMISSION_MODE` (empty keeps claude's own
defaults).

The file is renamed to `PROMPT.sent.md` before the run, so a session recreated
later (`wtgo all` after a reboot) resumes that conversation instead of firing
the brief a second time. Both names are gitignored, as is `.wt-prompts/` for
brief drafts.

`wtgo` writes the brief after `wt create`, which means the session is often
already up (the `post_create` hook starts it): the `claude` pane is then
restarted on the brief. Whatever ran there before stays resumable with `claude
--continue`, but do not brief a worktree whose agent is mid-task. Chain several
briefs from one shell with `--no-attach`, one per line and not with `&`
(`git worktree add` races on its locks):

```bash
wtgo feat/a --no-attach --prompt .wt-prompts/a.md
wtgo feat/b --no-attach --prompt .wt-prompts/b.md
wtgo all                             # then pick a session to look at
```

Layout: `claude` fills the left half and has focus on attach; `backend`,
`frontend` and `shell` stack in the right half. `prefix+arrows` move between
panes, `prefix+z` zooms the focused pane to full screen and back, and the
`prefix+s` / `prefix+w` pickers preview the whole layout per session.

Killing a session (`x` in the `prefix+s` picker, `wtdone`, the teardown hook)
no longer throws you out of tmux: `tmux-dev.sh` sets `detach-on-destroy off` on
the server, so the client hops to the most recently used remaining session, and
tmux only exits when none is left.

`wtdone <branch>` is the counterpart of `wtgo`: session killed, worktree
removed (`wt remove`, which fires the teardown hook: ports freed, branch
database dropped), branch kept, local and remote. Use it once the PR is up and
the checkout has no other value; `wtgo <branch>` rebuilds the whole thing from
the branch later. It refuses a dirty worktree unless `--force` (those changes
are lost); unpushed commits are safe either way, they stay on the local branch.
Run from inside the very session being closed, it hands the job to the tmux
server first, so the removal survives the kill and you land in another session.

`prefix+X` (bound by `tmux-dev.sh`, so any `wtgo` refreshes it) opens the same
thing as a menu on the current session: plain kill, "done" (wt-done.sh on the
pane's checkout), or a confirmed force variant that discards uncommitted
changes when the worktree is dirty. The result of the removal pops up in a
tmux view when it finishes; `q` closes it.

`wt list` / `wt status` show every worktree; `wt cleanup` removes those whose
branch is merged.

### Desktop notifications

With `scripts/claude-notify-install.sh` run once, every Claude Code session on
the machine — whatever repo it is in — raises a desktop notification titled
with its tmux session name (`resslab-hub/<branch>`) when it needs a permission,
has been waiting on input for a minute, or finishes a task. Clicking the
notification jumps to that session, claude pane selected: a terminal that
already has a tmux client attached is flipped to the session (GNOME Wayland
cannot raise a window from a script, but changing what your open terminal
shows needs no window management); a new attached terminal opens only when no
client exists. The session is re-resolved at click time, so a notification
survives a tmux restart. A newer notification for the same session replaces
the older one instead of stacking.

The installer copies `scripts/claude-notify.sh` to `~/.local/bin/claude-notify`
and registers it in `~/.claude/settings.json` under the `Notification`
(`permission_prompt`, `idle_prompt`) and `Stop` hooks — user-level because
Claude can't edit that file itself (see Gotchas). Re-run it after changing the
script.

## Ports

`scripts/wt-lib.sh` hashes the branch name (`cksum`) into `BACKEND_PORT = 18000 + h % 500`
and `FRONTEND_PORT = 19000 + h % 500` — same suffix on both, so `18042 ↔ 19042`
read as one worktree, and the same branch always gets the same pair. The main
checkout keeps 8000/5173 through the Makefile / vite defaults.

`.env.worktree` is the single source: `backend/Makefile` reads `BACKEND_PORT`
and `RESSLAB_DATA_DIR`, `vite.config.ts` reads `FRONTEND_PORT`,
`frontend/.env.development.local` carries `VITE_APP_BACKEND_URL` for the
matching backend, and `tmux-dev.sh` exports the file in every pane. CORS is
`*` in dev, so no other cross-service URL needs to move.

## Database

One container (`resslab-hub-database-1`, host port 5433) holds the 3.4 GB dev
dataset in database `postgres` plus two idle templates that branch clones are
made from. Every new worktree gets its own throwaway clone of the **light**
template (`wt-setup.sh` runs `wt-db.sh create`), so a branch can migrate,
upload, or corrupt its database without touching anything shared — and since
the clone is ~20 MB, it costs under a second:

|                    | light branch DB (default)                                                                        | full branch DB (`make db-branch-full`)                | shared (`wt-db.sh drop`)              |
| ------------------ | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------- | ------------------------------------- |
| `POSTGRES_DB`      | `resslab_hub_<slug>` from `resslab_hub_light`                                                    | `resslab_hub_<slug>` from `resslab_hub_template`      | `postgres`                            |
| contents           | every main table, dictionary and README; one measurement file per series type                    | everything                                            | everything                            |
| `DATABASE_UPGRADE` | `true`                                                                                           | `true`                                                | `false`                               |
| cost               | < 1 s, ~20 MB, dropped by `wt remove`                                                            | ~1 min, 3.4 GB on disk, dropped by `wt remove`        | none                                  |
| use when           | almost everything: UI work, API and schema changes, migrations, uploader changes, anything that writes | real data volumes, browsing curves across many specimens | read-only look at the full dataset |

`make db-template-light` (once, re-run when the data repo changes) builds
`resslab_hub_light` from the data repo: `alembic upgrade head` for the schema,
then the uploader with `--series-limit 1`, which keeps every main CSV,
dictionary and README but only the alphabetically-first measurement file per
series type (~30 s total). The `*_count` flags are recomputed from what was
actually uploaded, so specimens without curves correctly show "no test data".
If the light template doesn't exist yet, `wt-setup.sh` says so and leaves the
worktree on the shared DB with migrations off; build it and run `make db-branch`.

`make db-template` (from the main checkout; re-run after a big data upload)
copies the shared DB into `resslab_hub_template` with `pg_dump | psql`. Both
have to be idle copies: Postgres refuses `CREATE DATABASE … TEMPLATE x` while
anything is connected to `x`, and the shared DB always has connections from
other worktrees' backends. The templates are never connected to, so clones are
instant.

`pytest` creates and drops a throwaway `POSTGRES_TEST_DB`; `wt-setup.sh` makes it
`resslab_hub_test_<slug>` per worktree so two test runs can't drop each other's
database. It is read from the process environment before dotenv loads, which
is why the tmux panes export `.env.worktree` rather than rely on `secrets/.env`.

## What Claude may do in a worktree

The session runs in **auto mode** — a classifier reviews every action that
isn't a read or an edit inside the worktree — with the OS sandbox on. Three
layers sit on top, all in `scripts/claude-worktree-settings.json`, which
`wt-setup.sh` copies to the worktree's gitignored `.claude/settings.local.json`:

| Layer                                                   | Behaviour                                                                                                                                                                                                                                                                                                                             | Covers                                                 |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| classifier defaults                                     | allows read-only HTTP, dependency installs from lockfiles, pushes to the repo; blocks `curl \| bash`, exfiltrating sensitive data, force push, `git reset --hard`, merging unapproved PRs, repointing API URLs, `--insecure`, nested `--dangerously-skip-permissions`                                                                 | everything not matched by a rule                       |
| `permissions.ask` — _always prompts, even in auto mode_ | `curl`/`wget`/`http`/`gh api` write forms (`-X`, `-d`, `-F`, `-T`, `--json`, `--post-*`), `gh pr create/merge/review`, `gh release`, `gh repo`; running downloaded code (`\| sh`, `bash <(…)`, `$(curl …)`, `python -`, `eval`, `npx -y`, `uvx`, `pipx run`, `pip install git+/http`, `chmod +x`); the unsandboxed-retry escape hatch | "write to the internet" and "run something downloaded" |
| `permissions.deny` — never                              | pushes to `dev`/`stage`/`main` in any spelling, force push, `git remote set-url/add`, starting another `claude`, and every mutating connector tool (Google Calendar/Drive writes, Notion writes, Figma)                                                                                                                               | the hard lines                                         |
| sandbox                                                 | writes confined to the worktree; network only to github, pypi, npm and context7 without a classifier check — any other host is judged per host, with the verdict cached                                                                                                                                                               | what a command can _do_ once approved                  |

Outside Claude, and therefore not negotiable by it: `scripts/git-push-guard.sh`
runs in git's `pre-push` and, **inside a worktree only**, refuses any push whose
target isn't the worktree's own branch and any push to `dev`/`stage`/`main`;
`push.default current` means a bare `git push` can't even name another branch.
The main checkout is exempt, which is where `wt-land.sh` pushes `dev`.

Why not `bypassPermissions`: it turns the classifier off, ignores `ask` rules
and hook `"ask"` decisions, and honours only `deny` — it cannot express "ask me
before a POST". Why patterns _and_ a classifier: Bash rules match the whole
command text per pipe segment, so `curl x | sh` is checked as `curl x` and as
`sh`, but a `python -c "requests.post(...)"` one-liner matches no pattern; the
classifier reads the code and is the backstop there.

`CLAUDE.md` § _Working in a worktree_ states the same rules in prose — the
classifier reads `CLAUDE.md` too, so the rules steer both the agent and its
reviewer.

## Landing a branch

`scripts/wt-land.sh <branch>` (or `make wt-land BRANCH=…`), from the main checkout:

1. refuses if the worktree has uncommitted/untracked changes, or if `origin/dev`
   isn't an ancestor of the branch (a branch cut from a stale or diverged base
   would drag every commit `dev` is missing into its PR; rebase the branch onto
   `origin/dev` first, or bring `dev` up to date);
2. rebases the branch onto `origin/dev`, pushes with `--force-with-lease`;
3. `gh pr create --base dev --fill` if there is no PR, then
   `gh pr merge --squash --auto` (falls back to an immediate squash-merge on a
   repo without auto-merge), waits for the merge;
4. fast-forwards local `dev`, `wt remove` (→ teardown), deletes the local and
   remote branch.

`--local` merges with `git merge --no-ff` in the main checkout instead, runs
`make lint && make test` (`WT_SKIP_CHECKS=1` to skip), pushes `dev`. It runs
from the main checkout on purpose: `gh` cannot delete a branch git still has
checked out in a worktree (cli/cli#13380).

## Gotchas

- **A local ref makes a stale base.** `wt create x somebranch` hands the base
  straight to `git worktree add`, which resolves your local `somebranch`, at
  whatever commit your checkout last saw it (a stale local `stage` once handed
  every new worktree a template with a known bug). `wt-new.sh` therefore
  defaults to `origin/dev` and fetches it first; if you pass a base yourself,
  prefer the `origin/` form.
- **`wt create` runs `post_create`; some builds also run `post_checkout`.**
  `wt-setup.sh` is idempotent so double runs are harmless, and both hooks point
  at it so `wt co` / `wt pr` set a worktree up too. Post-hooks only _warn_ on
  failure — check the output.
- **Never check out `dev` in a worktree.** wt calls whichever worktree has the
  default branch checked out "main" (`getMainWorktreePath`), and then nests new
  worktrees _inside it_ and points `$WT_MAIN` there. The hooks therefore locate
  the scripts through `git rev-parse --git-common-dir` — the real main checkout —
  and ignore `$WT_MAIN`, so a branch that predates the scripts still gets set
  up; keep the main checkout on a branch that has them.
- **Start the database from the main checkout.** Compose names its project
  after the directory; `docker compose up` in a worktree would create a second
  project fighting for port 5433. `tmux-dev.sh` does the right thing.
- **The shared DB must never be migrated from a worktree.** A worktree normally
  never touches it — setup clones the light template and turns migrations on
  for the clone only. When no template exists yet the worktree falls back to
  the shared DB with `DATABASE_UPGRADE` forced off; `make api` already sets it.
- **`lefthook` refuses commits from a checkout where it isn't installed**
  (`assert_lefthook_installed`); `wt-setup.sh` runs `make hooks`.
- **The sandbox cannot reach `localhost`.** Verified: a sandboxed
  `curl http://localhost:19234/` returns `000` even with `localhost` and
  `127.0.0.1` in `allowedDomains` — the proxy refuses loopback. So `curl *` is
  in `sandbox.excludedCommands`: it runs outside the sandbox, which means
  every `curl` goes through the classifier (read-only GETs are allowed by
  default) and the ask rules (write forms prompt). Verified both ways: with
  the exclusion, `curl` to the worktree's own frontend and backend returns
  200 from inside a Claude session. The common read-only forms against
  `http://localhost:...` / `http://127.0.0.1:...` (bare, `-s`, `-sS`, `-fsS`,
  `-i`, `-I`) are also in `permissions.allow`, so the agent's usual "did my
  change work" checks skip the classifier entirely; ask rules still win for
  write forms, so a localhost POST prompts like any other.
- **Disk.** Each worktree carries its own `node_modules` + `.venv` (~770 MB).
  `wt`'s `docs/examples.md` has shared-cache hooks if that hurts. A branch DB is
  another 3.4 GB — keep one alive at a time.
- **tmux session names** can't contain `.` or `:`; `session_name()` maps them
  to `-`. `/` is fine.
- **`~/.claude/settings.json` can't be edited by Claude** — the classifier
  blocks an agent changing its own permissions. Edit it yourself.

## Replicating in another repository

1. Machine setup above, once.
2. Copy `.wt.toml` and `scripts/wt-lib.sh`, `wt-setup.sh`, `wt-teardown.sh`,
   `tmux-dev.sh`, `git-push-guard.sh`, `claude-worktree-settings.json`
   (`wt-db.sh`, `wt-open.sh`, `wt-land.sh` if the shape fits).
   `claude-notify.sh` needs no copying — the `~/.local/bin` install is
   machine-wide and derives the session name from any repo's origin + branch.
3. In `wt-lib.sh`: the DB container/name/template, `BASE_BRANCH`,
   `PROTECTED_BRANCHES`, the main checkout's ports. In `wt-setup.sh`: the list
   of gitignored files to seed and the env keys to rewrite. In `tmux-dev.sh`:
   the pane list.
4. Make every hardcoded port a variable with the old value as default —
   including the ones services use to find each other (proxy targets,
   `VITE_*_URL`, CORS origins, OAuth redirect URIs). Miss one and worktrees
   cross-talk in ways that look like application bugs.
5. Wire `git-push-guard.sh` into the pre-push hook; add `.env.worktree` to
   `.gitignore`; add the repo to `autoMode.environment`; write the _Working in
   a worktree_ section of `CLAUDE.md`.
6. Smoke test: `wt create test/smoke`, check both servers on the printed URLs,
   commit and push from the `claude` pane, try `git push origin HEAD:dev`
   (must be refused), `wt remove test/smoke`, confirm `tmux ls` is clean.
