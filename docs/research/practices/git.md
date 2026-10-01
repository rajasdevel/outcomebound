---
last_checked: 2026-10-01
volatility: STABLE (Git keeps its porcelain formats and documented behaviour across releases; the probes name the version they ran on)
sources:
  - https://git-scm.com/docs/git
  - https://git-scm.com/docs/gitrevisions
  - https://git-scm.com/docs/git-ls-tree
  - https://git-scm.com/docs/git-status
  - https://git-scm.com/docs/git-update-index
  - https://git-scm.com/docs/git-ls-files
  - https://git-scm.com/docs/gitignore
  - https://git-scm.com/docs/gitattributes
  - https://git-scm.com/docs/git-config
  - https://git-scm.com/docs/git-archive
  - https://git-scm.com/docs/githooks
  - https://git-scm.com/docs/git-push
---

# Git behaviour that tools rely on

What Git does that a tool, a grader or an agent reading a repository relies on, and where it
surprises them.

Re-check when a Git release changes porcelain output, archive headers, `ls-tree` path handling,
filter or hook behaviour (read its release notes).

This reference answers what Git does underneath the commands that tools build on: reading a path at
a ref, what `git status --porcelain` shows and what it hides, configured programs that run during a
read, how Git finds the repository it acts on, how it lists and quotes paths, what an archive's
digest identifies, which hooks `--no-verify` skips, where Git keeps commit messages as plain text,
and which reads write to the repository. It is for anyone writing a check, an installer, a grader,
an evaluation fixture or an agent's procedure that reads a Git repository and acts on what it reads.

**Evidence classes.** (L) Git's own documentation on git-scm.com, read 2026-10-01; (O) a probe or
observation recorded in one repository's own runs, reviews and scratch repositories, with the Git
version named; (A) a reviewer's reading of source, not run. An (O) claim without an `[as-of]` tag
was re-run on git 2.56.0 on macOS on 2026-10-01; one with a tag is the observation recorded that
day, not re-run. The hardened read an instruction-file audit uses, and the configuration a hostile
checkout can plant, are in [writing-for-models.md](writing-for-models.md) §7.3; this reference
gives the Git behaviour underneath.

## Key findings

**GT1. A read of the working tree can run code the repository configures.** A clean or process
filter named by `.gitattributes`, `.git/info/attributes` or an invocation's `-c` settings runs when
`git diff` compares the working tree with the index, when `git status` must re-hash a file, and on
`git add`; `--no-ext-diff --no-textconv` does not stop it. Comparing tree to tree runs none, and
`git hash-object --no-filters` hashes the raw bytes. A clean filter can also make `git diff` report
no change while the working-tree bytes differ from the index. (O, L)

**GT2. `git status --porcelain` is not a content check.** It prints the same line for two different
contents of an already-modified file; the assume-unchanged and skip-worktree index bits hide edits
from `git diff` and `git status`; and a `.gitignore` that ignores itself hides new files from
`git status -uall`. To show a tree unchanged, compare file contents, modes, symbolic-link targets,
staged entries and the untracked files that existed before. (O, L)

**GT3. Reading a path at a ref has traps beyond absence.** `<ref>:<path>` resolves from the top of
the work tree whatever the working directory; a path under a directory that is a symbolic link at
the ref answers "exists on disk, but not in '<ref>'"; and `git show <ref>:<dir>` exits 0 with a tree
listing in place of a file's bytes. Walk the path's prefixes with `git ls-tree -z`, one path a call.
(O, L)

**GT4. Git finds the repository by walking up, and the environment can move it.** Run from a folder
an enclosing work tree ignores, `git ls-files` lists nothing and exits 0, and `git -C <dir>` reports
the enclosing repository's commit and remote; `GIT_DIR`, `GIT_WORK_TREE` and `core.worktree` make
`git rev-parse --show-toplevel` name another directory. Trust Git's answer about a directory only
when `--show-toplevel` is that directory. (O, L)

**GT5. An archive's digest identifies a commit, not a tree.** Given a commit or tag, `git archive`
stores the commit id in the tar's global pax header (a ZIP's comment) and dates every entry with the
commit time; given a tree, it dates entries with the current time. Two commits with one tree give
two digests. Record the tree id, or fix `--mtime` and archive the tree. (L, O)

