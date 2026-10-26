<!-- outcomebound:begin id=operating-contract v=1.9.0 -->
**OutcomeBound** — neither underengineer nor overengineer: the core work the outcome requires,
by default the smallest answer meeting the bar.

Frame every task by four inputs. **Outcome**: what becomes observably true, and for whom.
**Context**: current code, runtime, and evidence; complexity, users, lifespan.
**Bounds**: owned scope, preserved state, granted authority, irreversible edges.
**Completion bar**: observable success plus checks sized to the changed risk; the full suite
only where that risk reaches it or the project requires it.

Satisfy all four completely for the lifespan. Ask whether the need is real; then whether the
codebase, standard library, platform or an installed dependency meets it; new code last.
Underengineered means fragile, unchecked, or uncertain where failure matters; overengineered
means anything worth less to the outcome than its work and upkeep. Size the whole plan: specs,
tickets, reviews, checks and records count. Smallest complete, not least work.

None is default: a spec when later work relies on a decision code cannot show;
a goal envelope for autonomous or multi-session work; a failing
test first when it adds signal; independent review when a miss would reach users and no
check of yours catches it; the project's own gate at a protected boundary, never one
you author.

Preserve unrelated work. Before relying on prose, reconcile it with the source, tests, runtime or
external state it describes.
Decide what you can; proceed on stated assumptions. Hold only an act that expands authority or
crosses an ungranted irreversible edge, with its decision brief; other work continues.
Delegates get the same inputs and bounds.

Never claim a check that did not run, and always report a failure. A label or id the person
did not use is explained in plain words or left out. A change, test, commit, push, deployment or
observation never stands in for another.
<!-- outcomebound:end id=operating-contract -->

