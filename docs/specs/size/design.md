---
name: size
status: ratified
---

# Size — design

## Outcome

An agent that builds a change can ask, at any time, how big the change is against the base that
matters, and what kind of lines it holds. It gets one cheap fact. A change once grew to tens of
thousands of lines against the production release, and most of the lines were test fixtures and
records. The agent never saw that number.

The one invariant `outcomebound size` holds: the counts are what Git reports for the work tree
against the base, plus the lines of the untracked files that Git does not ignore, and each count is
placed in one kind by the path alone. How: `outcomebound_tools/size.py`.

The verb does not say that a change is too big, and it does not say that a line was needed. A
person or an agent decides that. The verb runs no project command and writes nothing.

## Use

`outcomebound size [<target>] [--base REF] [--json]`. The target is a Git work tree (default `.`).
When the target is a folder inside a work tree, the verb measures the whole work tree.

The base is one of these, in this order:

1. `--base REF`. The verb measures the work tree against that commit as it is. It does not take a
   merge base. For stability work, the base is the release tag in production, for example
   `--base v1.4.3`.
2. The merge base of `HEAD` with the upstream of the current branch.
3. The merge base of `HEAD` with `origin/HEAD`.

If none of these exists, the verb refuses with `SIZE_BASE_MISSING` and names `--base`. If the
upstream of the branch is a pushed copy of the same branch, the default measures only what is not
pushed. In that case, name the base with `--base`.

The report has one line for each kind that is present: files, `+added`, `-removed` and net. It
has a total line, and the share of the added lines that are not `code`. With `--json`, the verb
prints the same data as one JSON object. The object holds `version`, `base` (`ref`, `how`,
`commit`), `kinds`, `total`, `non_code_share_of_added` (null where no line was added), and the
lists `binary` and `too_large` and the counts `untracked_files` and `skipped_untracked`.

Exits: 0 for a report; 1 where Git fails (the message holds the text of Git) or the base cannot be
found; 2 for a usage error.

## The count

- Tracked files: `git diff-index --numstat -M` against the base commit. It reports committed and
  uncommitted tracked changes together. A rename is one entry, at its new path. A binary file is
  one file with no lines.
- Untracked files: one `git ls-files --others --exclude-standard`. Each file counts as added lines.
  The verb reads at most 2 MB of a file. A larger file counts as one file with no lines, and a
  note names it. A file with a NUL byte in its first 8000 bytes is binary, as Git decides. A
  symbolic link counts as one line. An entry that is no file, such as a nested repository, is not
  counted, and a note says how many.

## The kinds

The first match wins. The match uses the path alone, with case folded.

| Kind | Paths |
| --- | --- |
| `records` | anything under `.agents/` or `.outcomebound/` at the top of the work tree |
| `tests` | a folder named `test`, `tests`, `__tests__`, `spec`, `specs` (but not `docs/specs`), `fixtures` or `testdata`; or a file named `test_*`, `*_test.*`, `*.test.*`, `*.spec.*` or `conftest.py` |
| `docs` | `*.md`, `*.rst`, `*.txt`, `*.adoc`, or anything under a folder named `docs` |
| `config` | CI files, `*.json`, `*.yaml`, `*.yml`, `*.toml`, `*.ini`, `*.cfg`, lock files |
| `code` | everything else |

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| The kind comes from the path alone, in a fixed order, and the order is in `--help` | a file-content test, which is slow and gives a different answer in each run; a project-set table, which is a configuration that nobody keeps | agent | decided |
| An explicit `--base` is the commit itself; only the default takes a merge base | a merge base always, which hides the work of a branch that has not forked from the release tag | agent | decided |
| The tracked count uses `git diff-index`, not `git diff`. The porcelain refreshes the index and writes it, even with `GIT_OPTIONAL_LOCKS=0` (seen with Git 2.56); a test holds that nothing is written | `git diff`, which writes the index of the project | agent | decided |
| The verb has no limit and no pass or fail. It reports a fact | a threshold with an exit code, which no evidence supports | agent | decided |
| The 2 MB bound on an untracked file protects the run time on a large work tree. A larger file is named, not guessed | reading every file, which stalls on a build output that is not ignored | agent | assumed |
| `requirements*.txt` and `CMakeLists.txt` count as `docs`, because the rule for `*.txt` comes first. The share of non-code lines is a little high for such a project | a special case for each file name, which grows without end | agent | assumed |

## Validation

`tests/test_size.py`, with temporary Git repositories: the kind of each path; committed,
uncommitted, staged, renamed and untracked changes; ignored files; binary files; the size bound; a
default base from an upstream and from `origin/HEAD`; an explicit base that is not a merge base; the
refusals; the shape of the JSON report; and that a run changes no file, the index included. The
verb is in the launcher help tests.
