---
name: sources
status: ratified
---

# Sources — design

This design lands with the change that adds `outcomebound sources`. The release canary
(`make canary`) must pass before that change lands, because it adds a verb to the engine.

## Outcome

Where requirements come from a document, an issue or a transcript, a person can see which part of
the source reached a requirement and which part did not, and an agent cannot drop a part without
the check saying so. The one invariant `outcomebound sources check` holds: every item of the
declared input set has exactly one row in the ledger, each row's item exists, and each row was
written against the item's current revision. How: `outcomebound_tools/sources.py` (the verb),
`sources_manifest.py` (items and the manifest), `sources_ledger.py` (the ledger),
`sources_check.py` (the checks); the wire formats are `schemas/sources-manifest.schema.json` and
`schemas/sources-report.schema.json`.

The check does not say that a requirement keeps what its source meant. A row for an item that
holds five constraints, linked to one requirement, passes; the report says so on each line.

## Edges

The data each verdict reads, and who can write it. `check` reads the manifests it is given, the
ledger file, and the source files the manifests name (to compare digests). The agent that fills
the ledger can write the ledger, can run `import` again, and can edit a manifest in a folder Git
ignores. The check therefore trusts no manifest on its digest alone: where the source file is
there and its digest matches, it splits the file as `import` does and compares the items with the
manifest's (`MANIFEST_DIFFERS`), and it checks quotes against the file's text. It reports
`SOURCE_CHANGED` against the source file as it stands, and reads `UNVERIFIED` where the file is not
there, since the manifest is then the only evidence of the items. A
person who needs more than that keeps the source outside the agent's reach and runs the check
there. `import` writes one manifest and, in the default folder, one ignore file. Nothing runs,
and no connection is opened.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| The importer reads markdown and plain text only. A source in another format (a tracker export, a document, a transcript) is converted to markdown by the person or agent first, and imported with `--converted` (maintainer, 2026-10-06) | a reader for each tracker and document format, built before a project brings that format | user | decided |
| A manifest holds the source text, so Git ignores it by default: `import` writes it to `.outcomebound/sources/` with a `.gitignore` of `*` beside it. A project opts in with `--track` (the default folder, no ignore file) or `--out` (its own folder, no ignore file) (maintainer, 2026-10-06) | committing manifests by default; a rule in the project's own `.gitignore`, which the engine cannot write for an adopter | user | decided |
| The ignore file is written only where it is absent, and `--track` removes it only where it is exactly `*` and a newline. A file a person edited stays | overwriting it on every import | agent | assumed |
| An ignore rule does not untrack a file that Git already tracks, and it does not protect a quote, a title or a name copied into a spec. The help says both, and the template asks for the shortest quote that anchors a requirement | a check that reads Git, which `import` does not otherwise need | agent | assumed |
| An item's id is `name:file:section` (the import name, the file's stem, the section), where the section is the slug of its heading (`preamble` before the first heading; `p<n>` for a paragraph of plain text), made unique within the file by a numeric suffix. Its revision is the sha256 of its text, in the engine's text form (CRLF as LF, trailing space stripped). Identity and revision are separate: an edited item keeps its id and shows a new revision; a renamed heading is a new id | an id from the item's text digest, which an edit changes; an id from its position, which an insertion changes | agent | assumed |
| An item is one heading section of any level, from its heading to the next heading; headings inside a fenced block are not headings. Plain text splits at blank lines | one item per file, which hides what a row covers; a parse of setext headings, tables and nested lists, which no project has asked for | agent | assumed |
| The raw digest of a file is the sha256 of its bytes with CRLF as LF, so one file has one digest in a checkout with `core.autocrlf` and one without. The manifest holds no time and no absolute path: `file` is relative to the folder of the import, or the file's name where the file is outside it. One input gives one manifest, byte for byte | a timestamp; the absolute path, which puts a local folder into a file a project may commit | agent | assumed |
| Partial is recorded per item, from what the importer observes: a code fence that never closes, and a U+FFFD that an earlier conversion left. A partial item reads `UNVERIFIED` and is carried into `check`. An unknown amount missing cannot be observed and is not claimed | a partial flag from a row count, which a complete export can match | agent | assumed |
| A suspect item is one whose text holds a hidden character or an override phrase, by the instruction audit's own classes. The flag is advisory and prints beside the item's disposition, and nothing in `check` fails on it. The manifest keeps the raw text. Every line the verbs print escapes characters outside printable ASCII, and prints no source text but a quote the ledger gave | stripping characters from the text, which changes what the source says; a FAIL on a carried suspect item, which a legitimate requirement with imperative words would meet, and which reads a clean item as safe | agent | assumed |
| A markdown reference note that cites an image (the file, its digest or revision, the region or state, an interpretation, the comparison sought) is an ordinary item. There is no image reader. Pixels are inferred by whoever reads them, and the note says so | an image importer before a real export shows what it must read | agent | assumed |
| The ledger is the `## Sources` table of the file where the requirements live: Source item, Disposition, Where, Basis. Requirements are the lines of that file's `## Requirements` section that start with `R<n>`; an id is never renumbered or reused, and belongs to the file that defines it. Both sections are optional in the spec template | a separate ledger file, which no one opens beside the requirements; a new column in the decisions table, which the rules for a design fix at four | agent | assumed |
| Dispositions are `carried` (to one or more requirement ids; basis `stated` with a quote, or `inferred`), `dropped (assumed)` or `dropped (decided)` (with a reason), `not requirement-bearing` (with a reason; the only disposition whose row may be a range), and `deferred` (names a ticket or a later design). `todo` is the skeleton's mark and reads as undisposed. The mapping is many to many: one item may carry to several requirements in one row, and several items to one requirement in several rows | one requirement per item, which loses the constraints beyond the first | agent | assumed |
| A range, which only a `not requirement-bearing` row may name (any other disposition with a range is `ROW_MALFORMED`, so no one row drops a whole source), is `<first id>..<last id>` within one manifest, in manifest order, with the digest of its items' revisions in place of one revision. An item added to the range or changed in it moves the digest, so a new item never takes a range's old disposition without a new row. A range of `not requirement-bearing` that holds items matching a short list of English modal and decision words reads `UNVERIFIED` and names them, as lexical candidates only | an engine rule that every candidate has its own row, which fails a long transcript; counting the candidates as information, under which a disposed ledger reads as coverage | agent | assumed |
| The declared input set is the manifests named on the command line. A row whose id names a manifest that is not given is `ITEM_UNKNOWN`, unless that manifest is the absent one | reading every manifest in a folder, which makes an old import part of every check | agent | assumed |
| `QUOTE_NOT_FOUND` is a quote occurrence check: the quote, with case, whitespace, curly quotes, `*` and backticks folded, occurs in the item's text. A quote that folds to nothing is `ROW_MALFORMED`, since it occurs in every item. The report line says it establishes nothing about meaning or authority | calling it fidelity, which it is not: "delete backups" occurs in "must not delete backups" | agent | assumed |
| `check` compares each manifest's raw digest with the file it names, found under `--root` (default the current folder). A different digest is `SOURCE_CHANGED`, a file not found is `SOURCE_FRESHNESS` and `UNVERIFIED`. Where the digest matches, the file is split as `import` splits it and its items, with their revisions and text, must be the manifest's: any item missing, added or different is `MANIFEST_DIFFERS`, and a quote is checked against the file's text. A manifest compared with itself finds neither a source that moved on nor an edited manifest | trusting the manifest alone, or its items where the raw digest matches, which a hand-edited manifest passes; failing where the file is absent, as it is in a CI that holds no source | agent | assumed |
| A manifest that is absent reads `UNVERIFIED`, and so does a partial item; neither hides a FAIL found elsewhere, and rows for the absent manifest's name are reported unchecked, never unknown | exit 2 before any other check runs | agent | assumed |
| `check --skeleton <manifest>...` prints a ledger section with one `todo` row per item, ids and revisions filled; each `--range FIRST..LAST` replaces the rows of its items with one row that holds the range's digest, so an agent never types an id or a digest | an agent that writes ids by hand | agent | assumed |
| Exits as `outcomebound tickets` exits: 0 PASS; 1 FAIL or a refusal; 2 UNVERIFIED or a usage error. `import` exits 2 where the manifest is partial; its refusals are `SOURCE_UNREADABLE`, `SOURCE_KIND_UNKNOWN`, `SOURCE_ENCODING`, `SOURCE_NAME_INVALID`, `SOURCE_EMPTY`, `SOURCE_DUPLICATE` and `SOURCE_UNWRITABLE`; `check`'s is `LEDGER_UNREADABLE` | a new code for UNVERIFIED | agent | assumed |
| An engine limit on items, file size or section length is not imposed | a cap chosen without evidence | agent | assumed |
| `check` reports a requirement carried from no item and not marked `[assumed]`, an item dropped on an assumption, a suspect item and a converted source, each as information that does not change the verdict | failing on them, which would hold work for a requirement the person gave by word | agent | assumed |

