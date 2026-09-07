You are in a git worktree (branch chore/frontend-tooling). Read CLAUDE.md first: ports are in
.env.worktree, never push dev or main. This session changes NO application logic and bumps
NO major version of TypeScript, Vite, Vitest, ESLint, Prettier, MapLibre or Pinia (a later
session does that after the other branches land). Five other sessions edit the app code in
parallel; you land first, so keep your diff mechanical.

## Verified facts (dev 100b7c2)

1. frontend/package.json declares `deck.gl` (meta package, zero imports; it pulls @arcgis,
   @esri, react-dom, ... into node_modules), `@deck.gl/geo-layers` (zero imports), `lodash` +
   `@types/lodash` (zero imports), `mdi` (2016 font package, zero imports; icons come from
   @mdi/js via vuetify/iconsets/mdi-svg), `nouislider` (zero imports), `typescript-json-schema`
   (only for the dead `schema` script). `@mdi/js` is a runtime dependency listed under
   devDependencies. node_modules is 957 MB today (hardlinked from the pnpm store, so the
   real per-worktree cost is small, but the install and the Docker image still pay it).
2. `type-check` runs `vue-tsc -p tsconfig.vitest.json --composite false`; that config sets
   "lib": [] so the app is type-checked with no standard library (works by accident through
   @types/node triple-slash refs) and every run is a cold full check. tsconfig.node.json
   references cypress / playwright configs that do not exist. Type-check passes today.
3. vite.config.ts has no build section: no manualChunks, no sourcemap, no sass
   `api: 'modern-compiler'`, and a commented "UNCOMMENT THIS IF YOURE HUGO" block.
   router/index.ts imports HomeView statically.
4. `test:unit` is `vitest` (watch mode). .github/workflows/quality-check.yml runs only on
   `main` (PRs target `dev`), has no test step, runs `pnpm run lint` WITH --fix, and its
   backend job calls flake8 and black, which are not installed (only ruff is).
   Node is 22 in CI and Dockerfile, README says 20, no .nvmrc / engines.
5. .husky/commit-msg sources .husky/_/husky.sh which does not exist; there is no root
   package.json, so husky / commitlint are installed nowhere. commitlint.config.js
   references a package that cannot resolve.
6. frontend/nginx.conf: "public, immutable" without max-age on hashed assets AND on *.json
   (style/light.json is not hashed); index.html gets a Pragma header carrying a
   Cache-Control value plus Cache-Control: public. frontend/Dockerfile runs `npm run build`
   (type-check + build) inside the image build.
7. Dead files with zero importers: src/utils/metadata.ts, src/utils/expressionMaplibre.ts,
   src/utils/layerSelector.ts, frontend/schema/, public/heatmap_params.json, frontend/.env
   VITE_PARAMETERS_URL / VITE_STYLE_URL and their env.d.ts entries. Do NOT delete
   utils/jsonWebMap.ts (another session removes it with its only user) nor utils/legendColor.ts
   (type import in MapLibreMap.vue). 32 console.* calls in shipped code, mostly
   services/trafficAnalysis.ts and stores/layers/urlSharing.ts: leave them, other sessions
   own those files.
8. .gitattributes is empty while .lfsconfig exists; about 90 MB of binaries in history.
   .editorconfig says 80 columns, prettier says 100.
9. README.md lists `make clean` and `make notebook`, which do not exist; frontend/README.md
   is the it4r-webmap template and documents the dead env vars.

## What to do

- package.json: remove deck.gl, @deck.gl/geo-layers, lodash, @types/lodash, mdi, nouislider,
  typescript-json-schema and the `schema` script; add @deck.gl/extensions at the same version
  as the other @deck.gl packages; move @mdi/js to dependencies; add "engines" and .nvmrc (22).
- The frontend is already on pnpm (done on dev before the sessions started: pnpm-lock.yaml,
  pnpm-workspace.yaml with allowBuilds, packageManager field, Makefile / wt-setup.sh /
  Dockerfile / CI switched, @deck.gl/extensions and the three @types/d3-* declared). Keep
  it: `pnpm install` regenerates pnpm-lock.yaml after your package.json edits, and never
  recreate package-lock.json. Report `du -sh node_modules` and `du -sh --apparent-size`.
