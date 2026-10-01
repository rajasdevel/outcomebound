<!--
The body of one OutcomeBound ticket. The issue's title is the outcome in one line; a draft file
begins with the heading `# <title>` instead, and this text follows it.

Write for the implementer who will take the ticket, and state only the decisions the tree does
not show; never copy an existing shape from the tree. `## Outcome`
and the block are required. Keep `## Design` and `## Limits` only where they carry a decision,
in this order. Name no test plan: which tests to write is the implementer's. In the block,
`human-only` and `done-when` need a value, and each `done-when` item names a claim; where the
outcome carries a risk no existing check covers, one of them is a claim the work adds for it,
and a line under `## Design` says what it must catch. `bounds` may be empty, which grants no
path, and `reads` may be empty where the ticket cites no section to read.

Lint the drafts before publishing them with `outcomebound tickets check <target> --draft <file>...`,
naming every draft of the breakdown so the relations between them are checked. Without
`.outcomebound/tickets.json` it refuses with `DECLARATION_MISSING`.
-->

## Outcome
What becomes observably true, and for whom, in one sentence. Where accepting settles something only the person can see, one line: `Accepting this decides: ...`.

## Design
The decisions the implementer would otherwise get wrong, and `Follow:` naming an existing file that already has the right shape.

## Limits
What must not change, when to stop and ask, and what this slice leaves out.

<!-- outcomebound:begin id=ticket v=1 -->
reads:
bounds:
human-only:
done-when:
<!-- outcomebound:end id=ticket -->
