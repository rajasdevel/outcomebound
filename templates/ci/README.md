# CI templates

Reference only. adopt never installs this; copy it into your CI yourself. Selection does not imply target wiring.

Each file carries two lines, selected separately; wire one or both and delete the other:

1. The install check, `outcomebound adopt . --check`: it reads each record adopt wrote as current,
   edited, stale or missing, and exits with the count that is not current.
2. The quality floor, `outcomebound floor check . --base <ref>`, for a project with a
   `.outcomebound/floor.json`.

| File | CI shape |
| --- | --- |
| `github-actions.yml` | GitHub Actions workflow |
| `gitlab-ci.yml` | GitLab CI pipeline |
| `Makefile.snippet` | A `make` target your CI already calls |
| `generic.sh` | Any other CI: a plain shell entry point |

`outcomebound` has to be on `PATH`: `github-actions.yml` installs it into the job's own Python
with `python -m pip install "git+https://github.com/rajasdevel/outcomebound@v<version>"`, pinned
to a published release; `uv tool install` or `pipx install` of the same, `pip install` of it into
a virtual environment, or a checkout's `scripts/outcomebound`, serves too. If you install from a
fork, change the URL to your fork's.

The floor runs the project's own ruff, mypy, gitleaks, bash and shellcheck, so place it after the
step that puts them on `PATH`: a missing or old tool reads `UNVERIFIED`, which fails the check.
`<ref>` is the commit the change replaces:

| CI system | Pull or merge request | Push |
| --- | --- | --- |
| GitHub Actions | `github.event.pull_request.base.sha` | `github.event.before` |
| GitLab CI | `$CI_MERGE_REQUEST_DIFF_BASE_SHA` | `$CI_COMMIT_BEFORE_SHA` |
| Anything else | `generic.sh <base-ref>` | `generic.sh`, which uses `HEAD~1` |

A new ref, such as a tag, carries an all-zero base, and the templates fall back to `HEAD~1`. The
base has to be in the clone, so each template asks for the whole history (`fetch-depth: 0`,
`GIT_DEPTH: 0`); a base the clone cannot resolve reads `UNVERIFIED` and fails. The check makes a
loosening visible; only the hosting service's branch protection can prevent one.
