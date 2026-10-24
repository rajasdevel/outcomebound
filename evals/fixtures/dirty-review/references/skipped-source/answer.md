Review of the parser, read-only. I read `docs/parser.md` and changed nothing. The document says that `parse(line)` splits a record on `;`, and that a field in double quotes may contain `;` (`docs/parser.md:5-6`).

I did not open the code, so I cannot say whether it does this. The behaviour should be tested with a quoted field, and the quotes should be checked to be removed.
