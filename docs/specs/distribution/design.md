---
name: distribution
status: ratified
---

# Distribution — design

## Outcome

An adopter installs OutcomeBound with one line,
`uv tool install git+https://github.com/rajasdevel/outcomebound@v<VERSION>`, and gets
`outcomebound` on `PATH`, running the engine and the files a checkout of that tag runs, on
Windows, macOS, Linux and in containers; a team and its CI pin one release in that line. From
1.6.0 each release is also on PyPI, so that `uv tool install outcomebound==<VERSION>` installs
the same files; the tagged Git URL stays a supported route, and the README names PyPI as a route
only after the first version is there and a person has checked it (the release sequence in
`docs/VERSIONING.md`). Someone
working on OutcomeBound itself uses a clone, whose `scripts/outcomebound` runs that checkout.
How: `pyproject.toml`, `scripts/build_backend.py`, `scripts/outcomebound`,
`outcomebound_tools/launcher.py`, `outcomebound_tools/__main__.py` and
`outcomebound_tools/home.py`, each opening with what it decides.

## What the package holds

The wheel holds `outcomebound_tools/`; the engine's own files under `outcomebound_tools/_home/`,
laid out as a checkout lays them out (`OutcomeBound.md`, `VERSION`, `LICENSE`, `NOTICE`,
`templates/`, `skills/`, `fragments/`, `schemas/`, `adapters/` and `scripts/new-spec.sh`); and
the console entry point `outcomebound` as its one command, whose module is shipped at the top
level as `_outcomebound_launch.py` (its source is `outcomebound_tools/launcher.py`).
`outcomebound_tools.home.ROOT` is the checkout's root where the package sits beside
`OutcomeBound.md`, and `_home/` otherwise, so every module reads the engine's files from one
place, `outcomebound home` prints it, and a skill's `$(outcomebound home)/…` path resolves either
way. The version is `VERSION`'s, read at build time; a pre-release such as `X.Y.Z-rc.N` is
written `X.Y.ZrcN`, as the wheel format needs, and any other form is refused. A checkout
contributes the files Git tracks, a source archive every file it holds but dotfiles and
bytecode; a checkout whose Git cannot list its files, and a tree without the engine, build
nothing. A shipped file is executable when it starts with a `#!` line. The source archive holds what rebuilds
the same wheel, byte for byte.

## Dependencies and their limits

The engine and build backend import only the Python standard library. The package declares
Python 3.10 or later and no third-party Python runtime or build requirements. Git 2.52.0 or later
is required for adoption and repository operations. The installed entry point runs Python; the checkout
launcher uses POSIX `sh`. The finish check uses a POSIX shell to run Done lines and needs only
the additional tools that those lines require. Windows uses the shell supplied by Git for
Windows. These distinctions, the optional browser libraries and the contributor tools are
listed in [the dependency inventory](../../dependencies.md).

