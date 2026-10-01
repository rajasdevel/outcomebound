---
last_checked: 2026-09-13
volatility: STABLE (the audit's measurements and the floor's method, Q1–Q15, §1–§7, §9–§10) / VOLATILE (§8 pinning and provisioning, §11 tool reference)
sources:
  - https://docs.astral.sh/ruff/linter/
  - https://docs.astral.sh/ruff/formatter/
  - https://mypy.readthedocs.io/en/stable/config_file.html
  - https://mypy.readthedocs.io/en/stable/existing_code.html
  - https://typescript-eslint.io/users/configs/
  - https://eslint.org/docs/latest/use/suppressions
  - https://phpstan.org/user-guide/baseline
  - https://golangci-lint.run/docs/configuration/file/
  - https://github.com/gitleaks/gitleaks
  - https://google.github.io/osv-scanner/usage/scan-source
  - https://go.dev/ref/mod
  - https://docs.astral.sh/uv/concepts/tools/
  - https://docs.pytest.org/en/stable/reference/customize.html
  - https://git-scm.com/docs/githooks
  - https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
  - https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/
---

# Quality floors: format, lint, type, secret and shell checks as a gate

What format, lint, type, secret and shell checks catch when run as a gate that blocks new problems
without demanding a clean tree first, and how to build and fit one.

Re-check when a tool named in §8 or §11 ships a new major or minor version, or a floor is fitted to
a new stack. The tool documentation dated 2026-09-13 in Sources is the sweep `last_checked` names;
facts added later carry their own date (`read 2026-10-01`, or `[as-of]`).

This reference collects what is known about running format, lint, type, secret and shell checkers as
a floor that blocks new problems without demanding a clean tree first: what such a floor catches
and misses, how baselines work and what they cost, what strict typing measures on unannotated code,
why a floor should run the project's own tool configuration, how to detect a loosening, how to fit a
floor to a project that already has findings and secrets, and how individual tools behave when read
by a machine. It is for anyone adding such a gate to a project, building one for agents to work
under, or judging whether one earns its upkeep.

**Evidence classes.** (M) measured in the named repository; (L) tool documentation, or tool
behaviour observed on the named version; (P) practitioner consensus; (A) one observation; (O) an
observation recorded in one repository's own engine, reviews and adoption records. Most
measurements come from two places. "The audited floor" is a floor that ran for eleven days in the CI
of "the audited repository", a standard-library Python codebase of about 60,000 lines; both were
audited afterwards with ruff 0.16.7 and mypy 2.3.1. "One adopting repository" is an existing project
with its own linter settings, where a floor was fitted; a few observations marked "an adopting
repository" or "one adopting project" come from other projects a floor was fitted to. Bracketed
ids resolve in
[`_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl).

## Key findings

**Q1. A floor catches its rules' defect classes, cheaply; it does not catch state, drift or a model's
judgment.** In the audited repository no commit message records a behaviour defect the floor
caught; what worked was three claims taking about 11 s in CI: a format gate that keeps diffs clean,
and lint and type baselines that block new findings. State and drift, such as deployed state that
differs from the repository, are outside what source checks see; §1 names checks that reach some of
it. (M, A)

**Q2. Untuned rule sets are mostly noise.** In the audited repository 49% of 1,078 lint findings were
two subprocess rules (ruff S603/S607), 467 of them in tests; the commits they caused added 238 `noqa`
suppression lines. Select rules by the defect class they catch: keep the `shell=True`
family (S602, S604, S605), drop S603/S607, fix the unused-import and redefinition residue. (M)

**Q3. Strict typing on unannotated code measures annotation completeness.** Of 5,161 mypy findings
under `strict`, 94% were three annotation rules (`no-untyped-def` 2,308, `no-untyped-call` 2,201,
`type-arg` 333) and 73% were in tests; non-strict with `check_untyped_defs` reported 265, and a sample
of the findings outside tests were idioms or false positives. `no-untyped-call` makes new code that
calls old code a new finding. Use basic mode with `check_untyped_defs`, and require annotations only
on the shipped package. (M)

**Q4. A baseline is keyed by path, rule and normalized message, counted as a multiset, and kept as
readable text.** Line numbers break identity on every insertion; absolute paths made it differ
between two checkouts (0 of 686 identities shared); a set lets a second identical finding through.
Baselines kept as 64-bit hashes could not be read by a person, were never tightened, and accumulated
1,784 stale lines out of 6,945. A sorted `path:rule:message` file tightens by deleting lines and
shows a loosening as added lines in a diff. (M, A)

**Q5. Run the project's own tool configuration; a floor that renders its own shadows it.** A floor
that rendered its own mypy config checked other files than the project's config named, and passed at
gate while the project's own mypy run reported the error (observed once); a rendered `mypy.ini`
written at the project's own path overwrites the project's file and is read back as the project's
targets; a rendered `ruff.toml` shadows a project's own settings and misses configs in parent
directories. (A)

**Q6. A loosening is visible only against the base, read from Git; preventing one needs the host.**
Compare the floor's files at the base ref with the candidate: a baseline that gained a line, a changed
tool config, a new suppression comment, a new allowlist entry, a removed or weakened check. Read the
old side from Git, never the working tree the diff could rewrite. A commit trailer can acknowledge a
loosening, but the same agent can edit the check; prevention needs server-side branch protection with
required review, and on a private repository on GitHub's free plan branch protection is not
available, so a `CODEOWNERS` line there guards nothing. (A, L) [as-of 2026-09-28]

**Q7. Fit an existing project by recording what is there and gating each change.** Record existing
findings at adoption, fail on new ones; never record a secret: rotate it or allowlist its
fingerprint, a change the loosening check reads. Scan for secrets only in commits since adoption,
and check that the adoption commit is an ancestor. On a scratch clone of one adopting repository the
first day read PASS on every claim fitted, with each secret-shaped finding listed once for triage and
the type claim left out because mypy stopped on a duplicate module name; a change adding findings
failed format and lint. (A)

**Q8. A run that analyzed nothing is not a pass.** Tools exit 0 with an empty report after reading
nothing (ruff excluding every file over 206 Python files; import-linter with zero contracts; a bats
loop over an empty list); several tool families exit non-zero for reasons unrelated to findings.
Key completion on something the tool printed, count the files measured, and read zero files, a
timeout, an unparsed report or an unexpected exit status as UNVERIFIED. (A, L)

**Q9. Require a minimum tool version, not an exact one, and keep a missing tool visible.** Exact pins
turned claims UNVERIFIED on patch drift (bash 5.2.21 on the CI runner against a 5.3 pin); patch-level
interpreter pins did the same on other machines. A tool missing at adoption must stay as an
UNVERIFIED claim, not disappear from the floor. (A)

**Q10. Parser fixtures must be captured from the real tool.** In one floor 61 of its 85 shipped
claims had hand-written parser fixtures (all 12 SQL, 12 of 13 PHP, 10 of 12
TypeScript); a home-grown shell parser misread `done < <(…)` and reported three false findings on
scripts `bash -n` accepts. Passing fixture comparisons establish consistency with the fixtures, not
correctness on the tool. (M, A)

**Q11. Line-count ceilings measure size, not defects, and invite splitting to fit.** Thirty files
sat over a 900-line ceiling while CI printed PASS; a module split to get under it grew back past it
fourteen minutes later unflagged; splits left 21- and 31-line modules. Function-size rules (ruff
C901, PLR0912/PLR0913/PLR0915) already bound what matters. (M)

**Q12. Observe-only and unprovisioned claims produce rows, not actions.** In the audited floor,
observe-mode claims produced one action in 11 days, undone 14 minutes later; claims whose tools were
never provisioned read UNVERIFIED in every report. Gate the few claims that catch something and drop
the rest. (M)

**Q13. A floor's own machinery can outweigh what it checks.** The audited floor, about 15,800 lines
with about 18,200 lines of tests, delivered three claims that took 11 s; a design of about
1,000–1,500 lines delivers the same. (M)

**Q14. Secret scanning leaks the secret unless every output is redacted.** Counts that print matching
lines, verbatim logs, parser notes and exception text can all carry it. Redact every string, key a
finding on the rule id rather than the message, and keep secrets out of committed policy. (A)

**Q15. Pinning a check's definition does not pin what it runs.** With the definition unchanged,
the script it invoked was edited from exit 1 to exit 0 and the run still read PASS. Pin and verify
every input the verdict depends on (script, checker module, configuration), before the run and
after every command. (O)

## 1. What a floor catches and misses (Q1, Q12)

**The audited floor, claim by claim** (from its CI floor report and a local run):

| Claim (mode) | What it caught | What it cost | Reading |
| --- | --- | --- | --- |
| `format` (gate), `ruff format --check` | no defect class; keeps diffs clean; 0 findings, 0.11 s | 4 format-only fix-up commits in 5 days, each fixed by one command | keep; run the formatter before committing |
| `lint` (baseline), ruff | 1,078 findings: S603/S607 531 (49%), 467 of them in tests; 249 auto-fixable (169 safe); 113 complexity; pyflakes residue (F811 25, F401 19, F841 6). It caught a complexity finding plus a subprocess finding in a test, and a complexity finding drove a real refactor. No behaviour bug recorded | 238 suppression comments for S603/S607; a second identical subprocess call in a file became a new finding; code shaped so a function would not grow | keep, retuned: about 378 findings after dropping S603/S607 and applying the 169 safe auto-fixes, 217 outside tests |
| `types` (baseline, strict), mypy | 5,161 findings, 94% annotation completeness, 73% in tests; four sampled findings outside tests were idioms or false positives | 6 commits added only annotations ("175 findings… all missing annotations"); CI had to install pytest beside mypy so mypy could resolve the suite's imports | keep, retuned: 265 findings in basic mode with `check_untyped_defs`, 98 outside tests |
| `module-lines` (observe, 900) | none: a size proxy | 30 files over the ceiling with CI printing PASS; splits and regrowth (Q11) | drop |
| `structure` (observe) | four real rot checks: tracked scratch state, dangling in-progress markers, documented scripts that must exist, entry points that must answer `--help`; run by hand, 1 of 4 failed (two fixture scripts exit 1 on `--help`) | none, because it never ran, so its failure was invisible | gate it (about 3 s) |
| `secrets` (gitleaks) | a real defect class | never ran: not provisioned in CI or locally | provision and gate at zero |
| `advisories` (osv-scanner), `unused-dependencies` (deptry), `lockfile-present` | nothing to catch in a standard-library-only runtime with no lockfile; the lockfile script reported `files=0` | permanent UNVERIFIED rows | drop here |
| `dead-code` (vulture) | 43 findings; of the 12 at 100% confidence, 11 were pytest fixture parameters used for their side effects and 1 an unused parameter; 31 at 60% | never ran in CI | run by hand at `--min-confidence 100` when cleaning up |
| `tests`, `coverage`, `mutation` (observe) | `tests` duplicated the project's own test command; coverage and mutation never ran | none | drop here |
| `shell.syntax` (`bash -n`) | parse errors in 31 scripts the suite already executes | UNVERIFIED in CI because the runner's bash 5.2.21 was not the pinned 5.3 | unpin, or drop |
| `shell.format` (shfmt) | — | UNVERIFIED everywhere; shfmt not installed | drop |
| `shell.function-lines` (60), `script-lines` (900) | function-lines' own parser misread `done < <(…)` and reported 3 false "unterminated" findings; all 31 shell files together were 1,931 lines | noise in every CI report | drop |
| `shell.injection` (`curl \| sh` and `eval` patterns) | the injection class; 0 findings in 31 files, 0.35 s | none | keep, gated while at zero |

A structure check that finds scripts by walking the filesystem (`rglob("*.py")`) executes what the
project does not own: scripts in a virtual environment, a build directory, or another checkout
nested in the tree and hidden from Git by `.git/info/exclude` (one such check ran a nested
worktree's copies with `--help`). Walk what Git tracks, `git ls-files -z`, and read an empty listing
(no repository, no Git, nothing tracked) as UNVERIFIED, never as a pass; without `-z`, Git quotes a
path holding a non-ASCII byte (`"bin/na\303\257ve.py"`), and a reader that does not unquote it skips
that script in silence (A, git 2.55.0) [as-of 2026-09-23].

Two ways a floor's own guidance can undo it (A). In one adopting project, an agent given a floor's
guidance with its list of tool commands ran the listed tools itself and reported every claim
UNVERIFIED: name the one command that runs the floor first, and say that the list is never a
substitute, since a tool run by hand establishes no floor verdict. And an observe-only plan listed
among required checks marked every run UNVERIFIED, and a generic CI script under `set -euo pipefail`
failed every run on its exit status: keep observe-only checks out of required checks, say in their
guidance that they gate nothing, and where CI runs one let only its UNVERIFIED exit through.

**What a floor does not establish.** That a model writes better code; anything about a tool run by
hand; that a lockfile or a declared schema validator is consistent or enforced rather than present;
deployed state; a rule nobody selected; anything the project's own branch protection does not cover.
Nor, per stack (A, the reasoning of an adversarial design review): that clippy, `cargo
check` or a dead-code lint covered any target, feature or build tag they were not run with; that
`#![forbid(unsafe_code)]` says anything about dependencies; that a PHP project's ORM migrations are
SQL files a migration linter can read; that sqlx's compile-time query check ran at all without its
recorded query cache or a database to check against; or that formatting and linting a notebook
establishes its execution order, clean outputs, data lineage or numerical reproducibility.
A report should keep apart: edited, formatted, lint-clean, type-clean, tests collected, tests passing,
covered on changed lines, committed.

**The failures that motivate checks.** Several projects carried a written "run everything in Docker,
never a host virtualenv" rule and also carried host virtualenvs; two documented agent incidents,
worktrees lost under a temporary directory and a session that edited sibling projects, were each
answered with a sentence of guidance; the one project with strict typing, a pinned linter, a
formatter, a type checker and structural tests was the one whose journal showed problems caught
rather than discovered (A). Checks that reach some state a source floor misses: render the same
artifact under two different `PYTHONHASHSEED` values in independent processes and compare bytes (two
renders with the same seed prove nothing); treat a skipped test as a finding, not a pass; measure
final identifiers in UTF-8 bytes against the target's limit (PostgreSQL allows 63 bytes, so a
60-character name can be 66 bytes). Drift against a deployed environment needs that environment's
credentials, which a repository floor should never hold.

