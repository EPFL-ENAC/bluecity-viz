// Commit message rules for CI (.github/workflows/quality-check.yml, wagoid action).
// Conventional Commits, with three exceptions:
// - GitHub squash-merge titles end with "(#123)" and carry no type. Let them through.
// - No rule on the subject case: our subjects often start with an acronym or a
//   name (OD, LFS, CO2, CVRP, SP2, EPFL, PMTiles) and the rule refused all of them.
// - No rule on the body line length: dependabot puts long URLs in its bodies.
export default {
  extends: ['@commitlint/config-conventional'],
  rules: { 'subject-case': [0], 'body-max-line-length': [0] },
  ignores: [(message) => /\(#\d+\)\s*$/.test(message.split('\n')[0])]
}
