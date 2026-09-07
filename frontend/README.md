# BlueCity Viz frontend

Vue 3 single page app: MapLibre for the basemap, Deck.gl on top for the
analytics overlays, Pinia for the state, Vuetify for a few remaining widgets.

## Setup

Node 22 (see `.nvmrc`) and pnpm. From this directory:

```bash
pnpm install
pnpm run dev
```

The dev server listens on 5173, or on `FRONTEND_PORT` when it is set. It
proxies `/api` and `/data` to the backend on `BACKEND_PORT` (8000 by
default), so the app always calls the backend on a relative path, in dev and
in production alike. Git worktrees get their own pair of ports, see
[docs/worktree-env/](../docs/worktree-env/).

## Scripts

| Command | What it does |
|---|---|
| `pnpm run dev` | Dev server with hot reload |
| `pnpm run build` | Type check and build |
| `pnpm run build-only` | Build without the type check (what the image runs) |
| `pnpm run preview` | Serve the built `dist/` |
| `pnpm run type-check` | `vue-tsc` on the app |
| `pnpm run type-check:test` | `vue-tsc` on the tests |
| `pnpm run test:unit` | Vitest, runs once |
| `pnpm run test:watch` | Vitest in watch mode |
| `pnpm run lint` | ESLint with `--fix` |
| `pnpm run lint:check` | ESLint without `--fix` (what CI runs) |
| `pnpm run format` | Prettier on `src/` |

## Layout

```
src/
├── components/
│   ├── dock/        # TrafficDock, CvrpDock: one per analytics tool
│   ├── sidebar/     # investigation tree, datasets, layers, tools
│   ├── panels/      # VisualizationsPanel, the map stage
│   ├── dialogs/     # add source, share, delete
│   └── ui/          # BcIcon, BcRow, BcSeg, BcSlider, BcDialogCard
├── composables/     # map setup, events, Deck.gl layer building
├── stores/          # Pinia: trafficAnalysis, layers, theme, apiKey
├── services/        # HTTP clients for the backend
├── config/          # layer definitions per dataset (PMTiles on S3)
├── utils/           # basemap style, colours, helpers
└── assets/          # tokens.css and the Suisse Int'l fonts
```

One page: a 360px sidebar on the left, the map full-bleed, and a 340px dock
on the right when a tool is open. No app bar, no drawer.

## Design system

The UI follows the Workbench design (EPFL design system, Architecture
sub-brand): Suisse Int'l, 1px hairlines, square corners, no shadows, mono
micro-labels, Blue City blue `#0500E1` as the only accent, red kept for
delete.

`assets/tokens.css` holds the `--bc-*` tokens, the shared classes and the
dark block, applied through `data-theme="dark"` on `<html>`.
`plugins/vuetify.ts` re-themes the Vuetify components that are still in use.
Build new UI from `components/ui/`, not from raw `v-card` or `v-checkbox`.

## Build output

`vite build` splits the vendor code into `maplibre`, `deck`, `vuetify` and
`d3` chunks, and the home view is loaded on demand, so a change in app code
does not invalidate the cached libraries. Sourcemaps are emitted but not
referenced from the bundles (`sourcemap: 'hidden'`).

More on the architecture in [CLAUDE.md](../CLAUDE.md), contribution rules in
[CONTRIBUTING.md](../CONTRIBUTING.md).
