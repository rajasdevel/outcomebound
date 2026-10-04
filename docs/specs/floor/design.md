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
it holds is recorded, and what each change adds is gated. How: `outcomebound_tools/floor.py`,
which opens with what it decides, and `outcomebound floor --help`.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| One module with seven verbs: `propose`, `apply`, `check`, `baseline`, `ratchet`, `provision`, `remove` | a module per concern, with an acceptance ledger, a policy classifier and rendered configs | user | decided |
| Each tool runs from the project root with the project's own config | a config rendered per recipe, which shadows the project's own and can read PASS on what the project's config fails | agent | decided |
| A claim may name a `prefix`, the command its tool runs through (`["uv", "run"]`, `["docker", "compose", "run", "--rm", "app"]`); its argv still starts with its tool. The prefix's first word comes from PATH's absolute entries, as a tool does, and `min_version` is asked through the same prefix, so the version read is the one that runs. `provision` says to install a prefixed tool where its prefix runs | a host tool only, which leaves a project whose tools live in a container or a managed environment without a type claim; a free-form argv, which loses the version probe and the tool's name for UNVERIFIED | agent | decided |
| A baseline is a sorted plain-text multiset of `path:code`, the code the last field, with no message, no position and no count; a `path:code:message` line from an earlier floor reads as `path:code`, and `check` prints each new finding's message and place beside its key | hashed, count-bearing identities nobody can read and nothing tightens; `path:code:message`, which turns a baselined finding new when a tool rewords its message, and which put a tool's words, with the project's own names in them, into a file a project's content checks read | agent | decided |
| No tool run, version probe, Git read or `provision` install has a time limit unless its claim sets `timeout_seconds` (a positive number); a run past it reads `UNVERIFIED`, and changing it loosens nothing (maintainer, 2026-10-04) | a fixed 900 s per tool and 120 s per Git read, which no measurement backed and which failed a slow but healthy tool in a large repository | user | decided |
| `check` prints every finding a claim fails on (maintainer, 2026-10-04) | the first 20 and a count, which made an agent rerun the floor to see the next 20 | user | decided |
| A claim whose `files` match no tracked file reads `PASS` (`0 findings in 0 files`), at `apply` and at `check`, so nothing presses a run to drop it; dropping it is a loosening, as any drop is (maintainer, 2026-10-04) | `UNVERIFIED` until a person rules on dropping the claim, which held a run that deleted the last script on a person's decision; a drop exempt once no tracked file matches, which let a rename out of the pattern drop every shell claim without a ruling | user | decided |
| Two modes, `gate` and `baseline` | an `observe` mode that reports and never fails | agent | decided |
| A claim whose tool is missing or older than its `min_version` reads `UNVERIFIED`, and `check` fails | an exact version pin, which turns a patch release into a skipped claim | agent | decided |
| Recipes for python and shell only; a project's own check joins as one more `exit` claim | recipes for stacks no adopter runs | user | decided |
| The secrets claim, `secrets`, is its own recipe, which `propose` offers to every project Git tracks a file in. Where Git tracks TypeScript, `propose` says on stderr why it proposes no type or lint claim (no recipe, and no parser that reads tsc's or ESLint's findings into a baseline) and prints `tsc --noEmit` and `eslint .` as `exit` claims through `npx --no` to add once the project passes them. A floor that holds `python.secrets` keeps it: the name changes nothing it does, and `apply` keeps the name of an installed claim that the proposal holds under another name, equal but for its name and mode, so applying a new proposal drops nothing | the secrets claim in the python stack, which left a project without Python with no secrets claim; TypeScript recipes, which the decision above leaves out | agent | decided |
| Where the project's mypy config names no `files`, the proposed types claim names each outermost folder whose `__init__.py` Git tracks, so mypy reads each module under one name. Where mypy stops (exit 2), the floor names the error with no code, the one that stopped it, with mypy's own hint; where that hint is mypy's module-mapping hint, it adds that `files` or `exclude` in the config, or folders after the claim's argv, decide what mypy reads. A folder a types claim adds after the folders it already names loosens nothing: mypy reads more | a bare `mypy .`, which maps a file in a folder without `__init__.py` to a top-level module and stops where two such folders hold files of one name; naming the first error, often an import mypy cannot find, which did not stop it | agent | decided |
| `shell.lint`: shellcheck 0.9.0 or later, `-f json1`, one run a script over the files the other shell claims cover, in baseline mode; `provision` prints its install command and never downloads it | no shell lint beyond syntax and injection | user | decided |
| This repository gates secrets: gitleaks is a pinned dev tool, installed by CI at a pinned version and checksum, and on each developer's machine | secrets left out of this repository's floor | user | decided |
| `apply` fits the floor to what the project holds: each claim runs once; one with findings records them in its baseline and becomes a baseline claim, except an `exit` claim, which stays a gate with its failure named; one whose tool runs but cannot read the project is left out, with why | a floor adopted strict, which fails a real project on hundreds of old findings before any change | user | decided |
| A claim whose tool is missing or too old at `apply` stays as proposed and reads `UNVERIFIED`; `apply` says to provision it and apply again | leaving it out, which drops the claim, a secrets claim as readily as any, with no trace in `floor.json` | agent | decided |
| `floor.json` records `adopted`: the commit, the day, and how many findings each baseline recorded, which `check` prints beside the claim; without `--base`, the secrets scan reads only the commits after that commit | a scan of the whole tree on every run, which fails on each old secret forever; counts read back from Git history, which a shallow clone lacks | user | decided |
| Without `--base` and without an adoption record, the secrets scan reads only the files Git tracks: gitleaks runs in a scratch directory that holds them (linked, or copied where a link cannot cross file systems) and the root's `.gitleaks.toml` and `.gitleaksignore`, tracked or not; a path that is a symlink, or that a symlinked folder leads outside the root, is left out (maintainer, 2026-10-04) | `gitleaks dir` over the root, which reads ignored folders (environments, local secrets, nested repositories) and then drops what it found there | user | decided |
| Where the merge base holds no `floor.json`, no commit from it to the adoption commit touches `floor.json`, and the adoption commit descends from it in HEAD's history, `check --base` starts both the secrets range and the loosening range at the adoption commit, so commits from before the floor existed never fail it; the secrets claim then also scans the files Git tracks, as without a base, so a secret committed before the adoption and still in the tree fails it (maintainer, 2026-10-04) | the merge base always, which failed a long branch on what it did before it adopted the floor; the adoption commit whenever it is later, which lets a record added to a floor the merge base already holds, or a floor removed and adopted again at the removing commit, hide a loosening committed before it, and lets a secret in the tree pass | user | decided |
| A secret is never recorded: `apply` lists the ones the tracked files hold, once, to rotate or to allowlist by fingerprint in `.gitleaksignore` | a secrets baseline, which leaves a committed secret quietly valid | user | decided |
| `apply --strict` fits nothing, adds no adoption record and keeps one already there, and says what each claim fails on now | one mode for every project | user | decided |
| A loosening, as listed below, fails `check --base` unless each commit between the merge base and HEAD that makes it, in its own diff, carries `Floor-Loosening: <what>; ruled <id>`, the id one word naming the decision in the project's own terms: an issue or pull request (`#123`), a decision record, or a link. The line covers the loosenings of its own commit, and no other commit's. Each loosening is counted (a suppression comment, a baseline line, a claim, a line of a tool config), and it passes where each commit whose own diff makes it carries the line and those commits make all of it; what no commit's own diff makes passes under no line. A merge makes what it loosens against every parent, its own edit, so the merge commit carries the line for it. A loosening a commit made at a path a later commit renames counts at its path at HEAD. `<what>` stays free text, so a line written before this rule reads as it did and covers its own commit | CODEOWNERS, which binds nothing without branch protection; a ledger the agent itself writes; one line anywhere in the range for every loosening in it, which let one ruling pass a later loosening that no ruling named; `<what>` matched against the change, which free text cannot carry and which earlier lines do not follow; coverage by file, and a ruled commit that only touches the file covering what no single commit makes, which let a ruling given for one change pass a merge's own edit and a loosening made before a rename | agent | decided |
| `apply` and `remove`, where OutcomeBound is installed (`.outcomebound/manifest.json`), print `outcomebound adopt <root>` as the next step when they install or remove `floor.json`: the project facts name a floor loosening as an irreversible edge only while a floor is installed, so `adopt --check` reads them stale until adopt runs again | `adopt --check` alone, which a person reads only once the install is already stale | agent | decided |
| Where ruff or mypy cannot write its cache in the tree (a sandbox that keeps the tree read-only, or a cache folder another user made), its cache goes to a scratch folder for the verb's run, through `RUFF_CACHE_DIR` or `MYPY_CACHE_DIR`, unless the environment already names one. The floor tries its cache folder where it is there, else the root, once a run; a claim with a prefix gets no variable, since a prefix such as `docker compose run` does not pass it on | caches in the tree only, which ruff and mypy cannot open there, so their claims read `UNVERIFIED`; caches always in a scratch folder, which makes every run start cold; a write to the root before every tool run | agent | decided |
| Adding a claim with its first baseline, moving a claim from `baseline` to `gate`, and an adoption record where there was none loosen nothing | every `floor.json` change read as a loosening, so adding a gate would need a recorded decision; exempting every baseline where an adoption record appears, which lets a strict floor be baselined in one commit | user | decided |

