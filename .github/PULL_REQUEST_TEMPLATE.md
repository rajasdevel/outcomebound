## What changed and why

<!-- The outcome, in one or two sentences. Link an issue or spec if one exists. -->

## Checks run

- [ ] `make gate`
- [ ] `make check`
- [ ] `make test`
- [ ] Narrower check(s), if any, and what they establish: <!-- e.g. a single test file -->

## Scope

- [ ] `outcomebound_tools/` and `scripts/` still import the standard library only (no new
      third-party dependency).
- [ ] Released `CHANGELOG.md` sections are untouched.
- [ ] A `CHANGELOG.md` `## [Unreleased]` bullet is added if this change reaches what a release
      ships.

## Sign-off

Every commit in this PR carries a `Signed-off-by` trailer (`git commit -s`), per
`CONTRIBUTING.md`'s DCO requirement.
