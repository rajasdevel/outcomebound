# Releasing records

Since September 2026, `CHANGELOG.md` is written at release from the commit subjects, by
`scripts/release_notes.py`:

- Write each commit subject as `type: text`: `fix:` for a fix, `feat:` for a feature, `perf:` or
  `refactor:` for a change in how it works; `docs:`, `test:`, `chore:` and `ci:` for the rest.
- Do not edit `CHANGELOG.md` by hand, and nothing goes under Unreleased: the notes are written from
  the subjects at release, and `make check` fails on a hand edit.

To see what the next release's notes will say: `python3 scripts/release_notes.py --dry-run`.

At a release, the maintainer copies the dry run under the new version's heading, commits it as
`release: <version>`, and tags `v<version>`.
