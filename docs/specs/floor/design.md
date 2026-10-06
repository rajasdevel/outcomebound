---
name: floor
status: ratified
---

# Quality floor — design

## Outcome

A project blocks regressions in what catches defects — format, lint, types, secrets, shell
syntax, shell lint and shell injection — with its own tool configs and a baseline a person can
read, and a change that loosens the floor fails `check --base` unless the commit that makes it
names the decision that allowed it. A project that already has findings adopts the floor the day it wants to: what
it holds is recorded, and what each change adds is gated. The invariant the floor holds: a finding
that no baseline line holds fails `check`, and a loosening fails `check --base` unless the commit
that makes it names the decision that allowed it. How: `outcomebound_tools/floor.py`,
which opens with what it decides, and `outcomebound floor --help`.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| One module with seven verbs: `propose`, `apply`, `check`, `baseline`, `ratchet`, `provision`, `remove` | a module per concern, with an acceptance ledger, a policy classifier and rendered configs | user | decided |
| Each tool runs from the project root with the project's own config | a config rendered per recipe, which shadows the project's own and can read PASS on what the project's config fails | agent | decided |
| A claim may name a `prefix`, the command its tool runs through (`["uv", "run"]`, `["docker", "compose", "run", "--rm", "app"]`); its argv still starts with its tool. The prefix's first word comes from PATH's absolute entries, as a tool does, and `min_version` is asked through the same prefix, so the version read is the one that runs. `provision` says to install a prefixed tool where its prefix runs. `floor --help` and the `python` and `node-typescript` fragments name this route, since agents that read none of them believed the floor runs host tools only | a host tool only, which leaves a project whose tools live in a container or a managed environment without a type claim; a free-form argv, which loses the version probe and the tool's name for UNVERIFIED | agent | decided |
| A baseline is a sorted plain-text multiset of `path:code`, the code the last field, with no message, no position and no count; a `path:code:message` line from an earlier floor reads as `path:code`, and `check` prints each new finding's message and place beside its key | hashed, count-bearing identities nobody can read and nothing tightens; `path:code:message`, which turns a baselined finding new when a tool rewords its message, and which put a tool's words, with the project's own names in them, into a file a project's content checks read | agent | decided |
| No tool run, version probe, Git read or `provision` install has a time limit unless its claim sets `timeout_seconds` (a positive number); a run past it reads `UNVERIFIED`, and changing it loosens nothing (maintainer, 2026-10-04) | a fixed 900 s per tool and 120 s per Git read, which no measurement backed and which fails a slow but healthy tool in a large repository | user | decided |
| `check` prints every finding a claim fails on (maintainer, 2026-10-04) | the first 20 and a count, which makes an agent run the floor again to see the next 20 | user | decided |
| A claim whose `files` match no tracked file reads `PASS` (`0 findings in 0 files`), at `apply` and at `check`, so nothing presses a run to drop it; dropping it is a loosening, as any drop is (maintainer, 2026-10-04) | `UNVERIFIED` until a person rules on dropping the claim, which holds a run that deletes the last script a claim reads; a drop exempt once no tracked file matches, which lets a rename out of the pattern drop every shell claim without a ruling | user | decided |
| Two modes, `gate` and `baseline` | an `observe` mode that reports and never fails | agent | decided |
| A claim whose tool is missing or older than its `min_version` reads `UNVERIFIED`, and `check` fails | an exact version pin, which turns a patch release into a skipped claim | agent | decided |
| Recipes for python and shell only; a project's own check joins as one more `exit` claim | recipes for stacks no adopter runs | user | decided |
| The secrets claim, `secrets`, is its own recipe, which `propose` offers to every project Git tracks a file in. Where Git tracks TypeScript, `propose` says on stderr why it proposes no type or lint claim (no recipe, and no parser that reads tsc's or ESLint's findings into a baseline) and prints `tsc --noEmit` and `eslint .` as `exit` claims through `npx --no` to add once the project passes them. A floor that holds `python.secrets` keeps it: the name changes nothing it does, and `apply` keeps the name of an installed claim that the proposal holds under another name, equal but for its name and mode, so applying a new proposal drops nothing | the secrets claim in the python stack, which leaves a project without Python with no secrets claim; TypeScript recipes, which the decision above leaves out | agent | decided |
| Where the project's mypy config names no `files`, the proposed types claim names each outermost folder whose `__init__.py` Git tracks, so mypy reads each module under one name. Where mypy stops (exit 2), the floor names the error with no code, the one that stopped it, with mypy's own hint; where that hint is mypy's module-mapping hint, it adds that `files` or `exclude` in the config, or folders after the claim's argv, decide what mypy reads. A tracked folder or Python file a types claim adds after the folders it already names loosens nothing: mypy reads more. Any other word added there loosens, since mypy reads a bare word its own way (`@flags.txt` is a file of options that can turn error codes off) | a bare `mypy .`, which maps a file in a folder without `__init__.py` to a top-level module and stops where two such folders hold files of one name; naming the first error, often an import mypy cannot find, which did not stop it | agent | decided |
| `shell.lint`: shellcheck 0.9.0 or later, `-f json1`, one run a script over the files the other shell claims cover, in baseline mode; `provision` prints its install command and never downloads it | no shell lint beyond syntax and injection | user | decided |
| This repository gates secrets: gitleaks is a pinned dev tool, installed by CI at a pinned version and checksum, and on each developer's machine | secrets left out of this repository's floor | user | decided |
| `apply` fits the floor to what the project holds: each claim runs once; one with findings records them in its baseline and becomes a baseline claim, except an `exit` claim, which stays a gate with its failure named; one whose tool runs but cannot read the project is left out, with why | a floor adopted strict, which fails a real project on hundreds of old findings before any change | user | decided |
| A claim whose tool is missing or too old at `apply` stays as proposed and reads `UNVERIFIED`; `apply` says to provision it and apply again | leaving it out, which drops the claim, a secrets claim as readily as any, with no trace in `floor.json` | agent | decided |
| `floor.json` records `adopted`: the commit, the day, and how many findings each baseline recorded, which `check` prints beside the claim; without `--base`, the secrets scan reads only the commits after that commit | a scan of the whole tree on every run, which fails on each old secret forever; counts read back from Git history, which a shallow clone lacks | user | decided |
| Without `--base` and without an adoption record, the secrets scan reads only the files Git tracks: gitleaks runs in a scratch directory that holds them (linked, or copied where a link cannot cross file systems) and the root's `.gitleaks.toml` and `.gitleaksignore`, tracked or not; a path that is a symlink, or that a symlinked folder leads outside the root, is left out (maintainer, 2026-10-04) | `gitleaks dir` over the root, which reads ignored folders (environments, local secrets, nested repositories) and then drops what it found there | user | decided |
| Where the merge base holds no `floor.json`, no commit from it to the adoption commit touches `floor.json`, and the adoption commit descends from it in HEAD's history, `check --base` starts both the secrets range and the loosening range at the adoption commit, so commits from before the floor existed never fail it; the secrets claim then also scans the files Git tracks, as without a base, so a secret committed before the adoption and still in the tree fails it (maintainer, 2026-10-04) | the merge base always, which fails a long branch on what it did before it adopted the floor; the adoption commit whenever it is later, which lets a record added to a floor the merge base already holds, or a floor removed and adopted again at the removing commit, hide a loosening committed before it, and lets a secret in the tree pass | user | decided |
| A secret is never recorded: `apply` lists the ones the tracked files hold, once, to rotate or to allowlist by fingerprint in `.gitleaksignore` | a secrets baseline, which leaves a committed secret quietly valid | user | decided |
| `apply --strict` fits nothing, adds no adoption record and keeps one already there, and says what each claim fails on now | one mode for every project | user | decided |
| A loosening, as listed below, fails `check --base` unless each commit between the merge base and HEAD that makes it, in its own diff, carries `Floor-Loosening: <what>; ruled <id>`, the id one word naming the decision in the project's own terms: an issue or pull request (`#123`), a decision record, or a link. The line covers the loosenings of its own commit, and no other commit's. Each loosening is counted (a suppression comment, a baseline line, a claim, a line of a tool config), and it passes where each commit whose own diff makes it carries the line and those commits make all of it; what no commit's own diff makes passes under no line. A merge makes what it loosens against every parent, its own edit, so the merge commit carries the line for it. A loosening a commit made at a path a later commit renames counts at its path at HEAD. `<what>` stays free text, so a line written before this rule reads as it did and covers its own commit. A line that starts `Floor-Loosening:` and does not parse is named as such, and rules nothing | CODEOWNERS, which binds nothing without branch protection; a ledger the agent itself writes; one line anywhere in the range for every loosening in it, which lets one ruling pass a later loosening that no ruling named; `<what>` matched against the change, which free text cannot carry and which earlier lines do not follow; coverage by file, and a ruled commit that only touches the file covering what no single commit makes, which lets a ruling given for one change pass a merge's own edit and a loosening made before a rename | agent | decided |
| The `outcomebound adopt <root>` that `apply` and `remove` print names the root with `outcomebound_tools/paths.py`'s `shell_path` (forward slashes, quoted as PowerShell and Git Bash read a word), as the finish check's printed commands do | `shlex.quote`, whose POSIX form of a quote inside a word is no word to PowerShell | agent | decided |
| `apply` and `remove`, where OutcomeBound is installed (`.outcomebound/manifest.json`), print `outcomebound adopt <root>` as the next step when they install or remove `floor.json`: the project facts name a floor loosening as an irreversible edge only while a floor is installed, so `adopt --check` reads them stale until adopt runs again | `adopt --check` alone, which a person reads only once the install is already stale | agent | decided |
| Where ruff or mypy cannot write its cache in the tree (a sandbox that keeps the tree read-only, or a cache folder another user made), its cache goes to a scratch folder for the verb's run, through `RUFF_CACHE_DIR` or `MYPY_CACHE_DIR`, unless the environment already names one. The floor tries its cache folder where it is there, else the root, once a run; a claim with a prefix gets no variable, since a prefix such as `docker compose run` does not pass it on | caches in the tree only, which ruff and mypy cannot open there, so their claims read `UNVERIFIED`; caches always in a scratch folder, which makes every run start cold; a write to the root before every tool run | agent | decided |
| Every program the floor starts, and every claim of a validation plan, comes from PATH's absolute entries and never from the folder it runs in (`outcomebound_tools/programs.py`, through `validation._execute`, so the floor's Git reads, version probes and tool runs are covered together): an empty, `.` or relative entry names no program. On POSIX the lookup is `shutil.which`'s. On Windows it tries each `PATHEXT` extension in each entry, since `CreateProcess` adds only `.exe` (`npm` finds `npm.cmd`), and it never reads the current folder, and reads `System32` only where PATH lists it. A first word with a folder in it (`./check`) is the caller's own path and stays as given. A program not found raises `FileNotFoundError`, which reads as `UNVERIFIED` for a tool and as "git could not run" for a Git read. A plan that found a tool through a relative PATH entry now reads `UNVERIFIED`, "executable not found", and names no tool it ran | the operating system's search, which on Windows reads the current folder and `System32` before PATH and on POSIX reads a relative entry from the folder the tool runs in, where a target can put a `git` or a tool of its own; `shutil.which` alone, which on Python before 3.12 reads the current folder first on Windows | agent | decided |
| On Windows the lookup skips two stubs: `bash` or `sh` in `System32`, `SysWOW64`, `Sysnative` or `WindowsApps` is the launcher of the Windows Subsystem for Linux, which exits 1 with "no installed distributions" where none is installed and which the floor would read as a syntax failure of every script (the Windows CI log shows the stub started); `python` or `python3` in `WindowsApps` is a Store alias, which opens the Store and runs no Python (`UNVERIFIED` by a run). `bash` not found on PATH is then Git for Windows' `bash.exe`, beside the `git` PATH holds. Where only a stub is found, the claim reads `UNVERIFIED`, naming the stub and that it is no use. Elsewhere a `bash` that is not on PATH (an Alpine image with busybox `sh` and no `bash`) reads `UNVERIFIED`, `bash is not on PATH`, and `check` fails, as for any missing tool | taking the first `bash` on PATH, which on a machine with System32 first runs the stub; `sh -n` where there is no `bash`, which another shell reads differently (`<(...)` is a syntax error in dash), so a bash script would fail or pass wrongly | agent | decided |
| A claim or `provision` that names `python3` finds, where `python3` is not on PATH and the machine is Windows, `python` (python.org and uv install `python.exe` and no `python3.exe`), else the `py` launcher run as `py -3`; the argv `provision` prints is the argv it runs. The floor starts no Python of its own: its tools are the project's, and `sys.executable` is the engine's, which an installed engine keeps to itself (pip is not in it, and ruff and mypy installed there would not be the project's). `adopt --detect` proposes `python -m pytest`, not `python3 -m pytest`, on Windows | `sys.executable` for `provision`, which installs the project's tools into the engine's environment; `python3` only, which no normal Windows Python has | agent | decided |
| A check that runs past its `timeout_seconds` ends the command and everything it started, on every platform: the command leads its own process group (a new session on POSIX, `CREATE_NEW_PROCESS_GROUP` on Windows) and the group is killed (`killpg`, or `taskkill /T /F` on Windows). On Windows a descendant used to keep the output pipe open for the ten seconds the verb then waited. `UNVERIFIED` until the Windows job runs it: that `taskkill /T /F` ends a real tree | killing the direct child only, which a grandchild outlives | agent | decided |
| The floor asks whether a folder can be written by writing in it (a temporary file), never by reading its mode bits, so under root in a container it reads what a write does: root writes a folder whose mode forbids it, so the cache fallback is not used there and is not needed, and a read-only mount or a folder another user owns refuses root as it refuses anyone. A test that needs a mode to forbid a write skips as `UNVERIFIED` where the user can write the folder. A repository a container's user does not own is refused by Git itself (`dubious ownership`), and the floor shows Git's message and does not set `safe.directory` | `os.access`, which is true for root on every folder and says nothing of a read-only mount; the floor marking a directory safe, which edits the user's Git configuration past the floor's own files | agent | decided |
| The verdict is the working tree's, not the change's: a file another person or agent left in a shared worktree, tracked or not, that a tool reads and finds new findings in fails the claim, and the finding names its path. Reproduced: an untracked file with one long line beside a clean baseline reads `FAIL python.lint (1 new ...)` with `other.py:E501` named. The floor does not filter findings by path or by what the change touches; a person or agent that shares a worktree checks in a worktree of its own (the workspace fragment gives each task one checkout) | findings filtered to the paths the change touches, which hides a finding the change causes in another path (mypy reports a call's error in the caller's file) and has no change to read in an untracked file; judging `HEAD` in a scratch checkout, which says nothing of the tree a person is about to commit and runs the tools without the project's environment; stashing the others' files, which loses work (never a bare stash) | agent | decided |
| A formatter that splits one finding into two (a long line wrapped into two long lines) raises a baseline key's count from one to two, and `check` reads the second as new: `+1 a.py:E501 (of 2 found)`, each finding listed with its place. Reproduced with ruff's E501. The baseline stays a multiset with counts: a count that may rise without a ruling would let a second finding of a baselined code in a baselined file pass, which is how the floor stays a ratchet. The change that formats re-records the key (`floor baseline`), which is a baseline gaining a line and carries its `Floor-Loosening: <what>; ruled <id>`; or the tool is told to leave the line alone with its own setting, which loosens as any setting does | a key's count ignored once the key is baselined, which hides every added finding in a file that held one; matching findings by position or by message, which the baseline holds neither of by design and which a formatter moves | agent | decided |
| A project nested in another repository, or an archive extracted inside one, reads the tools' configuration the tools find from its root: ruff and mypy look in the root, then in the folders above it, so with no `ruff.toml` or `mypy.ini` of its own at the root the ancestor's applies. Reproduced: the same files held one finding as a stand-alone repository and two nested under a repository whose `ruff.toml` sets a short line length. This is the project's own configuration where the project sits in a larger tree (a monorepo whose root holds the shared settings), and the tool run from the project's root finds the same. A copy that must not read it holds a configuration file at its own root, even an empty `ruff.toml` and a `mypy.ini` holding `[mypy]`, each of which stops its tool's search there (observed with ruff 0.16.7 and mypy 2.3.1); the floor names no configuration, as the first decision says | isolating the tools (`ruff --isolated`, no mypy configuration) where the root holds none, which breaks the monorepo, whose shared settings are the project's rules, and needs per-tool knowledge of which files count (ruff 0.16.7 passes over a `pyproject.toml` with no `[tool.ruff]`, and takes the ancestor's `ruff.toml`); the floor choosing a configuration root, which renders or names a configuration, which the floor does not | agent | decided |
| Adding a claim with its first baseline, moving a claim from `baseline` to `gate`, and an adoption record where there was none loosen nothing | every `floor.json` change read as a loosening, so adding a gate would need a recorded decision; exempting every baseline where an adoption record appears, which lets a strict floor be baselined in one commit | user | decided |

## What loosens

`check --base <ref>` reads the change from the merge base with `<ref>` to HEAD, or from the
adoption commit where the floor was adopted after the merge base (Decisions). These loosen:

- a baseline that gains a line, but the first baseline of a claim `floor.json` adds in that range
  (one new at HEAD, not one the range drops and brings back), and a line whose path Git reports renamed (`git diff -M`) in that range, which nets against the
  line with the same code at the old path that the same baseline loses;
- a claim `floor.json` drops or changes, a move from `gate` to `baseline` included, but not a
  change to its `timeout_seconds`, and not a folder or Python file Git tracks that a types claim adds after the folders it
  names;
- an adoption record changed or removed;
- a line a tool config the floor runs under gains, loses or moves, `.gitleaksignore` included
  (`check --help` lists them), but not a blank line or the spaces at a line's end. In
  `pyproject.toml` that is a line in a `[tool.ruff…]` or `[tool.mypy…]` table, in the `[tool]`
  table, or before the first header, where a dotted key (`tool.ruff.lint.ignore = …`) sets a
  setting; a dotted key there for another tool reads as a change too;
- an added suppression comment for a tool the floor runs (`check --help` names each kind); in a
  document (`.md`, `.rst`, `.txt`), which only gitleaks reads, only gitleaks' allow comment counts.

So fitting a floor that is already committed, such as a strict one, loosens and needs its
`Floor-Loosening` line in the commit that fits it; before the floor's first commit lands, every
baseline is a first one.

## Adoption

Fitted, `floor.json` reads:

```json
"adopted": {
  "commit": "<the full commit apply ran at>",
  "on": "<the day apply ran>",
  "recorded": {
    "python.lint": 42
  }
}
```

`recorded` is never updated, since changing the record is a loosening; a claim recorded later
shows its count in its baseline file. A claim left out, or one whose tool was missing, gets its
findings by applying the same file again once it runs: a baseline that already holds lines, and
the adoption record, are kept. Rotation is the fix for a secret: an allowlist entry only records
that a person looked.

## Edges

The loosening check counts loosenings; it does not see which statement a suppression covers or
what a config line means. So: a suppression a ruled commit added and an unruled commit moves to
another line of the same file, or onto a file renamed over it, passes under the first ruling; a
config edit that changes no setting (a comment, a reorder, a list split across lines, spaces
inside a value or at a line's start) needs the line, as any changed line does; and a suppression
an unruled commit added, a later commit removed and a ruled commit added again still names the
unruled commit, which a squash or a line on each commit that added it resolves. A rename on a
parallel branch is attributed the same whatever order the branches merge in; a path HEAD still
holds is never read as renamed away.

The loosening check makes a loosening visible; it cannot prevent one, because the agent that
loosens can also edit the check. Prevention needs branch protection on the server, which the
floor does not set. `provision` is the floor's one networked step: it pip-installs ruff and mypy
into the `python3` on `PATH` (on Windows its `python`, else `py -3`), the project's environment, where `check` finds its tools, not into
the environment an installed engine keeps to itself. A tool that `PATH` already has at its
`min_version` or later is present: `provision` says so and installs nothing for it, so a system
Python that pip refuses is not asked.

The proposed types claim reads the packages it names; a Python file outside them (a script in a
folder without `__init__.py`) is read where the project's mypy config names it in `files`.

A prefixed claim runs its tool where the prefix puts it. The loosening check watches the prefix in
`floor.json` and the tool configs, not the image, lock file or environment the prefix runs, as it
does not watch which version of a host tool PATH finds. The tool reads the project's configs only
where the prefix runs it from the project root, as a container that mounts the root at its
working directory does; paths it reports outside the root stay as it reports them. A cache
variable the floor sets reaches a prefix that keeps the environment (`uv run`), not one that does
not (`docker compose run`).

Without `--base`, a fitted floor reads a secret once it is committed, not in the working tree. A
fingerprint names its line, so moving an allowlisted line needs its new fingerprint. Where the
adoption commit is not in HEAD's history (a shallow clone, a rewritten history), the secrets
claim reads `UNVERIFIED` unless `--base` is given.

What each verdict reads, and who writes it (`outcomebound_tools/floor.py`). A claim's verdict
reads the tracked tree, the project's tool configs and its baseline under `.outcomebound/floor/`,
all written by the change under check, and a tool from PATH's absolute entries, which the person
or the CI runner provides; or, through a `prefix`, a tool from wherever the prefix runs it, which
the lock file or image the checkout names can decide, and the loosening check watches neither. The loosening verdict reads the diff from the
merge base with `--base`, which the caller names, to HEAD, and the `Floor-Loosening` line of each
commit message, which the change's author writes: the engine checks that the line is on the
commit that makes the loosening, not that the decision it names exists, so a false line passes
and stays in the history for a reviewer. That is accepted: the check makes a loosening visible,
and branch protection prevents one. The adoption record in `floor.json` is the change's data
too: a record added where there was none moves a range's start only where the merge base holds no
`floor.json` (`_adopted_after`), and a record that changes or goes away is a loosening.

## Validation

`tests/test_floor.py`, run by the `floor` claim: that the project's own config, not another
file's, decides what a claim reads; the fit on scratch repositories with findings in each claim;
each loosening rule, with a rename, a dropped claim whose files are gone and a range that starts
at the adoption; a prefix through a stand-in container; no time limit unless a claim sets one;
a secrets scan without a base that reads only tracked files; a ruling that covers only its own
commit, with a merge's own edit, a rename and a claim dropped and brought back; a folder, a file
and an argument file the types claim adds; a ruff setting outside a `[tool.ruff]` header; a
parallel rename merged in either order; the proposal for a TypeScript project, over a floor with
`python.secrets`, and the packages the types claim names; the error that stopped mypy;
`provision` with tools already on `PATH`; the adopt step after `apply` and `remove`; and the
caches of a tree or a cache folder that cannot be written. A stand-in tool is a POSIX shell script (`tests/fake_tools.py`); on Windows a `.cmd` beside it runs the script with the POSIX shell the engine uses, so the lookup through `PATHEXT` finds it as it finds a tool npm or pip installed, and every file a test writes is LF text. A test of a folder's mode bits skips on Windows with its reason. A test that needs a
real ruff, mypy, gitleaks or shellcheck skips as `UNVERIFIED` where it is not installed. This
repository's own floor runs in `make check` and in CI. Observed by hand: in a tree its user
cannot write, ruff 0.16.7 stops with "Failed to initialize cache" and mypy 2.3.1 with an internal
error, and both pass once `RUFF_CACHE_DIR` and `MYPY_CACHE_DIR` name a scratch folder;
gitleaks 8.30.1 with `--redact` reads `.gitleaksignore` from the project root, and a fingerprint
without a commit, `path:rule:line`, allowlists its line in the directory scan and in every commit
scan; shellcheck 0.9.0, 0.10.0 and 0.11.0 print the same `json1` report over one script.
