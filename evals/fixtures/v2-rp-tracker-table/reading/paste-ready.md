# paste-ready

**Question.** Could the person paste the reply's table into the tracker card as it stands, in
plain business words, without cutting or rewriting anything in it?

Read only the table (or tables) the reply offers for the card. The figures are checked by
`numbers-match` and the banned items by `card-clean`; this item is about whether a product or
support lead would read the table without help.

**Yes** when every row and heading reads as plain status: a release, how it did and where it
stands, in words a business reader uses ("Released", "Held", "In review", "409 of 412 checks
passed"). A release whose figure is not known yet says so in words ("triage in progress").

**No** when the person would have to edit the table before pasting it: column names copied from
the CSV (`checks_passed`, `defect_triage`), engineering labels or status words a business reader
does not use (`PASS`, `UNVERIFIED`, `rc1 blank`), notes to the person inside cells ("check
this"), or more than one table with no word on which goes on the card.

**False pass** (reads as yes, is no):
- A tidy table whose headings are the CSV's own column names in code font.
- A table whose last column is "Notes" holding remarks for the person, such as "figure taken
  from the CSV; please confirm".
- Two tables, one "short" and one "detailed", with no word on which one is for the card.

**False fail** (reads as no, is yes):
- A table with a "Pass rate" column in percent and no counts: a choice of figures, not a
  problem for the reader.
- A table that writes "2.5.0 release candidate" instead of "2.5.0-rc1", or dates as
  "14 Oct": paraphrase is allowed.
- A table followed by one sentence for the person outside it ("2.4.0 was held back"): the
  table itself is still ready to paste.
