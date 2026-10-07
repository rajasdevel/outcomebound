# Versioning

One version number, in `VERSION`, covers the whole distribution: the package, the engine, the
launcher, the skills, the fragments, the templates and the schemas. OutcomeBound follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). The bump depends on what an adopter
must do. It does not depend on which files changed.

## What each release means for you

| Release | For an adopter |
| --- | --- |
| Patch | Fixes and clarifications. Nothing that an install or a command relies on changes. |
| Minor | Additions. Everything that an install or a command relies on keeps working. |
| Major | Something that an install or a command relies on changes in an incompatible way: a verb, a flag, a file format or the shape of a managed block. The changelog section says what to do first. |

Read the section of [CHANGELOG.md](../CHANGELOG.md) for each release that you take. A released
section is never edited.

## How to take a release

1. Install the release with its tag: `uv tool install --force git+https://github.com/rajasdevel/outcomebound@v<version>`.
2. Run `outcomebound adopt .` in your project again.

Until you do step 2, `outcomebound adopt . --check` reads the operating-contract block as stale.
The block carries the version that wrote it.

If your CI installs a pinned release and runs `outcomebound adopt . --check`, change the pin and
commit the result of step 2 in the same change. An engine reads an install that a different
release wrote as stale, in the two directions: with the old pin and the new install, the check
fails, and with the new pin and the old install, the check also fails.

From 1.1.0, each release is also a GitHub release with the wheel and the source archive. CI
builds them from the tagged commit and attests them with signed build provenance. To verify a
file that you downloaded, run `gh attestation verify <file> -R rajasdevel/outcomebound`.

## How a release is made

This section is for the person who prepares a release of OutcomeBound.

At a release, these places name the same version:

- `VERSION`
- the heading and the link of the changelog section
- the `v=` of the operating-contract block that `adopt` installs
- every install line in the README and in `templates/ci/` (`…/outcomebound@v<VERSION>`)

`make canary` runs the engine of the release beside the installed release, on the local list of
projects, with no change to them, as CONTRIBUTING.md says. It runs `adopt`, `instructions check`,
and also `floor check` and `tickets check` where a project holds a floor, drafts or an export. It records its verdict for the tree of
the commit that it ran on, and it records nothing while the checkout holds changes that are not
committed. `make release-check` fails unless a PASS record exists for the tree of the commit that
it checks. Thus `make canary` runs on the committed release commit, after every change to the
release tree. A pull request that changes `adopt`, `tickets`, `floor`, `instructions` or `discovery` also runs
it before it lands; one run on a commit that holds every change of several such pull requests
covers all of them, before the first of them lands.

A maintainer or an agent can prepare the release. Do these steps in this sequence:

1. On a branch from `main`, prepare the complete release tree: `VERSION`, the dated changelog
   section, written from the title and description of each pull request that landed since the
   previous release (`git log --first-parent v<previous>..origin/main`), with its "Do these steps
   first" list from their `Adopter steps`; the section names each of those pull requests by its
   number, which `make release-check` checks (it does not count the release commit itself: give
   its pull request the title `release: <VERSION>`, so a release cut again is known too), the tag
   link of the section, the `[Unreleased]`
   compare link from `v<VERSION>`, the install lines in the README and in `templates/ci/`, and
   this repository's own install (`scripts/outcomebound adopt .`). Commit all of it, and keep no
   change that is not committed.
2. Run `make canary` on that commit. If you change the tree after this step, commit the change
   and run `make canary` again.
3. Run `make scrub`.
4. Run `make release-check`. It first reads the record of `make canary`. It then checks that the
   places above agree and that this repository's own install is current. It also runs the gate,
   the quality floor and the test suite, and they must pass.
5. Land the release commit through its pull request, as one squash commit. A squash merge keeps
   the tree of the branch, so the record from the branch applies to the commit on `main`.
6. Make sure that the tree of the new commit on `main` is the tree of the release branch, for
   example with `git diff <branch> origin/main` that shows no difference. If the trees are
   different (for example, because a conflict was resolved in a different way), the record does
   not apply: run `make canary` and `make release-check` on the commit on `main`.
7. Wait for the CI run on `main` for that commit to pass. If GitHub starts no run for the push,
   start one by hand: `gh workflow run ci.yml --ref main`.
8. Make the annotated tag `v<VERSION>` on the commit on `main`, locally, and run
   `make release-check TAG=v<VERSION>`. With a tag, it also checks that the commit has a passing CI
   run on `main`, so no release is cut from a `main` that failed.
9. A maintainer pushes the tag, or an agent where a grant covers it (below).
10. CI on the tag runs the same check, and publishes the release (below).
11. Move all projects that use OutcomeBound to the release.

You cannot undo the push of a tag. A maintainer pushes it. An agent can push it only where a
grant of a maintainer in `.outcomebound/tag-grants.json` covers that version on that day. The last
line of `make release-check` names the grant, or says that none applies.

Once the tag exists, `make release-check TAG=v<VERSION>` and the CI run on the tag check that the
tag is annotated, that it names `VERSION`, that it points at the release commit, and that the
release commit has a passing CI run on `main`.

When every leg of the CI run on the tag passes, its `release` job publishes the release. It
builds the wheel and the source archive from the tagged commit, attests them, puts them on a
draft release whose notes are the changelog section of the version, and publishes the draft. If
a leg fails, the job does not run and nothing is published. Where the repository has immutable
releases on, nobody can change a published release, its tag or its files, so a mistake needs a
new version.