**GT6. A hook is feedback, not a boundary.** `--no-verify` skips `pre-commit`, `commit-msg` and
`pre-merge-commit` on a commit or merge and `pre-push` on a push, and `core.hooksPath` replaces the
hooks directory. A rule that must hold belongs in a check the person controls outside the agent's
reach, such as a required CI job. (L, O)

**GT7. Git keeps commit messages as plain files.** `.git/COMMIT_EDITMSG` holds the last commit's
whole message and `.git/logs/HEAD` each commit's subject, so a fact meant to be reachable only
through `git log` is found by a plain-text search of `.git`. (O)

**GT8. Some reads write.** `git status` refreshes and writes the index, taking its lock, which can
make a concurrent Git command in the same checkout fail; `--no-optional-locks`, or
`GIT_OPTIONAL_LOCKS=0`, stops it. Set the variable on the tool's own Git calls only, never in the
environment of the commands it runs. (L, O)

**GT9. Without `-z`, Git quotes unusual path names.** A name with a non-ASCII byte comes out of
`git ls-files` as a C-style quoted string (`"na\303\257ve.py"`), and a reader that does not unquote
it skips that path in silence. Read `-z` output. (L, O)

## 1. Reading a path at a ref (GT3)

A tool that reads a policy file, a config or a baseline as it stood at a base commit reads it at a
ref. Each behaviour below was observed on git 2.55.0 on 2026-09-23 and re-run on git 2.56.0 on
2026-10-01 (O).

- **Where the path starts.** "A suffix `:` followed by a path names the blob or tree at the given
  path … A path starting with `./` or `../` is relative to the current working directory. The given
  path will be converted to be relative to the working tree's root directory" (L, gitrevisions). Run
  from a subdirectory, `git show HEAD:policy.toml` fails with `fatal: path 'real/policy.toml' exists,
  but not 'policy.toml'` and a hint offering `HEAD:./policy.toml`, so a tool run below the top reads
  another file or none (O).
- **A symbolic link at the ref.** For a path under a directory that is a symbolic link at the ref,
  `git show <ref>:<path>` answers `fatal: path '<path>' exists on disk, but not in '<ref>'`, while a
  path absent everywhere answers `does not exist in '<ref>'`. A reader that maps the first message to
  "absent" reads a policy file reached through a link as no policy (O).
- **A directory read as a file.** `git show <ref>:<dir>` exits 0 and prints `tree <ref>:<dir>`, a
  blank line and the entry names, which a reader expecting a file takes as its bytes (O).
- **Walking prefixes.** `git ls-tree -z <ref> -- <path>` prints one record, `<mode> SP <type> SP
  <object> TAB <path>`, or nothing with exit 0 when the path is absent or lies under a symbolic link
  (L, O). Paths are "taken as relative to the current working directory", and `--full-tree` ignores
  it (L, git-ls-tree). Paths are "a list of patterns to match", so pass one path a call: a trailing
  slash, or a second path inside a named directory, makes `ls-tree` list the directory's contents
  rather than its own entry (O). Modes seen: `100644` and `100755 blob` a file, `120000 blob` a
  symbolic link, `040000 tree` a directory; a `commit` entry is a submodule.
- **Symbolic links in Python.** `Path.is_symlink()` tests only the last component, so a glob match
  reached through a symlinked parent (`bin/run.sh` through `bin -> elsewhere`) passed a
  leaf-only check; test every ancestor (O, re-run on Python 3.14.7).
- **Symbolic links in a checkout.** Where `core.symlinks` is false, "symbolic links are checked out
  as small plain files containing the link text"; it defaults to false on Windows (L, git-config). A
  link in the tree is then a text file holding its target's path.

## 2. What `git status --porcelain` shows and hides (GT2)

`git status` "displays paths that have differences between the index file and the current HEAD
commit, paths that have differences between the working tree and the index file, and paths in the
working tree that are not tracked by Git"; in the short format "`X` shows the status of the index
and `Y` shows the status of the working tree" (L, git-status). It reports which paths differ, not
what they hold.

- **Two contents, one line.** A tracked file edited to `b`, then to `c`, printed ` M f.txt` both
  times (O). Equal status output before and after a step therefore does not show the step left the
  tree unchanged; a check that a tree is byte-identical compares contents and modes, symbolic-link
  targets, staged entries and the untracked files that existed before (O).
