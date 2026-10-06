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
`outcomebound_tools/adopt.py`, `outcomebound_tools/facts.py`, `outcomebound_tools/fragments.py` and `outcomebound_tools/textio.py`;
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
path read, with its sha256. `--check` recomputes the block: bytes other than both the record's and
the recomputation's read `edited`; a record other than the recomputation reads `stale`, naming each
fact that moved and each input that changed, or, where the bytes are the recomputation's, saying
so.

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
| The manifest (format 2) holds one `{kind, path, id, sha256}` record per owned block or file, written last. Where the `local` fragment is selected, the `guidance-pointers` record also holds the optional field `frame`: the sha256 of the block with the local fragment's inline text (its `**local** (<family>) — <applies>` line, a blank line and its body, as the block renders it) replaced by the mark `\0local\0` (a NUL character, `local`, a NUL character). A record is read with or without it; an engine of 1.1.1 or earlier reads a record that holds it, ignores it and drops it when it writes the manifest again | per-artifact base caches, source receipts and bundle digests; a format 3 for the one field, which an engine of 1.1.1 or earlier refuses, so each machine and CI job that pins one breaks once a person upgrades; the local fragment's text in the record, which copies the project's own file into the manifest; the digests of the inputs alone, which show that the source changed but not that nothing else in the block changed; a digest of the render for each source version, which this engine cannot compute for the release that wrote the record | agent | decided |
| A `guidance-pointers` block whose bytes differ from both its record and what this install writes is no edit where it is the recorded render with only the local fragment's inline text changed to what the fragment holds now: the source's edit, as the release that wrote the record renders it. The install writes it again without `--force` and names it on a `render` line, and `--check` reads it `stale`, saying so. The record's `frame` decides it. A record without `frame`, as an engine of 1.1.1 or earlier writes it, makes adopt read each earlier text of `.outcomebound/fragments/local.md` from the target's Git history (`git rev-list --all`, then `git cat-file --batch`) and takes the block as the source's edit where one of them, put in place of the inline text, gives the record's digest. Where neither decides, the block is refused as before | `frame` alone, which sends every install made before it to `--force` on the upgrade that brings it; the Git history alone, which an install never committed, or a shallow clone, does not hold; the same rule for the facts block, whose lines are derived from their sources, not copied, so no mark can stand in for them | agent | decided |
| An owned block or file whose bytes differ from its record is refused without `--force`, unless they are byte for byte what this install writes there: such bytes are no person's edit, so the install records them and its report names each on a `kept` line, and `--check` reads the record `stale`, saying so, with a next step that needs no `--force`. Bytes that differ from both are refused as before, save the source's edit the next row decides, so a person's edit is never overwritten without `--force` | overwriting it, or merging; refusing bytes this install writes too, which sends a person who changed the local fragment and its rendered block in one commit to `--force`, which also overrides the refusals that protect an edit; reading the block as `current` while its record is behind, so that the next change to its source reads as an edit | agent | decided |
| `--check` ends, when a record is not current, with the command that makes it current | one `doctor` verb over every layer, recording each choice declined | agent | decided |
| A harness that cannot be made to load `AGENTS.md` is refused before any write | a reminder and exit 0, leaving an install nothing loads | agent | decided |
| A harness's host file gets an `@AGENTS.md` import block, except where the harness table's row records `reads_agents_md` and none of the files it lists is in the target: that harness reads `AGENTS.md` itself | creating the host file for that harness | user | decided |
| An install prints the words an agent always loads, skill descriptions included, and warns where a folder's root-down instructions pass a row's `doc_byte_cap` (research `harnesses/codex.md` §2); no size refuses it | a size ceiling | user | decided |
| The byte-cap warning measures the folders another clone gets: it does not enter what Git ignores (`discovery.git_ignored`, as discovery reads it), a nested repository, `.git` or a link, and a folder that cannot be listed is passed over, never an error | measuring every folder, so that each scratch copy of the project in an ignored folder gives its own warning; stopping the install on a folder the user cannot read | agent | decided |
| One native copy per harness of each skill an install carries | a canonical `.outcomebound/skills/` copy beside the native ones | agent | decided |
| An install carries the four default skills and each skill a selected fragment's `skills:` names; the [skills design](../skills/design.md) says which and why. A skill is its whole folder, `SKILL.md` and every file beside it, one record per file: `--check` reports each, a recorded file the skill does not ship reads `stale`, and `--remove`, or deselecting its fragment, removes it | every shipped skill in every install; `SKILL.md` alone, which drops the notes a skill names | user | decided |
| Fragment bodies live in their pointer targets, and `AGENTS.md` carries one pointer per fragment | fragment bodies composed into one block every session loads | user | decided |
| The publishing edges (`publishing a package`, `moving a shared registry tag`) come only from `ci-release`, which a release or publish sign selects; the `python` and `node-typescript` fragments declare none, and a project that publishes without those signs lists the edge in its local fragment's `edges:` | a publishing edge from every stack fragment, which an application that publishes nothing carries too; an engine switch that turns a fragment's edge off | agent | decided |
| `--detect` proposes `runtime` where a file shows a runnable app or service (`Procfile`, a Compose file, `manage.py`, a `next`, `vite` or `playwright` config) and `deploy` where one shows deployment configuration (`fly.toml`, `vercel.json`, `netlify.toml`, `render.yaml`, `wrangler.toml`, `serverless.yml`, `Chart.yaml`, `skaffold.yaml`, `app.yaml`, a `deploy*` workflow, `*.tf`); a `Dockerfile`, a CI workflow or a package manifest alone proposes neither, since a library has them too | `detect: ["."]` for either, which loads deploy text into a project that deploys nothing; `Dockerfile` as a sign of either | agent | decided |
| The `deploy` fragment declares no `edges:`: which acts on a shared or production environment cannot be undone differs by project, so each project lists its own in its local fragment's `edges:`, and the generated Irreversible edges fact is never edited by hand. Browser, page and log content is data, stated once in `commands`, which `--detect` proposes everywhere | production edges declared by `deploy` for every project that selects it; the data rule restated in `runtime` | agent | decided |
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
| Where `.outcomebound/tickets.json` declares a claims plan that `tickets` can read, the install report warns where that plan's claims would run in a folder it was not written for: once for each claim whose declared `required_paths` are absent from the plan's working directory but present from the checkout root, and once where that working directory is the plan file's own folder below the checkout root (no `cwd`, or `"cwd": "."`). The line says what to write, `"cwd": ".."` from `.outcomebound/`. A declared path absent from both is planned, one a ticket's work will add, and is not reported, so the report never tells a plan whose `cwd` already runs at the root to change it. `tickets_claims.placement` decides it, the rule `tickets check` warns on, and an upgrade is where a plan written before a relative `cwd` started at the plan file's folder first meets that rule. It writes nothing to the plan and refuses nothing, since the plan is the project's file; with no declaration or no readable plan it says nothing, since `tickets check` refuses those; `--check` does not report it, since it reads only the install's own records | rewriting the plan's `cwd`, a write to a file the project owns; refusing the upgrade; leaving the report to `tickets check`, which an upgrade does not run | agent | decided |
| Where the install includes `codex`, the report prints one `UNVERIFIED` line with the route for unattended Desktop and IDE sessions, which are reported to have no `--add-dir` flag (`UNVERIFIED`: the research does not record it): add `<repository>/.agents` and the repository's Git common directory to `writable_roots` under `[sandbox_workspace_write]` in the person's Codex `config.toml`, since the default `workspace-write` sandbox keeps both read-only (research `harnesses/codex.md` §9). It is `UNVERIFIED` because the research documents neither that flag's absence nor the key, and because whether the harness can write those folders is not something adopt or `instructions check` can observe | adopt writing the person's Codex configuration, which is outside the target; a check that reports the harness's write access, which no file in the target shows | agent | decided |
| `--finish-check` writes a `hook` entry for `claude-code` and `codex`: the [finish-check design](../finish-check/design.md) | every harness | user | decided |
| A record's `sha256` is the digest of the artifact's text with CRLF as LF, for each block, each file adopt owns and each fragment or skill the engine ships. Adopt reads every owned artifact in that form, in `--check`, in an upgrade and in `--remove`, so a checkout that Git gave CRLF reads as it does with LF. A record written by 1.2.0 or earlier is read as it is: those releases wrote LF, so each digest is of LF text, and no marker, migration or format change is needed. A record of CRLF bytes (an engine checked out with CRLF) never matches the folded text: it reads `stale` where the engine renders the same text as before, else `edited`, and `--force` writes it again | digesting the raw bytes, which reads every record `edited` in a Windows checkout with `core.autocrlf`; a manifest format 3 that marks the line ending; accepting the digest of either form | agent | decided |
| Adopt writes into a file in the line ending that file has: CRLF where most of its line endings are CRLF, else LF; a new file is LF. A host whose text no block changed keeps its bytes, and a UTF-8 byte-order mark stays where it was. A host with mixed line endings keeps every line the blocks did not touch as it was, and the lines a block writes take the ending most of its lines use. Between identical neighbouring lines the alignment can move an ending from one of them to another; the content and every byte of unchanged text are kept. A removal gives a host back byte for byte, a mixed one too. `--check` and an upgrade read a file with a mark. The `local` fragment parses with CRLF and with a mark, and its digest is of the LF text | writing LF always, which mixes line endings in a CRLF host and rewrites every line of an owned file; writing CRLF on Windows, since a checkout does not follow the platform; a `.gitattributes` written into the target, which edits the adopter's repository beyond adopt's own files | agent | decided |
| This repository has a `.gitattributes` with `* text=auto eol=lf`. Every checkout of the engine, with any `core.autocrlf`, holds its skills, fragments and templates as LF, and the engine reads them in LF form, so an engine checked out with CRLF installs the same bytes as one with LF. It holds no binary file; `text=auto` leaves one alone | LF in the checkout only, with the engine reading raw bytes; converting only when the wheel is built | agent | decided |
| Every text the engine reads names UTF-8, accepts a byte-order mark, and decodes bytes itself: a standard input is read as bytes. An export and a standard input also accept UTF-16 with a mark, which Windows PowerShell 5.1 writes for a redirected file. The engine writes UTF-8 and LF | the console's code page, which decodes the same bytes differently by machine; refusing a file with a mark | agent | decided |
| A path in a report, a manifest, a record or a printed command is in POSIX form (`as_posix`). A command the engine prints for a person to run quotes each word with `shlex.quote` on POSIX. On Windows it quotes a word that is not plain in single quotes and doubles an apostrophe inside, which PowerShell and Git Bash both read whole, and it writes a path with forward slashes, which every Windows shell and program takes. cmd takes no single quotes, so such a command is for PowerShell or Git Bash. The `writable_roots` line prints POSIX-form paths in double quotes, since the backslash of a Windows path starts a TOML escape | finding the shell and quoting for it, which no variable tells reliably; double quotes, which PowerShell and Git Bash expand; TOML literal strings of native paths, which an apostrophe in a path breaks | agent | decided |
| The writer refuses a path that Windows cannot make a file of, on Windows only: a character of `< > " ? *` or the vertical bar, a device name with any extension (`CON`, `NUL`, `aux.txt`, `COM1` to `LPT9`), and a name that ends in a dot or a space. It refuses a directory junction on a destination's path as it refuses a symlink, and no other reparse point, since a cloud folder's placeholders carry their own. It tries a rename again a few times, after a short wait, when Windows refuses it, since a scanner or an editor holds the file for a moment | widening the path grammar, which would refuse paths that a recorded manifest holds; treating every reparse point as a link, which refuses a project in a synced folder; stopping at the first refused rename, which leaves an install half written | agent | decided |
| A name only Windows cannot hold (a device name, a character its file names lack, a trailing dot or space) is refused on Windows and written on every other platform. The engine's own paths are fixed names that hold none, and a name a project chose is not refused on a machine that can hold it: the writer says nothing of where the tree goes next, and Git on a Windows machine refuses such a name when it checks the tree out, which no engine decides. A test of the other platforms' behaviour runs where the file system holds the name and skips on Windows, with its reason | the same refusal on every platform, which stops a person on macOS or Linux from writing a file that their machine holds and their project may need, to protect a checkout the engine does not make; widening the path grammar, which would refuse paths that a recorded manifest holds | agent | decided |
| Discovery proposes the project's test commands with the Python of the host: `python -m pytest` and `python -m unittest discover -s tests` on Windows, where the installer from python.org and uv put `python` on PATH and `python3` is at most a Store alias that does not run, and `python3 -m ...` everywhere else. `declared_tests.PYTHON`, `PYTEST` and `UNITTEST` name them, and each test compares with those constants. A proposal stays a candidate that a person confirms, and `--detect` reads files only | choosing from what PATH holds when the proposal is made, which makes it depend on what is installed that day; `python` on every platform, which Debian and macOS lack | agent | decided |
| Every Git that the install, discovery, the harness-root read and `research` start is found with `programs.require("git")`: PATH's absolute entries only, with each `PATHEXT` extension on Windows. A bare `git` in the argv lets `CreateProcess` look in the current folder first, which is the target's own. A missing Git ends as `FileNotFoundError`, which each of those callers already reads as no Git | a bare `git`, which a target can answer for on Windows; one lookup at import, which a test cannot change | agent | decided |
| The upgrade corpus builds an earlier release's engine from `git archive` with `core.autocrlf=false`, and commits the bytes it writes with the same setting. A tag that has no `.gitattributes` gets CRLF from a Git whose default is `core.autocrlf=true`, which is every Git for Windows, and that release cannot read its own fragments then. That is a fact of the earlier release, which no change here repairs. The candidate's reading of a CRLF install is its own case, `crlf-checkout`, which writes the CRLF bytes itself | skipping an earlier release on Windows, which drops the upgrade check where CRLF is most likely; changing the extracted files after the archive, which tests a tree no adopter has | agent | decided |

