## How a change lands

1. Work on a short branch from the main branch, one change to a branch.
2. Open a pull request. CI runs Done on it, and a change merges only with CI green.
3. One human who is neither the author nor the person who directed the agent approves the change. An AI review runs first and never counts as that approval. No one, admins included, bypasses this review.
4. Merge. The way back is a revert of the merge.

A change is small enough when <<fill: the size rule, such as one reviewer can read the whole diff at once>>.
