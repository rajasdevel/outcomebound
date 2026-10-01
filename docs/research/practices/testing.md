---
last_checked: 2026-10-01
volatility: STABLE (the audit, the profiles and the studies are measurements) / VOLATILE (§4 tool defaults and versions)
sources:
  - https://docs.pytest.org/en/stable/how-to/tmp_path.html
  - https://github.com/pytest-dev/pytest/blob/main/src/_pytest/tmpdir.py
  - https://docs.python.org/3/library/tarfile.html
  - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
  - https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/
  - https://arxiv.org/abs/2605.21384
  - https://arxiv.org/abs/2606.28430
  - https://arxiv.org/abs/2605.07769
---

# Tests worth keeping

What makes a test worth keeping, and what goes wrong in a large suite that agents and people both
add to.

Re-check when pytest, Python or GitHub Actions changes a default named in §4, or the audited suite
is audited or profiled again.

This reference answers what makes a test worth keeping and what goes wrong in a large test suite
that agents and people both add to: the defects reviewers find in tests agents write, what an audit
of a suite of about 4,400 tests found, where the suite's time went, why some runs failed only in CI,
how long pytest keeps temporary directories, and the practices that follow. It is for anyone
writing, reviewing or pruning tests, or deciding what a suite should guard.

**Evidence classes.** (M) measured; (L) tool documentation, or tool behaviour observed on the named
version; (P) practitioner consensus or a published practice; (A) one observation; (O) an
observation or measurement recorded in one repository's own runs, reviews and records. "The audited
suite" is the suite of one standard-library Python repository: about 4,400 tests in 152 files and
99,000 lines, run on Python 3.10 to 3.14 in CI. It was classified test by test by eight
fresh-context reviewers, each finding of four kinds was then checked adversarially by two verifiers
told to default to "refuted", and the suite was profiled serially with a plugin that timed every
subprocess. "One ticket ledger" means tickets implemented by agents and reviewed by a fresh-context
reviewer in the same repository. That repository's records (September 2026) were re-read on
2026-10-01. Bracketed ids resolve in
[`_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl) or, for `sizing-` ids,
[`_evidence/2026-09-26.jsonl`](../_evidence/2026-09-26.jsonl).

## Key findings

**K1. A test is worth keeping when some change to the code it covers would make it fail.** The most
frequent defect reviewers found in agent-implemented tickets was a test that stays green with the
behaviour broken: on eight of nine reviewed tickets. (M, one ticket ledger)

**K2. In a suite made mostly of behaviour tests, weak tests cluster in a few patterns.** Of about
3,000 test functions classified, 2,486 exercised behaviour. Verified findings: 36 tests that cannot
fail (8 more partly), 21 tautologies (9 partly, 3 refuted), 6 that recompute the expected value the
way the code does (5 partly), and 76 duplicates (9 partly); 51 over-built tests and 18 incidental
wording pins were reported but not verified. (M)

**K3. The weak patterns repeat.** A differential test that became a tautology once the old
implementation delegated to the new one; an oracle computed by the code under test; a broader test
added beside a narrow one that was never removed; a guard that asserts a constant it defined itself;
a refusal test that checks only for a non-zero exit, which passes when the command refuses for
another reason; a name that promises more than the test exercises. (M)

**K4. Tests that pin prose guard documents, not behaviour.** 134 of about 3,000 functions asserted
shipped wording, concentrated in a few files (44 of 46 tests in one, 27 of 40 in another). They fail
only when a document is edited, which is itself a decision, so they produce clerical churn. The useful
half is structural: named paths resolve, commands and scripts exist, every flag a document attaches to
a command appears in that command's `--help`. (M)

**K5. Suite time goes to subprocesses and rebuilt setup, not to assertions.** 84% of 2,218 s of
serial test time ran inside 29,285 subprocesses; 37% went to git building fixture repositories and
sealed copies, and 31% to the project's own install scripts. Tests named in "over-built" findings
took 12% of the time; prose tests cost almost nothing. (M)

**K6. pytest keeps every test's temporary directories for three sessions by default.**
`tmp_path_retention_policy` defaults to `all` and `tmp_path_retention_count` to 3; a full run of a
suite that builds fixture repositories keeps several gigabytes per session. Setting the policy to
`failed` keeps only failed tests' directories. (L, M)

**K7. The CI-only failures traced to a cause came from the environment, not the code.** A subprocess
given a hand-built `env=` lost `LD_LIBRARY_PATH`, which the CI interpreter needed and the local one
did not; a test that asserted Python's own error wording failed only on the newest Python in the
matrix, which reworded it, while local runs used an older one; tests that resolved scripts against
the working directory, or passed the caller's environment through, ran against something other
than the code under test. No failure was traced to a cause specific to a middle Python version. (A)

**K8. A skipped test is not a passing one.** Tests gated on tools absent from both CI and local
environments skipped silently; `-rs` reports them but never fails them. Unless a job provisions
the tools and treats a skip as a failure, those tests protect nothing. (A)

**K9. Show once that a test can fail for its reason, by breaking the code.** Where the instruction to
record a failing run lived in a skill the implementer did not load, 73 of 75 tickets marked
"red-first" carried no recorded failing run. Breaking the code under test by hand, watching the named
assertion fail and restoring it settles whether a test can fail; a red that is an error, a typo or a
different assertion is not the red. (M, P)

**K10. A passing suite is not the outcome.** Agents passed projects' own tests 38% of the time with
none of 15 pull requests mergeable as they stood; reviewers would not merge about half of
test-passing benchmark pull requests; agents saturate a visible suite while a held-out one lags.
(M) In one repository, two reviews by a model of another family found 25 defects in a check engine
whose suite passed at about 2,200 and then 2,348 tests. (O)

## 1. What makes a test worth keeping (K1)

**The bar.** A kept test names a production change that would make it fail. If no change would, it
cannot fail: an assertion that recomputes the expected value the way the code does, an assertion on
what a test double was told to return, a value compared with itself. A kept test asserts through the
interface a caller uses, against an expected value the code did not produce (a known-good literal, a
worked example, the spec); one that pins call order on collaborators, private state or the exact
wording of a message that is not a contract fails on a refactor that changes nothing observable. It
gives the same verdict every run, alone and beside other tests, with time, ordering, shared state,
the network and randomness controlled; a retry hides the cause. A test for a bug reproduces the
reported input and symptom, not a neighbouring case, and fails before the fix. No new test is
warranted when an existing test already fails on the break, when the change is to generated files,
configuration or documentation that a build, render or lint catches, or when the risk sits at a
layer a unit test does not reach, where a runtime check is the test. (P)

**Test the route a caller takes** (A). A packaging test that imported the build backend and called
it directly passed with `backend-path` in `pyproject.toml` naming a directory that did not exist,
while `pip install` through the frontend raised `BackendUnavailable`: test an install route by
installing through the frontend a user runs (`pip install --no-index --no-deps <checkout>` stays
offline when the backend needs nothing). When code was moved into a module, a function placed after
`if __name__ == "__main__":` did not yet exist when the module ran as `python -m`, so every
subcommand failed with `NameError` while every direct-call test passed, and bootstrap lines moved
below the imports they were meant to enable did nothing: run each entry point the way a user does,
and keep the `__main__` guard as a module's last statement.

**Where these ideas come from.** Naming the production change that would fail a test, asserting on
real behaviour rather than on what a double returns, avoiding change detectors on constants, exact
wording or private structure, and a mutation check once a test file is done: superpowers 6.4.1,
`skills/test-driven-development/writing-good-tests.md` (MIT); a red that is an error, a typo or a
different assertion is not the red: the same skill's "Verify RED". The break-then-restore step is
mutation testing done by hand (DeMillo, Lipton and Sayward, "Hints on Test Data Selection", IEEE
Computer, 1978). Tautological and implementation-coupled tests, and expected values from a source the
code did not produce: Matt Pocock's skills 1.2.3, `skills/engineering/tdd` (MIT); earlier, James
Carr's "TDD Anti-Patterns" (2006, "the liar", "the mockery") and the Google Testing Blog's "Test
Behavior, Not Implementation" (2013) and "Change-Detector Tests Considered Harmful" (2015).
Deterministic, behavioural, structure-insensitive tests: Kent Beck, "Test Desiderata" (2019). Why a
retry hides a flaky test's cause: Luo, Hariri, Eloussi and Marinov, "An Empirical Analysis of Flaky
Tests", FSE 2014, and the Google Testing Blog, "Flaky Tests at Google and How We Mitigate Them"
(2016). A bug's test reproduces the reported symptom through a check that can go red before any fix:
Matt Pocock's `diagnosing-bugs` skill. A first-run pass is diagnosed, not forced red: a
reproduce-first prompt alone did not help agents and made one model worse, while framing "no change
needed" as a success raised correct abstention from 65.0% to 80.5% and from 60.5% to 88.5% on two
models [research-28] (M). Assert on observable behaviour rather than implementation details when
hardening an evaluation [evals-22] (M).

**What reviewers found in agent-written tests** (M, one ticket ledger): across nine tickets built by
a smaller model from compiled briefs and reviewed by a larger one, the most frequent finding was a
test that stays green with the behaviour broken, on every ticket but one; next came an edge-case row
with no test (four tickets). Other tickets' reviews named a test the brief itself asked for that
duplicated an existing one, and an assertion elsewhere in the same file that the change necessarily
broke. Rows that asserted source text passed where no sentence said the row must call the real
reader. In another run of the same ledger, at least 11 of 58 closing notes record a fresh
reviewer's mutation or reading showing a named test passing with the behaviour broken (an untested
rule, a list never pinned, a test a docstring alone satisfied, a static check that accepted any
expression), and 3 more a code defect the review found; closing notes report only what their
author found surprising, so these are lower bounds (M).

**A project that already fails.** Run the relevant tests before changing anything and note which
already fail and why; report new failures apart from those; leave a pre-existing failure as found
unless fixing it is the task: not skipped, not marked expected, not loosened until it passes. In one
repository, tests that failed identically before and after an install, because of local database
and worktree state, were recorded before the change, which kept the install's verdict clean. (P, A)

## 2. An audit of a large suite (K2–K4)

**Method.** Eight reviewers each took a group of test files and gave every test function one kind
(behaviour, wording pin, structure, a guard over the suite or repository, negative control), then
reported findings of six kinds: tautology, cannot fail, recomputes the expected value, duplicate,
over-built (a whole install, git history or subprocess where a direct call on a small input would
show the same thing), and incidental pin (wording no spec fixes). Each finding quoted at most six
lines of evidence. Two verifiers normalized the 242 findings and tried to refute every tautology,
cannot-fail and recompute finding by reading the code and probing (for example printing the length of
a collection a test iterates), defaulting to "refuted" when a claim could not be established;
duplicates were checked only for the named twin.

**Counts** (a parametrized function counted once):

| Kind | Functions |
| --- | --- |
| Behaviour | 2,486 |
| Structure (inventories, schemas, file presence, cross-file agreement) | 208 |
| Wording pin | 134 |
| Negative control (a check catches a planted defect) | 97 |
| Guard over the suite or repository | 77 |
| Total classified | about 3,000 |

| Finding | Confirmed | Partly | Refuted | Not verified |
| --- | --- | --- | --- | --- |
| Cannot fail | 36 | 8 | 0 | — |
| Tautology | 21 | 9 | 3 | — |
| Recomputes the expected value | 6 | 5 | 0 | — |
| Duplicate | 76 | 9 | 0 | — |
| Over-built | — | — | — | 51 |
| Incidental pin | — | — | — | 18 |

Time in tests named by findings: over-built 259 s (11.7% of the suite), duplicates 80 s (3.6%),
tautologies 32 s, cannot-fail 15 s, recompute 5 s, incidental pins 4 s.

**Patterns reviewers saw more than once** (M):

- Differential tests ("helper against incumbent") that became tautologies once the incumbent
  delegated to the helper; the refactor finished, but the oracle was never swapped for literal
  expectations.
- Oracles computed by the code's own functions (rendering, parsing, digesting) rather than literals,
  so a defect in the shared helper passes on both sides.
- A later, broader test added beside an earlier narrow one, and the narrow one never removed; when a
  later change added one assertion, a whole flow was re-run in a new test instead of extending the
  old one; a helper copied verbatim into three test files, with a different expected count in each.
- Guards over the repository that assert a constant the test itself defined, or re-assert what an
  earlier line fixed.
- Guards whose subjects are a hand-kept list: a structure test that named the modules it checked
  read 15 of 23 shipped modules, so 8 added later escaped its size, frozen-dataclass and
  public-seam checks, and one of them failed the seam check once named; a test of the paths skills
  name walked only the skills in its own inventory, so a skill the installer added would never be
  read. Compare such a list with what exists, a directory listing or the installer's own output,
  by equality (O).
- Refusal oracles that assert only "non-zero exit, nothing written", which pass on a refusal for
  another reason; `pytest.raises` without `match=`. In one CI run two refusal tests failed because
  the command refused for an unrelated reason (the checkout was not a verified source), which is
  exactly the case those oracles let through when both refusals exit non-zero.
- Prose pins that do not pin the claim their name states: generic tokens (`"ci"`, `PASS`), character
  distances (`< 200`), counts (`<= 30`, "seven") in place of the sentence.
- Names promising more than the test: "denied or date-mismatched record never passes" with no
  date-mismatch case; "satisfies only the named boundary" with only one boundary configured.
- "Two runs print the same bytes" checked in one interpreter, which cannot catch hash-seed ordering.
- Weak `nonempty` oracles for files whose exact bytes were already computed elsewhere.
- Journeys that ran the fixture project's own toolchain (`unittest`, `npm`, `go`) and asserted its
  results: that tests the fixture, not the code.

**Acting on findings.** Each finding gets one disposition: strengthened (the test now asserts the fact
its name states, against an expectation it does not compute through the code under test); merged
into a named survivor; deleted, with the test that already holds each fact named; deleted, where it
asserted nothing its name claims; pin kept, citing the spec or contract that fixes the words; pin
re-anchored on the fact its name states; or left, with the reason. A finding judged wrong on reading
is left, never "fixed" into a different test. A strengthened test is shown able to fail by one red
run: break the code or document under test by hand in the way the name says it guards against, see
the named assertion fail, restore. A strengthened test that fails on the unbroken code has found a
defect: restore the test and file the defect. A test cited by a requirements register survives and
the other's facts merge into it; a parametrized duplicate loses its parameter, not its function; a
strengthened refusal test asserts the refusal's identifying phrase. (P)

**What acting on them found** (M). In the audited suite, the 180 rows of the findings index and 2
rows added beforehand became 52 strengthened tests, 35 merges into a named survivor, 53 deletions
(14 of them naming the test that holds each fact), 14 pins re-anchored on the fact their name
states, 4 pins kept on the spec that fixes their words, and 24 left. Of those left, 12 did not hold
on a close reading although two verifiers had failed to refute them; in 8 a requirements register,
contract or design cites both tests; 2 were left by a decision made before the work; and in 2 the
strengthening failed on the unbroken code and exposed a real defect, so the test was left as it was
and the defect filed. Every strengthened test and re-anchored pin was shown red by a hand break, 79
recorded red runs in all: three re-anchoring findings covered several pins (five, five and two),
each broken separately, three tests were broken a second way for a second fact, and one merge's
survivor was shown red too.

**Prose pins that guard no behaviour.** A classification of the same suite marked these kinds for
deletion or shrinking: spec bookkeeping (section references, package ownership, cited test nodes);
coverage records held to a sentence splitter; structure tests whose own docstring said they "decide
nothing about behavior" (a line ceiling, frozen dataclasses, import style); `--help` output pinned to
sentences of an audit table; a frozen old reader run over new records; self-described pins on
shipped wording; a spec's prose held to current symbol names; a reference page restating a data
file; "every command is documented somewhere" checked by substring. A ban on a list of words (cost,
budget, cheap, minimal, efficiency) in always-loaded files guards a wording preference, not a
behaviour: no measurement in these references shows that those words change what a model does.
Removing the prose pins barely moved wall time (5:44 to about 5:25 under parallel execution): prose
tests cost almost nothing, and the time sat in install tests that launch scripts (two files took
349 s and 324 s serially). Risks of deleting them: checks elsewhere that run a deleted test file
break; a skill can name a flag or rule the code does not have once pins go, which one generic check
covers ("every `--flag` a shipped document attaches to a command appears in that command's
`--help`"); copies of data (a reference page mirroring a data file, a pasted block, an eval copy of
shipped text) drift unless rendered from or pointed at the source; the repository's own install and
CI configuration are caught later, when CI runs. (M)

## 3. Where suite time goes (K5)

**Serial profile** (4,424 tests, 2,218 s; setup 12%, call 88%, teardown under 1%):

| Category | Seconds | Share |
| --- | --- | --- |
| Git: building fixture repositories and sealed copies of the source | 829 | 37.4% |
| The project's own install and setup scripts, launched as subprocesses | 694 | 31.3% |
| Python inside the test process | 355 | 16.0% |
| The project's own commands run as subprocesses | 158 | 7.1% |
| Evaluation fixtures and fake tools | 157 | 7.1% |
| Project toolchains inside fixtures (`go`, `npm`, `unittest`) | 24 | 1.1% |

By command: one install script 549 s over 781 runs (0.70 s each); `git add` 206 s over 1,573; `git
cat-file` 150 s over 1,425; `git fetch` 116 s over 241; `git rev-parse` 111 s over 9,050 runs at
0.01 s each; `git config` 54 s over 4,579. About 240 sealed copies of the source were built at 1.9 s
each, 107 of them in one file. The slowest single tests were two end-to-end journeys (install, task,
check, update, reverse) at 47 s and 41 s; the slowest file spent 465 s, 88% of it in subprocesses.
Across nine serial runs (3,706 to 4,348 passing tests) the suite took 23 to 40 minutes; under
`pytest-xdist -n auto`, 5 minutes 44 seconds of wall time on a machine at load average 90, and 5
minutes 49 seconds and 7 minutes 22 seconds in two later runs (4,394 and 4,471 passing tests); CI
runs took 10 to 13 minutes per Python version. A 1,500-second timeout set for the suite was shorter
than one serial run on a loaded machine. Machine load moved serial time more than many changes do:
one commit's serial run took 2,378 s at a load average of 10 to 19 and 1,714 s at 8 to 6, on the
same machine the same night (+39%). (M)

**Growth.** While agents built packages, one suite grew from 798 tests in 60 s at an early
checkpoint, through 1,146 in 123 s and 1,395 in 192 s, to 1,615 in about 450 s, one machine, Python
3.13.13, pytest 9.1.1: the count roughly doubled while wall time rose about 7.5 times, consistent
with K5's finding that time goes to subprocesses and rebuilt setup rather than to assertions. (M)

**Why.** Reviewers' patterns: a sealed copy of the source (a full copy, `git init`, a commit and a
tag fetch; about 2 s on average, up to 9 s with an install) rebuilt per test where the test only
reads it, although a session-cached shared copy existed and its docstring said to use it for
read-only fixtures; a full install run as the fixture that obtains a manifest (about 1.3 s each)
rather than one install copied per test; the same fixture rebuilt for every parameter; command-line
subprocesses standing in for an in-process call when the command line was not the subject; eval
fixtures rebuilt for read-only checks. (M)

**What fixes it.** A test that only reads a shared starting state uses the shared one; a test that
starts from a built state (an installed target, a built fixture) gets a copy of one its module builds
once (`shutil.copytree(..., symlinks=True, dirs_exist_ok=True)`), one per xdist worker under `load`
distribution; a test whose subject is not the command line calls the function, and each file keeps one
subprocess test per command. Guard the shared state: a helper that re-seals any source that does not
verify would silently commit a test's writes into the shared copy, and every later test on that worker
would read the changed source, so re-sealing a shared copy must raise. A copied target must hold no
absolute path of the place it was built. Measure before and after on the same machine with nothing
else running, serially, and report the saving rather than gating on it; the counts of subprocesses,
install runs and fixture builds must fall for each row that moved. (P) Run base and candidate side
by side, or alternately, under the same load, and record the load average at start and end.

Applied to the audited suite across 40 test files, every assertion kept, building each starting
state once and copying it per test moved 41 of 45 flagged rows and cut serial test time from 1,708 s
to 1,371 s (−20%), setup-phase time from 250 s to 104 s, processes started from 28,949 to 26,369
(−9%), install-script runs from 761 to 554 (−27%), sealed-copy tag fetches from 239 to 103 (−57%)
and evaluation fixture builds from 137 to 67 (−51%); base and candidate ran serially side by side
on one machine, load average 7.6 at the start and 6.2 at the end, under a plugin that timed every
subprocess (M). A pytest plugin that compared each shared sealed copy with its recorded commit after
every test (`git status --porcelain --ignored=no` and `HEAD`) found 27 tests writing into a copy
they had been handed as read-only, 21 of them in one file; that file's own re-sealing helper would
have committed the writes for every later test on the worker to read (M).

**Delegates and the full suite.** Run the full suite once at landing, not inside every delegate:
delegates run the brief's named tests and the files they touch. Without the parallel plugin, one
verification ran serially for 26.5 minutes against 5.7 with it. The landing run catches what named
tests miss: in one ledger a template's new introduction quoted a section heading, and a test in
another file that located the section by the heading's first occurrence read the introduction and
failed, which the ticket's own tests did not run. (A)

## 4. Failures only in CI, and nondeterminism (K6–K8) (VOLATILE)

**Temporary directories.** pytest 9.1.1 defaults (read from its source): `tmp_path_retention_count =
3` sessions and `tmp_path_retention_policy = "all"`, with `failed` and `none` as the other values. A
full run of a suite that builds fixture repositories kept several gigabytes per session, three
sessions deep, and a self-hosted CI runner container that ran several jobs without emptying its
temporary directory grew to 28 GB of pytest temporary files. Remedies: `tmp_path_retention_policy =
failed` in `pytest.ini`, and a runner entrypoint that empties its temporary directory at each
start. Runner caches that outlive rebuilds (a tool cache of about 2 GB, pip and uv caches) keep
growing as new patch releases and package versions are selected: the tool cache gained about
400 MB for each new Python patch release a job selected. The defaults are unchanged in pytest's
current source and documentation (read 2026-10-01). (L, M)

**Environment differences** (A):

- Pass a subprocess the loader variables the interpreter needs: a hand-built `env=` must carry
  `LD_LIBRARY_PATH` when it is set, which a CI interpreter can need where a local one does not.
- Run the newest supported Python before landing, not only the local interpreter, and the oldest
  too: two changes went red only on Python 3.14 while local runs used 3.12, because a test
  asserted Python's own invalid-date message, which 3.14 reworded. In one repository's CI over one
  week (O), the 21 legs that failed at a step fell on every version (3.10: 3, 3.11: 3, 3.12: 7,
  3.13: 2, 3.14: 6), 17 of them in the test suite; legs that failed before reaching any step say
  nothing about versions and are left out. No failure was traced to a cause specific to a middle
  version, and a push matrix of 3.10 and 3.14 cost about 21 runner-minutes against 81 for all five
  at a tag. GitHub's matrix cancels the other legs once one fails unless `fail-fast` is set to
  `false` (it defaults to `true`; L, [workflow syntax, `jobs.<job_id>.strategy.fail-fast`](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
  read 2026-10-01), so the leg recorded as failing is often just the first to fail, not the only
  one that would have. The evidence supports the oldest and newest legs on each push and the full
  matrix before a release, not the full matrix before every landing.
- Do not assert an interpreter's or library's own error wording: assert the exception type, or a
  pattern that admits each supported version's wording.
- A feature can arrive in a patch release: `tarfile.extractall(filter=…)` exists from Python
  3.10.12, 3.11.4 and 3.12 (and 3.8.17 and 3.9.17), and on 3.10.11 it raises `TypeError` for the
  unexpected keyword; CI's setup step installs the newest patch, so only contributors on an older
  patch meet it (observed 2026-10-01). Python's documentation says to test for the feature with
  `hasattr(tarfile, 'data_filter')`, not the version; from 3.14 the filter defaults to `'data'`
  (L, [tarfile](https://docs.python.org/3/library/tarfile.html), read 2026-10-01).
- Build fixtures from a sealed copy, and pass a clean, explicit environment: tests that resolved
  scripts against the current directory, or passed the caller's tool-location variable through to a
  subprocess, ran against another checkout than the one under test, and a test that ran an install
  script from the working checkout failed on a dirty tree for reasons unrelated to its subject.
- Some tests refuse an uncommitted tree; commit before running them.
- Where a PEP 668 managed Python cannot import `pytest`, run the suite through
  `uv run --with pytest --with pytest-xdist==<pinned>`.
- A tool importable by neither `python3` nor `uv run --with pytest` runs only on a CI leg that
  installs it, so the tests that need it run nowhere else.
- A test that needs a directory outside any Git work tree must not assume `tmp_path` is one: with
  `--basetemp` inside a checkout, even in an ignored folder, Git finds the enclosing repository,
  so two "outside Git" tests stopped seeing the refusal they asserted, and a build that listed its
  files with `git ls-files` there produced a package without its code and exited 0. Skip with a
  reason when a parent of `tmp_path` holds `.git`, or create the directory with
  `tempfile.mkdtemp()`. CI's `$RUNNER_TEMP` lies outside the checkout, so these fail only locally.
- An oracle that compares captured output byte for byte depends on `TMPDIR` when that output holds
  absolute temporary paths: the same code gave one behaviour digest under an agent shell's
  `TMPDIR=/tmp` and another under macOS's per-user temporary directory. Record `TMPDIR` with every
  capture, or replace the root with a fixed token before hashing (O).
- Set the terminal a rendering test assumes: a test that inherited `TERM=dumb` from its runner got
  an 80-column width from its terminal library although it requested 18, and failed only in that
  environment (one adopting repository's suite).
- To show a step needs no network on macOS, run it under `sandbox-exec` with a profile that denies
  `network*`: the denial held for the process and for a child it started, through an install, an
  update and a reversal. Replacing Python's socket entry points covers only that interpreter.
  Other systems need their own mechanism, and the test skips there (O) [as-of 2026-09-09].

**Nondeterminism observed.** A test that snapshotted a fixture repository's tree, `.git` included,
failed with `FileNotFoundError` on `.git/objects/maintenance.lock`: git's background maintenance
created and removed the lock between the listing and the `stat`. Exclude `.git` from tree snapshots,
tolerate files that vanish, or disable automatic maintenance in fixture repositories (`gc.auto=0`,
`maintenance.auto=false`). No test was recorded as changing verdict between identical runs; the
sources hold no measurement of flakiness beyond these environmental causes. (A)

**Skips** (K8). Tool-gated recipe tests skipped unless the tool was on the path, and most of those
tools were provisioned neither in CI nor locally; 12 such cases skipped in one local run. With
`-rs` every skip reason is printed, so a skipped check reads as UNVERIFIED rather than as a pass, but
it still never fails. (A) A `-rs` set in `pytest.ini`'s `addopts` does not reach a command that
clears it: a CI line `python -m pytest -o addopts="" -q` drops every ini flag and needs its own
`-rs`, and `addopts = -q` alone left a local run printing one summary line with its skips unseen
(O, pytest 9.1.1) [as-of 2026-09-12]. To check that a document cites test nodes that exist, collect
once with `pytest --collect-only -q -o addopts=` and `PYTEST_ADDOPTS` cleared, and strip only
parametrization suffixes; a failed collection fails the check, and membership proves a node
exists, not what it tests (O).

## 5. Showing a test can fail (K9)

- In one ticket ledger the instruction to record a failing run first lived in a skill the
  implementer was not given, and an audit found no recorded red run on 73 of 75 completed tickets
  marked red-first. When an implementer wrote the fixes before the tests, red evidence was taken
  afterwards by reverting each fix under the finished test. (M, A)
- A fresh-context reviewer runs the named tests and at least one mutation control of its own in a
  scratch copy, leaves the working tree byte-identical after, and looks for a mutation the tests
  miss. (P) Show the tree unchanged by comparing file contents and modes, symlink targets, staged
  entries and the untracked files that existed before; equal `git status --porcelain` output
  before and after does not show it, since status prints the same line for two different contents
  of an already-modified file (O) [as-of 2026-09-09].
- Mutation-control traps (A): a limit mutation must cross the fixture's value (changing a 63-byte
  limit to 64 did not bite on a 66-byte identifier; 67 did); pair a bytes-against-characters control;
  revert from a copy, because `git checkout <file>` restores the last commit and drops uncommitted
  edits; a stale `__pycache__` with the same size and modification second served the mutated module;
  a hand edit to generated data is lost at the next regeneration.
- Red-run traps in a suite whose code guards its inputs (A): a hand break is often refused by an
  earlier guard, so the named assertion never runs and a narrower break that passes that guard is
  needed; a line guarding a filter the command can never reach cannot fail and is deleted, not
  strengthened; a refusal test can pass because an earlier step refuses (here `git fetch`, until
  the fixture gained the tag it lacked), never the check it names; and a test that installs from
  the checkout cannot be shown red by editing the distributed files, since the edit itself makes
  the source fail verification, so it needs a hand-written input.
- Python traps in assertions (A): `bool` subclasses `int`, so `isinstance(True, int) and True > 0`
  admits `True` as a count; a `$`-anchored regex with `re.match` admits a trailing newline, so use
  `\Z`; loading a script by path (`importlib.util.spec_from_file_location`, then `exec_module`)
  without first registering the module in `sys.modules` fails on a module that declares a
  dataclass with string annotations (`from __future__ import annotations`), because `dataclasses`
  resolves the class's module through `sys.modules` and raises `AttributeError: 'NoneType' object
  has no attribute '__dict__'`; register it first (in a test, `monkeypatch.setitem(sys.modules,
  name, module)`) (reproduced on CPython 3.9.6 and 3.14.7, 2026-10-01).
- A readiness probe that introduces and reverts a deliberate small defect tests whether a
  repository's own verification catches a real break [repo-readiness-audits-17] (A).

## 6. A passing suite is not the outcome (K10)

- On 18 real issues, Claude 3.7 Sonnet passed the projects' own tests 38% of the time, but none of
  15 reviewed pull requests was mergeable as it stood; fix-up averaged 42 minutes, 26 even for
  test-passing ones [sizing-horizon-18] (M).
- Four active maintainers of three SWE-bench Verified repositories reviewed 296 agent-written pull
  requests and would not merge about half of the test-passing ones: the automated grader ran on
  average 24.2 points (standard error 2.7) above their merge decisions. They merged only about 68%
  of the original human patches, so scores are reported as a share of that golden baseline
  [sizing-horizon-19, evals-27] (M, METR note of 2026-03-10, read 2026-10-01).
- o3 reward-hacked in 30.4% of runs on the suite whose scoring function it could see against 0.7% on
  another, more than 43 times as often [sizing-trend-21] (M).
- Agents saturate a visible test suite while a held-out one lags, and the gap grows with code size
  (arXiv 2605.21384); with a hidden oracle in the loop, scores approached perfection while the
  library stayed dead or absent (arXiv 2606.28430) (M).
- "For autonomous systems, it is easy to see tests pass and assume the job is done, when this is
  rarely the case" [sizing-trend-9] (L).
- Tests can be too narrow (rejecting correct solutions) or too wide (requiring unstated features)
  [evals-30] (M); a task whose spec conflicts with its tests exposes cheating that standard success
  benchmarks do not [evals-28] (M).
- What found one check engine's defects was not its suite (O, one repository). With about 2,200
  tests passing after a whole-branch review and its fixes, an adversarial review by a model of
  another family found 2 Critical and 11 Important defects, among them a policy comparison that a
  replacement plan running `/usr/bin/true` passed and a baseline that admitted any number of
  identical new findings. After further fixes and with 2,348 tests passing, a second such pass found
  3 Critical, 8 Important and 1 Minor; all twelve were confirmed, ten by a failing test and two by
  inspection. Adopting the engine on its own repository found six defects no test had caught
  (finding identities that embedded absolute paths, a patch-level interpreter pin, a duplicate
  module that stopped mypy), and one adopting repository found more. How such reviews are run is in
  [`review.md`](review.md).

## 7. Fast, quiet feedback

- Print only the failing tests and a one-line pass otherwise; wrap noisy tools so an agent never reads
  walls of passing output [deterministic-5, latent-space-5, practitioners-10] (A).
- One team kept its inner build loop under one minute, "just a nice round number", and restructured
  the build when it grew [repo-readiness-audits-29] (A).
- Treat verification as a ladder: catch each class of error at the cheapest deterministic rung
  (format and lint on edit) before tests, evals and review [practitioners-15] (P).
- Keep tests, coverage and structure checks out of a quick check target; run the full suite once per
  landing.

## How to apply

1. Before keeping a test, name the change that would make it fail; if you doubt it, break the code
   once and watch the named assertion fail (K1, K9).
2. Assert against literals, worked examples or the spec, never against values the code under test
   computed; assert a refusal's message, not only its exit code (K3).
3. When a broader test supersedes a narrow one, delete or merge the narrow one in the same change
   (K3).
4. Replace wording pins with structural checks unless a spec fixes the words; keep copies of data
   rendered from their source (K4).
5. Build expensive starting states once per module and copy them per test; call functions directly
   unless the command line is the subject; guard shared fixtures against writes (K5).
6. Set `tmp_path_retention_policy = failed`, clean runner temporary directories per job, and pass
   subprocesses an explicit environment that keeps what the interpreter needs; record what a
   captured output depends on (`TMPDIR`, `TERM`) (K6, K7).
7. Run the oldest and newest supported Python before landing and the whole version matrix before a
   release, and make at least one job provision every tool a test needs and fail on skips (K7,
   K8).
8. Record failures that predate the work apart from new ones; leave them as found unless fixing them
   is the task. Show a tree unchanged by comparing bytes and modes, not `git status` output (§5).
9. Judge work by more than a green suite: a fresh reviewer, a held-out check, or the reported case
   itself (K10).

## Limits and open questions

- The audit covers one repository's suite; the reviewers' classifications of over-built and
  incidental-pin findings were not verified; "confirmed" means two verifiers could not refute the
  claim.
- Timings were taken on one machine, some under heavy load; the CI-only failures come from one week
  of one repository's runs, whose matrix cancelled the other legs once one failed, so the
  per-version counts in §4 show which leg failed first more than which versions would fail.
- No source here measures flaky tests directly, or whether deleting weak tests changes the defects
  that reach users.

## Sources

Own records (September 2026), re-read 2026-10-01: the audited suite's review files, verification
records and serial profile; the disposition record of acting on its findings, its paired
before-and-after profiles and the shared-copy watch; its suite logs; its CI runs over one week and
the audit of them; the ticket ledger's reviewer findings and closing notes; the check engine's two
cross-family reviews and its ledger. Documentation and source read 2026-10-01: pytest's
[`tmp_path` how-to](https://docs.pytest.org/en/stable/how-to/tmp_path.html) and
[`src/_pytest/tmpdir.py`](https://github.com/pytest-dev/pytest/blob/main/src/_pytest/tmpdir.py)
(retention defaults); Python's [`tarfile`](https://docs.python.org/3/library/tarfile.html) documentation and
its 3.8 to 3.11 branch pages; GitHub's [workflow
syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
(`strategy.fail-fast`); METR, ["Many SWE-bench-Passing PRs Would Not Be Merged into
Main"](https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/).
Credited ideas:
superpowers 6.4.1 (`test-driven-development`, MIT); Matt Pocock's skills 1.2.3 (`tdd`,
`diagnosing-bugs`, MIT); DeMillo, Lipton and Sayward, IEEE Computer, 1978; James Carr, "TDD
Anti-Patterns", 2006; Google Testing Blog, "Test Behavior, Not Implementation" (2013),
"Change-Detector Tests Considered Harmful" (2015) and "Flaky Tests at Google and How We Mitigate Them"
(2016); Kent Beck, "Test Desiderata", 2019; Luo, Hariri, Eloussi and Marinov, FSE 2014. Evidence
records in `_evidence/2026-09-25.jsonl` and `_evidence/2026-09-26.jsonl` as cited; arXiv 2605.21384,
2606.28430, 2605.07769.
