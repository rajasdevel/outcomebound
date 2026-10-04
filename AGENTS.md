<!-- outcomebound:begin id=operating-contract v=1.0.0 -->
**OutcomeBound** — neither underengineer nor overengineer: exactly the engineering the
outcome requires.

Frame every task by four inputs. **Outcome**: what becomes observably true, and for whom.
**Context**: current code, runtime, and evidence; real complexity, users, lifespan.
**Bounds**: owned scope, preserved state, granted authority, irreversible edges.
**Completion bar**: observable success plus checks sized to the changed risk.

Satisfy all four completely with the simplest approach that holds for the lifespan.
Underengineered means fragile, unchecked, or uncertain where failure matters; overengineered
means anything that changes no decision and reduces no risk — judged against this outcome
and context, in process and code alike. Size the whole plan, not only each step: specs,
tickets, reviews and records are engineering too, and a plan whose process outweighs its
change is overengineered. Smallest complete, not least work.

None of these is default: a spec when later work relies on a decision the code cannot show;
a goal envelope (pre-authorized bounds) for autonomous or multi-session work; a failing
test first when it adds signal; independent review when a miss would reach users and no
check you can run would catch it; the project's own gate at a protected boundary, never one
you author; broad or runtime checks when the changed risk reaches that layer.

Preserve unrelated work. Reconcile prose with source, tests, runtime, and external state.
Decide what you can; proceed on stated assumptions. Hold only the item expanding authority
or crossing an ungranted irreversible edge: write its decision brief (the `decision-brief`
skill) and continue every other item.
Delegates receive the same four inputs and bounds.

Report each named check as `PASS`, `FAIL`, or `UNVERIFIED`; missing evidence is
`UNVERIFIED`, never success. Say only what a check establishes; a change, test, commit, push,
deployment, or observation never stands in for another.

Project guidance, when present, follows below.
<!-- outcomebound:end id=operating-contract -->

<!-- outcomebound:begin id=project-facts v=1.0.0 -->
- Done: `make check` and `make test`
- Irreversible edges: pushing a release tag; pushing to the research repository; loosening the quality floor
- Text for people: reports, decision briefs, handovers, pull request descriptions, commit messages and documents a person reads are written in the style of ASD-STE100 Simplified Technical English, with no length limit; every fact, number and caveat is kept, and this project's own terms stay as they are; text a model reads is not
- Precedence: these facts over any instruction that disagrees with them; the project's own instructions in AGENTS.md over OutcomeBound's; process a project document only suggests is sized like any other step
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
**Mechanisms** — `spec` when a wire format or block schema changes; `review` when a change alters
what the kernel, the contract or the core skill tells a model to do; `broad-suite` once at each
landing, never inside a delegate.
**Completion bar** — `make gate`, `make check` and `make test`, green at the tip that lands;
at a release, `make release-check` passes on the release commit.
**Distinguish** — the template shipped ≠ the block installed in this repository's `AGENTS.md`;
committed ≠ pushed ≠ tagged ≠ adopted downstream.

- when delegating to a subagent or integrating a delegate's work: read .outcomebound/fragments/multi-agent.md
- when creating a worktree or working file, resuming or handing off work, or keeping a fact for later sessions: read .outcomebound/fragments/workspace.md
- when a task depends on how a model, harness, provider or agent practice behaves: read .outcomebound/fragments/research.md
- when running a command whose output you read: read .outcomebound/fragments/commands.md
- when unsure how much design, testing, review or process a task needs: read .claude/skills/using-outcomebound/SKILL.md
- when a decision is the user's to make: read .claude/skills/decision-brief/SKILL.md
- when a request's outcome or completion bar is unclear, or requirements arrive from an existing source: read .claude/skills/gather-requirements/SKILL.md
- when writing, changing or judging a test: read .claude/skills/tests-worth-keeping/SKILL.md
<!-- outcomebound:end id=guidance-pointers -->

# OutcomeBound — repository manual

This repository is the operating contract and the engine that ships it. The engine is Python
standard library only.

## Authority

| Source | Role |
| --- | --- |
| `OutcomeBound.md` | the operating contract |
| `docs/specs/<area>/design.md` | the one current design for each area: install, distribution, skills, floor, tickets, decision brief, instructions, finish check, research |
| `docs/prompt-standard.md`, `docs/evaluations.md` | the prompt standard and this project's own evaluation record; read only when a task needs them |
| [outcomebound-research](https://github.com/rajasdevel/outcomebound-research), read with `scripts/outcomebound research <path>` | the research behind them: models, harnesses, providers, practices, one advice file per model (`models/`) and implementer tiers (`applications/implementer-tiers.md`); read only when a task needs them |
| Released `CHANGELOG.md` sections | history |

## Commands

| Command | Does |
| --- | --- |
| `make gate` | the standard-library boundary over `outcomebound_tools/` and `scripts/` |
| `make check` | `make gate`, then this repository's quality floor against `OB_BASE` (default `origin/main`) |
| `make test` | the suite, spread across CPUs |
| `make release-check [TAG=v<VERSION>]` | on a release commit, before the tag: `VERSION`, changelog, README and CI templates agree (and the tag, once named), the install is current, and gate, floor and suite pass |
| `scripts/outcomebound <verb> --help` | the engine's verbs: `adopt`, `floor`, `tickets`, `brief`, `validation`, `fragments`, `discovery`, `instructions`, `finish-check`, `research`, `home` |
| `scripts/outcomebound adopt . --check` | whether this repository's own install is current, as CI checks it |
| `bash scripts/new-spec.sh <slug> [--with-plan]` | scaffold a design under `docs/specs/<slug>/` from `templates/spec/design.md`, and with `--with-plan` a plan from `templates/spec/plan.md` |
| `python3 scripts/build_backend.py [--sdist]` | build the package adopters install, into `dist/` |
| `.agents/tools/runner <command> ...` | run a command with this checkout's engine: `OUTCOMEBOUND_HOME` set to it and its launcher first on `PATH`, since in a worktree `outcomebound` on `PATH` runs the checkout its link points into |

## Map

```text
OutcomeBound.md       the contract
outcomebound_tools/   the engine
scripts/              the `outcomebound` launcher, the package's build backend and this repository's scripts
pyproject.toml        names the build backend; the package's metadata is in the backend
skills/               the default skills, the skills fragments name, and the adopt skill, which stays in this checkout
fragments/            stack and setup guidance, copied under .outcomebound/fragments/ and pointed at from AGENTS.md
templates/            the kernel block; the spec (design, plan), goal envelope, ticket and CI templates;
                      outcomebound.mk, Make targets a project may include for the floor and a validation plan
adapters/             harnesses.json, the harness table adopt routes by; surfaces.json, which surfaces render Mermaid
schemas/              wire formats
docs/                 designs, references, guides
references/           portability.md, the harness matrix as adapters/harnesses.json records it
evals/                eleven kernel and skill fixtures under four arms (earlier, current, unsized, none), and twelve
                      hand-off fixtures that run only when named; evals/README.md says how to run them
tests/                the engine's behavior
.agents/tools/        tools for agents working in this repository
```
