---
name: floor
status: ratified
---

# Quality floor — design

## Outcome

A project blocks regressions in what catches defects — format, lint, types, secrets, shell
syntax, shell lint and shell injection — with its own tool configs and a baseline a person can
read, and a change that loosens the floor fails `check --base` unless a commit names the decision
that allowed it. A project that already has findings adopts the floor the day it wants to: what
it holds is recorded, and what each change adds is gated. How: `outcomebound_tools/floor.py`,
which opens with what it decides, and `outcomebound floor --help`.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| One module with seven verbs: `propose`, `apply`, `check`, `baseline`, `ratchet`, `provision`, `remove` | a module per concern, with an acceptance ledger, a policy classifier and rendered configs | user | decided |
| Each tool runs from the project root with the project's own config | a config rendered per recipe, which shadows the project's own and can read PASS on what the project's config fails | agent | decided |
| A baseline is a sorted plain-text multiset of `path:code:message`, with no position and no count | hashed, count-bearing identities nobody can read and nothing tightens | agent | decided |
| Two modes, `gate` and `baseline` | an `observe` mode that reports and never fails | agent | decided |
| A claim whose tool is missing or older than its `min_version` reads `UNVERIFIED`, and `check` fails | an exact version pin, which turns a patch release into a skipped claim | agent | decided |
| Recipes for python and shell only; a project's own check joins as one more `exit` claim | recipes for stacks no adopter runs | user | decided |
| `shell.lint`: shellcheck 0.9.0 or later, `-f json1`, one run a script over the files the other shell claims cover, in baseline mode; `provision` prints its install command and never downloads it | no shell lint beyond syntax and injection | user | decided |
| This repository gates secrets: gitleaks is a pinned dev tool, installed by CI at a pinned version and checksum, and on each developer's machine | secrets left out of this repository's floor | user | decided |
| `apply` fits the floor to what the project holds: each claim runs once; one with findings records them in its baseline and becomes a baseline claim, except an `exit` claim, which stays a gate with its failure named; one whose tool runs but cannot read the project is left out, with why | a floor adopted strict, which fails a real project on hundreds of old findings before any change | user | decided |
| A claim whose tool is missing or too old at `apply` stays as proposed and reads `UNVERIFIED`; `apply` says to provision it and apply again | leaving it out, which drops the claim, a secrets claim as readily as any, with no trace in `floor.json` | agent | decided |
| `floor.json` records `adopted`: the commit, the day, and how many findings each baseline recorded, which `check` prints beside the claim; without `--base`, the secrets scan reads only the commits after that commit | a scan of the whole tree on every run, which fails on each old secret forever; counts read back from Git history, which a shallow clone lacks | user | decided |
| A secret is never recorded: `apply` lists the ones the tracked files hold, once, to rotate or to allowlist by fingerprint in `.gitleaksignore` | a secrets baseline, which leaves a committed secret quietly valid | user | decided |
| `apply --strict` fits nothing, adds no adoption record and keeps one already there, and says what each claim fails on now | one mode for every project | user | decided |
| A loosening, as listed below, fails `check --base` unless a commit between the merge base and HEAD carries `Floor-Loosening: <what>; ruled <id>`, the id one word naming the decision in the project's own terms: an issue or pull request (`#123`), a decision record, or a link | CODEOWNERS, which binds nothing without branch protection; a ledger the agent itself writes | agent | decided |
| Adding a claim with its first baseline, moving a claim from `baseline` to `gate`, and an adoption record where there was none loosen nothing | every `floor.json` change read as a loosening, so adding a gate would need a recorded decision; exempting every baseline where an adoption record appears, which lets a strict floor be baselined in one commit | user | decided |

## What loosens

`check --base <ref>` reads the change from the merge base with `<ref>` to HEAD. These loosen:

- a baseline that gains a line, but the first baseline of a claim `floor.json` adds in that range;
- a claim `floor.json` drops or changes, a move from `gate` to `baseline` included;
- an adoption record changed or removed;
- a change to a tool config the floor runs under, `.gitleaksignore` included (`check --help` lists
  them);
- an added suppression comment for a tool the floor runs (`check --help` names each kind).

So fitting a floor that is already committed, such as a strict one, loosens and needs its
`Floor-Loosening` line; before the floor's first commit lands, every baseline is a first one.

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
floor does not set. `provision` is the one networked verb: it pip-installs ruff and mypy into the
`python3` on `PATH`, the project's environment, where `check` finds its tools, not into the
environment an installed engine keeps to itself.

Without `--base`, a fitted floor reads a secret once it is committed, not in the working tree. A
fingerprint names its line, so moving an allowlisted line needs its new fingerprint. Where the
adoption commit is not in HEAD's history (a shallow clone, a rewritten history), the secrets
claim reads `UNVERIFIED` unless `--base` is given.

## Validation

`tests/test_floor.py`, run by the `floor` claim: that the project's own config, not another
file's, decides what a claim reads; the fit on scratch repositories with findings in each claim;
and each loosening rule. A test that needs a real ruff, mypy, gitleaks or shellcheck skips as
`UNVERIFIED` where it is not installed. This repository's own floor runs in `make check` and in
CI. Observed by hand:
gitleaks 8.30.1 with `--redact` reads `.gitleaksignore` from the project root, and a fingerprint
without a commit, `path:rule:line`, allowlists its line in the directory scan and in every commit
scan; shellcheck 0.9.0, 0.10.0 and 0.11.0 print the same `json1` report over one script.