- Scripts: test:unit -> `vitest run`, add test:watch; add lint:check (no --fix); type-check
  on tsconfig.app.json plus type-check:test on the vitest config with a real `lib`; remove
  the dead project references. Keep TypeScript 4.8. If the real `lib` surfaces type errors
  in files other sessions own, fix only trivial ones and list the rest in the PR.
- vite.config.ts: build.sourcemap 'hidden'; manualChunks for maplibre (+ pmtiles), deck
  (@deck.gl/*, @luma.gl/*, @loaders.gl/*), vuetify, d3; scss api 'modern-compiler'; delete
  the commented proxy block. router/index.ts: `() => import('@/views/HomeView.vue')`. Do NOT
  edit HomeView.vue or VisualizationsPanel.vue (another session moves the deck.gl part into
  an async child component). Report `vite build` chunk sizes before/after.
- Delete the dead files in item 7 and their env.d.ts entries.
- CI (.github/** is yours entirely): trigger on dev and main, lint:check,
  type-check, `vitest run`, `vite build` for the frontend job; backend job = `uv sync`,
  `uv run ruff check --no-fix app`, `uv run ruff format --check app`, `uv run pytest`
  (the backend session adds the tests; pytest with no tests must not fail the job, use
  `--co -q || true` style or `pytest -p no:cacheprovider` with `-k` only once tests exist,
  simplest: run pytest only if backend/tests exists). Conventional commits enforced with a
  commitlint GitHub action.
- Husky / commitlint: delete .husky and commitlint.config.js (CI enforces the convention),
  document the convention in CONTRIBUTING.md.
- nginx.conf: max-age=31536000 immutable for hashed /assets/* only, no-cache for index.html
  and *.json. frontend/Dockerfile: `npm run build-only` (type-check runs in CI). Add
  frontend/.dockerignore.
- .gitattributes with LFS rules for *.graphml *.geojson *.pmtiles *.pdf and `*.ipynb -diff`
  (future files only, do NOT migrate history); align .editorconfig with prettier (100).
- Docs: fix README (targets, Node 22, project tree without schema/), rewrite
  frontend/README.md, move traffic_analysis_feature.md to docs/ and update it to the four
  modification actions (remove, speed50, speed30, speed10).

## You own

frontend/package.json, pnpm-lock.yaml, pnpm-workspace.yaml, .nvmrc, vite.config.ts, vitest.config.ts,
tsconfig*.json, env.d.ts, .env, router/index.ts, .github/**, .husky/, commitlint.config.js,
CONTRIBUTING.md, frontend/Dockerfile, frontend/nginx.conf, frontend/.dockerignore,
.gitattributes, .editorconfig, the dead files in item 7, README.md, frontend/README.md,
docs/traffic_analysis_feature.md.

## Do not touch

Any .vue / .ts under frontend/src except the deletions above and router/index.ts; config/**;
backend/** (Dockerfile, Makefile, pyproject are another session's). No repo-wide prettier or
eslint --fix run.

## Acceptance

- `rm -rf node_modules && pnpm install --frozen-lockfile` completes; `pnpm why deck.gl`,
  `pnpm why lodash`, `pnpm why mdi`, `pnpm why nouislider` find nothing; node_modules size
  reported.
- `npm run type-check`, `npm run lint:check`, `npm run test:unit` (exits, no watch),
  `npm run build-only` green; dist/ shows the vendor chunks and sourcemaps.
- Workflow file valid (npx actionlint or a careful read); triggers on dev.
- `docker build frontend` works; `curl -I` on /index.html shows Cache-Control: no-cache and
  on /assets/*.js shows max-age=31536000, immutable.
- App still works at http://localhost:$FRONTEND_PORT/ (map, layers, traffic tool, CVRP).

Small conventional commits (chore:/build:/ci:/docs:). Push the branch (never dev). Finish
with the URL and a before/after table (node_modules size, build time, entry chunk size).