**Guidance behind floors.** When documentation fails to hold a rule, promote it into code (custom
linters, structural tests) [deterministic-1] (L); write the lint's message to carry the fix
[deterministic-2] (L); map each written guideline to a lint rule so "lint green" is the definition of
done [deterministic-19] (A); never send a model to do a linter's job [practitioners-9] (P); enforce
style with linters and formatters rather than instruction text [other-labs-12] (P); treat
verification as a ladder, catching each class at the cheapest deterministic rung first
[practitioners-15] (P); rules that must always hold go into hooks or permissions, not prose
[anthropic-16] (L).

## 2. Rule selection and typing strictness (Q2, Q3)

- ruff: in a Python codebase that shells out, S603/S607 (subprocess with non-literal argv, program by
  relative name) produced 550 findings and E501 196 in one count; `[lint.per-file-ignores]` used as a
  baseline is file-scoped, so a new violation of a rule the file already ignores is suppressed too,
  and the gate protects new files, not new lines. `--add-noqa` inserts source comments; it does not
  create a baseline file. PLR0915 counts statements, not lines, so a 118-line function was not
  flagged. A configuration used as a Python floor: line length 100, target py310, select `E, F, W, I,
  UP, B, SIM, C4, PIE, RET, RUF, C901, PLR0912, PLR0913, PLR0915, PERF, S`, max complexity 10, max
  arguments 6, max branches 12, max statements 50, tests ignoring `S101, PLR0915, PLR0913`. (M, L)
- mypy under `--strict`, tried module by module on the audited repository's package: 1 of 43
  modules clean, 1,242 errors outside the checked boundary; a type gate over one clean module
  establishes almost nothing.
  Replacing the boundary with the whole tree plus a baseline gave 1,289 identities over 6,865
  findings. The debt could not gate; the formatter could. Recommended shape: basic mode plus
  `check_untyped_defs`, with `disallow_untyped_defs` for the shipped package only, then ratchet.
  `follow_imports = silent` for modules outside the checked set is narrower than taking on their
  strict findings, and is named debt. (M)
- Other stacks' type checks: PHPStan at `--level max` with strict rules is PHP's type check and runs
  as lint; TypeScript uses `tsc --noEmit` against a floor tsconfig extending the project's with strict
  flags; clippy runs with `-D warnings`; `go vet` is a heuristic analyzer, not a strict type mode.
  Weakening `strict`, `noImplicitAny` or `strictNullChecks` in a generated tsconfig is a loosening a
  byte comparison catches. (L)