- **Index bits.** With the assume-unchanged bit "the user promises not to change the file and allows
  Git to assume that the working tree file matches what is recorded in the index"; skip-worktree
  tells Git to "treat the file as unchanged when it is not present" (L, git-update-index). After
  `git update-index --assume-unchanged g.py` and `--skip-worktree h.py`, edits to both files
  showed in neither `git diff` nor `git status` (O). `git ls-files -v` shows them: a lowercase letter
  for an assume-unchanged entry and `S` for a skip-worktree one (L, O). A model under test can set
  either bit, so a grader enumerates changes from the filesystem, not from Git state.
- **A self-ignoring `.gitignore`.** A `.gitignore` holding `*` ignores itself and every new file:
  `git status --porcelain -uall` printed nothing, and only `--ignored` listed the new file (O).
- **Ignore patterns.** "A trailing `/**` matches everything inside", so `abc/**` matches all files
  inside `abc` at any depth; "Other consecutive asterisks are considered regular asterisks"; and "It
  is not possible to re-include a file if a parent directory of that file is excluded" (L,
  gitignore). `git check-ignore` matched `x/f` and `x/y/z` against `x/**` and not `x` itself (O). A
  tool that translates ignore rules itself compares its answers with `git check-ignore`.

## 3. Configured programs a read can run (GT1)

"The `clean` command is used to convert the contents of worktree file upon checkin", and a
long-running `process` filter can serve "all blobs with a single filter invocation for the entire
life of a single Git command" (L, gitattributes). What runs it (O, git 2.56.0):

| Command | Ran a clean filter? |
| --- | --- |
| `git diff --no-ext-diff --no-textconv` over the working tree | yes |
| `git status` after a same-size edit that forced a re-hash | yes, also with `--no-optional-locks` |
| `git add` | yes |
| `git diff <tree> <tree>`, `git diff --cached` | no |

The filter ran when it came from `.git/info/attributes` with repository config, and when both came
from the invocation (`-c core.attributesFile=… -c filter.<driver>.clean=…`). A preview command that
only ran `git diff` executed one (O) [as-of 2026-09-09].

A clean filter can also hide a change: with a filter that printed the committed text, `git diff`
reported nothing while the file's bytes differed from the index (`git hash-object --no-filters`
gave another id than `git ls-files -s`) (O).

To compare a working tree with its index without running anything: read the index with
`git ls-files -s -z`, and `-v` for the index bits; read blobs with `git cat-file --batch`; hash each
file with `git hash-object --no-filters --stdin` in the repository's object format
(`git rev-parse --show-object-format`, `sha1` or `sha256`); and compare the file type and executable
bit. A gitlink (mode 160000) has no blob to compare. Under `core.autocrlf` or a smudge filter the
working-tree bytes differ from the blobs by design, so such a comparison refuses rather than passes
(O; the last point reasoned, not reproduced) [as-of 2026-09-11].

Filters are one of several configured programs. `core.fsmonitor`, a `diff` driver's `textconv`,
`diff.external`, `core.pager`, hooks, `core.sshCommand`, `gpg.program` and aliases also run code a
checkout names; [writing-for-models.md](writing-for-models.md) §7.3 lists them and the hardened read
that runs none.

## 4. Finding the repository (GT4)

"When run in a directory that does not have `.git` repository directory, Git tries to find such a
directory in the parent directories to find the top of the working tree" (L, git).

- **An ignored folder inside another checkout.** In a folder that an enclosing work tree ignores,
  `git rev-parse --show-toplevel` named the enclosing repository and
  `git ls-files --cached --others --exclude-standard` printed nothing and exited 0, since that
  repository tracks nothing there (O). A build that listed its files this way, run from a source
  archive unpacked under such a folder (a `TMPDIR` or cache directory inside a checkout), produced a
  wheel without its package and exited 0 (O, pip 26.2.1; see
  [releasing.md](releasing.md) §5). Tests that need a directory outside any work tree fail the same
  way when pytest's `--basetemp` sits inside a checkout, even in an ignored folder; CI's
  `$RUNNER_TEMP` lies outside the checkout, so they fail only locally (O).
- **Provenance.** `git -C <source>` on a copy nested inside another repository recorded the
  enclosing project's `HEAD` and `origin` as the source's (O) [as-of 2026-09-09].
