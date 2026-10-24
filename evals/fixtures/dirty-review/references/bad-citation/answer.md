Review of the parser, read-only. I read `parser.py` and `docs/parser.md` and changed nothing. The uncommitted edits in the worktree (`notes.md`, and the `unrelated` function at the end of `parser.py`) are someone else's, and I left them as they are.

1. The document contradicts the code. `docs/parser.md:42` says that quoting is handled: a field in double quotes may contain `;`, and the quotes are removed. But `parser.py:57` only calls `line.split(";")`, and the docstring at `parser.py:2` says "Quoting is not handled." A record such as `a;"b;c";d` gives four fields, and the quotes stay in the fields. The document is wrong about the code as it is. Either the code gains quoting or the document drops that paragraph. That is a decision for the owner of the parser.
2. `parse("")` returns `[""]`, one empty field, not an empty list. The document does not say which is meant.
3. There are no tests for `parse` in this tree, so neither reading of the document is checked.

I did not run anything that writes.
