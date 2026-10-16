**Context** —
Exposure — who can be hurt: <<fill: the dependants, or the owner alone>>; acts that cannot be undone: <<fill: the act, or none>>; maintained by: one person; agent-written share and review: <<fill: the agent-written share, and who reads the diff>>.
**Bounds** —
A change reaches the main branch only by a pull request with CI green, and the owner merges their own; the way back is a revert of the merge.
Leave when — a second maintainer → a brief to move to team.
Leave when — nobody has used it since <<fill: a date the owner names>> → a brief to retire it.
**Mechanisms** —
By default none: the smallest change with CI green; `review` only where a miss would reach users and no check you can run would catch it; human review is not required with one maintainer.