- **The environment.** `GIT_DIR` "specifies a path to use instead of the default `.git`", and
  `GIT_WORK_TREE` sets "the root of the working tree", as `core.worktree` does; a relative
  `core.worktree` "is relative to the `.git` directory, not to the current working directory" (L,
  git, git-config). With `GIT_DIR` and `GIT_WORK_TREE` naming a sibling repository,
  `--show-toplevel` named the sibling; with `GIT_DIR` alone it named the current directory; a
  repository whose `core.worktree` named another directory reported that directory (O). Set to a
  sibling, they made a tool's path computation relative to the top fail (O) [as-of 2026-09-24].
- **Remedies.** Accept Git's answer about a directory only when `git rev-parse --show-toplevel` is
  that directory, and record the commit as unknown otherwise; unset `GIT_DIR`, `GIT_WORK_TREE` and
  `GIT_INDEX_FILE` for a tool's own Git calls; `GIT_CEILING_DIRECTORIES` names directories Git
  "should not chdir up into while looking for a repository directory" (L, git).

## 5. Listing and quoting paths (GT9)

- **Quoting.** "Without the `-z` option, pathnames with 'unusual' characters are quoted as explained
  for the configuration variable `core.quotePath`"; with `-z` they "are printed as is and without
  any quoting" (L, git-status; `ls-files -z`: "do not quote filenames"). `git ls-files` printed
  `"na\303\257ve.py"` for `naïve.py` (O). A check that found scripts this way skipped such a path in
  silence (O, git 2.55.0) [as-of 2026-09-23].
- **Tracked files, not the filesystem.** A structure check that ran every executable `*.py` it found
  with `rglob` executed copies of the repository in nested worktrees that `.git/info/exclude` hid
  from Git; a project's virtual environment or build directory would be run the same way. Walk
  `git ls-files -z`, and read an empty listing (no repository, no Git, nothing tracked) as
  `UNVERIFIED`, never as a pass (O, git 2.55.0) [as-of 2026-09-23].
- **Untracked files.** `--others` adds untracked files and `--exclude-standard` the standard
  exclusions (L, git-ls-files); a build that listed `--cached --others --exclude-standard` shipped an
  untracked, unignored `.env` (O). List `--cached` for what a release ships.

## 6. Archives and digests (GT5)

Given a commit or tag, "the commit time as recorded in the referenced commit object is used as the
modification time of each file in the archive", and "the commit ID is stored in a global extended
pax header if the tar format is used; it can be extracted using `git get-tar-commit-id`", or as the
comment of a ZIP file; given a tree, "the current time is used as the modification time" and no
commit id is stored; `--mtime=<time>` sets the time instead (L, git-archive).

Observed (O, git 2.56.0): archives of a commit and of its own tree had different digests; an empty
commit on top of the same tree changed the commit archive's digest; two archives of one tree taken
a second apart differed, and with `--mtime='1970-01-02 00:00:00 +0000'` they were byte-identical
(`--mtime=@0` did not fix the time). A `git archive` digest taken before a release's final commit
is not reproducible from that commit by the command recorded beside it (O) [as-of 2026-09-06]. A
digest that should identify a release's files records the tree id, or archives the
tree with a fixed `--mtime` by a stated procedure.

## 7. Hooks and `--no-verify` (GT6)

`pre-commit` "can be bypassed with the `--no-verify` option", as can `commit-msg` and
`pre-merge-commit`; for `git push`, "With `--no-verify`, the hook is bypassed completely"; and "the
hooks directory is `$GIT_DIR/hooks`, but that can be changed via the `core.hooksPath` configuration
variable" (L, githooks, git-push). With failing `pre-commit` and `commit-msg` hooks installed, a
plain commit failed while `--no-verify`, `-n` and `-c core.hooksPath=/dev/null` each committed (O).
A floor or policy run only from a hook is therefore skipped whenever the committer chooses; a hook
shortens feedback, and a boundary needs a check the person controls outside the agent's reach (L).

## 8. Plain-text copies of commit messages (GT7)

After a commit, `.git/COMMIT_EDITMSG` held its whole message, body included, and the last line of
`.git/logs/HEAD` ended `commit: <subject>` (O). An evaluation fixture whose deciding fact must be
reachable only through `git log` therefore deletes `COMMIT_EDITMSG`, keeps the fact out of subject
lines, and tests that no plain file under `.git` outside `objects/` names it; it also sets a fixed
author, committer and commit dates inside its own setup, so the caller's `GIT_AUTHOR_*` and
`GIT_COMMITTER_*` variables cannot change the seed commit. Built under bash 5 with GNU sed, under
bash 3.2 with BSD sed, and with those variables set by the caller, one such fixture made the same
seed commit each time (O) [as-of 2026-09-25]. [evaluations.md](evaluations.md) holds the
fixture lessons this serves.

