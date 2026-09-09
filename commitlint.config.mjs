// Commit message rules for CI (.github/workflows/quality-check.yml, wagoid action).
// Conventional Commits, with four exceptions:
// - GitHub squash-merge titles end with "(#123)" and carry no type. Let them through.
// - A merge commit is not a change of its own. The default list knows the forms
//   git writes itself, which all start with a capital M, so one written by hand
//   ("merge dev into feat/x") was refused. Same forms, any case.
// - No rule on the subject case: our subjects often start with an acronym or a
//   name (OD, LFS, CO2, CVRP, SP2, EPFL, PMTiles) and the rule refused all of them.
// - No rule on the body line length: dependabot puts long URLs in its bodies.
export default {
  extends: ['@commitlint/config-conventional'],
  rules: { 'subject-case': [0], 'body-max-line-length': [0] },
  ignores: [
    (message) => /\(#\d+\)\s*$/.test(message.split('\n')[0]),
    (message) => /^merge (branch|tag|pull request|remote-tracking|\S+ into )/i.test(message)
  ]
}