## What loosens

`check --base <ref>` reads the change from the merge base with `<ref>` to HEAD, or from the
adoption commit where the floor was adopted after the merge base (Decisions). These loosen:

- a baseline that gains a line, but the first baseline of a claim `floor.json` adds in that range
  (one new at HEAD, not one the range drops and brings back), and a line whose path Git reports renamed (`git diff -M`) in that range, which nets against the
  line with the same code at the old path that the same baseline loses;
- a claim `floor.json` drops or changes, a move from `gate` to `baseline` included, but not a
  change to its `timeout_seconds`, and not a folder a types claim adds after the folders it names;
- an adoption record changed or removed;
- a line a tool config the floor runs under gains, loses or moves, `.gitleaksignore` included
  (`check --help` lists them), but not a blank line or the spaces at a line's end;
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

The loosening check makes a loosening visible; it cannot prevent one, because the agent that
loosens can also edit the check. Prevention needs branch protection on the server, which the
floor does not set. `provision` is the floor's one networked step: it pip-installs ruff and mypy
into the `python3` on `PATH`, the project's environment, where `check` finds its tools, not into
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

## Validation

`tests/test_floor.py`, run by the `floor` claim: that the project's own config, not another
file's, decides what a claim reads; the fit on scratch repositories with findings in each claim;
each loosening rule, with a rename, a dropped claim whose files are gone and a range that starts
at the adoption; a prefix through a stand-in container; no time limit unless a claim sets one;
a secrets scan without a base that reads only tracked files; a ruling that covers only its own
commit, with a merge's own edit, a rename and a claim dropped and brought back; a folder the types
claim adds; the proposal for a TypeScript project, over a floor with `python.secrets`, and the
packages the types claim names; the error that stopped mypy; `provision` with tools already on
`PATH`; the adopt step after `apply` and `remove`; and the caches of a tree or a cache folder that
cannot be written. A test that needs a
real ruff, mypy, gitleaks or shellcheck skips as `UNVERIFIED` where it is not installed. This
repository's own floor runs in `make check` and in CI. Observed by hand: in a tree its user
cannot write, ruff 0.16.7 stops with "Failed to initialize cache" and mypy 2.3.1 with an internal
error, and both pass once `RUFF_CACHE_DIR` and `MYPY_CACHE_DIR` name a scratch folder;
gitleaks 8.30.1 with `--redact` reads `.gitleaksignore` from the project root, and a fingerprint
without a commit, `path:rule:line`, allowlists its line in the directory scan and in every commit
scan; shellcheck 0.9.0, 0.10.0 and 0.11.0 print the same `json1` report over one script.