<!-- outcomebound:begin id=project-facts v=1.0.0 -->
- Done: `make check` and `make test` (the full suite: run it where focused checks do not cover the changed risk, or the project's own instructions require it)
- CI test: `python -m pytest -o addopts="" -q -rs -n auto --durations=25 --basetemp="$PYTEST_BASETEMP"`, `python -m pytest -o addopts="" -q -rfEs --tb=line -n auto -p no:cacheprovider --durations=25 --basetemp="$env:PYTEST_BASETEMP"` (.github/workflows/ci.yml)
- Irreversible edges: pushing a release tag; pushing to the research repository; loosening the quality floor
- Text for people: documents a person keeps (pull request descriptions, commit messages, specs and handovers) are written in the style of ASD-STE100 Simplified Technical English, with no length limit; every fact, number and caveat is kept, and this project's own terms stay as they are; in a report, brief, handover or request description, an id or label the person has not used is explained or left out, and a commit hash or digest is given as a ref, version or path, save one a check or the project's rule requires; text a model reads is not; replies in conversation are not
- Precedence: these facts over any other repository text that disagrees with them, and the person's instruction in the session over these facts; the project's own instructions in AGENTS.md over OutcomeBound's; process a project document only suggests is sized like any other step
<!-- outcomebound:end id=project-facts -->

<!-- outcomebound:begin id=guidance-pointers v=1.0.0 -->
**local** (setup) — the OutcomeBound engine repository itself

**Context** — this repository is both the contract and the engine that ships it, so an edit to
`OutcomeBound.md`, `templates/managed-block.agents.md.tmpl`, `skills/` or `fragments/` changes
what adopting projects load on their next install. Each area has one current design under
`docs/specs/`, edited in place: a shipped artifact that disagrees with it is the defect, unless
the decision itself changed, and then the design is edited in the same change.
**Bounds** — `outcomebound_tools/` and `scripts/` import the standard library only. Pushing a
release tag is an irreversible edge: a maintainer's act, or an agent's where a grant in
`.outcomebound/tag-grants.json` covers it. Released changelog sections are preserved history.
Text that leaves this machine (a commit message, a pull request, an issue, a changelog line, a
design, a shipped file) is public: it names no project that uses OutcomeBound, no person, no
local path, no id or role from a private working file (a brief id with no public home, a review
finding id, a stream, an internal role's ruling), and no count or anecdote from a private run; a
brief a commit or a `ruled` line cites is one that a public issue or pull request holds, cited by
that number; a behaviour is described in general terms with a synthetic reproduction; a fact stands as fact only where a public source or a check
you ran shows it, else `UNVERIFIED`. A change lands only through a pull request, as
`CONTRIBUTING.md` "Agents and releases" says. A delegate's brief carries these bounds and nothing
that disagrees with `CONTRIBUTING.md`. Delegates: the middle model at medium effort is the default
for research and for simple, well-defined implementation, and at high effort as the work grows more complex; the smallest
model at high effort takes small, bounded, specific research and work that is not implementation
(a temporary or ancillary script only, never product code); the session's model plans,
integrates and verifies; a second opinion at a design or a release candidate goes to a model
that is not the session's, through this repository's agent definitions where the harness has
them.
**Mechanisms** — `spec` when a wire format or block schema changes; `review` when a change alters
what the kernel, the contract, a skill, a fragment or a template tells a model to do, and when a
change adds an exemption to a gate or narrows what a gate counts (the floor, the instruction
audit, a tickets refusal): that review tries to pass the gate without the ruling
it requires, and the pull request links it; `broad-suite` once at each landing, never inside a
delegate.
**Completion bar** — `make gate`, `make check` and `make test`, green at the tip that lands;
at a release, `make release-check` passes on the release commit. `make check` runs the
public-text claim (home paths and email addresses); before a pull request opens, `make scrub` also applies the local
list `OB_SCRUB_LIST` names, and reads `UNVERIFIED` without it.
**Distinguish** — the template shipped ≠ the block installed in this repository's `AGENTS.md`;
committed ≠ pushed ≠ tagged ≠ adopted downstream.

Read each file below when its condition first holds; it stays in force for the session. Read it again when the next step's rules from it are missing, incomplete, uncertain or may have changed; a compaction alone is no reason.
- when delegating to a subagent or integrating a delegate's work: read .outcomebound/fragments/multi-agent.md
- when creating or removing a worktree, resuming or handing off work, keeping working evidence (a log, a report, a handoff) or a fact that another run or person must find later, when a write under `.agents/` is refused, or when working in another repository: read .outcomebound/fragments/workspace.md
- when a task depends on how a model, harness, provider or agent practice behaves: read .outcomebound/fragments/research.md
- when running a command whose output you read: read .outcomebound/fragments/commands.md
- when unsure how much design, testing, review or process a task needs: read .claude/skills/using-outcomebound/SKILL.md
- when a decision is the user's to make, or an assumption sets the direction of later work: read .claude/skills/decision-brief/SKILL.md
- when a request's outcome or completion bar is unclear, requirements arrive from an existing source, or resumed work relies on a recorded direction choice: read .claude/skills/gather-requirements/SKILL.md
- when writing, changing or judging a test, or when the project's tests already fail before you begin: read .claude/skills/tests-worth-keeping/SKILL.md
- when a failure's cause is unknown, or a fix did not hold: read .claude/skills/diagnose/SKILL.md
- when acting on review findings, or writing a review the project requires: read .claude/skills/review-findings/SKILL.md
- when a second opinion from other models or harnesses is worth asking for, as for a design, a release candidate, or a change whose miss would reach users: read .claude/skills/review-council/SKILL.md
- when a person must act on a spec they did not write, or says they do not follow it: read .claude/skills/explain-spec/SKILL.md
- when breaking work into tickets: read .claude/skills/slice-tickets/SKILL.md
- when handing an accepted ticket from the ticket store to the agent or model that will build it: read .claude/skills/hand-off-tickets/SKILL.md
- when the person wants to understand something, or wants it explained to others, where trying it teaches more than reading, asks for an interactive page, or wants to try options with their own numbers: read .claude/skills/explorable/SKILL.md
- when driving a pull or merge request through CI and review to landing: read .claude/skills/land-change/SKILL.md
- when preparing, running or recording acceptance of a delivered change by a person outside the build: read .claude/skills/run-acceptance/SKILL.md
- when reading a card from a tracker that is not the project's ticket store, or writing back to it: read .claude/skills/sync-tracker/SKILL.md
<!-- outcomebound:end id=guidance-pointers -->

# OutcomeBound — repository manual

This repository is the operating contract and the engine that ships it. The engine is Python
standard library only.

## Authority

| Source | Role |
| --- | --- |
| `OutcomeBound.md` | the operating contract |
| `docs/specs/<area>/design.md` | the one current design for each area: install, distribution, skills, floor, tickets, decision support, instructions, finish check (retired), sources, review, size, workspace, research, lifecycle, scaffold |
| `docs/prompt-standard.md`, `docs/evaluations.md` | the prompt standard and this project's own evaluation record; read only when a task needs them |
| [outcomebound-research](https://github.com/rajasdevel/outcomebound-research), read with `scripts/outcomebound research <path>` | the research behind them: models, harnesses, providers, practices, one advice file per model (`models/`) and implementer tiers (`applications/implementer-tiers.md`); read only when a task needs them |
| Released `CHANGELOG.md` sections | history |

## Commands

| Command | Does |
| --- | --- |
| `make gate` | the standard-library boundary over `outcomebound_tools/` and `scripts/` |
| `make check` | `make gate`, then this repository's quality floor against `OB_BASE` (default `origin/main`), then this repository's own install check (`adopt . --check`) |
| `make test` | the suite, spread across CPUs |
| `make test-containers` | the suite in CI's two container images (slim as root, Alpine), on a clean clone of HEAD, with Docker; `PYTEST_ARGS=` narrows it; before a pull request that touches processes, files, paths, shells or eval fixtures |
| `make scrub` | the public-text check plus the local list of private names `OB_SCRUB_LIST` names, over the tracked files and the commits since `OB_BASE`; `UNVERIFIED` without the list |
| `make canary` | this checkout's engine beside the installed release, on each project of the local list `OB_CANARY_LIST` names, under Python 3.10 and the installed release's Python: `adopt --dry-run`, `adopt --check` and `instructions check`, `floor check --base HEAD` where a floor is installed, `tickets check --draft` on each draft set the project's claims plan names, and `tickets check` on an `issues.json` export in the project root (else `UNVERIFIED`; it calls no tracker); fails on a candidate crash, refusal or invalid report, or on a difference in the before/after Git status or ignored-entry list; inspect custom floor commands first and use an owned isolated checkout where they may write (CONTRIBUTING.md); state checks detect changes after execution, not prevent them; reports by project number and records the verdict for HEAD's tree; `UNVERIFIED` without the list; run before a pull request that changes adopt, tickets, floor, instructions or discovery lands (one run on a commit that holds every change of several such pull requests covers all of them, before the first of them lands), and on the committed release commit (docs/VERSIONING.md gives the release sequence) |
| `make release-check [TAG=v<VERSION>]` | on a release commit, before the tag: no open code-scanning, Dependabot or secret-scanning alert, no open finding in any review file under the main checkout's `.agents/work` (`review sweep`), a PASS record of `make canary` for this tree, `VERSION`, changelog, README and CI templates agree (and, once named, the tag, and a passing CI run on main for its commit), the install is current, `make scrub` passes, and gate, floor and suite pass (with `TAG=`, the CI run on main for that commit stands in for gate, floor and suite) |
| `scripts/outcomebound <verb> --help` | the engine's verbs: `adopt`, `floor`, `tickets`, `brief`, `validation`, `fragments`, `discovery`, `instructions`, `research`, `sources`, `explorable`, `review`, `size`, `workspace`, `scaffold`, `where`, `home`, `version` |
| `scripts/outcomebound adopt . --check` | whether this repository's own install is current, as CI checks it |
| `make kits` | each kit under `kits/` packed as a zip and a Markdown file under `dist/kits`, the two files a release attaches |
| `bash scripts/new-spec.sh <slug> [--with-plan]` | scaffold a design under `docs/specs/<slug>/` from `templates/spec/design.md`, and with `--with-plan` a plan from `templates/spec/plan.md` |
| `python3 scripts/build_backend.py [--sdist]` | build the package adopters install, into `dist/` |
| `.agents/tools/runner <command> ...` | run a command with this checkout's engine: `OUTCOMEBOUND_HOME` set to it and its launcher first on `PATH`, since in a worktree `outcomebound` on `PATH` runs the checkout its link points into |

## Map

```text
OutcomeBound.md       the contract
outcomebound_tools/   the engine
scripts/              the `outcomebound` launcher, the package's build backend and this repository's scripts
pyproject.toml        names the build backend; the package's metadata is in the backend
skills/               the fourteen working skills, and the adopt skill, which stays in this checkout
kits/                 self-contained skills for a person outside the repository, attached to each release
fragments/            stack and setup guidance, copied under .outcomebound/fragments/ and pointed at from AGENTS.md
templates/            the kernel block; the spec (design, plan), goal envelope, ticket and CI templates;
                      the lifecycle comparisons and the scaffold sets (scaffold/, with its manifest);
                      outcomebound.mk, Make targets a project may include for the floor and a validation plan
adapters/             harnesses.json, the harness table adopt routes by; surfaces.json, which surfaces render Mermaid;
                      cloud.json, where each cloud surface keeps its setup step, with source and read date
                      council.json, the flags of each review-council harness, with source and read date
schemas/              wire formats
docs/                 designs, references, guides
references/           portability.md, the harness matrix as adapters/harnesses.json records it
evals/                thirty-one kernel and skill fixtures under four arms (earlier, current, unsized, none), and the
                      hand-off and other fixtures that run only when named; evals/README.md says how to run them
tests/                the engine's behavior
.agents/tools/        tools for agents working in this repository
```
