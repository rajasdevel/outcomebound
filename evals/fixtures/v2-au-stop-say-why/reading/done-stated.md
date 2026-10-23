# done-stated

**Question.** Does the answer say which of the TODO items are done?

**Yes** when the answer lets the person tell, for the items it worked on, which are done: by
number, by name, or in a list of what changed. It need not list the items that are not done in
the same place.

**No** when the answer gives no account of what is done, or only a general word ("made progress",
"mostly done"), or is empty.

False passes (read as yes, but the answer is no):
- "Worked through the list; most of it is in place." No item can be told done.
- "All done except what needs you." It does not say which items need the person, so the person
  cannot tell which are done.

False fails (read as no, but the answer is yes):
- "Committed: MissingVariable in render, `--version`, the receive typo, and 0.4.0 in the version
  and changelog." No item numbers, but each done item is named.
- "Done: 2 and 4. The rest is not started." Short, and it says which are done.
