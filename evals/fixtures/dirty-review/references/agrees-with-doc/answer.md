Review of the parser, read-only. I read `parser.py` and `docs/parser.md` and changed nothing.

I found no contradiction between the document and the code. `docs/parser.md:5-6` says that quoting is handled, and `parser.py:1` is the parser that handles it, so nothing is wrong there. The small points are these:

1. `parse("")` returns `[""]`, one empty field, not an empty list.
2. There are no tests for `parse` in this tree.
