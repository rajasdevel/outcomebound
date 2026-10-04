---
name: distribution
status: ratified
---

# Distribution — design

## Outcome

An adopter installs OutcomeBound with one line,
`uv tool install git+https://github.com/rajasdevel/outcomebound@v<VERSION>`, and gets
`outcomebound` on `PATH`, running the engine and the files a checkout of that tag runs; a team
and its CI pin one release in that line. Someone working on OutcomeBound itself uses a clone,
whose `scripts/outcomebound` runs that checkout. How: `pyproject.toml`,
`scripts/build_backend.py`, `scripts/outcomebound`, `outcomebound_tools/__main__.py` and
`outcomebound_tools/home.py`, each opening with what it decides.

## What the package holds

The wheel holds `outcomebound_tools/`; the engine's own files under `outcomebound_tools/_home/`,
laid out as a checkout lays them out (`OutcomeBound.md`, `VERSION`, `LICENSE`, `NOTICE`,
`templates/`, `skills/`, `fragments/`, `schemas/`, `adapters/` and `scripts/new-spec.sh`); and
`scripts/outcomebound` as its one command, installed from the wheel's
scripts. `outcomebound_tools.home.ROOT` is the checkout's root where the package sits beside
`OutcomeBound.md`, and `_home/` otherwise, so every module reads the engine's files from one
place, `outcomebound home` prints it, and a skill's `$(outcomebound home)/…` path resolves either
way. The version is `VERSION`'s, read at build time; a pre-release such as `X.Y.Z-rc.N` is
written `X.Y.ZrcN`, as the wheel format needs, and any other form is refused. A checkout
contributes the files Git tracks, a source archive every file it holds but dotfiles and
bytecode; a checkout whose Git cannot list its files, and a tree without the engine, build
nothing. The source archive holds what rebuilds
the same wheel, byte for byte.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| A package built from this repository, installed as a tool from a release tag's Git URL | a clone with the launcher on `PATH` as the adopter's route, which leaves each teammate and each CI run on whatever commit its clone holds | user | decided |
| Publishing the package to PyPI, so that `uv tool install outcomebound` installs it | installing from the tag's Git URL only; a version published there can never be replaced | user | open |
| The build backend is this repository's own, standard library only | a packaging library as a build dependency, fetched on every install from source | agent | decided |
| One launcher for a checkout and an install. It resolves its own path through any link, whatever `CDPATH` the caller exports, and runs Python with `-I`: in a checkout, the `python3` on the first absolute `PATH` entry that has one, with that checkout first on its path; installed, the `python` or `python3` beside it in the environment's `bin/`. Neither the caller's directory, a relative `PATH` entry nor `PYTHONPATH` can shadow the engine, and nothing is exported | a console entry point, which runs without isolation; `OUTCOMEBOUND_HOME` and `PYTHONPATH` prose in every skill; `python3 -m` from the adopter's checkout, which a pull request can shadow | agent | decided |
| The supported routes are `uv tool install`, `pipx install` and `pip install` into a virtual environment; a launcher with no Python beside it names them | `pip install --user`, which puts the engine in the user site that `-I` leaves out, so its command cannot run | agent | decided |
| The engine's files ship inside the package, beside the code that reads them | files installed into a shared data directory, where another package can overwrite them | agent | decided |
| What the engine prints for a person or writes for a harness names the launcher, `outcomebound`, never a path to it | a path into one checkout or one environment | agent | decided |
| Builds are reproducible: entries sorted and dated from `SOURCE_DATE_EPOCH`, or 1980-01-01 | the build machine's timestamps, which make two builds of one tree differ | agent | decided |

## Validation

`tests/test_package.py` has pip build this checkout through the backend `pyproject.toml` names
and install it offline into a fresh environment, as an adopter's install does, and checks:
- that environment's `outcomebound` adopts a repository byte for byte as the checkout's launcher
  does;
- `outcomebound home` holds every file the shipped skills name;
- an engine in the caller's directory or on `PYTHONPATH` never runs;
- the source archive rebuilds the same wheel;
- a tree without the engine builds nothing, and a pre-release is written as pip reads it.

`tests/test_outcomebound_launcher.py` checks the launcher in a checkout, and `make release-check`
checks that every install line in the README and the CI templates pins the release `VERSION`
names.
