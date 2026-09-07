You are in a git worktree (branch chore/tooling-upgrades) created from dev AFTER the six
perf/refactor branches landed. Read CLAUDE.md first (ports in .env.worktree, never push dev
or main). Goal: get off end-of-life tooling, in separately revertible commits, each leaving
type-check / lint / tests / build green.

1. @types/node 22, typescript 5.9, @vue/tsconfig 0.7, vue-tsc 3. Remove preserveValueImports
   and importsNotUsedAsValues from tsconfig.app.json (TS 5 errors when they are combined with
   verbatimModuleSyntax) and the ignoreDeprecations band-aid in tsconfig.node.json. Fix the
   type errors that moduleResolution 'bundler' surfaces. Report type-check time before/after.
2. vitest 3, then vite 7 + @vitejs/plugin-vue 6 + vite-plugin-vuetify latest. Fold
   vitest.config.ts into vite.config.ts.
3. prettier 3 + prettier-plugin-organize-imports 4 (keep trailingComma none, printWidth 100),
   one formatting-only commit for the whole frontend.
4. eslint 9 flat config (eslint.config.js), @vue/eslint-config-typescript 14,
   eslint-plugin-vue 10, drop @rushstack/eslint-patch. Update the CI scripts if names change.
5. pinia 3 (needs vue >= 3.5, already installed). Then maplibre-gl 5 with a manual QA pass on
   the map (addProtocol, setStyle diff, removed events, the lazy source logic); if anything
   regresses, stay on 4 and write why in the PR.
6. Backend: `uv lock --upgrade` for minor/patch only, run pytest.
7. Add a Renovate (or Dependabot) config with grouped minor updates, weekly, so this does not
   drift again.

Acceptance: npm run type-check, lint:check, test:unit, build-only green; backend pytest
green; app works at http://localhost:$FRONTEND_PORT/ (map, layers, theme switch, traffic tool,
CVRP). Small conventional commits (chore:/build:). Push the branch (never dev).