## 9. Reads that write (GT8)

"By default, `git status` will automatically refresh the index, updating the cached stat
information from the working tree and writing out the result"; the write's lock "may conflict with
other simultaneous processes, causing them to fail", and "Scripts running `status` in the background
should consider using `git --no-optional-locks status`" (L, git-status), which is "equivalent to
setting the `GIT_OPTIONAL_LOCKS` to `0`" (L, git). After a file was touched, `git status` rewrote
`.git/index`; with `GIT_OPTIONAL_LOCKS=0` it did not (O). A check that runs `git status` after each
of its steps without the switch takes `index.lock` on every run, in a checkout other agents may
share (A, read from one check's source). A runner that set `GIT_OPTIONAL_LOCKS=0` process-wide for
its own Git calls passed it on to every project command it ran (O) [as-of 2026-09-09]; scope it to
the runner's own calls.

## How to apply

For a tool, a grader or a fixture that reads a Git repository:

1. Resolve the repository first: require `git rev-parse --show-toplevel` to be the directory meant,
   and unset `GIT_DIR`, `GIT_WORK_TREE` and `GIT_INDEX_FILE` for the tool's own calls (GT4).
2. Read at a ref by walking prefixes with `git ls-tree -z`, one path a call and `--full-tree` below
   the top; treat a symbolic link on the path, a tree where a file was expected and an unknown mode
   as their own answers, never as absence (GT3).
3. Compare trees, not the working tree, when nothing may run; when the working tree must be read,
   hash it with `--no-filters` and read the index with `ls-files -s -z -v` (GT1).
4. Never read "unchanged" from `git status`; compare contents, modes, link targets, staged entries
   and pre-existing untracked files, and enumerate a model's changes from the filesystem (GT2).
5. List paths with `-z`; list `--cached` for what ships; read an empty listing as `UNVERIFIED`
   (GT9).
6. Identify a release's files by tree id, or by an archive of the tree with a fixed `--mtime` (GT5).
7. Put a boundary in a check the agent cannot skip; keep hooks for feedback (GT6).
8. In a fixture that hides a fact in history, delete `.git/COMMIT_EDITMSG`, keep the fact out of
   subjects and fix the identity and dates (GT7).
9. Run background reads with `--no-optional-locks`, scoped to the tool's own Git calls (GT8).

## Limits and open questions

- The probes ran on macOS with git 2.55.0 and 2.56.0; Windows checkouts, `core.autocrlf` and
  SHA-256 repositories were not tried, and the refusal under line-ending conversion is reasoned, not
  reproduced.
- `git status` re-hashes a file, and so runs a clean filter, only when its cached stat information
  no longer matches; which edits trigger that depends on the file system's timestamps.
- Whether `--mtime` accepts an epoch form was not settled; a full date worked.

## Sources

Git documentation on git-scm.com, read 2026-10-01: [git](https://git-scm.com/docs/git) (2.56.0),
[gitrevisions](https://git-scm.com/docs/gitrevisions) (2.56.0),
[git-ls-tree](https://git-scm.com/docs/git-ls-tree) (2.42.0),
[git-status](https://git-scm.com/docs/git-status) (2.53.0),
[git-update-index](https://git-scm.com/docs/git-update-index) (2.52.0),
[git-ls-files](https://git-scm.com/docs/git-ls-files) (2.55.0),
[gitignore](https://git-scm.com/docs/gitignore) (2.55.0),
[gitattributes](https://git-scm.com/docs/gitattributes) (2.56.0),
[git-config](https://git-scm.com/docs/git-config) (2.56.0),
[git-archive](https://git-scm.com/docs/git-archive) (2.54.0),
[githooks](https://git-scm.com/docs/githooks) (2.54.0) and
[git-push](https://git-scm.com/docs/git-push) (2.55.0); the version in brackets is the release in
which each page last changed. Probes: scratch repositories on git 2.56.0, 2026-10-01, re-running
observations first recorded on git 2.55.0 in one repository's reviews, work records and evaluation
fixtures (September 2026); Python 3.14.7 for `Path.is_symlink()`.
