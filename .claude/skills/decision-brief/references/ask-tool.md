# Asking through a question tool

Where the harness asks the user through a question tool, with choices to pick, draw the brief in
your message first, then pipe the same document to `outcomebound brief --ask -` and ask with what it
prints, filling the tool's fields by name: its question or title, its header, and each option's
label and description, or its `line` where the tool takes options as plain strings. Never put a
drawn brief's lines into the tool's fields; the tool shows each field as one line. Where the tool
refuses the number of options a brief carries, or the brief has none and the tool needs some, the
drawn brief in your message is the ask: put no question for that brief, and the user answers in
words. A brief with `explore` carries a last choice, `Explore it first`; where the tool refuses
that many choices, leave it out, and the drawn brief's offer stands.
