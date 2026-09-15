# Perf and organization briefs

One brief per Claude session, one session per worktree. `launch.sh` creates all six
worktrees from `origin/dev` and fires the brief in each `claude` pane.

## Before launching (do once, on the main checkout, on `dev`)

1. `origin/dev` is at `100b7c2` (Workbench redesign, PR #57) as of 2026-09-07; the briefs
   quote line numbers from that commit. `launch.sh` cuts every branch from `origin/dev`.
2. Backend formatting: run `cd backend && uv run ruff format app && uv run ruff check --fix app`
   and commit it as `chore(backend): ruff format` if it changes files. Two sessions add ruff to
   CI; if dev is not clean, both would reformat every file and conflict.
3. `git status` in the main checkout must be clean (a dirty `frontend/package-lock.json`
   blocks `wtx land`; `git checkout frontend/package-lock.json` drops the npm drift).

## Sessions

| # | Branch | Brief | Area |
|---|---|---|---|
| S1 | `perf/state-persistence` | `s1-state-persistence.md` | stores/layers, localStorage, investigations |
| S2 | `perf/deck-rendering` | `s2-deck-rendering.md` | deck.gl composables, traffic store, VisualizationsPanel, TrafficDock |
| S3 | `perf/maplibre-layers` | `s3-maplibre-layers.md` | MapLibreMap, useMapLogic, config/, LegendMap |
| S4 | `perf/backend-routing` | `s4-backend-routing.md` | routes.py, graph_service, routing, bpr, sampling |
| S5 | `chore/frontend-tooling` | `s5-frontend-tooling.md` | package.json, vite, tsconfig, CI, dead files, docs |
| S6 | `fix/backend-cvrp-quality` | `s6-backend-cvrp-quality.md` | cvrp_service, main.py, tests, backend Dockerfile |
| S7 | `feat/od-pairs-ui` | `s7-od-pairs-ui.md` | frontend half of the OD pair count: GET /baseline, trips control in the dock, persistence. After S1 to S6 landed |
| FINAL | `chore/tooling-upgrades` | `final-tooling-upgrades.md` | major version bumps, only after S1 to S6 landed |

File ownership is written in each brief. Shared files have one owner; the other sessions
keep the public names that owner depends on.

## Landing order (from the main checkout, `wtx land <branch>`)

1. S5 (mechanical: deps, tsconfig, CI, dead files). Everyone rebases across it early.
2. S6 (backend, owns `uv.lock` first, gives the pytest harness).
3. S4 (rebases on S6, re-runs `uv lock`, adds the graph lock around the CVRP copy).
4. S1 (smallest frontend diff, fixes the `restoreState` contract).
5. S2 (largest frontend diff, only one touching VisualizationsPanel).
6. S3 (config and MapLibre, no one waits on it).
7. S7, in a fresh worktree from the updated dev. Land it before starting FINAL: FINAL
   has a prettier 3 formatting commit that touches most files, and would conflict with
   anything still open.
8. FINAL, in a fresh worktree from dev with S7 in.

S1 to S6 landed on dev on 2026-09-07 with `wtx land <branch> --local`. Use
that mode: it merges with `--no-ff`, runs lint:check, type-check and ruff on the merged
tree, and does not rebase, so a branch that merged `origin/dev` lands as it is.

Tell each running session `git merge origin/dev` after every landing, so conflicts show up
while the context is fresh.

## Measured baseline (dev at 100b7c2, this machine)

| Path | Value |
|---|---|
| 60 pointermove events over the road layer | 1.7 s (28 ms each) |
| Store change with traffic tool open | 136 ms stringify + localStorage QuotaExceeded (2.7 MB) |
| Open traffic tool | 240 ms long task |
| POST /recalculate, 1 removed edge | 3.0 s wall, 1.7 s server, 2.9 MB |
| Same, congestion 3 iterations | 11 s server |
| PMTiles fetched at startup, 1 active dataset | 11 files |
| node_modules (npm, before pnpm) | 985 MB |