## Edges

Writes stay inside the target and go through `fileplan.write`: never through a symlink (on Windows, nor a junction), never into
`.git` in any spelling, staged and renamed atomically, and refused when a file changed after it was
read. Every byte adopt did not write is preserved, save a settings document's whitespace and an
empty `hooks` object or `Stop` list it had, which `--remove` deletes; `--remove` restores a file
adopt created or extended to what it held before: the fragment copies, the skill folders and
`.agents/.gitignore` and `.outcomebound/.gitignore` go, the project's own `local.md` stays. Reading a fact runs nothing from the
target.

A project can edit a rendered block and its source in the same way, while the release also
changes how that block renders. For the `guidance-pointers` block and the `local` fragment it
inlines, adopt decides each case without `--force`:

| Block bytes on disk | adopt |
| --- | --- |
| equal to the record | updates it |
| equal to the new render | records it, on a `kept` line |
| equal to neither: the source's edit, rendered by the release that wrote the record | updates it, on a `render` line |
| equal to neither: a person's edit | refuses without `--force` |

The record's `frame`, or for a record without it the local fragment's earlier text in Git, tells
the last two rows apart. A record without `frame` whose earlier fragment text Git does not hold
reads as a person's edit, so it is refused without `--force`. `tests/test_upgrade_corpus.py` holds each
row, from 1.0.0 and from the newest release, with a candidate that renders the block anew.

## Validation

`tests/test_adopt.py`, `tests/test_adopt_line_endings.py`, `tests/test_facts.py`,
`tests/test_fragments.py`, `tests/test_fileplan.py`, `tests/test_textio.py`,
`tests/test_outcomebound_launcher.py` and `tests/test_paths.py`, run by the `adopt` claim; CI checks
this repository's own install with `scripts/outcomebound adopt . --check`.
