# Dependencies

The OutcomeBound engine and build backend use the Python standard library only. The package
declares no third-party Python runtime or build requirement. Installed tools, optional features
and this repository's checks have different needs.

## Install and run the engine

| Dependency | Where it is needed | Why |
| --- | --- | --- |
| Python 3.10 or later | Engine and build backend | Runs the command and its standard-library modules. CI tests Python 3.10 through 3.14. |
| Git 2.52.0 or later and a Git worktree | Adoption and repository operations | Reads tracked files, history, worktree identity and preservation state. |
| One of uv, pipx, or pip in a virtual environment | Installation | Installs the package and creates the command. They are alternative routes. A Git URL also needs Git and network access. |
| POSIX `sh` | Checkout launcher and finish-check Done lines | Runs shell command lines. The installed entry point itself runs Python. On Windows, Git for Windows supplies `sh.exe`. |
| The project's own check tools | Done lines or a selected floor | Runs the checks that the project declared. A missing tool reads UNVERIFIED. |
| Windows job objects and `taskkill.exe` | Windows process cleanup | A job object, through the standard library's `ctypes`, stops a timed-out command's whole process tree. The command starts suspended, joins the job, and is then resumed through the thread calls of `kernel32` (`CreateToolhelp32Snapshot`, `OpenThread`, `ResumeThread`). `taskkill.exe` is the fallback where a job cannot be made or joined. All of these are operating-system features. |

Package metadata comes from [the build backend](../scripts/build_backend.py); the empty build
dependency list is in [pyproject.toml](../pyproject.toml). Python isolation is part of the
[distribution design](specs/distribution/design.md). `pip install --user` is not a supported
route because the isolated engine ignores the user site.

