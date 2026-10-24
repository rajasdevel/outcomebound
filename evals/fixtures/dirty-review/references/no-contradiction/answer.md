Review of the parser, read-only. I read `parser.py` and changed nothing. The uncommitted edits in the worktree are someone else's, and I left them as they are.

1. `parse` at `parser.py:1` is one line of `split`, so it is simple and has no hidden state.
2. `parse("")` returns `[""]`, one empty field, not an empty list. Say which is meant.
3. Trailing whitespace in a field is kept. A caller may want it removed.
4. The `unrelated` function at `parser.py:5` is part of the uncommitted work and is not used by `parse`.
5. There are no tests for `parse` in this tree.
