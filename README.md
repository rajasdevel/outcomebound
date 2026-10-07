# OutcomeBound

[![CI](https://github.com/rajasdevel/outcomebound/actions/workflows/ci.yml/badge.svg)](https://github.com/rajasdevel/outcomebound/actions/workflows/ci.yml)

**Toward trustworthy delegation to coding agents.**

Hand a coding agent the outcome. OutcomeBound asks it for work sized to that outcome, a true
report of every check, and only the decisions that are yours. It is a short contract in your
`AGENTS.md`, and a small tool that installs the contract and keeps it current. The tool is Python
standard library only, and it does not run your agent.

## What it asks of your agent

A one-line fix should not come back with a design note. A risky change should not come back
without a test, or with a report that says "done" when nothing was pushed. The contract asks for:

- **Right-sized work.** Exactly the engineering the outcome needs, in code and in process.
- **Honest reports.** Each check is `PASS`, `FAIL` or `UNVERIFIED`, and missing evidence is never
  success. A passing test is never reported as a push, and a push never as a deployment.
- **Autonomy within your bounds.** The agent decides what it can, states its assumptions, and
  holds only an act you did not grant, and continues the rest. Your decisions come back as short **decision
  briefs**, each with the options, a recommendation, and whether the choice can be undone.

Here is one, as an agent puts it to you. `outcomebound brief` draws it from the agent's JSON, and
the words follow the plain style of `--human-style ste`:

> #### D1 · The fix needs a migration that rewrites the orders table. When do we run it?
> - 👉 Recommend: C — It stops the bug today and keeps the table rewrite in the window your team already uses · confidence 75% (inferred)
> - Options:
>   - A Run it on Sunday in the maintenance window — No customer sees a slow checkout
>     - 🔻 Downside: The bug stays in production for four more days
>   - B Run it online now, in batches of 10,000 rows — The bug is fixed today
>     - 🔻 Downside: Checkout is slower for about 40 minutes while it runs
>   - C Ship a code-only workaround now, and run the migration on Sunday — The bug stops today, and no one sees a slow checkout
>     - 🔻 Downside: Two changes to review, and the workaround must come out after Sunday
> - Why now: The workaround can ship today only if you choose it before the 16:00 deploy
> - ✅ Checked: The fix and the workaround pass the unit tests, and the migration ran on a copy of staging in 38 minutes
> - ⚠️ Not checked: Load on production during an online run; only a run under real traffic would settle it
> - ⛔ Undo: The migration rewrites 4.2 million rows; going back needs a restore from backup

A second aim is the same quality for less: no ceremony that a change does not need, and
hand-offs that let a smaller, lower-priced model build what a strong model planned
([below](#hand-off-to-a-smaller-model)). This is an aim, not yet a measured result.

## What it changes, measured

The test project suggested a design note, a decision record, the full slow suite and a second
reader for every change. The task was a two-character bug fix, then a small new option. Without
OutcomeBound, every run treated the fix like a feature. With it, every run treated the fix like
a fix.

| Three runs of each task, one model | With OutcomeBound | Without |
| --- | --- | --- |
| Made the change correctly, with a regression test | 6 of 6 | 6 of 6 |
| Skipped the design note and decision record the change did not need | 6 of 6 | 0 of 6 |
| Ran focused tests instead of the slow full suite | 5 of 6 | 0 of 6 |
| **Right-sized, by the task's own bar** | **6 of 6** | **0 of 6** |

Same correctness and less ceremony. On the fix, every run with OutcomeBound named the skipped
suite as `UNVERIFIED` and gave the reason. The model was `gpt-6.1-sol` through Codex, 2026-09-30.
An earlier pass on `gpt-6-sol`, with an earlier install that had no project-facts line about
suggested process, did not stop that process on these two tasks. The rerun changed the model and
the install together ([E7 and E10](docs/evaluations.md)). The run records are not published, and
in these passes models sometimes read the graders (E12): rerun the fixtures to check. Every
result, its method and its limits are in the [evaluation record](docs/evaluations.md).

## Where it stands

| | Today | Not yet measured |
| --- | --- | --- |
| **Right-sized work** | Shown on the over-engineering side: process a change does not need stops | The under-engineering side: a shortcut that breaks something. No task separates the arms there yet |
| **Honest reports** | Shown: a skipped check is named `UNVERIFIED`, with the reason | More harnesses and surfaces |
| **Autonomy in your bounds** | In the contract and the skills. No ladder run put a question to the person. Runs in other passes did, and unnecessary questions are not yet measured | Measure it on long, multi-session work |
| **Efficiency** | A test-first hand-off took a smaller model from 6 to 9 passes of 9 on three small tasks | Cost per finished task. The install adds text, and text costs tokens: about 27% more per run in one pass (`gpt-6-sol`, skill fixtures); the ladder rerun went both ways. The bet is fewer rounds, and that bet is not yet measured |
| **Models** | OpenAI models through Codex, three runs a cell (nine in the hand-off comparison) | Claude, Gemini and open-weight models; more runs |

Two things hold by design. OutcomeBound sizes only process that a project suggests: what your
project requires stays required (no fixture yet tests a project whose process is required). And its checks inform you; they are not an authority boundary.
The instruction check is lexical, and you judge what it finds. The quality floor makes a
loosening visible, and your branch protection is what prevents one.

## Try it

You need Python 3.10 or later, and a Git work tree: Git is the undo. OutcomeBound runs on
Windows (PowerShell, cmd or Git Bash), macOS and Linux, and in containers, such as Debian and
Alpine images. CI runs the test suite on a hosted Windows runner and in a Debian and an Alpine
container. On Windows, install [Git for Windows](https://gitforwindows.org): `adopt` needs Git,
and the finish check runs your Done commands with the `sh` of Git for Windows. On macOS and
Linux the finish check uses the system `sh`. The tool installs for Claude Code, Codex, Cursor,
Gemini CLI and Amp. Another harness can use `--harness generic`, and then you check that it
loads the files. pi is not verified yet, so `adopt` refuses it
([references/portability.md](references/portability.md)).

```sh
uv tool install git+https://github.com/rajasdevel/outcomebound@v1.3.0
cd your-repo
outcomebound adopt . --detect
```

`pipx install` and `pip install` into a virtual environment work too. The install commands are the
same in PowerShell, cmd and a POSIX shell. The commands that OutcomeBound prints for you to paste
are for POSIX shells and PowerShell, not cmd. They give an `outcomebound` program: an `.exe` on
Windows. `pip install --user` does not work, because `outcomebound` runs Python isolated (`-I`),
which ignores the user site. Where `PYTHONPATH` is set in the environment that runs
OutcomeBound, it must hold absolute folders only: a relative entry such as `.` or `src` lets a
file of the repository replace the command's first step.

`--detect` writes nothing. It prints the install command that your files suggest, for example
`outcomebound adopt <your-repo> --harness claude-code --fragments python,commands --done 'python3 -m pytest'`
(it prints the absolute path of the repository). Run it, read
the diff, and commit. Your agent's next session reads the contract. The install writes:

```text
AGENTS.md             the contract; Done, CI test and irreversible edges from your files
.claude/skills/       nine skills: sizing, decision briefs, requirements, tests, diagnosing a failure,
                      review findings, explaining a spec, slicing tickets, handing one off (per
                      harness)
.outcomebound/        the fragments you select, and a manifest of what adopt wrote
CLAUDE.md, GEMINI.md  an @AGENTS.md import, only where the harness needs one
```

Put `outcomebound adopt . --check` in CI: it fails while a block or file is stale, edited or
missing. To upgrade, install a newer tag with `uv tool install --force`, then run
`outcomebound adopt .` again. `adopt` overwrites a block that you edited only with `--force`, and
`outcomebound adopt . --remove` takes out exactly what it wrote.

<details>
<summary>The contract, in full</summary>

Source: [templates/managed-block.agents.md.tmpl](templates/managed-block.agents.md.tmpl). Long form: [OutcomeBound.md](OutcomeBound.md).

```markdown
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
Decide what you can; proceed on stated assumptions. Hold only an act that expands authority or
crosses an ungranted irreversible edge: write its decision brief (the `decision-brief` skill); all
other work continues.
Delegates receive the same four inputs and bounds.

Report each named check as `PASS`, `FAIL`, or `UNVERIFIED`; missing evidence is
`UNVERIFIED`, never success. Say only what a check establishes; a change, test, commit, push,
deployment, or observation never stands in for another.
```

</details>

## When you want more

### The finish check

With `adopt --finish-check`, your Done commands decide when a turn can end:

```mermaid
flowchart TD
    turn(["The agent ends its turn"]) --> changed{"Has the working tree or HEAD changed<br/>since the turn began?"}
    changed -- no --> idle["The turn ends. Nothing runs.<br/>A failure is shown to you again."]
    changed -- yes --> cmds["Your Done commands run"]
    cmds -- PASS --> pass["The turn ends. You see PASS:<br/>not reviewed, not landed."]
    cmds -- FAIL --> known{"Did it fail in the same way<br/>when the turn began,<br/>or when adopt measured Done?"}
    known -- yes --> told["The turn ends.<br/>You see the known failure."]
    known -- no --> retry{"Sent back<br/>once already?"}
    retry -- no --> back["The failure goes back to the agent.<br/>It keeps working."]
    back --> turn
    retry -- yes --> report["The turn ends.<br/>The report goes to you."]
    classDef ok fill:#d5f5e3,stroke:#1e8449,color:#0b3d1f
    classDef bad fill:#fadbd8,stroke:#c0392b,color:#641e16
    class pass ok
    class back,report,told bad
```

With `--finish-check`, `adopt` runs your Done commands one time. It shows the verdict and the
time of each command. It records each command that fails now as a known failure, with its exit
code, the names of the failing tests that its output gives, and the commit. A known failure does
not send the agent back while it fails in the same way: the same exit code, and no new failing
test name. All other failures send the agent back. The record applies only in a checkout whose
history contains the measured commit. When a known command passes, the check removes it from the
record, and its next failure sends the agent back. The check reads test names from the summary
lines of pytest, unittest, go test, cargo test, jest, vitest and make. If a command prints no such
names, only its exit code is compared, so a new failure in that same command does not send the
agent back; the message says so. Split your Done into smaller commands to make this gap smaller.
`adopt --finish-check` measures Done again. When it replaces an earlier record, it names each
failure that is new since that record. Read these lines: an agent that runs it after its change
broke code makes those failures known. An install without `--finish-check` does not run Done.

A second entry in the same settings file runs at each prompt and records the commit and the
working tree (tracked and untracked files; ignored files are not compared) at the start of the
turn; it prints nothing. A turn that ends on that commit and tree runs nothing and holds nothing, so a failure that the environment caused while the agent only
read does not send it back. A failure that the tree already had at the start of the turn, with the
same failing test names, is shown to you as known before the turn, and does not send the agent
back; a new failure does. The check compares with the last Done run on the tree at the start, so
a tree that Done never ran on has no such record. A failure that the agent caused in an earlier
turn and left unfixed is also known before the later turns, and is shown to you each time. Without the entry (an install from before it,
or a harness that does not fire the event), the check behaves as before. Each time the record
decides a stop, the message to you names the time it was written. The record is trusted only for
the same session and, where the harness gives a transcript to check against, only if it was written
before the agent's first reply or tool call of the turn. Where it gives none, the session alone
decides. An agent that forges the prompt input, edits the transcript or writes the Git directory
can still write one; the contract forbids it, and the message shows each use.

The hook checks the checkout at the working directory of the session. If the agent works in a
worktree and the session stays in the main checkout, a PASS tells you nothing about the worktree.
In that flow, the agent runs the Done commands in the worktree before it lands the work.

It is observed in Claude Code. It is built for Codex, but not yet observed there. The install
report itself says `UNVERIFIED` for the hook, until you see its PASS message end a run. In Codex,
the agent sees the reason of a hold; you see the other messages. Codex runs a new or changed hook
only after you trust it in `/hooks`. A change to Done or to the timeout changes the entry, and the
prompt entry is a new entry in an upgraded install, so trust them again; `adopt` tells you when. The Done commands may take up to 600 seconds, the harnesses'
default. If Done takes longer when `adopt` measures it, `adopt` tells you, and
`adopt --finish-timeout <seconds>` sets a longer time.

### Hand off to a smaller model

Where a project declares a ticket store, a strong model slices large work into tickets that you accept. The
`hand-off-tickets` skill then gives each implementer what its tier needs: the ticket's brief alone
at the outcome tier, plus the approach, signatures, invariants, edge cases and milestones at the
design tier. At the spec tier, the brief comes from `outcomebound tickets brief <id> --detail full`,
and the work goes one step at a time:

```mermaid
sequenceDiagram
    participant S as Strong model
    participant M as Smaller model
    loop Each step of the ticket
        S->>S: Write failing tests and stubs
        S->>M: The step's package
        M->>M: Make the tests pass, change none of them
        M->>S: Commit and hand over
        S->>S: Review the step
    end
    Note over S,M: The ticket lands through your project's own gate.
```

The tier comes from you, or from the research library's placement table. In 63 runs, the spec
package raised `gpt-6-luna` at `xhigh` from 6 to 9 passes of 9, and `gpt-6-astra` at `high`
passed 9 of 9 with it or without it. The whole gain was one requirement on one of three small
tasks, and the design package's effect did not show. Each tier had one model, all from one maker,
through one harness. The comparison measured hand-written packages, not the `hand-off-tickets`
skill. `--detail full` alone scored 6 of 9, the same as the ticket alone, and by the rules written
before the runs it would be cut. The project keeps it as the default brief of the spec tier, to be
judged on longer work.

### A quality floor for a project with history

Most projects already carry lint and type debt. Fixing all of it first blocks real work, and
ignoring it lets it grow. The floor records the findings you have today, and fails only what is
new. This repository runs on its own floor: 26 old lint findings and 46 old type findings are in
a baseline, and every change since has added none. When a change adds new ones, the check names
them:

```text
FAIL python.lint (2 new, 26 baselined)
  +1 outcomebound_tools/tickets.py:F401
    260:12 `os` imported but unused
  +1 outcomebound_tools/tickets.py:S307
    261:12 Use of possibly insecure function; consider using `ast.literal_eval`
FAIL python.types (1 new, 46 baselined)
  +1 outcomebound_tools/tickets.py:no-untyped-def
    259:0 Function is missing a type annotation
```

An agent that hides a finding instead of fixing it fails too. A new suppression comment, a
baseline that grows or a changed tool config is a loosening, and it passes only when the commit
that makes it names the decision that allowed it:

```text
FAIL loosening (1 in origin/main..HEAD, 1 not ruled; the commit that makes a loosening carries Floor-Loosening: <what>; ruled <id>)
  outcomebound_tools/tickets.py adds # noqa: s307 (not ruled: <commit> carries no Floor-Loosening line)
```

`outcomebound floor propose . > floor.json` prints the claims for your stack (Python and shell)
and a secrets claim for every project, and `outcomebound floor apply . --floor floor.json --accept`
fits them to the findings you have today. It runs your own ruff, mypy, gitleaks and shellcheck with your own configs. The floor makes
a loosening visible; your branch protection is what holds it to a person's decision.

### Also optional

- **Instruction check** (`outcomebound instructions check .`): reports hidden characters, override
  phrases and risky harness settings in the files your agents load. It writes nothing. A hit you
  judge safe, you record with `outcomebound instructions rule . <id>`, in your own file outside the
  project; it then stops changing the result until that file changes.
- **Review check** (`outcomebound review check <file>`): fails where a finding in a review file has no disposition (`fixed`, `rejected` or `deferred`), or no `Reviewed:` ref.
- **Sources** (`outcomebound sources import`, `outcomebound sources check`): where requirements come
  from a document, an issue or a transcript saved as markdown or text, `import` splits it into items
  that each have an id and a revision digest, and `check` fails where the ledger in your spec leaves
  an item without a disposition, cites an item that is not there, quotes words the item lacks, or
  records an item that has changed since. It says what it does not establish: a requirement that
  keeps one item's words may still lose its other constraints. The manifest holds the source text,
  so Git ignores it unless you opt in.
- **Text for people** (`adopt --human-style ste`): agents write reports and commit messages for
  people in the style of ASD-STE100 Simplified Technical English.
- **Workspace** (the `workspace` fragment): where several agents share one machine's checkout, four
  folders under `.agents/` hold each task's worktree, working files, hand-off page and shared
  notes, and Git ignores them. The [workspace guide](docs/workspace.md) says what it gives you and
  what it does not.
- **Command habits** (the `commands` fragment): habits that stop a pager, editor or prompt from
  hanging a run and keep long output out of context, without hiding an error. `adopt --detect`
  proposes it for every repository. The [command habits guide](docs/commands.md) gives each
  habit's reason and source.
- **Research** (the `research` fragment): [outcomebound-research](https://github.com/rajasdevel/outcomebound-research)
  is a separate, neutral library about models, providers, harnesses and practices. From a clone
  (`outcomebound research clone <folder> --accept`), `outcomebound research <path>` prints a file
  headed by the clone's commit and the sha256 of its text. An agent cites the file by its path,
  that commit and that digest. A finding goes back with `outcomebound research ingest`, which
  prints a prefilled issue link.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) (DCO sign-off, no CLA) and [SECURITY.md](SECURITY.md).
Apache-2.0, with one exception: the text that `adopt` writes into your repository carries no
license-copy, changed-file notice or NOTICE duty (Sections 4(a), 4(b) and 4(d); see
[LICENSE](LICENSE)). The license grants no right to use the OutcomeBound name (Apache-2.0
Section 6). You can say that a project uses OutcomeBound, and a fork ships under its own name.
Claude Code, Codex, Cursor, Gemini CLI, Amp and other product names belong to their owners;
OutcomeBound is not affiliated with them.

## Acknowledgements

Ideas in OutcomeBound come from these GitHub repositories, named for credit. The text is our own,
and none of them is affiliated with OutcomeBound or endorses it:
[obra/superpowers](https://github.com/obra/superpowers),
[mattpocock/skills](https://github.com/mattpocock/skills),
[anthropics/skills](https://github.com/anthropics/skills),
[agentsmd/agents.md](https://github.com/agentsmd/agents.md),
[agentskills/agentskills](https://github.com/agentskills/agentskills),
[cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill),
[cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design),
[UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai),
[addyosmani/agent-skills](https://github.com/addyosmani/agent-skills),
[DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail). The research
library's [credited ideas](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/skills.md)
page is where sources are recorded.