Git 2.52.0 is the compatibility minimum. It was
[released on 17 November 2025](https://www.kernel.org/pub/software/scm/git/). The Linux CI leg
with Python 3.10 builds that exact version from source, checks its published SHA-256, and runs
the normal checks with its own executable and helper directory. That leg passed in hosted CI
on the v1.5.0 release commit ([run](https://github.com/rajasdevel/outcomebound/actions/runs/37826685203)).
A native Git for Windows 2.52.0 check remains `UNVERIFIED`. Older Git releases are outside the
supported range, even where they work.

Use a current patched Git release, especially
[Git for Windows](https://git-scm.com/install/windows). The compatibility minimum is not a
security update policy: [Git has no LTS release](https://github.com/git/git/blob/master/SECURITY.md)
and does not guarantee security maintenance for older feature tracks. Common-directory readers
resolve `rev-parse --git-common-dir` against the command's working directory; they need no
`--path-format=absolute` option. The [distribution design](specs/distribution/design.md) states
what the minimum-version checks establish.

The engine and finish hook do not require Node, npm, jq, rg, curl, Docker, sg, make or a package
manager for their own work. A project can use any of them in its Done commands. Installing a
harness can also have requirements of its own.

## Optional features

| Feature | Dependency | Why |
| --- | --- | --- |
| Automatic explorable browser check | Chrome, Chromium, Edge or Brave | The checker runs a Chromium-family browser headless and reads its printed document. It does not install a browser. |
| Explorable charts | Chart.js 4.5.1 from jsDelivr | Draws charts; the pinned script has a subresource-integrity hash. |
| Explorable diagrams | Mermaid 11.17.2 from jsDelivr | Draws diagrams; the module URL is pinned by version. It has no subresource-integrity field. |
| Selected Python floor | ruff and mypy | Runs the project's formatter, lint and type checks. |
| Selected shell floor | Bash and ShellCheck | Checks syntax, injection patterns and shell findings. The shipped ShellCheck recipe requires at least 0.9.0. |
| Selected secrets floor | gitleaks | Checks tracked files or history for secrets. The shipped recipe requires at least 8.21.2. |
| Floor provisioning | pip, only for missing ruff or mypy | Installs into the project's Python only with `--accept`. It prints gitleaks and ShellCheck installation routes instead of downloading them. Go or a system package manager is needed only if the user chooses such a route. |
| Research reads | A configured OBR clone | Reads the documents offline. Only accepted clone or pull acts need Git and network access. |
| GitHub ticket export or publication | GitHub CLI and access to GitHub | Produces a local export or performs the separately authorized tracker act. Engine ticket checks read the export and call no tracker. |
| Optional spec scaffold | Bash, cat, grep, dirname, mkdir and sed | Creates draft files from the shipped templates. |

[The library pins](../templates/explorable/libraries.json), [floor recipes](../outcomebound_tools/floor.py)
and [browser finder](../outcomebound_tools/explorable_browser.py) define these requirements.
The browser check can read a local HTML file. A local HTTP server is not an engine requirement.
Other stacks use the project's own commands and floor claims. A stack fragment does not install
that stack's runtime or make it a dependency of every OutcomeBound project.

An explorable page loads a chart or diagram library only when it uses that feature. A failed
load shows a fallback: chart data or diagram source, with a visible notice. Core inputs and
calculations still run. This does not make the rendered chart or diagram available offline.
A controlled browser test returns HTTP 404 for both libraries and checks the visible fallbacks,
inputs and calculations. It covers that unavailable-library case. Other offline, content-policy
and provider failures remain UNVERIFIED until observed.

## Development tools

This repository's [requirements-dev.txt](../requirements-dev.txt) has four direct pins. None
is imported by the engine.

| Tool | Pin | Why |
| --- | --- | --- |
| pytest | 9.1.1 | Runs the behavioral suite. |
| pytest-xdist | 3.8.0 | Runs tests across CPUs. Local `make test` also supports serial execution. |
| ruff | 0.16.7 | Checks format and lint. |
| mypy | 2.3.1 | Checks types with pytest importable in the same environment. |

The active [repository floor](../.outcomebound/floor.json) also requires gitleaks 8.21.2 or
later and Bash. CI downloads gitleaks 8.30.1 and checks its published archive checksum. This
repository does not currently select the ShellCheck floor claim. Make runs contributor
conveniences; the commands can also be run directly. uv is an optional fallback when the
chosen Python lacks the development tools. The contributor `upstream-check` uses GitHub CLI
for read-only API calls.

Direct pins do not lock indirect packages. The distribution metadata for those pinned tools
introduces these names:

| Introduced by | Indirect packages | Why |
| --- | --- | --- |
| pytest | iniconfig, packaging, pluggy, pygments | Configuration, version parsing, plugin hooks and diagnostic highlighting. |
| pytest on Windows | colorama | Terminal color support. |
| pytest on Python before 3.11 | exceptiongroup, tomli | Compatibility for exception groups and TOML. |
| pytest-xdist | execnet | Worker communication. |
| mypy | mypy_extensions, pathspec, ast-serialize | Type extensions, file selection and AST serialization. |
| mypy on CPython | librt | Compiled runtime support. |
| mypy, and exceptiongroup on older Python | typing_extensions | Typing compatibility. |
| mypy on Python before 3.11 | tomli | TOML parsing. |

Ruff declares no Python package dependencies. Optional extras of these tools are not selected
by this repository. The table is information about distribution metadata, not an added
constraint list. Exact resolved versions depend on Python, platform and install date; inspect
the environment's distribution metadata when a check changes.

No development lockfile or hash constraints are currently kept. Add a lock only when a clean
install shows that a different indirect resolution changes a required check. Record the
interpreter, platform and resolved packages first. Keep a resolved-environment record distinct
from the dependencies that the repository declares. A lock generator and runtime packages
are not required to make that diagnosis.

## Evaluations and CI

The model eval runner uses Python, Bash and Git. A Codex run also needs Codex CLI, a ChatGPT
login and an explicitly named model. A separate Claude Code native check needs that harness
and its model access. These are evaluation requirements. `ps` supports timeout cleanup on
non-Linux POSIX hosts; Linux reads `/proc`, and Windows uses a job object that the command joins before it runs, with taskkill as the fallback. The canary also needs
an installed prior OutcomeBound release, its Python and Python 3.10. It can find the latter
through uv or an explicit interpreter path.

[The CI workflow](../.github/workflows/ci.yml) uses these hosted dependencies:

| Dependency | Why |
| --- | --- |
| GitHub Actions and hosted Ubuntu/Windows runners | Run the platform matrix and release jobs. |
| actions/checkout v7.0.1 and actions/setup-python v7.0.0 | Fetch source and provide Python. Both actions are pinned by commit. |
| actions/attest-build-provenance v4.2.2 | Attests release files; pinned by commit. |
| python:3.13-slim and python:3.13-alpine | Check Debian and musl containers. These tags are not pinned by digest. |
| apt-get or apk, with distribution repositories; sudo on the hosted Linux runner | Install Git inside the containers or the minimum-Git build dependencies on the hosted runner. |
| Git 2.52.0 source, build-essential, libcurl4-openssl-dev, libexpat1-dev, gettext, zlib1g-dev and xz-utils | Build the pinned minimum Git in the existing Linux Python 3.10 leg. The source SHA-256 is pinned; distribution build packages are not. These are CI build dependencies, not engine requirements. |
| pip and package-index access | Install development tools and their indirect packages. |
| curl, uname, sha256sum, tar and mkdir | Download, verify and unpack gitleaks or the minimum Git source. |
| awk, ls, GitHub CLI and the GitHub release API | Extract release notes, inspect artifacts and publish the release. |
| GitHub API or a saved CI-run export | Check main CI for the release commit. The release checker uses Python's standard-library HTTP client. |
| Dependabot | Proposes weekly pip and action updates after a seven-day cooldown. |

PR sign-off checks use Git and grep. The main-green workflow uses `gh api --jq`; jq expression
support is part of GitHub CLI, so no separate jq executable is required. rg is not a workflow
dependency. Hosted runner images and indirect development packages can change even when the
action commits and direct tool versions are pinned. This is separate from reproducible
wheel content and the release's checks.
