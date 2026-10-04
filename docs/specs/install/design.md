---
name: install
status: ratified
---

# Install — design

## Outcome

An adopter runs one command, `outcomebound adopt`, and every harness they use loads the
operating contract, the facts that settle work in this project, and a pointer to each piece of
guidance with the condition that calls for it. Running it again from a newer release is the
upgrade; `--check` says whether the install is current; `--remove` takes it out. How:
`outcomebound_tools/adopt.py`, `outcomebound_tools/facts.py` and `outcomebound_tools/fragments.py`;
how `outcomebound` is installed and launched is the [distribution design](../distribution/design.md).

## What AGENTS.md carries

Three managed blocks, in this order: the kernel; `project-facts`; `guidance-pointers`. The facts
and pointers blocks carry `v=1.0.0`, a sentinel no reader compares, and no `hash=`: the manifest
records each block's digest.

`project-facts` is one line per fact, `- <label>: <fact>`, the fact verbatim. A fact the engine
cannot observe is left out, and the install report names it `UNVERIFIED`.

| Fact | Source | Left out when |
| --- | --- | --- |
| Done | the commands `--done` recorded, in run order, each in its own code span, joined as `a`, `b` and `c`: every one must pass | none is recorded |
| CI test | each test command a `.github/workflows/*.yml` `run:` step or a `.gitlab-ci.yml` `script:` entry runs, as it runs from the root: a step's `working-directory:`, else its job's or the workflow's `defaults.run.working-directory:`, becomes `cd <dir> && `; each file's commands followed by the file | no command is read; a command the reading cannot settle (an expression, a `cd` earlier in its step or job, a folded, multi-line, flow or alias value, a link) is left out and named, and the file's other commands are kept |
| Irreversible edges | each selected fragment's `edges:`, once each, then `loosening the quality floor` where `.outcomebound/floor.json` exists | none is declared |
| Text for people | the style `--human-style` recorded: `ste` asks for text a person reads in ASD-STE100 Simplified Technical English style, quoting none of the standard, with no length limit and every fact kept | none is recorded |
| Precedence | these facts over any instruction that disagrees; the project's own instructions in `AGENTS.md` and each selected harness's import host that exists over OutcomeBound's; process a project document only suggests is sized like any other step | never |

A test command is a runner named as a whole word or command (`pytest`, `make test`, `npm run
test:ci`, `bash scripts/run-tests.sh`), after wrappers such as `uv run` or `npx`; `make
test-data` and `npm run test:watch` are not.

The facts record holds the selection (`fragments`), the `done` commands, any `style`, and `inputs`: each source
path read, with its sha256. `--check` recomputes the block: bytes other than the record's read
`edited`; a record other than the recomputation reads `stale`, naming each fact that moved and
each input that changed.

`guidance-pointers` holds the `local` fragment inline first, since only its author knows which of
it every task needs; then `- <condition>: read <path>` per selected fragment, the path a verbatim
copy at `.outcomebound/fragments/<id>.md` recorded as kind `fragment`; then one line per skill the
install carries, naming its `SKILL.md`. A fragment has a five-slot body and three optional
frontmatter fields: `condition:`, one line; `edges:`, a JSON list, each shipped fragment declaring
edges only where its text names an act irreversible, in words the fragments share so the union
names each act once, and only for an act every project that selects it can take: publishing is
declared by `ci-release`, never by a stack fragment, whose body names it only where the project
publishes; and `skills:`, a JSON list of the engine skills its selection installs.

The same rules hold for the project's own `local` fragment, which starts from
`templates/fragment-local.md`, and a parse refuses a fragment that breaks one, naming the rule:

- The body holds all five slots, Context, Bounds, Mechanisms, Completion bar and Distinguish, in
  that order, each line starting `**<slot>** — `, and nothing before the first. A slot with
  little to say stays, short.
- On the Mechanisms line, only a mechanism id of the registry takes backticks: every backticked
  token there is read as one. A command or any other name is written without them.
