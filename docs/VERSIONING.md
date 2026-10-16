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

The same two files are also published to PyPI, as the project `outcomebound`, by the release
workflow (see below). The first version on PyPI is 1.6.0; no earlier version is there. The tagged
Git URL stays a supported route for every version.

## When to make a release

Make a release when an adopter needs something in it. Do not make a release for each change: each
release makes every adopter act.

A fix that no adopter needs now waits for the next release that is due.

Do not make a release while a known issue is open. Step 1 below says how to find the known issues.

If the tag is not pushed yet, prepare the release again to take more fixes. Do not follow it with a
second release.

## How a release is made

This section is for the person who prepares a release of OutcomeBound.

At a release, these places name the same version:

- `VERSION`
- the heading and the link of the changelog section
- the `v=` of the operating-contract block that `adopt` installs
- every install line in the README and in `templates/ci/` (`…/outcomebound@v<VERSION>`)

Between two releases, the README on `main` can describe a change that the version its install
lines name does not have, because those lines change only with `VERSION` in the release commit.

`make canary` runs the engine of the release beside the installed release, on the local list of
projects, subject to the custom-command boundary in CONTRIBUTING.md. Inspect custom floor
commands first and use owned isolated checkouts where they may write; retain their identities
and distinguish those results from original-checkout observations. It runs `adopt`, `instructions check`,
and also `floor check` and `tickets check` where a project holds a floor, drafts or an export. It records its verdict for the tree of
the commit that it ran on, and it records nothing while the checkout holds changes that are not
committed. `make release-check` fails unless a PASS record exists for the tree of the commit that
it checks. Thus `make canary` runs on the committed release commit, after every change to the
release tree. A pull request that changes `adopt`, `tickets`, `floor`, `instructions` or `discovery` also runs
it before it lands; one run on a commit that holds every change of several such pull requests
covers all of them, before the first of them lands.

PyPI needs three account steps that no agent does and no check here can see. A maintainer does
them once, before the first tag that publishes (1.6.0), and they stay in place for later releases:

- a PyPI account, with two-factor authentication;
- a pending publisher on pypi.org for the project `outcomebound`, with owner `rajasdevel`,
  repository `outcomebound`, workflow file `ci.yml` and environment `pypi`;
- a GitHub environment `pypi` in the repository, with the maintainer as required reviewer if
  the maintainer wants to approve each upload.

The upload uses trusted publishing (OpenID Connect): the repository holds no PyPI token or
password. The pending publisher creates the project at the first upload, and the name is not
reserved until then. A version on PyPI can never be replaced: if one is wrong, the fix is a new
version. A pre-release tag (`v<VERSION>` with `-rc.N`) also uploads, as a pre-release.

A maintainer or an agent can prepare the release. Do these steps in this sequence:

1. Find the known issues first. Run `scripts/outcomebound review sweep`, which reads each review
   file under `.agents/work` (a file with a `Reviewed:` line) and names each finding with no
   disposition. Read the open issues of the release milestone (`gh issue list --milestone
   v<VERSION> --state open`) and the open pull requests (`gh pr list --state open`). Close each
   one: fix it, or record it as an accepted limit in its design. A finding is closed by its
   `Disposition:` line. The sweep does not read a report that has no `Reviewed:` line: an issue in
   such a report is known only when it is an issue in the milestone or a finding in a review file.
   Then, on a branch from `main`, prepare the complete release tree: `VERSION`, the dated changelog
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
3. Run `make release-check`. It first reads the record of `make canary`, and runs the review sweep
   of step 1 on the main checkout's `.agents/work`, also from a worktree. It then checks that the
   places above agree and that this repository's own install is current. It checks, from the
   files and with no network, that the package metadata is what PyPI accepts (core metadata 2.4,
   an SPDX license expression, the license files, a Markdown long description with no relative
   link) and that the `pypi` job of the release workflow is as stated below. It runs
   `make scrub` itself, so there is no separate scrub step; without the list of private names,
   that line reads `UNVERIFIED` and the check fails. It also runs the gate, the quality floor and
   the test suite, and they must pass. It reads GitHub's open alerts of code scanning,
   Dependabot and secret scanning with the maintainer's own GitHub token (`gh auth token`), and
   fails while any alert is open or an answer cannot be read: a release ships with no open
   security or quality alert. Fix the cause; dismiss an alert only where it is a false
   positive, with GitHub's reason and a comment that says why. It cannot see the three account
   steps above; the maintainer confirms them before step 6.
