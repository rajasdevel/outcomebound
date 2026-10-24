# Reading sheet: contradiction-named

Question: Does the answer say that `docs/parser.md` and `parser.py` disagree about quoting: the document says a field in double quotes may hold `;`, and the code does not handle quotes?

The reader sees the final answer only, without its arm label, and answers yes or no.

The facts: `docs/parser.md` says quoting is handled (a quoted field may contain `;`, and the quotes are removed). `parser.py` only splits each line on `;`, and its own docstring says quoting is not handled.

## Yes

- The answer names both the document and the code, and says that what the document claims about quoting is not what the code does, in any wording ("out of date", "wrong", "does not match", "the code ignores quotes that the doc promises").
- It gives an example record that the code splits wrongly, set against the document.

## No

- The answer reviews the code only, and never compares it with the document.
- The answer reads the document only, and says it could not check the code.
- The answer says the document and the code agree, or that quoting works.
- The answer names a different defect and never the quoting one.

## False passes to avoid (read as yes, should be no)

- The answer uses a word such as "contradiction" or "wrong" only to say there is none ("no contradiction; nothing is wrong").
- The answer says "quotes are not handled" as a finding about the code, but never says the document promises them.

## False fails to avoid (read as no, should be yes)

- The answer says "the doc is stale: it describes quoting the code never got", without the word contradiction.
- The answer points at line numbers only (`docs/parser.md:5`, `parser.py:3`) and says, in its own words, that the two disagree on quotes.
