# CI templates

These files are examples for you to copy. `adopt` never installs them, and choosing a harness or
a fragment never wires a CI system for you. Copy the file that fits your CI, and change it to
match your project.

Each file holds two checks. They are separate, so wire one or both and delete the other:

1. **The install check**, `outcomebound adopt . --check`. It reads each record that `adopt` wrote
   as current, edited, stale or missing. It exits with the number of records that are not
   current, at most 100.
2. **The quality floor**, `outcomebound floor check . --base <ref>`. Use it only in a project
   that has a `.outcomebound/floor.json`.

## Choose a file

| File | CI shape |
| --- | --- |
| `github-actions.yml` | A GitHub Actions workflow |
| `gitlab-ci.yml` | A GitLab CI pipeline |
| `Makefile.snippet` | A `make` target that your CI already calls |
| `generic.sh` | Any other CI: a plain shell entry point |

## Put `outcomebound` on `PATH`

Every template needs `outcomebound` on `PATH`. Install it at a published release:

- `github-actions.yml` installs it into the job's own Python with
  `python -m pip install "git+https://github.com/rajasdevel/outcomebound@v<version>"`.
- The other templates use `uv tool install "git+https://github.com/rajasdevel/outcomebound@v<version>"`.
- `pipx install` of the same address works. So does `pip install` into a virtual environment, or
  a link to a checkout's `scripts/outcomebound`.
- If you install from a fork, change the address to your fork's.

Each template names the release that it shipped with. When you upgrade, change the version in
your copy.

## Wire the quality floor

The floor runs your project's own ruff, mypy, gitleaks, bash and shellcheck. Place it after the
step that puts them on `PATH`. A tool that is missing or too old reads `UNVERIFIED`, and
`UNVERIFIED` fails the check.

`<ref>` is the commit that the change replaces:

| CI system | Pull or merge request | Push |
| --- | --- | --- |
| GitHub Actions | `github.event.pull_request.base.sha` | `github.event.before` |
| GitLab CI | `$CI_MERGE_REQUEST_DIFF_BASE_SHA` | `$CI_COMMIT_BEFORE_SHA` |
| `Makefile.snippet` | The `outcomebound-floor` target, with `OB_BASE=<ref>` | The same. `OB_BASE` is `HEAD~1` if you do not set it |
| `generic.sh` | `generic.sh <base-ref>` | `generic.sh`, which uses `HEAD~1` |

A new ref, such as a tag, has an all-zero base. The GitHub Actions and GitLab CI templates then
use `HEAD~1`.

The base must be in the clone, so clone the whole history. The GitHub Actions template sets
`fetch-depth: 0`, and the GitLab CI template sets `GIT_DEPTH: 0`. With the other two templates,
set this in your own CI. A base that the clone cannot resolve reads `UNVERIFIED`, and the check
fails.

The floor makes a loosening visible. It does not prevent one. Only the branch protection of your
hosting service can prevent a loosening.
