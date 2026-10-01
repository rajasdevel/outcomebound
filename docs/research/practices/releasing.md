---
last_checked: 2026-10-01
volatility: STABLE (packaging specifications and Python's flags, §§1–6) / VOLATILE (§7 GitHub Actions, §8 hosted minutes and self-hosted runners, §9 publishing a repository)
sources:
  - https://packaging.python.org/en/latest/specifications/binary-distribution-format/
  - https://packaging.python.org/en/latest/specifications/version-specifiers/
  - https://packaging.python.org/en/latest/specifications/source-distribution-format/
  - https://packaging.python.org/en/latest/specifications/recording-installed-packages/
  - https://peps.python.org/pep-0517/
  - https://peps.python.org/pep-0668/
  - https://docs.python.org/3/using/cmdline.html
  - https://docs.python.org/3/library/site.html
  - https://pypi.org/help/
  - https://reproducible-builds.org/docs/source-date-epoch/
  - https://docs.astral.sh/uv/concepts/tools/
  - https://github.com/actions/checkout/pull/2356
  - https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
  - https://docs.github.com/en/actions/reference/security/secure-use
  - https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions
  - https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility
---

# Packaging and releasing a command-line tool

Re-check when a new major version of `actions/checkout` or `actions/setup-python`, a change to
GitHub's Actions pricing or concurrency settings, a uv, pip or pipx release that changes tool
installs, or a revision of a packaging specification.

How a command-line tool written in Python's standard library is packaged, installed, versioned,
built reproducibly, tagged, published and run in CI, and what changes when its repository goes
public.

This reference answers how to ship a command so that the person who installs it runs exactly the
engine they installed: what a wheel's scripts and console entry points do, what Python's isolated
mode guarantees and what it leaves out, which install routes work and which fail, how to spell
versions and pre-releases, what frontends enforce in a wheel and a source archive, how to build the
same bytes twice, why publishing to PyPI is irreversible, what GitHub Actions does on a tag push and
with concurrent pushes, how to secure a workflow and a self-hosted runner, what hosted minutes cost,
and what renaming or publishing a repository changes. It is for anyone packaging, installing or
releasing a command-line tool, or wiring its CI.

**Evidence classes.** (S) a specification or standard: the Python packaging specifications, PEPs,
POSIX; (L) a vendor's or tool's own documentation, changelog or issue tracker; (O) an observation or
measurement recorded in this project's own packaging work, reviews and CI, with the tool versions
named; (A) a reviewer's note or a reading not reproduced. "The package" is one standard-library
command, built by its own PEP 517 backend and installed as a uv tool, with pipx, or with pip into a
virtual environment; its packaging was probed with uv 0.11.6, pip 26.2.1, pipx 1.17.8 and CPython
3.10.11 to 3.14.7, on macOS and in a Debian container. "One repository's CI" is a GitHub repository
on the free plan whose tests ran on GitHub-hosted runners, then on a self-hosted runner, over two
weeks.

## Key findings

**RL1. Ship the command as a script that runs its own environment's interpreter with `-I`.** A
console entry point runs without isolation, so `PYTHONPATH` and the user site reach it; a POSIX `sh`
script shipped in the wheel's `.data/scripts/` installs as the command and can run the interpreter
beside it with `-I`, which kept a planted copy of the engine on `PYTHONPATH` and in the caller's
directory from running. (S, O)

**RL2. `-I` guards against the caller, not against the environment's owner.** It implies `-E`, `-P`
and `-s` but not `-S`, so `.pth` files and `sitecustomize` still run, and it leaves out the user
site, so a `pip install --user` of such a command cannot import its own package. Install into an
environment that holds only the tool: `uv tool install`, `pipx install`, or pip into a virtual
environment. (S, O)

**RL3. Write the wheel's version in its normal form.** `1.1.0-rc.1` is `1.1.0rc1` to the version
specification, and a wheel whose file name carries the SemVer spelling failed to install with
`Invalid build number: rc.1`. Validate the version at build time. (S, O)

**RL4. A version published to PyPI can never be replaced.** A file name is never reusable, even
after the project is deleted, and deletion is permanent; a corrected build ships under a new
version. Installing from a release tag's Git URL needs no index. (L)

**RL5. A standard-library build can be byte-identical everywhere.** With entries sorted and dated
from `SOURCE_DATE_EPOCH` (clamped at 1980), gzip written with mtime 0 and PAX tar entries owned by
uid 0, one package built the same wheel and source archive across three Python versions, two
operating systems, two zlib versions, two umasks and with or without Git. (L, O)

**RL6. A build that lists its files with Git can ship nothing, or too much.** Inside an ignored
folder of another checkout, `git ls-files` lists nothing and exits 0, and the build produced a wheel
without its package; `--others` ships untracked files such as `.env`. List `--cached` only when
`git rev-parse --show-toplevel` is the source root, and refuse a build that lacks a required file.
(O)

**RL7. `actions/checkout` before v6.0.2 turns an annotated tag into a lightweight one on a tag
push.** A release check that requires an annotated tag then fails, silently under `bash -e`. Re-fetch
the tag in the step that reads it, or use v6.0.2 or later, which fetches tags by refspec. (O, L)

**RL8. Pin actions by commit, keep the token read-only, and keep pull requests off a self-hosted
runner.** A full-length commit SHA is the only immutable way to use an action; the default token
should read contents only; a self-hosted runner on a public repository runs any fork's pull request;
and `actions/checkout` up to v5 leaves its token in `.git/config` for every later step unless
`persist-credentials: false`. (L)

**RL9. A concurrency group per workflow and ref keeps CI current, but only for checks that do not
need every push's range.** With `cancel-in-progress: false`, the run in progress finishes and only
the ref's waiting run is replaced by a newer push; a tag's or a pull request's run is never cancelled
by a push to the default branch. That setting protects running jobs, not queued ones: a check whose
base is the commit a push replaced (`github.event.before`) never reads the changes of a push whose
waiting run was cancelled. A check that must read every push's range runs with no group;
OutcomeBound's own CI and its CI template carry none for that reason. (L, O)

**RL10. Hosted minutes run out fast on a private repository.** GitHub Free includes 2,000 minutes
a month for private repositories; a tag run over five Python versions took 81 runner-minutes and a
push over two about 21, so the allowance covers about 24 such tag runs or 95 such pushes a month.
Standard hosted runners are free for public repositories. (L, O)

**RL11. Going public exposes the Actions history, and a rename breaks action references.** Making a
private repository public makes its Actions history and logs visible to everyone and erases stars
and watchers; after a rename, Git traffic redirects but a workflow using an action hosted in the
renamed repository fails with `repository not found`. (L)

## 1. The command a package installs (RL1, RL2)

**Scripts in a wheel.** At install, each subtree of a wheel's `<name>-<version>.data/` moves onto its
destination, so a file under `.data/scripts/` lands in the environment's scripts directory; "If the
first line of a file in `scripts/` starts with exactly `b'#!python'`, rewrite to point to the correct
interpreter", and "Unix installers may need to add the +x bit to these files if the archive was
created on Windows"; the scripts directory "may only contain regular files" (S, binary distribution
format). A script whose first line is `#!/bin/sh` installed byte for byte with mode 755 under pip
26.2.1, uv 0.11.6 and pipx 1.17.8 (O). uv 0.11.6, installing a wheel that held one POSIX `sh` script
there and one console entry point, reported "Installed 2 executables" and placed both in the tool
bin directory as symbolic links into the tool environment's `bin/` (O, 2026-10-01); uv's docs:
"Tool executables are symlinked into the executable directory on Unix and copied on Windows" (L).