## Checks

Each line of a report names its code, says what it found, and says what it does not establish
(`LIMITS` in `outcomebound_tools/sources_check.py`). As `instructions check` prints, the first
line is the verdict and its counts, each line that did not pass follows with a `next:` step, and
the passing lines print only under `--verbose` or `--json`.

| Code | Verdict | Finds |
| --- | --- | --- |
| `ITEM_UNDISPOSED` | FAIL | an item in the input set with no row, or only a `todo` row |
| `ITEM_UNKNOWN` | FAIL | a row for an id no given manifest holds |
| `ITEM_DUPLICATE` | FAIL | two rows for one item, ranges included |
| `TARGET_MISSING` | FAIL | a carried row names a requirement id that `## Requirements` does not define |
| `QUOTE_NOT_FOUND` | FAIL | a stated quote that does not occur in its item |
| `ITEM_CHANGED` | FAIL | a row's revision is not the manifest's current one |
| `SOURCE_CHANGED` | FAIL | a source file differs from the one its manifest was made from |
| `MANIFEST_DIFFERS` | FAIL | a source file that matches its manifest's digest splits into items other than the manifest's: one missing, one added, or one with other text, partial flags or suspect flags |
| `ROW_MALFORMED` | FAIL | a row with the wrong cells, an unknown disposition, a missing Where or Basis, or a range on a disposition but `not requirement-bearing`, or a bad range |
| `REQUIREMENT_DUPLICATE` | FAIL | a requirement id defined twice |
| `LEDGER_MISSING` | FAIL | no `## Sources` section |
| `MANIFEST_INVALID` | FAIL | a manifest that does not read as one, two with one name, or a source `file` that is absolute, holds `..` or resolves outside `--root`, which is never read |
| `MANIFEST_ABSENT`, `SOURCE_PARTIAL`, `SOURCE_FRESHNESS`, `RANGE_CANDIDATES` | UNVERIFIED | the evidence is not there |
| `SUSPECT`, `DROP_ASSUMED`, `REQUIREMENT_UNSOURCED`, `SOURCE_CONVERTED` | INFO | a fact the person may want, not a verdict |

What stays judgment, and no line claims: whether a requirement says what its source meant,
whether a drop is right, which readings of a source conflict, whether an item is an attack,
speaker truth, the source's currency and authority.

## Validation

`tests/test_sources_import.py` and `tests/test_sources_check.py`: import is deterministic and
valid against its schema; each FAIL code has a ledger that triggers it and the clean ledger beside
it; an absent manifest hides no FAIL; a partial item and a file not found read UNVERIFIED; an item deleted from a manifest, or a quote planted in its text, fails; a range
digest moves when an item in it changes; every report line carries its limit; output escapes. The
ledger format and the check have not met a real project's source: the release canary is the
first such run, and what it finds becomes a case in the suite.
