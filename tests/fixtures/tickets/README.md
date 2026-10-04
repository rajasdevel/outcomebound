# `tickets` fixtures

| file | holds | repository |
| --- | --- | --- |
| `github-export.json` | a whole export, in one page, of a fictional project's tracker | `example-org/example-project` (placeholder) |
| `github-export-truncated.json` | one page whose `pageInfo` reports a further page | `owner/project` (placeholder) |

`github-export.json` is shaped as the pinned query, `templates/tickets/github-export.graphql`,
answers it, for a fictional library's lending service. Every issue carries `ob-ticket` and a
well-formed ticket block, so the export reads clean. It holds:

- parents with children: `#1`, whose 25 children include `#2`, itself the parent of
  `#12`–`#23`;
- blockers, among them `#24` blocked by `#39`, `#28` by `#27` and `#9`, and the `#31`–`#38`
  chain, in which each ticket waits on earlier ones;
- holds on `#1`, `#2`, `#4`, `#5`, `#8`, `#9`, `#11`, `#25` and `#28`, carried by both the
  `human-only` label and the block, which agree on every ticket;
- open and closed tickets, and no issue `#30`, the number a pull request took.

Each node also carries fields the pinned query does not ask for: the issue's times, its
author, `assignees`, `comments` and `timelineItems`, so the tests can show that the reader
passes over what it does not read. Every login in the file is the placeholder `example-user`.

The export holds no dropped ticket, no relation to another repository, no issue outside the
gate and no malformed value. `tests/test_tickets_github.py` builds each of those cases, and
every refusal and per-connection truncation, as a `variant(...)` copy of this file, so each
test changes only what it names.

`github-export-truncated.json` is the page-truncation case `test_truncation_table` reads: a
page that is not the last one. It reads against its own placeholder repository.

An issue transferred in from another repository reads, once exported, the same as one that
originated there, so no fixture can tell the two apart and neither pins that case.