- TypeScript in more detail (L, [typescript-eslint
  configs](https://typescript-eslint.io/users/configs/) and [typed
  linting](https://typescript-eslint.io/troubleshooting/typed-linting/), read 2026-10-01): the
  `strict` and `strict-type-checked` configurations are 'not considered "stable" under Semantic
  Versioning', so their rules can change outside a major release; the project service throws an
  error for a file its nearest tsconfig does not include unless the file is allowlisted in
  `allowDefaultProject`; type checking is switched off for a `files` match such as `**/*.js` with
  `disableTypeChecked`, since tsconfigs include JavaScript only with `allowJs` or `checkJs`; and
  `stylistic-type-checked` adds rules beside the strict set rather than replacing it, so leaving it
  out keeps style to the formatter. `tsc --noEmit` does not cover Vue or Svelte templates
  (`vue-tsc`, `svelte-check` do), framework-generated types or the production bundle. A floor
  tsconfig that extended the project's added `noEmit`, `strict`, `exactOptionalPropertyTypes`,
  `noFallthroughCasesInSwitch`, `noImplicitOverride`, `noImplicitReturns`,
  `noPropertyAccessFromIndexSignature`, `noUncheckedIndexedAccess` and `useUnknownInCatchVariables`,
  and its ESLint half of complexity was `complexity` 10, `max-depth` 4, `max-params` 6,
  `max-statements` 50 and `max-lines` 900; biome was kept only as a substitute formatter, having no
  counterpart to the typed rules (A, a configuration never run against the tools).
- Other analyzers (L, read 2026-10-01): Clippy's documentation says the `restriction` group "should,
  emphatically, not be enabled as a whole", so a floor names the lints it adopts; automated
  accessibility tests such as axe through Playwright "can detect some common accessibility
  problems", while "many accessibility problems can only be discovered through manual testing";
  ArchUnit checks dependency and layering rules someone wrote down, not whether that architecture is
  right; Staticcheck, Error Prone and Semgrep rules each check named bug patterns.

## 3. Baselines and finding identity (Q4)

**Identity.**

- Key a finding on rule, path relative to the component root, and a content anchor (the enclosing
  symbol or the normalized message); keep line and column only for display. A test that shifted every
  line by seven proved identities stable. Normalize paths (a leading `./` names the same file as none); ruff's
  JSON reports absolute filenames, so two checkouts of one tree at different paths shared 0 of 686
  identities and a baseline could not travel to CI.
- Normalization that worked: lower-case, collapse whitespace, strip `line 42`, `column 7`, `l.12`,
  `:12:4` and the leftover punctuation, keep other numbers (rule codes, lengths, counts). Hash the
  exact bytes: a helper that stripped trailing whitespace mapped three distinct findings to two ids.
- Anchor by tool type: formatters (prettier, php-cs-fixer, rustfmt, gofumpt, `go mod tidy -diff`) on
  the path, and prettier reports only the path, so it cannot run in baseline mode; dependency and
  advisory tools (osv-scanner, cargo-deny, govulncheck) on the package or module name with the version
  in the locator, so upgrading to a fixed release retires the finding; tests on the test name; secrets
  on the rule id; architecture tools on the edge or layer pair; unused-symbol tools on the symbol;
  squawk on the rule name, because its messages quote SQL.
- Some tools keep a native baseline: PHPStan writes one with `--generate-baseline`, and golangci-lint
  reports only issues new since a revision with `issues.new-from-rev` (L, [PHPStan
  baseline](https://phpstan.org/user-guide/baseline) and [golangci-lint configuration](https://golangci-lint.run/docs/configuration/file/),
  read 2026-10-01); ruff's `--add-noqa` writes suppression comments, not a baseline. ESLint,
  from 9.24.0, records existing violations in `eslint-suppressions.json` with `--suppress-all` or
  `--suppress-rule` and drops resolved ones with `--prune-suppressions`; vulture's
  `--make-whitelist` writes the current findings as a file later runs read, which serves as one.
  mypy, clippy and knip document none: mypy suppresses existing errors by module (`ignore_errors`)
  or by line (an inline ignore comment), clippy by lint level, and knip's command line has no baseline
  option (L, [ESLint bulk suppressions](https://eslint.org/docs/latest/use/suppressions),
  [vulture](https://github.com/jendrikseipp/vulture), [mypy, using mypy with an existing
  codebase](https://mypy.readthedocs.io/en/stable/existing_code.html), [Clippy
  configuration](https://doc.rust-lang.org/clippy/configuration.html), [knip
  CLI](https://knip.dev/reference/cli), read 2026-10-01). A floor that keys every tool on one
  identity scheme reads them all the same way; one built on native baselines inherits each tool's
  own idea of what is new.
- Count-bearing messages (ruff's `` `_main` is too complex (17 > 10) ``): drop the measurement from
  the anchor and store the count as a magnitude, `<id> <count>`, paired per identity, largest first;
  the same function made simpler passes and lowers the count; a higher count has grown. E501 and
  W505 keep the count in the anchor, because a line has no name to pair it with. If the anchor
  carries the number, any change to the function's complexity is a new identity and splitting the
  function is the only way to retire it. ruff's `PLR0912`, `PLR0913` and `PLR0915` messages name no
  function (`Too many branches (18 > 12)`, `Too many arguments in function definition (15 > 6)`,
  `Too many statements (88 > 50)`), so with the count taken out their anchors pair one file's
  occurrences by count alone; match counted rules by the whole code (`C901`, `PLR09` and two
  digits), so that `XC901` or `PLR09111` is not counted (L, ruff 0.16.7 output) [as-of 2026-09-23].
  Other stacks carry the count in the message too: ESLint `Method 'render' has a complexity of 14.
  Maximum allowed is 10.`, golangci-lint ``cyclomatic complexity 14 of func `handle` is high (>
  10)``, phpmd `The method render() has a Cyclomatic Complexity of 17.` (hand-written fixtures,
  UNVERIFIED on the tools).

**Counting.**

- A baseline is a multiset: one line per accepted occurrence, and a second identical finding beyond
  the accepted count is new. Two F841 findings (`x = 1` in `a()`, `x = 2` in `b()`) shared one
  normalized identity, and a set baseline holding it once passed both.
- Limits of message-keyed multisets: deleting one recorded finding and adding a same-key finding
  elsewhere in the file passes by count; a moved file reads as new findings plus stale ones (three
  new, three stale in a probe); a same-key finding added elsewhere in the same file fails, as it
  should.
- An aggregate count ceiling passes when one old error is deleted and one new one added, and a lower
  count can hide a more severe new defect; if a tool has no stable identity, call its ceiling an
  aggregate debt ceiling and say what it cannot see.
- An absent or unreadable baseline is not an empty one: in baseline mode it reads UNVERIFIED with a
  remedy, never "every existing finding is new". Key baselines by component and claim, or one
  component's baseline absorbs another's debt.

**Keeping it honest.**

- The ratchet only shrinks: it writes, per identity, the lesser of the recorded and the observed
  count and lowers ceilings to what was observed; never from a capped list (reports capped at 50
  findings per claim) or from a parser that reports no count. In one run 88 of 1,289 type identities
  retired.
- Establish a baseline only when its absence is the run's sole problem: tool identity verified, run
  completed, a supported exit status, a positive count of files measured, evidence saved.
- Adding an exclusion and then ratcheting launders reduced inspection into apparent improvement; tool,
  parser and config updates change counts without any code change.
- Agents working under a floor fix a new finding or suppress it inline with a reason; they never add a
  baseline line, and they may tighten freely.
- Write baselines claim by claim: one optional tool nobody had installed made an all-or-nothing
  ratchet refuse every baseline, on the audited repository and on an adopting one alike (O). Record
  a baseline for each claim that verified, list the rest by name, and provision tool by tool for the
  same reason.
- A sorted plain-text file of `path:rule:message` lines, without line or column, is readable, diffable
  and shrinks by deletion. Opaque hashed baselines in the audited floor were touched by 3 commits in
  11 days, none a tightening, and hid 98 real-looking type errors outside tests.

## 4. Tool configuration: run the project's own (Q5)

- Run each tool from the project root with the project's own configuration; ruff, mypy and gitleaks
  find theirs. A rendered configuration silently shadows the project's wherever the tool would read
  it (`.eslintrc*`, `pyproject.toml` `[tool.ruff]`, `setup.cfg` `[mypy]`, `package.json`
  `eslintConfig`). Shadowing can pass a gate the project's own configuration fails (Q5). A rendered
  `mypy.ini` written at the project's own path overwrites the project's file, and the next render
  reads the floor's copy back as the project's targets (`files = src` becomes `files = .`), losing
  the original. If a floor must add settings, it detects the native config, refuses without explicit
  consent per tool, never merges, and never reads its own file back as native.
- Where each tool looks: mypy reads the first of `mypy.ini`, `.mypy.ini`, `pyproject.toml`
  `[tool.mypy]` and `setup.cfg` `[mypy]`, and only one, walking up from the working directory to the
  repository root and then trying user-level files (L, [mypy configuration
  file](https://mypy.readthedocs.io/en/stable/config_file.html), read 2026-10-01); its targets are
  `files` and `packages` (a package name resolves through the module roots) and `mypy_path` adds
  roots. In mypy's source, `defaults.py` lists `CONFIG_NAMES` (`mypy.ini`, `.mypy.ini`) and
  `SHARED_CONFIG_NAMES` (`pyproject.toml`, `setup.cfg`), and `config_parser._find_config_file`
  returns the first that carries a mypy section, whether or not it names `files`; `mypy -v` logs the
  file it read on its `Config File:` line (L, mypy source read 2026-10-01). A floor that read
  `setup.cfg` before `pyproject.toml`, and skipped a first config that named no targets, passed its
  type check at gate over `legacy/` while mypy's own run checked `src/` and reported an error there
  (A, mypy 2.3.1) [as-of 2026-09-24]: take targets from the first config mypy itself reads, and let
  one that names none keep the component root rather than borrow another file's targets. A
  `pyproject.toml` whose only mypy content is `[[tool.mypy.overrides]]` tables is still mypy's
  config, since mypy passes over a shared file only when it has no `tool.mypy` key; a reader that
  matches `[name]` headers with a single-bracket pattern misreads `[[tool.mypy.overrides]]` and
  reports no config, and a rendered `mypy.ini` then hides the project's overrides: the project's own
  `mypy` passed while the floor's gate failed on the one module the override told mypy to skip. A
  `[[tool.mypy]]` array where mypy expects a table stops mypy with `TypeError: str object expected;
  got dict`, and `mypy --config-file=` with an empty value runs with no config, which shows what a
  config is hiding (A, mypy 2.3.1) [as-of 2026-09-25]. ruff reads `ruff.toml` and `pyproject.toml`
  `[tool.ruff]`; a dotted key (`tool.ruff.line-length = 88`) or an inline table declares the section
  as much as a table header. shellcheck reads a project's `.shellcheckrc`; a `shellcheckrc` without
  the dot is read only under `$XDG_CONFIG_HOME`. Search the component root and then each parent up
  to the repository root, nearest first, stopping at the first directory holding one of the tool's
  configs. When one component's root sits below another's, give each path to the nearest component
  only: otherwise the outer component also lints the nested root, where its `tests/**`
  per-file-ignore misses the nested tests, and a changed path under both roots runs both; exclude
  each nested root from the outer component's run (A, one adopting project's layout).
- Which test runner a project declares (L, read 2026-10-01; [pytest
  configuration](https://docs.pytest.org/en/stable/reference/customize.html), [GNU make makefile
  names](https://www.gnu.org/software/make/manual/html_node/Makefile-Names.html),
  [just](https://just.systems/man/en/quick-start.html), [tox
  configuration](https://tox.wiki/en/latest/reference/config.html)). pytest looks for `pytest.toml`,
  `.pytest.toml` (from 9.0), `pytest.ini`, `.pytest.ini`, `pyproject.toml` with `[tool.pytest]`
  (9.0) or `[tool.pytest.ini_options]`, `tox.ini` with `[pytest]` and `setup.cfg` with
  `[tool:pytest]`; by convention a `pytest` requirement or a `conftest.py` at the root or in
  `tests/` also declares it, while a plugin requirement such as `pytest-cov` alone declares nothing.
  tox reads `tox.ini`, `setup.cfg`, `pyproject.toml` under `tool.tox` (natively or through a
  `legacy_tox_ini` key) and `tox.toml`, its INI forms now deprecated. GNU make tries `GNUmakefile`,
  `makefile` and `Makefile` in that order, and `.PHONY: test` is not a `test` target. just finds
  `justfile` in any capitalisation, or `.justfile`, searching upward. `go test ./...` runs where
  `go.mod` is, not at a `go.work` root with no module, and a workspace member's lockfile sits in the
  nearest enclosing directory that holds one. A detector that offered `python3 -m unittest` to a
  project declaring pytest in `pyproject.toml`, with a `conftest.py` and a `make test` target,
  proposed a command the project does not run (A).
- mypy layout traps: a same-named module under two directories aborted mypy with `Duplicate module
  named …`, outside the JSON parser's statuses (excluding the duplicate tree fixed it;
  `explicit_package_bases` with `namespace_packages` makes them two modules); with `files = src` and
  explicit package bases but no `mypy_path = src`, `src/pkg/x.py` was read as both `src.pkg.x` and
  `pkg.x`. mypy's `exclude` is a regex, and an empty alternation matches everything, so render `(?!)`
  when nothing is excluded. `python3 -m mypy` needs mypy importable by that exact interpreter; a
  `uv tool install mypy` satisfies neither the check nor its version probe; an isolated `uvx mypy` can
  lack the project's dependencies and plugins.
- Exclusion syntax differs per tool: comma-joined globs for vulture and phpmd; regexes for deptry,
  mypy and deptrac; arrays for ruff, tsconfig, PHPStan `excludePaths` and php-cs-fixer;
  `**/<tree>/**` globs for ESLint `ignores`; regex lists for the gitleaks allowlist and golangci
  `exclusions.paths`; gitignore syntax for prettier's ignore file (and `--ignore-path` replaces
  prettier's defaults, so the project's own ignores must be named again); no flag at all for shfmt
  and gofumpt. Apply exclusion names to paths relative to the component root: matching absolute path
  parts made any component under a directory named `build`, `vendor` or `dist` measure zero files.
  gitignore matching must honour parents, `*`, `**` and `!` negations; exact-string matching
  produced false FAILs. Compared with `git check-ignore` over 46 rule shapes, a translation of `*`
  to one path segment and `**` to any depth at segment boundaries agreed with Git on 14 of 15
  designed cases; Git's `x/**` matches everything under `x` but not `x` itself, and a `**` away from
  a segment boundary matches within one segment only (A) [as-of 2026-09-23]. A matcher that leaves
  out `?`, `[...]`, negations or a slash-free rule's match at any depth should say so where it is
  used.
- Rendered configs should exclude the floor's own installed directory, or adopting a floor arrives as
  a lint diff. Install a tool's config only when a selected claim runs that tool.
- A tool binary tracked in the repository is code the change under review controls. A floor meant to
  hold against that change runs its tools from outside the checkout or from an environment built from
  locked dependencies, not from a directory the change can edit.

## 5. Detecting a loosening (Q6)

**What counts.** The worst grade wins (unclassified, then loosening, then tightening, then none):

| Change | Grade |
| --- | --- |
| A component removed, or its root narrowed | loosening |
| A tool version changed, or the same version with a different identity probe | loosening |
| A tool substituted for a claim | loosening |
| A claim removed; a mode moved toward observe; a selection entry removed | loosening |
| A threshold moved against its declared direction | loosening; unknown direction or a non-integer value is unclassified |
| An exemption added, or its reassess-by date extended | loosening |
| A baseline occurrence added | loosening |
| A tool config changed, or a suppression comment added (`noqa`, `type: ignore`, `shellcheck disable`), or a `.gitleaksignore` entry added | loosening |
| A policy file removed; the acceptance log rewritten or truncated | loosening |
| A plan path or a baseline's bound path changed; a parameter changed; any other policy file changed | unclassified, treated as loosening |
| A claim added; a mode moved toward gate; a baseline entry removed; an exemption narrowed | tightening |

**Ways a comparison lets a loosening through**, each observed in probes of one implementation (A):

- Comparing only part of the policy: pointing the check plan at a new plan that ran `/usr/bin/true`
  graded "tightening"; a fabricated identity probe (`python3 -c 'print("ruff 0.16.7")'`) passed as
  "none"; declaring a fast selection over an implicit default graded "tightening". Compare the whole
  effective policy: plan paths, baseline bindings, identity probes and effective selections.
- Reading the base's policy from the candidate's file list let the candidate drop its profile from
  the list and be compared against nothing; read the base's policy at its own path and compare the
  union of both lists. Identify the policy file by path, never by JSON shape: a weakened tsconfig
  carrying the profile's keys escaped comparison.
- Rendering only the candidate graded restoring a generated default (`max-complexity = 10`) over an
  accepted stricter value (`5`) as "none"; render both sides. A value several claims share (an
  exclusion list) must be classified as the combined effective value.
- A change whose displayed before and after were equal (one baseline identity swapped for another)
  was covered by an unrelated acceptance; the display must be injective (`["a,b"]` and `["a","b"]`
  joined with commas looked the same), and acceptances scoped by component.
- Chains of step acceptances (4 to 5, 5 to 6) can accept a squashed range (4 to 6); compare timestamps
  as instants (`…T23:00:00+05:00` is earlier than `…T20:00:00Z` the same day).
- Grading a configuration revision by its number made every revision move a loosening, including
  moves whose only change was a rendering at the same description. Grade a move by rendering the
  installed profile under
  the old and the new revision and comparing the effective policy; read the old revision from Git at
  the base or from a released tag, never from bytes the diff under review could have written; an
  unreadable old side caps the result at UNVERIFIED.
- A fresh adoption record laundered baseline growth: a floor recorded without an adoption record
  (strict mode writes empty baselines) could be refitted with new findings recorded and read "no
  loosening". Exempt from the loosening check only a claim whose baseline file was absent at the base,
  not one that was empty.
- Pinning a check's definition does not pin what it runs: with the definition unchanged, the script
  it invoked was edited from exit 1 to exit 0 and the run reported PASS under the trusted
  definition (O). Pin each declared input the outcome depends on (the script, an
  imported checker module, the checker's configuration) and verify those pins before the run and
  after every command; a claim that declares no inputs reports its trust as UNVERIFIED and never
  reaches a trusted PASS, and files found among its arguments are a diagnostic, never proof that
  the declaration is complete. A hook that refuses any staged change to its own configuration
  refuses the commit that installs it, leaving `--no-verify` as the only way through; let the
  caller supply an accepted pin for the staged file instead (O).

**Acknowledging a loosening.** A loosening passes when a commit in the range carries a trailer naming
what was loosened and who decided (`Floor-Loosening: <what>; ruled <decision id>`), and
`git log --grep '^Floor-Loosening:'` is the ledger. This makes a loosening visible; it cannot
prevent one, since the same agent can edit the check. An acceptance log inside the agent's writable
tree gives cooperative detection, not enforcement.

**Enforcement.** Prevention needs a gate the project controls that obtains the accepted policy
independently of the candidate: branch protection with required review over the policy paths, set
outside the repository. A `CODEOWNERS` line counts only when branch protection requires code-owner
review, and only after it is read back with no later matching rule below it (a later rule wins). On
a private repository on GitHub's free plan the branch-protection API answers 403 ("Upgrade to GitHub
Pro or make this repository public"), so there it guards nothing (L) [as-of 2026-09-28]. Each
`CODEOWNERS` line is one file pattern followed by its owners, so a line naming two paths reads the
second as an owner and protects only the first: write one pattern per line, and escape a space
inside a path (L, GitHub's "About code owners" and GitLab's Code Owners syntax, read 2026-10-01; not
tested against either service). A floor run only from a Git `pre-commit` hook is skipped by `git
commit --no-verify`, which bypasses the `pre-commit` and `commit-msg` hooks (L,
[githooks](https://git-scm.com/docs/githooks), read 2026-10-01): a hook shortens feedback, and only
a check the project controls outside the agent's reach, such as a required CI job, holds a boundary.

**The base ref in CI** (L, A):

- On a pull request compare against `origin/${{ github.base_ref }}` (GitHub) or
  `origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME` (GitLab), passed through `env:` and never interpolated
  into the shell.
- On a push compare against `github.event.before` or `$CI_COMMIT_BEFORE_SHA` when it is not the
  all-zero id of a new ref and `git rev-parse --verify --quiet` resolves it, else `HEAD~1`; a
  multi-commit push is one policy diff, not its tip against `HEAD~1`; a tag is a new ref, so its
  base is `HEAD~1`. Gate a push step on the default-branch ref, not only on the event, or it runs on
  feature branches where `HEAD~1` is not the base.
- Default clones are shallow on GitHub and GitLab, so the base does not resolve and the check reads
  UNVERIFIED on every pull request while looking wired; set `fetch-depth: 0` or `GIT_DEPTH: 0`, or
  fetch the target branch. An unset CI variable passed as an empty base produced a green run that
  compared nothing.
- On GitLab a job's `rules` decide which pipelines it joins: a job with none defaults to `except:
  merge_requests`, so it runs in branch pipelines, feature-branch pushes included, but not in
  merge request pipelines; a rule `if: $CI_PIPELINE_SOURCE == "merge_request_event"` is what makes a
  project run merge request pipelines at all, and mixing the two without `workflow:rules` runs
  duplicate pipelines (L, [GitLab merge request
  pipelines](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/), read 2026-10-01; A
  [as-of 2026-09-25]).
- Resolve the base with `git rev-parse --verify <ref>^{commit}` and then `git merge-base <ref>
  HEAD`. Only Git's own "does not exist in" and "exists on disk, but not in" messages can mean a
  file is absent at the ref; a damaged object, a missing pack or a permission error must refuse, not
  read as absent. The second message also answers for a path under a directory that is a symlink at
  the ref, so a reader that maps it to "absent" reads a policy file behind a link as no policy (git
  2.55.0) [as-of 2026-09-23]. Under a localized Git those messages change, so pin the locale for Git
  subprocesses. For a symlink, `git show <ref>:<path>` returns the link target as the blob, and for
  a directory `git show <ref>:<dir>` exits 0 and prints a tree listing (`tree <ref>:<dir>`, a blank
  line, the entries) as if it were the file's bytes. `<ref>:<path>` resolves from the repository's
  top whatever the working directory (`<ref>:./<path>` is relative to it), so a tool run from a
  subdirectory reads another file or none. To read a path safely, walk its prefixes with `git
  ls-tree -z <ref> -- <prefix>`, one prefix a call (given several paths, `ls-tree` lists a named
  directory's children rather than its own entry), with `--full-tree` when run below the top: each
  call prints one record, `<mode> <type> <object>`, a tab and the path, or nothing with exit 0 where
  the path is absent; mode `120000` is a symlink, `040000 tree` a directory, a `commit` entry a
  submodule, and `100644` or `100755 blob` a file (A, git 2.55.0) [as-of 2026-09-23]. In Python,
  `Path.is_symlink()` tests only the last component, so a glob match reached through a symlinked
  parent passes a leaf check; test every ancestor (A). `git rev-parse --show-toplevel` honours
  `GIT_DIR`, `GIT_WORK_TREE` and `core.worktree`: set to a sibling repository, they made Git name a
  top outside the target, and computing paths relative to it failed; require the top to be the
  target or one of its ancestors, and unset those variables for Git subprocesses (A)
  [as-of 2026-09-24].
  Expand changed paths with `git diff --name-only -z --no-ext-diff --no-textconv
  --ignore-submodules=all --no-renames <base>...HEAD`, read NUL-delimited, and strip
  `GIT_EXTERNAL_DIFF`, `GIT_OPTIONAL_LOCKS` and `GIT_PAGER` from the environment.
- The base's policy is read by its path from the repository root, so a floor installed for a
  directory below the top of the repository cannot be compared with its base unless its files are
  named from the root; install it at the root with that directory as a component, or run without a
  base comparison and say so.

## 6. Fitting an existing project, and secrets (Q7, Q14)

**Record at adoption, gate each change.** At adoption the floor records every existing finding per
claim and the adoption commit and date; afterwards a claim fails only on findings beyond its record.
Secrets are never recorded: each one found is listed once for triage, to be rotated or allowlisted by
its fingerprint in `.gitleaksignore`, and that file's change is itself a loosening. Without a base,
the secrets claim scans only commits since adoption; the adoption commit must be an ancestor
(`git merge-base --is-ancestor`), since after a rebase a range from it spans the rewritten history. A
shallow clone without the adoption commit reads UNVERIFIED ("fetch it, or pass --base"). A tool
missing when the floor is fitted leaves its claim UNVERIFIED until provisioned; dropping it silently
hides, for example, the only secrets check from CI and reviewers. When a tool cannot settle at
adoption (mypy stopping on a duplicate module name), the claim is left out with the file named.

An example of the output shape, on a scratch project with one finding per claim:

```text
$ floor apply . --accept
python.lint: 1 finding recorded; mode baseline
python.secrets: 1 finding in the files Git tracks, never recorded
  rotate each secret, or allowlist it: add its line below to .gitleaksignore,
  a change check --base reads as a loosening
  pkg/settings.py:aws-access-token:1
shell.lint: 2 findings recorded; mode baseline

$ floor check . --base <adoption commit>
PASS python.format (0 new, 1 baselined)
FAIL python.lint (1 new, 1 baselined)
  +1 pkg/style.py:F401:`sys` imported but unused  at 1:8
PASS python.secrets (0 findings)
PASS loosening (none in <adoption commit>..HEAD)
```

A check that writes evidence inside the project must ignore that directory, or every later status
shows it as untracked files (O, an adopting repository).

**Secret scanners.** gitleaks can scan a commit range (`gitleaks git --log-opts=<base>..HEAD
--redact`) or a directory (`gitleaks dir`; the older `detect` and `protect` commands, `detect
--no-git` among them, were deprecated in v8.19.0 and are hidden from `--help`; L, [gitleaks
README](https://github.com/gitleaks/gitleaks), read 2026-10-01). A directory scan is the wrong
gate for a change: it misses a secret added and removed within one push, reads untracked local
files such as `.env`, and inherits whatever the floor excludes; the commit-range scan with
gitleaks' own allowlist covers what the change committed (A, gitleaks 8.21.2 options)
[as-of 2026-09-28]. On gitleaks 8.30.1 a `.gitleaksignore` fingerprint of the form
`path:rule:line` (for example `cfg.py:generic-api-key:1`) allowlisted the finding in both modes. A
configuration with `[extend] useDefault = true` keeps the default rules; an `[allowlist] paths` entry
is a tree the scan does not read, never a secret it forgives. gitleaks and osv-scanner have no npm or
uv wrapper (`npx --yes gitleaks`: "could not determine executable to run"; `npx --yes osv-scanner`:
404). (L, A)

**Redaction.** A secret scanner's evidence can leak the secret through counts that print matching
lines, verbatim execution logs, parser notes and exception text quoting input. Redact every string a
security parser emits (messages become `<redacted>`, notes are replaced, exception text dropped); keep
security logs to the redacted findings list; keep the anchor, or identities change; never let the
message decide identity, since it can carry the secret. Fully redacted failure notes leave nothing to
diagnose from, and widening them risks leaking a prefix of scanned text. Take connection strings and
tokens from the operator's environment, never from committed policy (Atlas reads `ATLAS_URL` and
`ATLAS_TOKEN`). `npm audit` transmits the project's dependency inventory; `osv-scanner --offline`
against a recorded database snapshot does not, and a snapshot's identity, not only its date, should be
recorded. `shell=False` does not sandbox a tool's configuration, plugins or build scripts. (A, L)

## 7. Runs that establish nothing (Q8)

**Vacuous passes observed** (A, L):

- `ruff check --no-cache --isolated --exclude '*.py' --output-format json .` exits 0 with `[]` over a
  tree of 206 Python files; ruff's JSON is a bare list with no file count, so an empty list reads the
  same whether ruff read everything or nothing.
- import-linter with no contracts exits 0 with `Contracts: 0 kept, 0 broken.`
- A bats entry-point list that matched nothing rendered an empty loop that reported PASS.
- shellcheck on a nonexistent file prints an error, then `[]`, with a non-zero exit.
- knip JSON of the wrong shape (`{"Issues": []}`) read as clean unless the `issues` key is required.
- cargo's `{"reason":"build-finished","success":false}` with `error: failed to run custom build
  command` (exit 101) was read as clean; so was a cargo test binary's `ok` summary followed by `error:
  doctest failed`.
- A Go package that fails with no failing test (a `TestMain` or teardown failure); PHPStan's
  top-level `errors` string (`Internal error: …`); govulncheck findings without `fixed_version`; a
  coverage converter that wrote an empty LCOV and exited 0 on unreadable input; a SQL statement
  scanner whose masking order let an apostrophe in a comment hide the next `DROP TABLE`.
- `bash -n a.sh b.sh` parses only its first operand; `find … -exec bash -n {} ;` exits 0 whatever the
  scripts do, so the diagnostics text must become the finding.
- pytest writes JUnit to the `--junitxml` path and a human summary on stdout; parsing stdout as JUnit
  read a passing suite as UNVERIFIED. A skipped test inside an exit-0 JUnit report is a finding, not a
  pass.
- A script that reads `--help` as an ordinary argument: one checked a directory named `--help`,
  found no file, printed `OK` and exited 0; another opened `--help` as its input path and raised. A
  check that every entry point "answers `--help`" passes the first; give each script an argument
  parser that answers `-h` and `--help` itself.

**Wrong-direction failures observed:** diff-cover's trailing `Failure. Coverage is below 90%.` after
its JSON made a below-threshold run read UNVERIFIED instead of FAIL; making every uncovered file a
finding made a 90% threshold behave as 100%; exact-string gitignore matching produced false FAILs.

**Reading output safely.** Merging stderr into stdout puts deprecation warnings, resolver lines and
banners in front of a JSON document: read from the first line that opens one and keep the prefix as a
note; scan from line starts, since a brace inside a warning is not a document. Five tool families exit
non-zero for reasons unrelated to findings, so declare per parser which exit statuses mean the tool
completed and key completion on something it printed. Tolerance stops where it would turn a failure
into a clean tree: a prefix plus an empty report plus a non-zero exit is "not completed". Keep "no
document found" apart from "a document of the wrong shape". A declared output file that is absent or
unreadable is "not supplied", not a clean read; deptry writes no JSON file at all when it fails before
analysis. Analysis scripts should always print a final completion line (`… files=<n>`) and exit 0
whether or not they find anything, so one that died reads UNVERIFIED. Parsers should be pure (no
filesystem, clock or network), and an exception becomes "not completed" with only its type in the
note.

**Verdict precedence** that avoids a false PASS, first match wins: tool identity not established;
timed out, executable or input missing, or parser not completed; zero files measured; exit status
outside the parser's completion statuses; baseline absent — each UNVERIFIED; then gate (any finding
not exempt fails), baseline (any occurrence beyond the record fails) or observe (report only). A
measured-file count is the runner's estimate, not the tool's own selection: label it measured or
reported. An all-observe plan runs and reports UNVERIFIED with its observations, never PASS; CI can
tolerate that with ` || [ $? -eq 2 ]`. Keep what runs apart from what gates: running every claim on
every invocation ran monthly mutation checks each time, so periodic claims belong in their own plan.
Two recipes rendering the identical command keep one copy at the strongest mode and report the
dropped one; a selection naming a dropped claim is noted as running nothing.

## 8. Pinning and provisioning (Q9) (VOLATILE)

- A claim needs its tool present at or above a minimum version; a missing tool makes the claim
  UNVERIFIED, and a gating UNVERIFIED fails the check by name. Exact pins turn claims UNVERIFIED on
  patch drift; interpreters and shells pinned at major.minor and matched by prefix (`3.14` admits
  `3.14.7` and refuses `3.140.1`) avoid it. Match versions component-wise, not by substring.
  clippy and rustfmt carry version numbers distinct from cargo's; vulture and import-linter print
  two-component versions (`vulture 2.16`) that bare-semver readers cannot parse; goimports
  publishes no version at all.
- Probe the executable that will run, under the claim's exact path: with project-local directories
  (`.venv/bin`, `node_modules/.bin`, `vendor/bin`) first on the path, the probe found
  `.venv/bin/shfmt` while the claim ran another shfmt. A version probe never provisions, and
  discovery never runs programs found on a path the target controls.
- Offer a package script as a check candidate only by name from an allowlist (`test`, `test:*`,
  `lint`, `lint:*`, `typecheck`, `check`, `verify`, `format:check`): `dev`, `start`, `serve` and
  `watch` offered as tests hang when run, and a fixture's script named `test` ran a deployment, so
  a name is never evidence of what a command does. Label each candidate as an observed command
  with unverified effects, and run none until a person has read and confirmed its exact command
  (O).
- A passing local gate does not say how hosted CI obtains its tools: a reference workflow copied
  with its placeholder repository (`your-org/…`) left that unresolved while the local gate passed
  (A). Settle where CI gets each tool, at which pinned version, before wiring the line; a
  local run and a hosted run are separate evidence.
- Provisioning is a separate, consented, network-enabled step: print each command first, stop at the
  first failure, succeed only when a re-probe passes, and provision into the environment the checks
  run (`python3 -m pip` under the component's path, not a bare `pip` that installed elsewhere). `uvx
  --offline ruff@<v>` resolves only after a prior `uv tool install`, which lands in `~/.local/bin`,
  a path a project whose `.venv` carries its own ruff never runs; `uv add --dev ruff==<pin>` touches
  `pyproject.toml` and `uv.lock` instead. `uvx` and `npx --yes` both install into caches, and a
  direct version pin does not freeze a tool's own dependency tree. `go run <module>@<version>` (the
  module cache), `cargo install --root <dir>` and a downloaded `composer.phar` were the cache-only
  routes used to capture fixtures without a system install (A) [as-of 2026-09-14]; each fetches on
  first use, as `go tool` does for a tool tracked by the `tool` directive Go 1.24 added to `go.mod`
  (the directive: L, [Go 1.24 release notes](https://go.dev/doc/go1.24), read 2026-10-01), so each
  is a provisioning act and never a check-time path. ESLint with plugins, PHP tools and cargo
  subcommands need a real installation. An environment made by `uv tool install` held no pip
  (`python -m pip` failed with `No module named pip`), and only the tool's own command is linked
  onto `PATH`, so a tool that provisions with `sys.executable -m pip` fails there, and would install
  where checks never look if it worked (A, uv 0.11.6) [as-of 2026-10-01]; pipx's documentation says
  its pip backend lends each environment one shared pip through a `.pth` file, while its uv backend
  builds environments without pip (L, [how pipx
  works](https://pipx.pypa.io/latest/explanation/how-pipx-works.html), read 2026-10-01). Provision
  into the interpreter the project's checks run, found on `PATH`. `npm install --save-dev` puts
  tools under `node_modules/.bin`, which is not on the path. `shfmt-py==3.14.1` does not exist on
  PyPI; `shfmt-py==4.2.0` ships shfmt 3.14.1.
- Offline switches for a check environment: `CARGO_NET_OFFLINE=true`, `COMPOSER_DISABLE_NETWORK=1`,
  `GOFLAGS=-mod=readonly`, `GOPROXY=off`, `GOTOOLCHAIN=local`, `PIP_NO_INDEX=1`, `UV_OFFLINE=1`,
  `npm_config_offline=true`; and `GOWORK=off`, which keeps a Go check to its own module when a
  `go.work` workspace sits above it ("If `GOWORK` is set to `off`, the command will be in a
  single-module context"; L, [Go modules reference](https://go.dev/ref/mod), read 2026-10-01). Under
  `-mod=mod`, `go vet` and `go test` added a `go` line to `go.mod` and wrote `go.sum`; cargo without
  `--locked` created `Cargo.lock`. With the read-only switches nothing is written: under
  `-mod=readonly` a module missing `go.sum` entries makes `go vet`, `go test` and `go list -deps`
  exit 1 ("missing go.sum entry"), and `cargo check`, `clippy` and `test` with `--locked` and no
  `Cargo.lock` exit 101; with a current lock they leave it byte-identical (A, go 1.27.1, cargo
  1.98.1) [as-of 2026-09-25]. Read such a refusal as UNVERIFIED, not as a finding. With `GOFLAGS`
  unset, go acts as if `-mod=vendor` were given in a module whose `go.mod` says 1.14 or later and
  that has a `vendor` directory; golangci-lint loads packages through `go list` and is exposed the
  same way; `--frozen` is `--locked` plus `--offline` (L, the Go modules reference and Cargo's
  command documentation, read 2026-10-01). A `toolchain` line with `GOTOOLCHAIN=local` does not
  enforce exact equality. `FOO=` and an unset `FOO` behave differently in enough tools that a plan
  must say which it means. Declare network locations refused in check parameters: govulncheck
  against its network database printed 14,493 lines, and a `-db https://…` value sends a request
  from inside a check. No offline switch stops govulncheck: `GOPROXY=off` governs the go command's
  module downloads, while govulncheck v1.1.4 hands an `http` or `https` `-db` to Go's standard HTTP
  client and a `file` URL to a local reader, refusing other schemes (L, govulncheck v1.1.4 source,
  read 2026-10-01); it made a `HEAD /index/modules.json.gz` request to a local server with every
  offline marker set, and a govulncheck built from source reports `v0.0.0`, which a version gate
  refuses (A) [as-of 2026-09-25].
- A syntax check through `python -m compileall` needs `-f`: without it, compileall skips a source
  whose cached bytecode records the same modification time (the source compares a header of magic
  number, flags and timestamp), and a run without `-f` accepted stale bytecode (O [as-of
  2026-09-09]; L, [compileall](https://docs.python.org/3/library/compileall.html) and its source,
  read 2026-10-01). Exclude an intentionally invalid fixture with `-x <regex>` and a recorded reason
  rather than dropping the check. A pass establishes syntax for that interpreter only: not imports,
  tests or runtime behaviour.
- Keep volatile values (observation times, install timestamps, run directories) out of pinned policy;
  take "today" from the caller rather than reading a clock inside the library.

## 9. Parser fixtures (Q10)

- Capture every fixture (clean, findings, failure) from the pinned tool, recording the command and
  version; replace capture-directory absolute paths with component-relative ones and edit nothing
  else; keep a recipe "candidate" until every parser it names is captured. In one floor, fixtures
  were captured for ruff, mypy, vulture, deptry, import-linter, mutmut, shellcheck, shfmt, bash,
  bats, pytest, pytest-cov, rustfmt, clippy, cargo check, cargo test, gofumpt, go vet, go test and
  `go mod tidy -diff`; hand-written for gitleaks, osv-scanner, diff-cover, the generic JUnit and
  LCOV readers, golangci-lint, govulncheck, cargo-machete, cargo-deny and every TypeScript, PHP and
  SQL parser. At an earlier count, 8 of the 27 parsers of its five candidate stacks (Rust, Go,
  TypeScript, PHP and SQL) were captured; Q10 gives the later count by claim. Facts resting on
  hand-written fixtures are UNVERIFIED on the tool.
- 144 passing fixture comparisons established consistency with the fixtures, not native-tool
  correctness; qualifying a stack also needs a composed journey with injected defects, a
  baseline-gaming attempt, a missing-tool run, an upgrade and a reversal. Sample projects clean by
  construction never exercise a real finding; put findings fixtures in separate scratch projects.
- Mutation controls: a limit mutation must cross the fixture's value (63 to 64 did not bite on a
  66-byte identifier; 63 to 67 did); pair a bytes-versus-characters control; revert from a copy, since
  `git checkout <file>` drops uncommitted edits; a stale `__pycache__` with the same size and mtime
  second served the mutated module; a hand edit to generated JSON is lost at the next regeneration.
- Python traps in count checks: `bool` subclasses `int`, so `isinstance(True, int) and True > 0`
  admits `files: True`; a `$`-anchored regex with `re.match` admits a trailing newline, so use `\Z`.

## 10. What a floor costs (Q11–Q13)

- The audited floor: 25 modules and about 15,800 lines, about 18,200 test lines, 7,300 template
  lines, 5,900 spec lines and 45 fixture trees. What reached CI and mattered was three claims in
  about 11 s, roughly `ruff format --check`, `ruff check` and `mypy`, each with a baseline filter. A
  smaller design of about 1,000–1,500 lines (each claim as argv, output format and mode; a plain-text
  baseline; gate and baseline modes; a minimum-version check) delivers the same. (M)
- Adoption debt on the audited repository when the floor was installed (M): fitted by
  hand, `ruff format` would have rewritten 118 of 142 Python files, and 1,286 lint findings sat
  behind 117 `[lint.per-file-ignores]` lines covering 459 file-and-rule pairs, so the gate held
  new files, not new lines. Fitted through the engine, the format gate reported 116 files once the
  immutable trees were excluded (128 with them); the tree was reformatted once, in its own
  mechanical commit, and `ruff format --check` then gated 276 files. The first content-anchored
  baselines held 528 lint identities over 1,133 occurrences and 1,289 type identities over 6,865.
  An import-cycle check run once by hand found one real cycle between two core modules; it was
  never gated, so nothing kept it from returning. Lint and type counts elsewhere in this reference
  differ by date and configuration (1,286 by hand, 1,133 occurrences, 1,078 at the later audit;
  6,865 and then 6,945 type findings).
- Line ceilings (Q11): a module split to go under 900 lines regrew to 946 fourteen minutes later with
  nothing flagging it; the audited floor's own modules sat at 900, 899 and 889 lines. (M)
- The audited floor's `tests` claim duplicated the project's own test command, and the suite
  asserted the format claim a second time; running the whole test suite inside a quick check target
  is expensive, so tests, coverage and structure stay out of a fast selection. Record each claim's
  duration.
- Tests that only prove matrix coverage (that a table cell exists) can pass for commands that do not
  exist.

## 11. Tool reference (VOLATILE)

Check-only invocations with machine-readable output, as used in 2026-09 (versions are those observed;
"hand-written" marks behaviour taken from documentation rather than observed):

| Stack | Format | Lint | Types | Other |
| --- | --- | --- | --- | --- |
| Python | `ruff format --check --diff` | `ruff check --output-format json` (with `--exit-zero`, findings come from the JSON) | `python3 -m mypy --output json` | vulture (text, `path:line: message (N% confidence)`); deptry `--json-output <path>`; import-linter; `uv lock --check`; pytest `--junitxml`; pytest-cov LCOV plus diff-cover |
| TypeScript | `prettier --check` (paths only) | ESLint 9 flat config, `typescript-eslint` `strictTypeChecked` with `projectService`, `--format json` (hand-written) | `tsc --noEmit -p <floor tsconfig>` (hand-written) | knip `--reporter json`; dependency-cruiser; vitest JUnit and LCOV |
| PHP | `php-cs-fixer check --diff --format json` | PHPStan `analyse --level max` with strict rules, `--error-format json` | covered by PHPStan | phpmd JSON; deptrac; composer-unused; composer-require-checker; `composer validate --strict`; PHPUnit `--log-junit` (all hand-written) |
| Rust | `cargo fmt --check` | `cargo clippy --all-targets --message-format json -- -D warnings` | `cargo check --all-targets --message-format json` | cargo-deny (advisories, bans); cargo-machete; cargo-llvm-cov `--lcov`; `cargo metadata --locked` |
| Go | `gofumpt -l .` (lists paths, exits 0 either way) | golangci-lint v2 `run --output.json.path stdout` | `go vet -json ./...` (heuristic) | govulncheck `-json` against a recorded `-db`; `go test -json`; `go mod tidy -diff`; `go mod verify` |
| Shell | `shfmt -d` | `shellcheck -f json -S style <files>` | `bash -n` per file | an `eval` and pipe-to-shell pattern scan; bats `--formatter junit` |
| SQL | `sqlfluff lint` restricted to layout rules (sqlfluff has no format check) | `sqlfluff lint --format json` in the detected dialect | — | squawk `--reporter json` for PostgreSQL migrations; a destructive-statement scan for other dialects |
| Shared | — | — | — | gitleaks; osv-scanner `--offline`; diff-cover over LCOV or Cobertura; actionlint, hadolint, yamllint, codespell |

Per-tool facts beyond those above (L, A):

- **ruff 0.16.7** formats Python code blocks inside Markdown; it rewrote a spec's sketches into 73
  expanded lines, so documents whose exact bytes matter need excluding. `ruff format --check` exits
  2 when a file cannot be parsed, and its first output line still reads `unformatted: File would be
  reformatted`; the `error: Failed to parse <file>` line comes later, so on exit 2 report the first
  line that starts with `error` (A, ruff 0.16) [as-of 2026-09-29]. Its documentation gives 2 for an
  abnormal end "due to invalid configuration, invalid CLI options, or an internal error" and names
  no parse failure (L, [ruff formatter](https://docs.astral.sh/ruff/formatter/), read 2026-10-01).
- **vulture 2.16** prints records of the shape `path:line: message (N% confidence)` for more than
  unused names: `unreachable code after …` and `unsatisfiable … condition` too. One adopting
  repository's report carried `unsatisfiable 'ternary' condition`, which a reader expecting only
  `unused …` refused, failing the claim; `vulture .` walks a project's `.venv` unless `--exclude`
  names it (A) [as-of 2026-09-17].
- **osv-scanner 2.x**: the source scan is `osv-scanner scan source --offline --format json
  --output-file <path> .` (`--output` still works but is deprecated); it finds the lockfiles, SBOMs
  and Git directories in the target directory, and searches subdirectories only with `-r` or
  `--recursive`, so a scan of the root reads only the root's lockfiles (L, [osv-scanner
  usage](https://google.github.io/osv-scanner/usage/scan-source) and its flag source, read
  2026-10-01; never run here).
- **pytest** leaves no `__pycache__` or `.pytest_cache` with `PYTHONDONTWRITEBYTECODE=1` and `-p
  no:cacheprovider`; `pytest --version` identifies pytest, not the pytest-cov plugin; parsing JUnit
  with `xml.etree` resolves no external entity but does not stop an internal-entity expansion.
- **diff-cover**: `--format json:- -q` prints the JSON report on stdout; `--json-report <path>`
  writes a file; useful fields are `total_num_lines` and `total_percent_covered`. A diff-coverage
  percentage does not prove every changed executable file was in the report: deleting tests or
  changing inclusion shrinks the denominator, so record the resolved merge-base and the measured
  file set. A coverage claim with no resolvable base, or whose test run did not happen, is
  UNVERIFIED.
- **Coverage formats**: vitest, pytest-cov and cargo-llvm-cov write LCOV; PHPUnit writes Clover and
  `go test -coverprofile` its own format, so both need a converter; `gocov convert` emits gocov
  JSON, not LCOV; `go test -coverprofile=<dir>/cover.out` fails when `<dir>` does not exist; LCOV's
  file count is its `SF:` records.
- **cargo** writes non-JSON progress on stderr and reports one diagnostic once per compiled target
  (lib and lib test), so collapse duplicates; clippy exits 101 on a finding and on a missing manifest,
  so key completion on `{"reason":"build-finished"}`; on stable, `cargo test --message-format json`
  covers the build, not test outcomes, so read one `test result:` line per test binary; cargo-deny
  prints concatenated JSON values (`json.loads` fails with "extra data"), completing on its `summary`
  record.
- **Go**: golangci-lint caps how many issues it prints per linter and how many identical issues
  (`issues.max-issues-per-linter`, default 50; `issues.max-same-issues`, default 3; "Set to 0 to
  disable"), so a floor that baselines its findings sets both to 0, or a capped report reads as the
  whole (L, [golangci-lint configuration](https://golangci-lint.run/docs/configuration/file/), read
  2026-10-01). A v2 configuration used as a Go floor (A, never run clean):
  `version: "2"`; `linters.default: standard` (the default) plus `bodyclose`, `errorlint`, `funlen`
  (60 lines, 50 statements), `gocognit` (15), `gocyclo` (10), `gosec`, `nilerr`, `noctx`, `revive`
  and `unconvert`; and `formatters: gci, gofumpt` in place of goimports, the formatters having moved
  to their own section in v2; one run then serves complexity, dead code (`unused`) and security
  (`gosec`). golangci-lint prints a human summary after its JSON; golangci-lint 2.6.1 could not read
  go 1.27 export data, so every issue came out as `typecheck`; gofumpt skips `vendor`, `testdata`
  and `go.mod` ignore directives; `go mod tidy -diff` exits 0 or prints `diff <a> <b>` headers, and
  a non-zero exit with no header means it refused to run; depguard and Go's compiler-enforced
  `internal/` rule cover import direction.
- **Shell**: shellcheck expands no globs and runs no shell, so pass literal paths; it reports an
  unused variable (SC2034), and clean quoting diagnostics do not prove the absence of injection;
  shfmt skips only version-control directories and has no exclusion flag (run it through `find …
  -prune -o … -exec shfmt -d {} +`); `bash -n` cannot parse bats (`@test "x" { … }` fails with exit
  2); bats has no coverage reporter. Quote each shell entry (`shlex.quote`): a double-quoted
  `scripts/$(printf EXPANDED).sh` is executed. Running a script with `--help` to learn whether it is
  harmless is itself execution: run only the entry points the project declares, expanded to literal
  paths when the check is written and never globbed at run time, and never execute a library (no
  executable bit, or a `# library` marker in its first five lines). A rule set that demands `set
  -euo pipefail` or a working `--help` from every script rejects sourced libraries and non-CLI
  scripts. The shellcheck codes closest to injection are SC2086 (unquoted expansion), SC2046
  (unquoted command substitution) and SC2091 (executing a substitution's output) (A, L, a design
  review and the as-built recipe).
- **SQL**: sqlfluff `format` applies fixes and `fix --check` asks before applying, so neither is a
  check; sqlfluff honours only `.sqlfluffignore`. A statement scanner must mask `--`, `/* */`, `'…'`
  (with `''` escapes) and `$tag$…$tag$` in one left-to-right pass, preserving line numbers, must not
  mask `"…"` identifiers (which would hide `DROP TABLE "orders"`), and must split on `;` only after
  masking; a quoted `;` in an identifier (`ALTER TABLE "t;u" DROP COLUMN x;`) still splits wrongly.
  The presence of `$jsonSchema` in a MongoDB migration does not show the validator is installed or
  enforced. Atlas `migrate lint` needs a development database and, from v0.38, a paid plan and
  authentication.
- **Package managers**: `uv sync` and `npm ci` are not read-only (`npm ci` removes an existing
  `node_modules`); `npm ci --dry-run` is not a lock-consistency check; frozen resolution is weaker
  than a reproducible artifact. Lockfile to manager: `uv.lock` uv, `package-lock.json` npm,
  `composer.lock` Composer, `Cargo.lock` cargo, `go.sum` go. A `uv.lock` written in a project with
  no `[project]` table locks nothing: it declared `requires-python = ">=3.13"`, `uv lock --check`
  failed with "No `project` table found", and `uv sync` warned and built a bare 3.13 environment (A,
  uv 0.11.6 [as-of 2026-10-01]; uv's documentation, read the same day, names no behaviour for that
  case).
  `uv lock --check` is the lockfile counterpart of `--locked` for other commands (L).
- **Mutation testing** (periodic, never gated): mutmut (Python), Stryker (TypeScript), Infection
  (PHP), cargo-mutants (Rust), gremlins (Go); none for shell.
- **Not covered by the checks above**: a shell function no script calls (a wrong answer deletes
  code), and orphaned or wrongly layered data models, which need the project's own model graph and
  naming conventions.

## How to apply

1. Choose claims by defect class: format (gate), lint with a rule set tuned to real bug classes
   (baseline, then gate), types in basic mode with `check_untyped_defs` (baseline), secrets (gate at
   zero), shell syntax and injection (gate). Leave out line ceilings, observe-only claims and claims
   whose tools nobody will install (Q2, Q3, Q11, Q12).
2. Run each tool with the project's own configuration from the project root; if the project has none,
   add one as an ordinary project file (Q5).
3. Record existing findings at adoption in plain-text baselines keyed `path:rule:message`, counted
   as a multiset; triage secrets instead of recording them (Q4, Q7).
4. Gate each change against the base read from Git: new findings fail, and so does any loosening not
   acknowledged in a commit trailer; fetch full history in CI (Q6).
5. Treat a run that measured nothing, timed out, or exited unexpectedly as UNVERIFIED, and make a
   gating UNVERIFIED fail (Q8).
6. Require tools at a minimum version and keep a missing one visible as UNVERIFIED (Q9).
7. Capture every parser fixture from the real tool (Q10).
8. Protect the floor's files with required review on the host where the plan allows it; where it does
   not, say that the check is visible but not enforced (Q6).
9. Let agents fix or suppress inline with a reason, never grow a baseline, and tighten freely.
10. Pin and verify every input a check runs (script, checker module, configuration), not only its
    definition, and walk what Git tracks rather than the filesystem when a check executes scripts
    (Q15, §1).

## Limits and open questions

- The measurements come from one audited floor over 11 days and a few adopting repositories; no
  controlled comparison shows a floor changes defect rates or what agents write.
- Much tool behaviour for TypeScript, PHP, SQL, gitleaks, osv-scanner, diff-cover, golangci-lint and
  govulncheck rests on documentation and hand-written fixtures, and is UNVERIFIED on the tools.
- Whether commit-trailer acknowledgement changes behaviour, and how often agents try to loosen a
  floor, is unmeasured.

## Sources

Tool documentation cited (dated 2026-09-13 unless noted): [uv tools](https://docs.astral.sh/uv/concepts/tools/)
and [uv tool guide](https://docs.astral.sh/uv/guides/tools/); [npm exec](https://docs.npmjs.com/cli/npm-exec/),
[npm ci](https://docs.npmjs.com/cli/v11/commands/npm-ci/) and [npm audit](https://docs.npmjs.com/cli/v8/commands/npm-audit/);
[Go toolchains](https://go.dev/doc/toolchain) and [go vet](https://go.dev/cmd/vet/);
[Atlas migration lint](https://www.atlasgo.io/versioned/lint);
[SQLFluff CLI](https://docs.sqlfluff.com/en/latest/reference/cli.html);
[gofumpt source](https://raw.githubusercontent.com/mvdan/gofumpt/master/gofmt.go);
[gocov](https://github.com/axw/gocov); [Ruff linter](https://docs.astral.sh/ruff/linter/);
[typescript-eslint configs](https://typescript-eslint.io/users/configs/) and
[typed linting](https://typescript-eslint.io/troubleshooting/typed-linting/);
[PostgreSQL lexical structure](https://www.postgresql.org/docs/current/sql-syntax-lexical.html).
vulture, deptry, phpmd, prettier and gitleaks documentation was read without a recorded URL or date.
Tools observed: ruff 0.16.7, mypy 2.3.1, pytest 9.1.1, pytest-cov 7.1.0, vulture 2.16, deptry 0.25.1,
import-linter 2.15, mutmut 3.8.0, shellcheck 0.11.0, shfmt 3.14.1, bash 5.3.15, bats 1.11.1, gitleaks
8.30.1, rustfmt 1.9.0, clippy 0.1.98, cargo 1.98.1, go 1.27.1, gofumpt 0.9.1, git 2.55.0, uv 0.11.6.
Evidence records: [deterministic-1, deterministic-2, deterministic-19, practitioners-9, practitioners-15,
other-labs-12, anthropic-16] in `_evidence/2026-09-25.jsonl`. GitHub branch-protection API response
read 2026-09-28. Own records (September 2026): the audited floor's report, CI runs and git
history; its design reviews, execution ledger and adoption records; records of fitting a floor to
two adopting repositories; no tool was re-run for this reference.

Documentation and source read 2026-10-01 for the facts added that day: [mypy configuration
file](https://mypy.readthedocs.io/en/stable/config_file.html) and mypy's `defaults.py`,
`config_parser.py` and `build.py`; [pytest
configuration](https://docs.pytest.org/en/stable/reference/customize.html); [GNU make makefile
names](https://www.gnu.org/software/make/manual/html_node/Makefile-Names.html);
[just](https://just.systems/man/en/quick-start.html); [tox
configuration](https://tox.wiki/en/latest/reference/config.html);
[githooks](https://git-scm.com/docs/githooks) and
[git-commit](https://git-scm.com/docs/git-commit); [GitHub code
owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners);
[GitLab Code Owners syntax](https://docs.gitlab.com/user/project/codeowners/reference/) and
[advanced syntax](https://docs.gitlab.com/user/project/codeowners/advanced/); [GitLab merge request
pipelines](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/) and [job
rules](https://docs.gitlab.com/ci/jobs/job_rules/); [gitleaks](https://github.com/gitleaks/gitleaks);
[ruff formatter](https://docs.astral.sh/ruff/formatter/); [uv project
sync](https://docs.astral.sh/uv/concepts/projects/sync/); [how pipx
works](https://pipx.pypa.io/latest/explanation/how-pipx-works.html);
[compileall](https://docs.python.org/3/library/compileall.html); [osv-scanner source
scan](https://google.github.io/osv-scanner/usage/scan-source); [PHPStan
baseline](https://phpstan.org/user-guide/baseline); [ESLint bulk
suppressions](https://eslint.org/docs/latest/use/suppressions) and [the v9.24.0
announcement](https://eslint.org/blog/2025/04/introducing-bulk-suppressions/);
[vulture](https://github.com/jendrikseipp/vulture); [mypy with existing
code](https://mypy.readthedocs.io/en/stable/existing_code.html); [Clippy
configuration](https://doc.rust-lang.org/clippy/configuration.html); [knip
CLI](https://knip.dev/reference/cli); [golangci-lint
configuration](https://golangci-lint.run/docs/configuration/file/) and [v2 migration
guide](https://golangci-lint.run/docs/product/migration-guide/); [Go modules
reference](https://go.dev/ref/mod) and [Go 1.24 release notes](https://go.dev/doc/go1.24); govulncheck
v1.1.4 source (`internal/client`, `internal/scan`); [Cargo
check](https://doc.rust-lang.org/cargo/commands/cargo-check.html);
[Clippy](https://doc.rust-lang.org/clippy/); [Playwright accessibility
testing](https://playwright.dev/docs/accessibility-testing); [ArchUnit](https://www.archunit.org/);
[Staticcheck checks](https://staticcheck.dev/docs/checks/); [Error Prone](https://errorprone.info/);
[Semgrep rules](https://docs.semgrep.dev/writing-rules/overview); typescript-eslint, re-read.

Pinned from documentation in 2026-09 and not observed unless marked (L, not re-checked): prettier
3.6.2 (answered `--version` through npx), eslint 9.39.0, typescript 5.9.3, vitest 3.2.4, knip
5.64.2, dependency-cruiser 17.0.1; php-cs-fixer 3.90.0, phpstan 2.1.31, phpmd 2.15.0, phpunit
12.3.9, composer 2.8.12, composer-unused 0.9.4, composer-require-checker 4.16.1, deptrac 3.0.3;
cargo-deny 0.18.5, cargo-llvm-cov 0.6.22, cargo-machete 0.9.1; golangci-lint 2.6.1 and govulncheck
1.1.4 (both run); sqlfluff 3.4.2, squawk 2.24.0, atlas 0.38.0; osv-scanner 2.0.2; diff-cover 10.5.1
(run). Version commands that differ from `<tool> --version`: `gitleaks version`, `golangci-lint
version`, `atlas version`, `govulncheck -version`; cargo subcommands answer `cargo <sub>
--version`; import-linter's executable is `lint-imports` and dependency-cruiser's `depcruise`;
mutmut's version was read through `importlib.metadata`.