Git 2.52.0, [released on 17 November 2025](https://www.kernel.org/pub/software/scm/git/), is the
compatibility minimum. The Linux Python 3.10 CI leg builds that exact source release with its
published SHA-256, installs it under the runner's temporary directory, and selects both its
executable and helper directory before the normal checks. It excludes only the Tcl/Tk GUI;
network helpers and the commands the engine uses remain in the build. The other CI legs keep
their platform's Git. The Linux Python 3.10 leg passed in hosted CI on the v1.5.0 release
commit, with its Git 2.52.0 setup and selection steps and the full test suite
([run](https://github.com/rajasdevel/outcomebound/actions/runs/37826685203)). This adds no runtime dependency and no CI job.

The common-directory readers in `finish_check.py` and `scripts/canary.py` use
`rev-parse --git-common-dir` and resolve a relative result against the command's working
directory. Qualification with the actual minimum-version binary must check a main checkout,
a linked worktree and their subdirectories, including paths with spaces. A test that replaces
a Git result checks path handling but does not qualify a Git release. Older versions can work,
but are outside the supported range.

A Git 2.52.0 source build on macOS passed those common-directory checks with the actual binary.
Both readers resolved the same common directory, with the correct subdirectory prefix for
finish-check records. The focused checks also passed record sharing between worktrees and the
CI facts and release prerequisites. This establishes those local behaviours. The complete
minimum-version suite on Linux is covered by the hosted CI leg above. A native Git for Windows
2.52.0 check remains `UNVERIFIED`.

Use a current patched Git release; on Windows, use current
[Git for Windows](https://git-scm.com/install/windows). The compatibility minimum does not mean
that its feature track still receives security fixes. [Git's security policy](https://github.com/git/git/blob/master/SECURITY.md)
has no LTS version and guarantees maintenance only for the latest feature track.

Development tools have direct version pins. Indirect packages and CI container tags are not
locked. Keep those limits separate from the reproducible wheel build. A development lock is
conditional on a demonstrated change in clean-install resolution that changes a required
check's result. Record the interpreter, platform and resolution first. A new runtime dependency
or lock generator is not required by that decision.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| A package built from this repository, installed as a tool from a release tag's Git URL | a clone with the launcher on `PATH` as the adopter's route, which leaves each teammate and each CI run on whatever commit its clone holds | user | decided |
| Publish the package to PyPI, the first version being 1.6.0, through trusted publishing; the tagged Git URL stays a supported install route (user, 2026-10-09) | installing from the tag's Git URL only; a version published to PyPI can never be replaced, which the release sequence accepts by checking everything it can before the tag | user | decided |
| The release workflow's job `pypi` uploads the wheel and the source archive that the job `release` published, downloaded from that GitHub release, so PyPI holds the attested bytes. It runs only for a version tag, after `release`, in the GitHub environment `pypi`, has no checkout, and holds `id-token: write` on the job and not on the workflow. The upload uses the `pypa/gh-action-pypi-publish` action pinned by full commit, with PyPI's OpenID Connect exchange and no stored token; the pending publisher on PyPI names the repository, the workflow file `ci.yml` and the environment `pypi`. `make release-check` reads the job's shape and the package metadata from the files and calls no network; the PyPI account, the pending publisher and the GitHub environment are a maintainer's steps that it cannot see, and a person checks the version page and a fresh install after the upload (`docs/VERSIONING.md`) | an API token kept as a repository secret, which can be stolen and used anywhere; a second build in the `pypi` job, whose files would match the release only if the build stayed reproducible; one job for the release and the upload, which would give the upload the release's write permissions; publishing from a pull request or a branch | agent | decided |
| The package's core metadata is version 2.4 (PEP 639), which PyPI accepts: `License-Expression: Apache-2.0` and `License-File` for `LICENSE` and `NOTICE`, kept under `<name>-<version>.dist-info/licenses/` in the wheel and at the top of the source archive, with no `License` field and no license classifier. The expression names Apache-2.0 alone: the exception for the text that `adopt` writes into a project has no SPDX identifier that PyPI accepts, so `LICENSE`, which holds it, ships as the full terms. The long description is the README, with each relative link and image made absolute at the release's tag at build time (a page of the repository for a link, the raw file for an image), so that it resolves on PyPI while the README in the repository stays relative | metadata 2.2 with a free-text `License` field, which PyPI deprecates beside an expression; `Apache-2.0 AND LicenseRef-…`, which tells a reader that two licenses both apply when the exception only relaxes one; absolute links written into the README, which break when a document moves and read worse in the repository; a build step that needs a Markdown library | agent | decided |
| Each release tag that passes every CI leg is published by CI as a GitHub release: the wheel and the source archive built from the tagged commit, attested with signed build provenance (`actions/attest-build-provenance`), on a draft that is then published, so that an immutable release can hold them; the install route was then the tag's Git URL (maintainer, 2026-10-04), and the PyPI upload below follows this release and keeps these files | a tag with no release files, which leaves an adopter nothing to verify; a separate workflow on the tag, which runs beside the checks and could publish a failing tag | user | decided |
| The build backend is this repository's own, standard library only | a packaging library as a build dependency, fetched on every install from source | agent | decided |
| The installed command is a console entry point, `outcomebound = _outcomebound_launch:main`, which pip and uv make an `outcomebound` program on every platform: a script in `bin/` on POSIX, an `.exe` in `Scripts\` on Windows, in both the one file of that name. It runs `sys.executable -I -X utf8 -m outcomebound_tools <arguments>`: the Python of the environment that holds the engine, so the command resolves its engine with no link or neighbour to follow, also where uv copies the executable. The engine runs as a child process on every platform, and its exit code is returned (128 plus the signal number for a child that a signal ended): Windows has no call that replaces a process, since `os.execv` there ends the parent at once and a harness that waits for a hook would see the hook end before the check did, and one path serves both systems. Ctrl-C is left to the child, which the console sends it as well, and SIGTERM is passed on to it. `-I` keeps the caller's directory, a relative `PATH` entry and `PYTHONPATH` off the engine's path, and nothing is exported. The remainder: before the second start, a file named `_outcomebound_launch.py` in a folder that `PYTHONPATH` names is imported in place of the hop, since an installer writes a console script without `-I`. An absolute `PYTHONPATH` entry is the caller's own choice, as is a replacement of `outcomebound` on `PATH`. A relative entry (such as `.` or `src`) names a folder of the target, which a hook runs in, so a file the target commits there replaces the first hop; the caller's folder alone does not, and 1.3.0's sh launcher, which ran `python -I` at once, did not have this remainder. No code closes it: one wheel cannot ship the sh launcher for POSIX and an entry point for Windows under one name. The README asks that `PYTHONPATH`, where set, hold absolute folders only. The hop is not inside `outcomebound_tools`, so a folder on `PYTHONPATH` that holds an `outcomebound_tools` of its own cannot take it | the sh launcher as the package's data script, which pip copies as it is: no `.exe`, no shebang on Windows (PowerShell, cmd and a harness's process cannot run it), and a uv copy in `.local\bin` has no Python beside it to find; an entry point inside `outcomebound_tools`, which such a folder could take; an entry point that runs the engine in its own process, with no second start, which runs without `-I` and so lets `PYTHONPATH` shadow the engine; `os.execv` on POSIX, which keeps signals and the exit code with no forwarding, but the quality floor's S606 rule flags the call and no exemption is added without a maintainer's ruling (the open row below); `OUTCOMEBOUND_HOME` and `PYTHONPATH` prose in every skill; `python3 -m` from the adopter's checkout, which a pull request can shadow | agent | decided |
| The launcher runs the engine as a child process on every platform; no exemption of the quality floor's S606 rule is sought (maintainer, 2026-10-07): the child process already keeps exit codes and signals, and CI tests it on every platform | an exemption for the launcher, so that a POSIX launcher replaces its process with `os.execv`: it loosens the floor for no observed failure | user | decided |
| A checkout keeps its POSIX sh launcher, `scripts/outcomebound`, for contributors, this repository's scripts and its CI, and it is not in the wheel. It resolves its own path through any link, whatever `CDPATH` the caller exports, using the selected Python's standard library and no external dirname or readlink, and runs the first `python3` or `python` that an absolute `PATH` entry names and that runs as Python 3.10 or later, with `-I -X utf8` and the checkout first on its path: a relative entry, a Store stub that opens a store and a Python 2 are passed over. On Windows it runs under Git for Windows' `sh`, with Python on `PATH`, and `make` is a separate install; that is UNVERIFIED until a contributor or a CI job runs it there | one Python launcher for both: its `#!/usr/bin/env python3` line searches `PATH` with its relative entries, and the checkout's scripts and `.agents/tools/runner` start it as a command; a second launcher file in the wheel, so that `bin/` holds two files named `outcomebound` | agent | decided |
| A failure of a launcher or of the verb table exits 127 where there is no Python or no engine to run, and 1 for no verb or a verb the table does not hold, and never 2 | exit 2 for a usage error, as `argparse` does, which a harness's stop hook reads as holding the turn, so that a missing Python or an old hook entry would hold every turn end | agent | decided |
| Every verb's stdout and stderr are UTF-8 with LF line ends on every platform: `__main__.main` reconfigures both streams, each keeping its own error handler, and the launchers add `-X utf8`. A script, a path or a JSON document the engine prints reads the same through a pipe or a redirect | the console's code page and `\r\n`, which stop a verb with `UnicodeEncodeError` on a character outside cp1252 and add a carriage return to `$(outcomebound home)` and to a printed script; `PYTHONUTF8` and `PYTHONIOENCODING`, which `-I` makes the engine ignore; an encoding chosen verb by verb | agent | decided |
| The wheel and the source archive mark a file executable when it starts with a `#!` line | `os.access`, which is true for every file on Windows, so a wheel built there differs from the release wheel; Git's mode (`git ls-files -s`), which a source archive unpacked on Windows has lost | agent | decided |
| The supported routes are `uv tool install`, `pipx install` and `pip install` into a virtual environment | `pip install --user`, which puts the engine in the user site that `-I` leaves out, so its command cannot find the engine and exits 1 | agent | decided |
| The engine's files ship inside the package, beside the code that reads them | files installed into a shared data directory, where another package can overwrite them | agent | decided |
| What the engine prints for a person or writes for a harness names the launcher, `outcomebound`, never a path to it | a path into one checkout or one environment | agent | decided |
| Builds are reproducible: entries sorted and dated from `SOURCE_DATE_EPOCH`, or 1980-01-01 | the build machine's timestamps, which make two builds of one tree differ | agent | decided |
| The packaging path refuses a checkout whose Git cannot list its files, and `build_backend.py` does not set `safe.directory`: it is the maintainer's own path, run in their own checkout. The CI container job, whose checkout belongs to another user than the container's root, runs `git config --system --add safe.directory "$GITHUB_WORKSPACE"` after the checkout, so that the suite's isolated home (which hides a `--global` setting) still sees it, and the engine is not changed to suit that job | `-c safe.directory` in the build or in the engine's Git reads, which trusts a target for the user; `--global`, which the suite's isolated `HOME` hides | agent | decided |
| `scripts/check-structure.py` runs a tracked executable through the interpreter its `#!` line names where the platform has no `#!` (Windows): a Python file under the Python that runs the check, a shell file under the shell of Git for Windows (never the Windows Subsystem for Linux launcher in the Windows folder), and a first line that names another interpreter reads as a problem, not as a pass. On POSIX the file itself runs, since its mode bit is the promise. It imports the standard library only | running every file directly, which cannot start a `.sh` or `.py` file on Windows; skipping the check on Windows, which leaves a script that fails its help unseen there | agent | decided |
| The CI test command is plain text: the temporary folder of each job reaches `--basetemp` through the environment variable `PYTEST_BASETEMP` (`$PYTEST_BASETEMP` in a POSIX shell, `$env:PYTEST_BASETEMP` in PowerShell, the Windows job's default shell), set in the step's `env:` where the `${{ }}` expression is, so that the project facts read each CI test command and name none as `runs an expression` | an expression in the command line, which the facts cannot settle | agent | decided |

## Validation

The installed-package hook test runs the actual stored hook command on a synthetic project
with a restricted runtime PATH. It checks a pass, a changed-tree failure and an unavailable
project tool without a package-manager or development-tool dependency. This is direct command
evidence; it does not claim the native harness emitted the hook event.


`tests/test_package.py` has pip build this checkout through the backend `pyproject.toml` names
and install it offline into a fresh environment, as an adopter's install does, and checks:
- that environment's `outcomebound`, the one program of that name in its scripts folder (`bin/`,
  or `Scripts\` with an `.exe` on Windows), adopts a repository byte for byte as the checkout's
  engine does, and exits 1 for a verb it does not hold;
- `outcomebound home` holds every file the shipped skills name;
- an engine in the caller's directory or on `PYTHONPATH` never runs;
- the source archive rebuilds the same wheel, and the wheel marks the files Git tracks as
  executable, and no others, even where `os.access` is true for every file;
- the metadata is what PyPI accepts and renders: version 2.4 fields as the decision above
  states them, the same text in the wheel and the source archive, the license files in both,
  and no relative link in the long description;
- a tree without the engine builds nothing, and a pre-release is written as pip reads it.

`tests/test_release_check.py` checks that `make release-check` fails, on its own line, for
metadata without a license expression and for a `pypi` job that is not pinned by full commit,
is outside the environment `pypi`, does not need `release`, or runs where the whole workflow
holds `id-token: write`. A build checked with `twine check` and `packaging`'s strict metadata
validation passed on the change that added the job; the upload itself, the pending publisher and
the first install from PyPI are `UNVERIFIED` until a maintainer has made the first release.

`tests/test_outcomebound_launcher.py` checks the engine as the launchers start it (isolated,
UTF-8, exit 1 for an unknown verb, UTF-8 with LF into a stream that is cp1252 with CRLF), the
entry point (its command line, the child's exit code, Ctrl-C left to the child, SIGTERM passed
on, and exit 127 where Python cannot start), and the checkout's sh launcher where `sh` runs. A
real Windows run is the Windows CI job. `make release-check`
checks that every install line in the README and the CI templates pins the release `VERSION`
names.
