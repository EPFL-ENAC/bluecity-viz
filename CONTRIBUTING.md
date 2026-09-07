# Contributing to BlueCity Viz

Thanks for taking the time to contribute.

BlueCity Viz has three parts: a Vue 3 frontend (`frontend/`), a FastAPI
backend (`backend/`), and Python processing tools (`processing/`). See
[CLAUDE.md](CLAUDE.md) for the architecture and [README.md](README.md) for a
quick start.

## Setup

You need Node 24 (see `frontend/.nvmrc`), pnpm, Python 3.12 with
[uv](https://docs.astral.sh/uv/), and GNU Make.

```bash
make install   # frontend pnpm install + backend/processing uv sync
make dev       # backend on :8000 and frontend on :5173
```

`processing/` is only needed for data conversion work.

## Branches and pull requests

- Branch from `dev` and open the pull request against `dev`. `main` holds the
  releases, do not open a PR against it.
- One topic per branch. Name it after the change: `feat/traffic-dock`,
  `fix/legend-scale`, `chore/frontend-tooling`.
- Link the issue in the PR body so both sides stay in sync.
- Add screenshots or a short GIF for any UI change.
- Do not commit `dist/`, `node_modules/`, or data files. Big binaries
  (`.graphml`, `.geojson`, `.pmtiles`, `.pdf`) go through git LFS, the rules
  are in `.gitattributes`.

## Commit messages

We follow [Conventional Commits](https://www.conventionalcommits.org/). The
commitlint job in CI checks every commit in the pull request, so a wrong
message fails the build.

```
<type>(<scope>): <short summary in lower case>
```

Types: `feat`, `fix`, `chore`, `build`, `ci`, `docs`, `refactor`, `perf`,
`test`, `revert`. Scope is optional, usually `frontend`, `backend` or
`processing`.

```
feat(frontend): add the betweenness delta scale
fix(backend): keep the graph lock during the CVRP copy
chore(frontend): delete dead files
```

Breaking changes get a `!` after the type (`feat(backend)!: ...`) and a
`BREAKING CHANGE:` line in the body. `release-please` reads these messages to
build the changelog, so the type decides the version bump.

## Checks

CI runs on every push and pull request to `dev` and `main`
(`.github/workflows/quality-check.yml`). Run the same commands before you
push.

Frontend, from `frontend/`:

```bash
pnpm run lint:check       # eslint, no auto-fix
pnpm run type-check       # vue-tsc on the app
pnpm run type-check:test  # vue-tsc on the tests
pnpm run test:unit        # vitest, runs once
pnpm run build-only       # vite build
```

`pnpm run lint` and `pnpm run format` write the fixes, use them while you
work. `pnpm run test:watch` keeps vitest open.

Backend, from `backend/`:

```bash
uv run ruff check --no-fix app
uv run ruff format --check app
uv run pytest
```

## Code style

Prettier and ESLint own the frontend formatting (no semicolons, single
quotes, 100 columns). Ruff owns the backend (100 columns, double quotes).
`.editorconfig` matches both. Set up the editor plugins so you get the
feedback while typing instead of in CI.

New UI goes through the Workbench design system: build from
`frontend/src/components/ui/` and the `--bc-*` tokens in
`assets/tokens.css`, not from raw Vuetify components. The details are in
CLAUDE.md.

## Working on several branches at once

The repo has a git worktree setup: one checkout, one tmux session and one
pair of ports per branch. `make go BRANCH=feat/x` creates it and attaches.
The full guide is in [docs/worktree-env/](docs/worktree-env/).

## Reporting issues

Use the [issue templates](https://github.com/EPFL-ENAC/bluecity-viz/issues/new/choose).
For a bug, say what you did, what you expected and what happened, and add the
browser console output if it is a frontend problem.

## Code of conduct

By taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
