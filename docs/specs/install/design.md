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
`outcomebound_tools/adopt.py`, `outcomebound_tools/facts.py` and `outcomebound_tools/fragments.py`,
each opening with what it decides; how `outcomebound` is installed and launched is the
[distribution design](../distribution/design.md).

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
test:ci`, `go test`, `bash scripts/run-tests.sh`), after wrappers such as `uv run` or `npx`; `make
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
names each act once; and `skills:`, a JSON list of the engine skills its selection installs.
`fragments compose` renders both blocks for a selection; `--inline` emits the kernel, the skills
an install would carry and the fragment bodies, for a delegate's role prompt.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| One route, `outcomebound adopt` | a second, modular install route beside it | user | decided |
| Re-running is the upgrade, and Git is the undo | three-way merges against copies of every release | user | decided |
| No backward compatibility: a manifest of another format is refused, even under `--force` | migrating its records, whose shape would sit beside format 2's for the same paths | user | decided |
| The manifest (format 2) holds one `{kind, path, id, sha256}` record per owned block or file, written last | per-artifact base caches, source receipts and bundle digests | agent | decided |
| An owned block or file whose bytes differ from its record is refused without `--force` | overwriting it, or merging | agent | decided |
| `--check` ends, when a record is not current, with the command that makes it current | one `doctor` verb over every layer, recording each choice declined | agent | decided |
| A harness that cannot be made to load `AGENTS.md` is refused before any write | a reminder and exit 0, which leaves an install nothing loads | agent | decided |
| A harness's host file gets an `@AGENTS.md` import block, except where the harness table's row records `reads_agents_md` and none of the files it lists is in the target: that harness reads `AGENTS.md` itself, and no host file is written | creating the host file on every install for that harness | user | decided |
| An install prints the words an agent always loads, its blocks and each skill's description a harness lists, and no size refuses it | a size ceiling that refuses an install | user | decided |
| One native copy per harness of each skill an install carries | a canonical `.outcomebound/skills/` copy beside the native ones | agent | decided |
| An install carries the four default skills and each skill a selected fragment's `skills:` names, as `tickets` names `slice-tickets`; the [skills design](../skills/design.md) says which and why. A skill is its whole folder, `SKILL.md` and every file beside it, one record per file: `--check` reports each, a recorded file the skill does not ship reads `stale`, and `--remove`, or deselecting its fragment, removes it | every shipped skill in every install; `SKILL.md` alone, which drops the notes a skill names | user | decided |
| Fragment bodies live in their pointer targets, and `AGENTS.md` carries one pointer per fragment | fragment bodies composed into one block every session loads | user | decided |
| Done is what `--done` records, in run order; `--detect` proposes the floor's runner, `outcomebound floor check . --base origin/main`, where a floor is installed, then the first test command the CI test fact reads, or, where CI names none, discovery's first check command for the root. Like the install, `--detect` refuses a target outside a Git work tree | Done read from a profile; discovery's candidate ahead of the command CI already runs | agent | decided |
| The CI test fact is adopt's reading; discovery's document is unchanged | a field in discovery's document | agent | decided |
| Precedence never names a file a harness documents as one person's | naming every file a harness may load, so an untracked file could make a checkout stale | agent | decided |
| `generic` serves a harness the table does not list: named as `--harness generic`, the default where none is named or recorded, and what `--detect` proposes where no harness file is found. Each skill goes once under `.outcomebound/skills/`, which the pointers name even beside native copies, and the install report reads `UNVERIFIED` that the harness reads `AGENTS.md`. Any other name the table does not list is refused | no route for such a harness; the kernel alone, with no skill and no pointer | agent | decided |
| Selecting the `workspace` fragment also installs `.agents/.gitignore` from `templates/workspace.gitignore`, keeping its four folders out of Git, as its own record of kind `ignore`, owned whole; its first line sends any other ignore to the root `.gitignore` | lines in the root `.gitignore`, whose `#` comments the managed-block markers do not fit; asking the adopter to ignore them by hand | user | decided |
| `--finish-check` writes a `hook` entry for `claude-code` and `codex`: the [finish-check design](../finish-check/design.md) | every harness | user | decided |

## Edges

Writes stay inside the target and go through `fileplan.write`: never through a symlink, never into
`.git` in any spelling, staged and renamed atomically, and refused when a file changed after it was
read. Every byte adopt did not write is preserved, save a settings document's whitespace and an
empty `hooks` object or `Stop` list it had, which `--remove` deletes; `--remove` restores a file
adopt created or extended to what it held before: the fragment copies, the skill folders and
`.agents/.gitignore` go, the project's own `local.md` stays. Reading a fact runs nothing from the
target.

## Validation

`tests/test_adopt.py`, `tests/test_facts.py`, `tests/test_fragments.py`,
`tests/test_outcomebound_launcher.py` and `tests/test_paths.py`, run by the `adopt` claim; CI checks
this repository's own install with `scripts/outcomebound adopt . --check`.
