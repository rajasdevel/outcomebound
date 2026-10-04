Thank you for your pull request. Fill in the sections below. If a line does not apply, say why
in a few words.

## What changed and why

<!-- The outcome, in one or two sentences. Link an issue or a spec if one exists. -->

## Checks run

Mark each check that you ran at the tip of this branch. A check that you did not run stays
unmarked.

- [ ] `make gate`
- [ ] `make check`
- [ ] `make test`
- [ ] A narrower check, if you ran one, and what it shows: <!-- for example, one test file -->

## Scope

- [ ] `outcomebound_tools/` and `scripts/` still import only the Python standard library. This
      change adds no third-party dependency.
- [ ] This change leaves the released sections of `CHANGELOG.md` as they were.
- [ ] If this change reaches what a release ships, it adds a bullet under `## [Unreleased]` in
      `CHANGELOG.md`.
- [ ] Public text: the title, the body, the commit messages and the files name no private
      project, person, local path, internal id or run anecdote.

## Sign-off

- [ ] Every commit in this pull request has a `Signed-off-by` trailer (`git commit -s`), as
      [CONTRIBUTING.md](https://github.com/rajasdevel/outcomebound/blob/main/CONTRIBUTING.md#sign-off-your-commits-dco-no-cla) describes.
