# OutcomeBound

[![CI](https://github.com/rajasdevel/outcomebound/actions/workflows/ci.yml/badge.svg)](https://github.com/rajasdevel/outcomebound/actions/workflows/ci.yml)

**Work sized to the outcome. Evidence for each step.**

OutcomeBound gives your coding agent a 300-word contract, thirteen skills it reads when a task
needs them, and engine checks that run your project's own commands. The agent does the engineering
that the outcome needs: no less, and no more. It holds only the decisions that are yours, and it
reports what is true, what is not done, and which check shows it.

It works through the harness you already use (Claude Code, Codex, Cursor, Gemini CLI, Amp). The
engine is Python standard library only, and it never runs your agent.

[Quick start](#quick-start) · [What you get](#what-you-get) · [How it works](#how-it-works) ·
[Evidence and limits](#evidence-and-limits) · [Harness support](references/portability.md)

## What you get

| Feature | What it does |
| --- | --- |
| **The contract** | A short block in `AGENTS.md`: frame each task by outcome, context, bounds and completion bar; size the plan to the risk; report against the ask. |
| **Skills on demand** | Requirements, decision briefs, tests, diagnosis, review, specs, tickets, hand-offs, landing, acceptance and more. Each loads only when its trigger matches. |
| **Lifecycle scaffold** | `outcomebound scaffold` writes the files a prototype, solo, team or organization project needs, and lists each value still to fill. |
| **Decision briefs** | An act outside the agent's authority comes back as options, a recommendation, evidence and an undo line. Other work continues. |
| **Quality floor** | Keep old lint and type debt visible, reject new findings, and make each loosening a recorded decision. |
| **Ticket hand-off** | Slice work into outcomes you accept, then hand each one to an implementer with the detail its tier needs. |
| **Instruction check** | Read agent instructions for hidden characters, override phrases and risky settings. |

## From idea to delivery

![Outcome, context, bounds and completion bar carry through requirements, design and accepted work, build and validation, release and delivery, operation and maintenance, and retirement. Start at the current state and use only the stages the outcome needs.](docs/assets/outcomebound-lifecycle.svg)

A local bug fix goes straight to its regression check. An export feature keeps its format and
privacy constraints with the accepted work, lands through your route, and checks the delivery.
The [lifecycle reference](skills/using-outcomebound/references/lifecycle.md) gives the evidence
and hand-offs for each stage. Your project records its own lifecycle in a few lines.

## Quick start

You need Python 3.10 or later, Git 2.52.0 or later, and a Git work tree.

```sh
uv tool install outcomebound==1.6.0
cd your-repo
outcomebound adopt . --detect       # writes nothing; prints the install command for your files
```

For a Python project with a `make test` target and both harnesses' folders, it prints:

```sh
outcomebound adopt . --harness claude-code,codex --fragments python,commands --done 'make test'
```

Run that command, read the diff, and commit the files. The install writes no hook and runs no
command of yours. Start a new agent session, and add `outcomebound adopt . --check` to CI to catch
stale or edited managed files.

You can also give the whole onboarding to your agent: ask it to follow the guide that `--detect`
names. It proposes only the project facts an agent would otherwise get wrong, each with the file
that shows it, and asks you once for what the repository cannot show.

### Start a new project

```sh
mkdir my-app && cd my-app && git init
outcomebound scaffold . --lifecycle solo --visibility private         # the plan; writes nothing
outcomebound scaffold . --lifecycle solo --visibility private --accept
outcomebound scaffold . --lifecycle solo --visibility private --check # the values left to fill
```

The plan names each file, each platform act and who does it (a branch rule, a secret scan), and
the `adopt` command for the lifecycle. The scaffold writes only absent files, never edits a present
one, and installs nothing. Then ask your agent to start the project: the
[new-project reference](skills/using-outcomebound/references/new-project.md) sizes the idea, tests
what could end it, and builds a walking skeleton with a Done command that can fail.

### Upgrade or remove

```sh
uv tool install --force outcomebound==1.6.0
outcomebound adopt .          # every managed file current; an edited block is kept unless --force
outcomebound adopt . --remove # takes out what the install owns
```

After an upgrade, `adopt --check` reads each managed file as `stale` until `adopt` runs. The
finish-check hook entries that 1.6.0 and earlier wrote do nothing from 1.7.0, and `adopt` takes them
out.

<details>
<summary>Other installers and environment requirements</summary>

`pipx install outcomebound==1.6.0` also works, or `python -m pip install outcomebound==1.6.0`
inside an activated virtual environment. Each release is on PyPI from 1.6.0; the tagged Git URL
(`git+https://github.com/rajasdevel/outcomebound@v1.6.0`) installs the same release, and every earlier one. These commands work in PowerShell, cmd and POSIX shells; detection prints
commands for POSIX shells and PowerShell. On Windows, install [Git for Windows](https://gitforwindows.org). `pip install --user` is not supported. If the environment sets `PYTHONPATH`, use absolute
folders only. See [dependencies and portability](docs/dependencies.md).

</details>

## How it works

The contract frames each task with four inputs:

| Input | Question it answers |
| --- | --- |
| **Outcome** | What must become observably true, and for whom? |
| **Context** | What do the code, runtime and evidence show? |
| **Bounds** | What work and authority are granted, and what state must be preserved? |
| **Completion bar** | Which result and checks establish success for this change? |

The agent decides what it can, states its assumptions, and adds a spec, a test first, a review or a
wider check only when the outcome and risk need one. Your project's required process stays
required; process a document only suggests is sized to the task.

The report starts from the ask: what is now true, and what is not done. Then each check is `PASS`,
`FAIL` or `UNVERIFIED`, and missing evidence is `UNVERIFIED`. Committed, pushed, deployed and
observed are separate states.

OutcomeBound installs no hook. The project facts name the Done commands as the full suite; the
agent runs them where the change's risk reaches them, the project requires them, or the work
lands, and its report gives each check it ran as `PASS`, `FAIL` or `UNVERIFIED`. Read the [contract block](templates/managed-block.agents.md.tmpl) and the
[full operating contract](OutcomeBound.md).

## Evidence and limits

Each claim of a measured effect links to its run in the
[evaluation record](docs/evaluations.md), with its model, its arms and its limits:

- Small tasks: comparisons showed less suggested process with correct changes kept; other
  comparisons passed on both sides and showed no gain ([E7 and E10](docs/evaluations.md)).
- Onboarding guide: 2 of 3 runs passed with it and 0 of 3 without it, on Claude Sonnet 5.5
  ([E23](docs/evaluations.md#e23-160-pass-the-new-project-route-onboarding-and-the-changed-skills-on-claude-subagents)).
- New-project reference: 3 of 3 with it and 0 of 3 without it on a weak idea and on a spike that
  misses its bar ([E23](docs/evaluations.md#e23-160-pass-the-new-project-route-onboarding-and-the-changed-skills-on-claude-subagents)).

These are bounded observations, not proof of general reliability. The engine's own behaviour is
held by its test suite. An install does not prove that a native session loaded a skill: the
[harness guide](references/portability.md) separates configuration from observed
behaviour. The instruction check is lexical, and a person judges its findings. Your permissions,
harness trust and branch protection enforce authority; OutcomeBound's checks inform decisions.

## More

- **Hand off to a smaller model:** the [ticket guide](docs/tickets.md) and the
  [hand-off skill](skills/hand-off-tickets/SKILL.md).
- **Quality floor:** `outcomebound floor propose . > floor.json`, then
  `outcomebound floor apply . --floor floor.json --accept`; see the [floor design](docs/specs/floor/design.md).
- **Review and source checks:** `outcomebound review check <file>` and `outcomebound sources check`
  check accounting (a disposition for each finding, a digest for each source), not correctness.
- **Size of a change:** `outcomebound size [--base REF]` says how many lines the work tree adds and
  removes against a base (for stability work, the release tag in production), and how many of them
  are code, tests, docs, config or records; see the [size design](docs/specs/size/design.md).
- **Text for people:** `adopt --human-style ste` asks for ASD-STE100 Simplified Technical English
  in reports and commit messages.
- **Workspace and commands:** the [workspace guide](docs/workspace.md) and the
  [command guide](docs/commands.md).
- **Research:** the [research library](https://github.com/rajasdevel/outcomebound-research) holds
  dated model, harness and practice evidence; `outcomebound research <path>` returns a file with
  its commit and digest. Cite the file by its path, that commit and that digest in a record.
- **Business requirements kit:** [`kits/business-requirements/SKILL.md`](kits/business-requirements/SKILL.md),
  attached to each release, for a Business Owner to paste into their own assistant. `adopt` does
  not install it.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) (DCO sign-off, no CLA) and [SECURITY.md](SECURITY.md).
Apache-2.0, with one exception: the text that `adopt` writes into your repository carries no
license-copy, changed-file notice or NOTICE duty (Sections 4(a), 4(b) and 4(d); see
[LICENSE](LICENSE)). The license grants no right to use the OutcomeBound name (Apache-2.0
Section 6). You can say that a project uses OutcomeBound, and a fork ships under its own name.
Claude Code, Codex, Cursor, Gemini CLI, Amp and other product names belong to their owners;
OutcomeBound is not affiliated with them.

## Acknowledgements

Ideas in OutcomeBound come from these repositories. The text is our own. None of them is
affiliated with OutcomeBound or endorses it:
[obra/superpowers](https://github.com/obra/superpowers),
[mattpocock/skills](https://github.com/mattpocock/skills),
[anthropics/skills](https://github.com/anthropics/skills),
[agentsmd/agents.md](https://github.com/agentsmd/agents.md),
[agentskills/agentskills](https://github.com/agentskills/agentskills),
[cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill),
[cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design),
[UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai),
[addyosmani/agent-skills](https://github.com/addyosmani/agent-skills),
[DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail),
[worrydream/Tangle](https://github.com/worrydream/Tangle).
The research library's [credited ideas](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/skills.md)
page records the sources.