**A console entry point is not isolated.** The wrapper uv 0.11.6 generated for a console entry point
ran with `sys.flags.isolated` 0, so `PYTHONPATH` and the user site applied to it (O, 2026-10-01). A
shipped `sh` launcher that runs `"$dir/python" -I -m <package>` closes that: a module of the engine's
name planted on `PYTHONPATH` and in the caller's directory never ran, on CPython 3.10.11 and 3.14,
also with `PYTHONHOME` and `PYTHONSTARTUP` set; `-I` keeps the working directory off `sys.path` for
`-c` on 3.10 as well (O, the package's test, 2026-10-01).

**What `-I` does and does not do.** "Run Python in isolated mode. This also implies `-E`, `-P` and `-s`
options. In isolated mode `sys.path` contains neither the script's directory nor the user's
site-packages directory. All `PYTHON*` environment variables are ignored, too" (added in 3.4; `-P`,
"Don't prepend a potentially unsafe path to `sys.path`", in 3.11) (S, Python command-line
documentation). It does not imply `-S`, so the `site` module still runs: "An executable line in a
`.pth` file is run at every Python startup", and `site` imports `sitecustomize` (S, `site`
documentation). A planted `.pth` in the environment changed what the installed command imported (O,
2026-10-01). `-I` therefore protects the command from the caller's directory and environment, not
from whoever owns the environment it runs in; a uv tool or pipx environment holds only the tool,
while a CI job's shared interpreter holds whatever the project installed beside it.

