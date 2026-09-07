// Commit message rules for CI (.github/workflows/quality-check.yml, wagoid action).
// Conventional Commits, with one exception: GitHub squash-merge titles end with
// "(#123)" and carry no type. Let them through.
module.exports = {
  extends: ['@commitlint/config-conventional'],
  ignores: [(message) => /\(#\d+\)\s*$/.test(message.split('\n')[0])]
}
