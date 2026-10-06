---
name: distribution
status: ratified
---

# Distribution — design

## Outcome

An adopter installs OutcomeBound with one line,
`uv tool install git+https://github.com/rajasdevel/outcomebound@v<VERSION>`, and gets
`outcomebound` on `PATH`, running the engine and the files a checkout of that tag runs, on
Windows, macOS, Linux and in containers; a team and its CI pin one release in that line. Someone
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

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| A package built from this repository, installed as a tool from a release tag's Git URL | a clone with the launcher on `PATH` as the adopter's route, which leaves each teammate and each CI run on whatever commit its clone holds | user | decided |
| Publishing the package to PyPI, so that `uv tool install outcomebound` installs it | installing from the tag's Git URL only; a version published there can never be replaced | user | open |
| Each release tag that passes every CI leg is published by CI as a GitHub release: the wheel and the source archive built from the tagged commit, attested with signed build provenance (`actions/attest-build-provenance`), on a draft that is then published, so that an immutable release can hold them; the install route stays the tag's Git URL | a tag with no release files, which leaves an adopter nothing to verify; a separate workflow on the tag, which runs beside the checks and could publish a failing tag | user (maintainer, 2026-10-04) | decided |
| The build backend is this repository's own, standard library only | a packaging library as a build dependency, fetched on every install from source | agent | decided |
| The installed command is a console entry point, `outcomebound = _outcomebound_launch:main`, which pip and uv make an `outcomebound` program on every platform: a script in `bin/` on POSIX, an `.exe` in `Scripts\` on Windows, in both the one file of that name. It runs `sys.executable -I -X utf8 -m outcomebound_tools <arguments>`: the Python of the environment that holds the engine, so the command resolves its engine with no link or neighbour to follow, also where uv copies the executable. The engine runs as a child process on every platform, and its exit code is returned (128 plus the signal number for a child that a signal ended): Windows has no call that replaces a process, since `os.execv` there ends the parent at once and a harness that waits for a hook would see the hook end before the check did, and one path serves both systems. Ctrl-C is left to the child, which the console sends it as well, and SIGTERM is passed on to it. `-I` keeps the caller's directory, a relative `PATH` entry and `PYTHONPATH` off the engine's path, and nothing is exported. The remainder: before the second start, a module named `_outcomebound_launch` on `PYTHONPATH` would be imported in place of the hop, and only the caller's own environment can place one, which also lets it replace `outcomebound` itself on `PATH`. The hop is not inside `outcomebound_tools`, so a folder on `PYTHONPATH` that holds an `outcomebound_tools` of its own cannot take it | the sh launcher as the package's data script, which pip copies as it is: no `.exe`, no shebang on Windows (PowerShell, cmd and a harness's process cannot run it), and a uv copy in `.local\bin` has no Python beside it to find; an entry point inside `outcomebound_tools`, which such a folder could take; an entry point that runs the engine in its own process, with no second start, which runs without `-I` and so lets `PYTHONPATH` shadow the engine; `os.execv` on POSIX, which keeps signals and the exit code with no forwarding, but the quality floor's S606 rule flags the call and no exemption is added without a maintainer's ruling (open: with one, POSIX can replace the process); `OUTCOMEBOUND_HOME` and `PYTHONPATH` prose in every skill; `python3 -m` from the adopter's checkout, which a pull request can shadow | agent | decided |
| A checkout keeps its POSIX sh launcher, `scripts/outcomebound`, for contributors, this repository's scripts and its CI, and it is not in the wheel. It resolves its own path through any link, whatever `CDPATH` the caller exports, and runs the first `python3` or `python` that an absolute `PATH` entry names and that runs as Python 3.10 or later, with `-I -X utf8` and the checkout first on its path: a relative entry, a Store stub that opens a store and a Python 2 are passed over. On Windows it runs under Git for Windows' `sh`, with Python on `PATH`, and `make` is a separate install; that is UNVERIFIED until a contributor or a CI job runs it there | one Python launcher for both: its `#!/usr/bin/env python3` line searches `PATH` with its relative entries, and the checkout's scripts and `.agents/tools/runner` start it as a command; a second launcher file in the wheel, so that `bin/` holds two files named `outcomebound` | agent | decided |
| A failure of a launcher or of the verb table exits 127 where there is no Python or no engine to run, and 1 for no verb or a verb the table does not hold, and never 2 | exit 2 for a usage error, as `argparse` does, which a harness's stop hook reads as holding the turn, so that a missing Python or an old hook entry would hold every turn end | agent | decided |
| Every verb's stdout and stderr are UTF-8 with LF line ends on every platform: `__main__.main` reconfigures both streams, each keeping its own error handler, and the launchers add `-X utf8`. A script, a path or a JSON document the engine prints reads the same through a pipe or a redirect | the console's code page and `\r\n`, which stop a verb with `UnicodeEncodeError` on a character outside cp1252 and add a carriage return to `$(outcomebound home)` and to a printed script; `PYTHONUTF8` and `PYTHONIOENCODING`, which `-I` makes the engine ignore; an encoding chosen verb by verb | agent | decided |
| The wheel and the source archive mark a file executable when it starts with a `#!` line | `os.access`, which is true for every file on Windows, so a wheel built there differs from the release wheel; Git's mode (`git ls-files -s`), which a source archive unpacked on Windows has lost | agent | decided |
| The supported routes are `uv tool install`, `pipx install` and `pip install` into a virtual environment | `pip install --user`, which puts the engine in the user site that `-I` leaves out, so its command cannot find the engine and exits 1 | agent | decided |
| The engine's files ship inside the package, beside the code that reads them | files installed into a shared data directory, where another package can overwrite them | agent | decided |
| What the engine prints for a person or writes for a harness names the launcher, `outcomebound`, never a path to it | a path into one checkout or one environment | agent | decided |
| Builds are reproducible: entries sorted and dated from `SOURCE_DATE_EPOCH`, or 1980-01-01 | the build machine's timestamps, which make two builds of one tree differ | agent | decided |

## Validation

`tests/test_package.py` has pip build this checkout through the backend `pyproject.toml` names
and install it offline into a fresh environment, as an adopter's install does, and checks:
- that environment's `outcomebound`, the one program of that name in its scripts folder (`bin/`,
  or `Scripts\` with an `.exe` on Windows), adopts a repository byte for byte as the checkout's
  engine does, and exits 1 for a verb it does not hold;
- `outcomebound home` holds every file the shipped skills name;
- an engine in the caller's directory or on `PYTHONPATH` never runs;
- the source archive rebuilds the same wheel, and the wheel marks the files Git tracks as
  executable, and no others, even where `os.access` is true for every file;
- a tree without the engine builds nothing, and a pre-release is written as pip reads it.

`tests/test_outcomebound_launcher.py` checks the engine as the launchers start it (isolated,
UTF-8, exit 1 for an unknown verb, UTF-8 with LF into a stream that is cp1252 with CRLF), the
entry point (its command line, the child's exit code, Ctrl-C left to the child, SIGTERM passed
on, and exit 127 where Python cannot start), and the checkout's sh launcher where `sh` runs. A
real Windows run is the Windows CI job. `make release-check`
checks that every install line in the README and the CI templates pins the release `VERSION`
names.