**A launcher reached through a link finds itself first.** In a tool bin directory the command is a
symbolic link, so `dirname "$0"` names the bin directory, not the environment that holds the
interpreter; the script follows the link (a `readlink` loop) before it looks beside itself (O, uv
0.11.6, 2026-10-01). Paths with spaces, relative and absolute link chains and a link to a link all
resolved under macOS `/bin/sh`, dash, bash, zsh and busybox ash (O).

**Shell traps in a launcher** (O, macOS `/bin/sh`, dash, bash 5 and zsh, 2026-10-01):

- **`CDPATH`.** "If a non-empty directory name from `CDPATH` is used … that pathname shall be written
  to the standard output" (S, POSIX `cd`). With `CDPATH` exported, `here=$(cd "$(dirname "$0")" &&
  pwd -P)` captured the directory `cd` printed, or a same-named directory elsewhere, so the variable
  held two lines and every command that invoked the launcher by a relative path failed. Write
  `CDPATH='' cd -P -- "$(dirname -- "$0")"`.
- **zsh does not split unquoted parameters.** "Words of unquoted parameters are not automatically
  split on whitespace unless the option `SH_WORD_SPLIT` is set", which sh and ksh emulation set (L,
  zsh manual). `for dir in $PATH` with `IFS=:` ran once under `zsh script`, while `zsh --emulate sh`
  worked; split with parameter expansion (`${rest%%:*}`, `${rest#*:}`) instead.
- **Relative `PATH` entries.** Resolving `python3` from `PATH` ran a `python3` in the caller's
  directory when `PATH` held `.`; take absolute entries only.

**Finding the interpreter.** A prefix may hold `python3` and no `python` (Homebrew's `bin`, or a
Debian `/usr/local` beside a system `python3`), so a launcher tries both before it gives up, and its
error names the supported install routes (O, 2026-10-01).

## 2. Install routes

**What worked** (O, uv 0.11.6, 2026-10-01): `uv tool install` from a local wheel, from
`git+file:///<path>@<branch>` and from `git+ssh://git@github.com/<owner>/<repo>.git@main`;
`pipx install` of the same Git URL with spaces in `PIPX_HOME` and `PIPX_BIN_DIR`; and
`pip install` into a fresh virtual environment. Against a private repository,
`git+https://github.com/<owner>/<repo>` waited for credentials instead of failing, so an unattended
run puts a timeout around it. Each uv install wrote `uv-receipt.toml` in the tool environment,
recording the requirement as given (a path, or `git = "ssh://…?rev=main"`) and the executables it
linked, and the environment ran a uv-managed CPython 3.13.13 rather than the system interpreter.
`UV_TOOL_DIR` ("the directory where uv stores managed tools") and `UV_TOOL_BIN_DIR` ("the 'bin'
directory for installing tool executables") (L, uv docs) put both in a scratch directory, so a probe
leaves the person's own tools untouched.

**What failed** (O, Debian `python:3.10-slim` container and macOS, 2026-10-01):

- **`pip install --user`.** The command lands in `~/.local/bin`, which holds no interpreter; with a
  `python` linked there, `-I` (which implies `-s`) still dropped the user site, and the command could
  not import its own package.
- **A system interpreter.** `pip install` into a Homebrew or Debian system `python3` refused with
  pip's `externally-managed-environment` error. The mechanism is PEP 668's `EXTERNALLY-MANAGED`
  marker, whose Debian example message says to "create a virtual environment using python3 -m venv
  path/to/venv" (S, PEP 668). A step that installs tools says to activate the project's virtual
  environment first. With only `/usr/bin` on `PATH`, macOS supplied the Command Line Tools' Python
  3.9, whose pip could not find mypy 2.3.1.
- **pip inside a tool environment.** Environments that `uv tool install` and `pipx install` create
  held no pip (`No module named pip`), and only the tool's own command was linked onto `PATH`, so a
  tool that provisions other tools with `sys.executable -m pip` failed there, and would have
  installed them where its checks never look had it worked. Provision into the interpreter the
  project's checks run, found on `PATH` (O, uv 0.11.6, pipx 1.17.8).
- **Editable installs.** PEP 660's hooks are optional (S); with no `build_editable` hook,
  `pip install -e .` failed with a clear message and `uv pip install -e` with a traceback.

**Test the route a user runs.** A packaging test that imported the build backend and called it
in-process passed with `backend-path` in `pyproject.toml` naming a directory that does not exist,
while `pip install` through the frontend raised `BackendUnavailable` (O, 2026-10-01). PEP 517 requires
`backend-path` to "refer to a location within the source tree" and the backend to be loaded from it
(S). Install through the frontend in the test (`pip install --no-index --no-deps <checkout>` stays
offline when the backend needs nothing), and keep the in-process build for byte-level checks.
Creating the test's virtual environment needs `ensurepip`, which "is an optional module. If it is
missing from your copy of CPython, look for documentation from your distributor" (L, Python docs);
such a test reads `UNVERIFIED` where it is missing.

## 3. Versions and pre-releases (RL3)

"Pre-releases should allow a `.`, `-`, or `_` separator between the release segment and the
pre-release segment. The normal form for this is without a separator", a separator is also allowed
between the signifier and its number, and "Pre-releases allow the additional spellings of `alpha`,
`beta`, `c`, `pre`, and `preview` for `a`, `b`, `rc`, `rc`, and `rc` respectively" (S, version
specifiers). So `1.1.0-rc.1` normalizes to `1.1.0rc1`. A wheel built with `1.1.0-rc.1` in its file
name failed `pip install` with `ERROR: Invalid build number: rc.1` (O, pip 26.2.1, 2026-10-01). A
project that tags `vX.Y.Z-rc.N` writes the wheel's version in the normal form, and its build refuses
a version string outside PEP 440 with a clear message.

## 4. What frontends enforce in a wheel and a source archive

Frontends do not all enforce the formats the same way (O, pip 26.2.1 and uv 0.11.6, 2026-10-01):

- **`RECORD` is CSV.** "It is a CSV file containing one record (line) per installed file", readable
  by "the default `reader` of Python's `csv` module" (S, recording installed projects). A path with an
  unquoted comma made uv refuse the wheel (`RECORD file is invalid … CSV error`) while pip installed
  it with a warning; write `RECORD` with `csv.writer`.
- **Metadata version.** A source archive's `PKG-INFO` "MUST conform to at least version 2.2 of the
  metadata specification" (S, source distribution format); pip and uv accepted 2.1, which would
  matter on upload.
- **Offline builds.** `get_requires_for_build_wheel` and `_sdist` default to `return []` (S, PEP
  517); a backend returning `[]` built and installed with no network (`pip --no-index`,
  `uv --offline`).

## 5. Reproducible builds (RL5, RL6)

**Fixing the bytes.** `SOURCE_DATE_EPOCH` "is a standardised environment variable that distributions
can set centrally and have build tools consume this in order to produce reproducible output", in
seconds since the Unix epoch; its zip example clamps the value with `max(315532800, …)`, since a zip
entry cannot be dated before 1980-01-01 (L, reproducible-builds.org). A standard-library backend that
sorts entries, dates them from `SOURCE_DATE_EPOCH` or 1980-01-01, writes gzip with mtime 0 and a
basename-only header, and writes PAX tar entries with uid 0 and empty owner names produced
byte-identical wheels and source archives across CPython 3.10, 3.13 and 3.14, on macOS and Debian,
with Apple zlib 1.2.12 and Debian zlib 1.3.1, under umask 077 and 000, with and without Git, from
`/`, and through `uv build`; a wheel rebuilt from the source archive equalled the one built from the
checkout (O, one package, 2026-10-01). An empty `SOURCE_DATE_EPOCH` crashed a backend that passed it
to `int()`; treat empty as unset (O). zlib-ng, and a file system that marks every file executable
(the executable bit was read with `os.access`, not from Git's recorded mode), were not tested.

**Choosing the files** (O, git 2.55.0 and pip 26.2.1, 2026-10-01):

- `git ls-files --cached --others --exclude-standard` run inside a directory that an enclosing work
  tree ignores exits 0 with no output, because Git finds the enclosing repository, which tracks
  nothing there ([git.md](git.md) §4). A pip install from a source archive unpacked under such a
  folder (a `TMPDIR` or cache directory inside a checkout) built a wheel without its package and
  exited 0; `uv build` and a Git-URL install, which unpack elsewhere, were unaffected.
- `--others` adds untracked, unignored files, so a stray `.env` shipped.
- A fallback that walks the tree when Git is missing or refuses shipped ignored files (`.DS_Store`)
  and changed the artifact's hash.
- A package built from a working tree carried uncommitted files without saying so: 39 of 136 files
  in one package (O).

Trust the listing only when `git rev-parse --show-toplevel` is the source root, list `--cached` for
what a release ships, refuse a build that lacks a required file, and record the source commit and
whether the packaged bytes differ from it.

## 6. PyPI and release tags (RL4, RL7)

**PyPI.** "PyPI does not allow for a filename to be reused, even once a project has been deleted and
recreated", and "Deletion of a project, release or file on PyPI is permanent and irreversible,
without exception"; a correction ships as a new version (L, PyPI help). Publishing to the index is an
irreversible act; installing from a release tag's Git URL (`uv tool install
git+https://github.com/<owner>/<repo>@v<version>`) needs no index and no upload.

**Annotated tags on a tag push.** With `fetch-depth: 0` and `fetch-tags: true`, `actions/checkout@v4`
first fetched every tag and then, for the tag event, ran `git fetch --no-tags --prune
--no-recurse-submodules origin +<commit>:refs/tags/<tag>`, so `git cat-file -t refs/tags/<tag>` read
`commit`, not `tag`. A release check requiring an annotated tag then fails before any test runs,
with no message under `bash -e`, and a fail-fast matrix cancels its other jobs;
`git fetch --force --no-tags origin "refs/tags/<tag>:refs/tags/<tag>"` in the step restored the
annotated tag, and the check then passed in every leg (O, one repository's CI and a local
reproduction [as-of 2026-09-25]). Upstream, the issue "Preserve tag annotations"
has been open since 2020-06-26; the fix shipped in `actions/checkout` v6.0.2 (pull request 2356,
merged 2026-01-09), which fetches tags by the refspec `+refs/tags/*:refs/tags/*` "instead of `--tags`
flag. This fetches the actual tag objects, preserving annotations"; the v4 and v5 lines carry no such
change: their latest releases, v4.4.0 and v5.1.0 of 2026-07-20, backport the pull-request checkout
default and input handling, and keep the tag fetching v6.0.2 replaced (L, the action's changelog,
release notes, source at those tags, pull request and issue 290, read 2026-10-01). A check step
prints what it compared, so a failure under `set -e` names its cause.

**Recording what a release contains.** A digest of `git archive` output identifies a commit, not a
tree ([git.md](git.md) §6), and a committed record naming the commit that contains it can never
match ([cli-conventions.md](cli-conventions.md) §3).

## 7. GitHub Actions (VOLATILE) (RL7–RL9)

**Concurrency.** "By default, any existing `pending` job or workflow in the same concurrency group
will be canceled and the new queued job or workflow will take its place"; "To also cancel any
currently running job or workflow in the same concurrency group, specify `cancel-in-progress:
true`"; with `queue: single` (the default) "At most one job or workflow run can be `pending`", with
`queue: max` "Up to 100"; and "concurrency group names must be unique across workflows to avoid
canceling in-progress jobs or runs from other workflows" (L, "Control the concurrency of workflows
and jobs"). A top-level group keyed `${{ github.workflow }}-${{ github.ref }}` with
`cancel-in-progress: false` therefore keeps, by default, one run in progress and one waiting per ref,
and a push to the default branch never cancels a tag's or a pull request's run. Without
`github.workflow` in the key, the group is shared with every workflow in the repository; a
`concurrency` key on a matrix job whose name holds no matrix value puts every leg in one group
(inference from the naming rule, not observed). `cancel-in-progress: true` leaves a started commit
with no verdict.

In one repository whose five-version matrix ran on two self-hosted runners at about 15 minutes a
job, runs queued with no group waited up to 3 h 23 min; with the group, over three hours the run in
progress finished with its own conclusion, each of the four runs queued behind it was cancelled
without starting a job within a second of the next push, and the last one ran (O [as-of
2026-09-24]).

**What a group costs.** A push whose waiting run is cancelled is compared by no push run, since the
next run's `github.event.before` is its own push's, so a policy check keyed on `before` never sees
the cancelled range; the suite still runs over the whole tree at the newer commit (O). For example:
push A is running; push B loosens a policy and waits; push C, harmless, replaces the waiting B. C's
check compares B with C, so the loosening between A and B is read by no push run.
`cancel-in-progress: false` protects the running A, not the queued B. A group therefore suits checks
that judge the tree at a commit, not checks that judge each push's range. OutcomeBound's own CI
workflow and its CI template carry no concurrency group: their quality-floor step takes
`github.event.before` as the base of a check for loosening, and each says in a comment that a
cancelled waiting run would leave its push's changes unread by that check.

**A matrix stops at its first failure.** `strategy.fail-fast` defaults to `true`, and then GitHub
"will cancel all in-progress and queued jobs in the matrix if any job in the matrix fails" (L). A
list of failing legs records which leg failed first, not which versions fail.

**Pinning and permissions.** "Pinning an action to a full-length commit SHA is currently the only
way to use an action as an immutable release", and the default permission of `GITHUB_TOKEN` should
be read access to repository contents only, widened per job where a job needs more (L, "Secure use
reference"). A version tag such as `@v4` names whatever commit its owner moves it to.

**Checkout credentials.** For `actions/checkout` v4: "The auth token is persisted in the local git
config. This enables your scripts to run authenticated git commands. The token is removed during
post-job cleanup. Set `persist-credentials: false` to opt-out"; v6.0.0 moved the credentials to "a
separate file under `$RUNNER_TEMP` instead of directly in `.git/config`" (L, the action's README and
changelog). With v4 or v5, every later step of the job can read the token from `.git/config`. v7,
and since 2026-07-20 the v6.1.0, v5.1.0, v4.4.0, v3.7.0 and v2.8.0 backports, released as breaking
changes, refuse by default to check out a fork's pull request code for `pull_request_target` and
`workflow_run` (L, README and release notes).

**Self-hosted runners and pull requests.** "Self-hosted runners should almost never be used for
public repositories on GitHub, because any user can open pull requests against the repository and
compromise the environment"; on a private repository, "anyone who can fork the repository and open a
pull request (generally those with read access to the repository) are able to compromise the
self-hosted runner environment" (L, "Secure use reference"). A workflow that sends every event to a
self-hosted runner would run any fork's pull request on that machine once public; choosing the runner
by event keeps pull requests hosted: `runs-on: ${{ github.event_name == 'push' &&
vars.<RUNNER_VARIABLE> || 'ubuntu-latest' }}` (O, one repository's workflow).

## 8. Hosted minutes and self-hosted runners (VOLATILE) (RL10)

GitHub Free includes 2,000 minutes a month of GitHub-hosted runners for private repositories, and
"The use of standard GitHub-hosted runners is free" in public repositories (L, "About billing for
GitHub Actions"). In one repository's CI on a private repository (O), a tag run over five Python
versions took 81 runner-minutes and a push over two about 21, in rounded minutes; a day of frequent
pushes used most of a month's allowance.

A self-hosted runner on a developer's machine moves that load onto the machine (O, the same
repository): its jobs take the CPUs local test suites use; a run queued while the machine sleeps
waits 24 hours and is then cancelled; a runner re-registered under its old name reports "a session
for this runner already exists" for about two minutes; a runner container that runs several jobs
keeps every job's temporary files unless its temporary directory is emptied (pytest's reached 28 GB
in one container), so empty `/tmp` at each container start; and the tool cache, about 2 GB, gains
about 400 MB for each new Python patch release a job selects. A test
that hands a subprocess a built `env=` must carry `LD_LIBRARY_PATH` for such a runner's Python
([testing.md](testing.md) K7).

## 9. Publishing a repository (VOLATILE) (RL11)

**Renaming.** "All existing information, with the exception of project site URLs, is automatically
redirected to the new name", including issues, wikis, stars and followers, and "all `git clone`, `git
fetch`, or `git push` operations targeting the previous location will continue to function"; but
"GitHub will not redirect calls to an action hosted by a renamed repository. Any workflow that uses
that action will fail with the error `repository not found`", and a new repository created under the
old name ends the redirects (L, "Renaming a repository"). An old clone then points at the new
repository, not the renamed one (inference).

**Making a private repository public.** "Actions history and logs will be visible to everyone",
"Anyone can fork your repository", "Stars and watchers for this repository will be erased" and "All
push rulesets will be disabled" (L, "Setting repository visibility"). Read the logs of past runs for
secrets and personal paths before the switch, and move pull requests off any self-hosted runner (§7).

**What a private repository on the free plan lacks.** Its branch-protection API answered 403,
"Upgrade to GitHub Pro or make this repository public", so a required check could not be enforced:
CI ran after work had landed and a `CODEOWNERS` file bound nothing (O [as-of 2026-09-28]).

**Security reports.** Private vulnerability reporting is enabled per repository, "You can only report
vulnerabilities privately for repositories where this feature is enabled", and it "is separate from
a repository's `SECURITY.md` file" (L, GitHub docs). A `SECURITY.md` linking the private reporting
form leads nowhere until the setting is on, and GitHub's community profile lists a missing security
policy (A, reviewers' notes; neither found in the docs read).

**Pushing an existing history.** Create the GitHub repository empty: "To avoid errors, do not
initialize the new repository with README, license, or gitignore files" (L, "Adding locally hosted
code to GitHub"), and "If you're importing an existing repository to GitHub, don't choose any of
these options, as you may introduce a merge conflict" (L, "Creating a new repository"). Any of
those files gives the new repository a first commit of its own, unrelated to the history being pushed
(inference; the docs name the error, not the commit).

**Tags and releases.** "Releases are based on Git tags" (L, "About releases"); a release is created
from a tag, and pushing a tag alone does not make one (inference from the docs, not stated there).

## How to apply

For a command-line tool released from a Git repository:

1. Ship the command as a `sh` script in the wheel's `.data/scripts/` that follows its own link, finds
   `python` or `python3` beside itself and runs it with `-I`; set `CDPATH=''` on its `cd`, split
   `PATH` without word splitting and skip relative entries (RL1).
2. Document `uv tool install`, `pipx install` and pip into a virtual environment; say that
   `pip install --user` and a system interpreter do not work, and why (RL2).
3. Validate the version against PEP 440 at build time and write pre-releases as `X.Y.ZrcN` (RL3).
4. Build from `git ls-files --cached` only when the top-level is the source root; refuse a build
   missing a required file; write `RECORD` with `csv.writer` and `Metadata-Version: 2.2` (RL6, §4).
5. Fix the bytes with `SOURCE_DATE_EPOCH` and sorted, uid-0, mtime-0 archives; check by building
   twice on different machines (RL5).
6. Test installing through the frontend a user runs, offline (§2).
7. Install from the release tag's Git URL until publishing to PyPI is decided; treat an upload as
   irreversible (RL4).
8. In the workflow: pin actions by commit SHA, set `permissions: contents: read` at the top, set
   `persist-credentials: false` on `actions/checkout` before v6, re-fetch the tag before checking it
   is annotated (or use v6.0.2 or later), and send pull requests to hosted runners; group
   concurrency by workflow and ref with `cancel-in-progress: false` only when no check needs every
   push's range, and leave a workflow whose check compares each push with `github.event.before`
   (such as a quality floor's loosening check) with no group (RL7–RL9).
9. Before going public, read the Actions logs, remove pull-request access to self-hosted runners,
   turn on private vulnerability reporting, and run the documented install line from a machine with
   no credentials (RL11).

## Limits and open questions

- The packaging observations come from one package and one review day, on macOS and one Debian
  image; Windows, zlib-ng and a PyPI upload were not tried.
- The CI figures come from one repository over two weeks; GitHub's prices, defaults and action
  versions change, and the billing page was read for the included minutes, not for runner multipliers.
- That a matrix-level `concurrency` key makes legs cancel each other's waiting legs is inferred from
  the naming rule, not observed; whether `actions/checkout` v4 has an input that prevents the commit
  fetch for a tag event was read from its source on 2026-09-24, not re-checked.
- No primary source was found for which Linux distributions ship `venv` without `ensurepip`.

## Sources

Specifications, read 2026-10-01: [binary distribution
format](https://packaging.python.org/en/latest/specifications/binary-distribution-format/);
[version specifiers](https://packaging.python.org/en/latest/specifications/version-specifiers/);
[source distribution
format](https://packaging.python.org/en/latest/specifications/source-distribution-format/);
[recording installed
projects](https://packaging.python.org/en/latest/specifications/recording-installed-packages/);
[PEP 517](https://peps.python.org/pep-0517/); [PEP 660](https://peps.python.org/pep-0660/); [PEP
668](https://peps.python.org/pep-0668/); [POSIX
`cd`](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/cd.html).
Documentation, read 2026-10-01: Python [command line](https://docs.python.org/3/using/cmdline.html),
[`site`](https://docs.python.org/3/library/site.html),
[`venv`](https://docs.python.org/3/library/venv.html) and
[`ensurepip`](https://docs.python.org/3/library/ensurepip.html); [PyPI help](https://pypi.org/help/);
[SOURCE_DATE_EPOCH](https://reproducible-builds.org/docs/source-date-epoch/); uv
[tools](https://docs.astral.sh/uv/concepts/tools/) and [environment
variables](https://docs.astral.sh/uv/reference/environment/); the zsh manual,
[Expansion](https://zsh.sourceforge.io/Doc/Release/Expansion.html) and
[Options](https://zsh.sourceforge.io/Doc/Release/Options.html); `actions/checkout`
[README](https://github.com/actions/checkout/blob/main/README.md),
[CHANGELOG](https://github.com/actions/checkout/blob/main/CHANGELOG.md), [issue
290](https://github.com/actions/checkout/issues/290) and [pull request
2356](https://github.com/actions/checkout/pull/2356), the
[releases](https://github.com/actions/checkout/releases) of 2026-07-20 and the backport pull
requests 2500–2504 and 2523–2527; GitHub Docs: [control the concurrency of
workflows and
jobs](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency),
[workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
(`strategy.fail-fast`, read from the reusable snippet in GitHub's docs repository), [secure use
reference](https://docs.github.com/en/actions/reference/security/secure-use), [about billing for
GitHub
Actions](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions),
[renaming a
repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository),
[creating a new
repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository),
[adding locally hosted code to
GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github),
[setting repository
visibility](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility),
[privately reporting a security
vulnerability](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability),
[configuring private vulnerability
reporting](https://docs.github.com/en/code-security/security-advisories/working-with-repository-security-advisories/configuring-private-vulnerability-reporting-for-a-repository)
and [about
releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).
Own records: one package's probes, packaging test and reviews; one repository's tag runs and a local
reproduction of the tag fetch, its concurrency record, its CI and security audits, and its runner
notes. OutcomeBound's `.github/workflows/ci.yml` and `templates/ci/github-actions.yml`, read
2026-10-01.