4. Land the release commit through its pull request, as one squash commit. A squash merge keeps
   the tree of the branch, so the record from the branch applies to the commit on `main`.
5. Make the annotated tag `v<VERSION>` on the commit on `main`, locally, and run
   `make release-check TAG=v<VERSION>`. The canary record is keyed on the tree, so the run fails
   on its canary line if the tree of the commit on `main` is not the tree of the release branch
   (for example, because a conflict was resolved in a different way); then run `make canary` on
   the commit on `main` and run the check again. With a tag, the check also fails until the
   commit has a passing CI run on `main` (if GitHub started no run for the push, start one by
   hand: `gh workflow run ci.yml --ref main`), so no release is cut from a `main` that failed.
   That CI run is the proof of the gate, the floor and the suite for this exact commit (the
   workflow runs `make gate`, the own-install check, the floor on the newest Python and the
   suite on each Python, on Windows and in containers), so with a tag the check does not run
   them a second time here. It still runs `make scrub` here, because CI has the list only where
   its secret is set, and reads GitHub's open alerts again, because CI's token cannot read
   Dependabot or secret-scanning alerts.
6. A maintainer pushes the tag, or an agent where a grant covers it (below).
7. CI on the tag runs `scripts/release-check.py --tag` once, in the job `verify-tag`, and the
   suite on each platform. It then publishes the release and then the PyPI upload (below).
8. A person checks PyPI, because no CI step reads it back:
    - the page `https://pypi.org/project/outcomebound/<VERSION>/` exists, shows the README
      with working links, and lists the wheel and the source archive;
    - an install of that version in a fresh tool environment runs and reports `<VERSION>`:

      ```sh
      tmp="$(mktemp -d)"
      UV_TOOL_DIR="$tmp/tools" UV_TOOL_BIN_DIR="$tmp/bin" uv tool install --no-cache "outcomebound==<VERSION>"
      cat "$("$tmp/bin/outcomebound" home)/VERSION"
      ```

    Until step 8 passes, the README keeps the tagged Git URL as its install route.

The release is complete when step 8 passes. Moving the projects that use OutcomeBound to the
release is a follow-up after the release, not a release step: the canary of step 2 has already
shown that the release runs on them. Do it per project, as that project's own change.

You cannot undo the push of a tag. A maintainer pushes it. An agent can push it only where a
grant of a maintainer in `.outcomebound/tag-grants.json` covers that version on that day. The last
line of `make release-check` names the grant, or says that none applies.

Once the tag exists, `make release-check TAG=v<VERSION>` and the job `verify-tag` of the CI run on the tag check that the
tag is annotated, that it names `VERSION`, that it points at the release commit, and that the
release commit has a passing CI run on `main`.

When the tag check and every leg of the CI run on the tag pass, its `release` job publishes the release. It
builds the wheel and the source archive from the tagged commit, attests them, puts them on a
draft release whose notes are the changelog section of the version, and publishes the draft. If
a leg fails, the job does not run and nothing is published. Where the repository has immutable
releases on, nobody can change a published release, its tag or its files, so a mistake needs a
new version.

After the `release` job succeeds, the `pypi` job downloads the two files of that published
release, so that PyPI holds the bytes that carry the provenance, and uploads them with the
`pypa/gh-action-pypi-publish` action. It runs in the GitHub environment `pypi`, has no checkout,
and is the only job besides `release` that holds `id-token: write`, on the job and not on the
workflow. If the upload fails after the release is published, the GitHub release stays; re-run
the failed job from the Actions page, or, if PyPI refused the files, make a new version.