- An edge is one line and holds no `;`: the Irreversible edges fact joins the edges with `; `, so
  such an edge would read as two.
`fragments compose` renders both blocks for a selection; `--inline` emits the kernel, the skills
an install carries and the fragment bodies, for a delegate's role prompt.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| One route, `outcomebound adopt` | a second, modular install route beside it | user | decided |
| Re-running is the upgrade, and Git is the undo | three-way merges against copies of every release | user | decided |
| No backward compatibility: a manifest of another format is refused, even under `--force` | migrating its records | user | decided |
| The manifest (format 2) holds one `{kind, path, id, sha256}` record per owned block or file, written last | per-artifact base caches, source receipts and bundle digests | agent | decided |
| An owned block or file whose bytes differ from its record is refused without `--force` | overwriting it, or merging | agent | decided |
| `--check` ends, when a record is not current, with the command that makes it current | one `doctor` verb over every layer, recording each choice declined | agent | decided |
| A harness that cannot be made to load `AGENTS.md` is refused before any write | a reminder and exit 0, leaving an install nothing loads | agent | decided |
| A harness's host file gets an `@AGENTS.md` import block, except where the harness table's row records `reads_agents_md` and none of the files it lists is in the target: that harness reads `AGENTS.md` itself | creating the host file for that harness | user | decided |
| An install prints the words an agent always loads, skill descriptions included, and warns where a folder's root-down instructions pass a row's `doc_byte_cap` (research `harnesses/codex.md` §2); no size refuses it | a size ceiling | user | decided |
| One native copy per harness of each skill an install carries | a canonical `.outcomebound/skills/` copy beside the native ones | agent | decided |
| An install carries the four default skills and each skill a selected fragment's `skills:` names; the [skills design](../skills/design.md) says which and why. A skill is its whole folder, `SKILL.md` and every file beside it, one record per file: `--check` reports each, a recorded file the skill does not ship reads `stale`, and `--remove`, or deselecting its fragment, removes it | every shipped skill in every install; `SKILL.md` alone, which drops the notes a skill names | user | decided |
| Fragment bodies live in their pointer targets, and `AGENTS.md` carries one pointer per fragment | fragment bodies composed into one block every session loads | user | decided |
| The publishing edges (`publishing a package`, `moving a shared registry tag`) come only from `ci-release`, which a release or publish sign selects; the `python` and `node-typescript` fragments declare none, and a project that publishes without those signs lists the edge in its local fragment's `edges:` | a publishing edge from every stack fragment, which an application that publishes nothing carries too; an engine switch that turns a fragment's edge off | agent | decided |
| Done is what `--done` records, in run order; `--detect` proposes, where a floor exists, `outcomebound floor check .`, `--base` the remote's default branch or `origin/main` where one resolves; then the CI test fact's first command, else discovery's first root check command; and refuses a target outside a Git work tree | Done read from a profile; discovery's candidate ahead of the command CI already runs | agent | decided |
| The CI test fact is adopt's reading; discovery's document is unchanged | a field in discovery's document | agent | decided |
| Precedence never names a file a harness documents as one person's | naming every file a harness may load, so an untracked file could make a checkout stale | agent | decided |
| `generic` serves a harness the table does not list: named as `--harness generic`, the default where none is named or recorded, and what `--detect` proposes where no harness file is found. Each skill goes once under `.outcomebound/skills/`, which the pointers name even beside native copies, and the install report reads `UNVERIFIED` that the harness reads `AGENTS.md`. Any other unlisted name is refused | no route for such a harness; the kernel alone, with no skill and no pointer | agent | decided |
| Selecting the `workspace` fragment also installs `.agents/.gitignore` from `templates/workspace.gitignore`, keeping its four folders out of Git, as its own record of kind `ignore`, owned whole; its first line sends any other ignore to the root `.gitignore`. `--detect` proposes it where one of those folders exists, not for `.agents/skills/`, which a Codex or Amp install writes | lines in the root `.gitignore`, which the managed-block markers do not fit; asking the adopter to ignore them by hand; a proposal for any `.agents/` folder | user | decided |
| `--detect` proposes `commands` everywhere: `detect: ["."]` matches every target | the habits in `workspace`; a kernel line | user | decided |
| `--detect` reads `CLAUDE.md` or `.claude/` as `claude-code`, `.codex/` as `codex`, `.cursor/` as `cursor`, and `GEMINI.md` or `.gemini/` as `gemini`; `AGENTS.md` alone names no harness. A test command it takes from discovery, not from CI, carries a comment that it runs on the host, so that a project that runs its tests only in a container gives that command instead | reading the project's rules to decide host or container, which a lexical read cannot settle | agent | decided |
| Discovery does not enter what Git ignores, which one `git ls-files --others --ignored --exclude-standard --directory` names without listing an ignored folder's contents, nor a folder holding its own `.git`; where Git lists nothing, its limits say no `.gitignore` was applied | a hand-written `.gitignore` reader; walking everything to the entry limit | agent | decided |
| Every install writes `.outcomebound/.gitignore`, a record of kind `ignore` and id `local-records`, owned whole: it keeps `research-inbox/` and every `.outcomebound-checks/` under `.outcomebound/` out of Git, which `research ingest` and `validation` write on this machine. A validation plan outside `.outcomebound/` writes its logs beside it, which the project ignores itself. A `.outcomebound/.gitignore` the project wrote, with no record, is refused by name, even under `--force`, so its lines are moved to the root `.gitignore` and not lost | lines in the root `.gitignore`, which the managed-block markers do not fit; asking each adopter to ignore them by hand | agent | decided |
| The install report warns, and refuses nothing: for each path the run writes that `git check-ignore` matches, naming the rule, since another clone never gets it and reads it missing; where the run changes a tracked `AGENTS.md` that holds changes not committed; and for each instruction file a selected harness also loads from a folder above the target, as its row's `ancestors` records (Claude Code: research `harnesses/claude-code.md` §1), whose paths resolve from that folder | refusing such an install; un-ignoring paths in the project's `.gitignore` | agent | decided |
| Where the install includes `codex`, the report prints one `UNVERIFIED` line with the route for unattended Desktop and IDE sessions, which are reported to have no `--add-dir` flag (`UNVERIFIED`: the research does not record it): add `<repository>/.agents` and the repository's Git common directory to `writable_roots` under `[sandbox_workspace_write]` in the person's Codex `config.toml`, since the default `workspace-write` sandbox keeps both read-only (research `harnesses/codex.md` §9). It is `UNVERIFIED` because the research documents neither that flag's absence nor the key, and because whether the harness can write those folders is not something adopt or `instructions check` can observe | adopt writing the person's Codex configuration, which is outside the target; a check that reports the harness's write access, which no file in the target shows | agent | decided |
| `--finish-check` writes a `hook` entry for `claude-code` and `codex`: the [finish-check design](../finish-check/design.md) | every harness | user | decided |

## Edges

Writes stay inside the target and go through `fileplan.write`: never through a symlink, never into
`.git` in any spelling, staged and renamed atomically, and refused when a file changed after it was
read. Every byte adopt did not write is preserved, save a settings document's whitespace and an
empty `hooks` object or `Stop` list it had, which `--remove` deletes; `--remove` restores a file
adopt created or extended to what it held before: the fragment copies, the skill folders and
`.agents/.gitignore` and `.outcomebound/.gitignore` go, the project's own `local.md` stays. Reading a fact runs nothing from the
target.

## Validation

`tests/test_adopt.py`, `tests/test_facts.py`, `tests/test_fragments.py`,
`tests/test_outcomebound_launcher.py` and `tests/test_paths.py`, run by the `adopt` claim; CI checks
this repository's own install with `scripts/outcomebound adopt . --check`.
