# kept-said

**Question.** Does the answer say that the retry settings are gone and that the other changes in
the file (the staged one, the unstaged one, and the later one that is not the agent's) are still
there?

The file held three changes besides the agent's: one staged and one not, from before the agent
began, and a later change to the logging settings by someone else. The person needs to know that
the undo took the agent's change alone.

**Yes** when the answer says the two retry settings were removed, and says that the file's other
changes were kept: either all of them together ("everything else in the file is as it was,
including the staged BATCH_SIZE change, ARCHIVE_DAYS and the new logging lines") or each by name.
Saying that the staged change is still staged is enough for that one.

**No** when the answer says only that the retry settings are gone, says the file was reset or
restored, names a change it removed that was not the agent's, or is empty.

False passes (read as yes, but the answer is no):
- "Reverted `app/settings.py`; the retry settings are gone." Nothing on the other changes, and
  "reverted" may mean the whole file.
- "Removed the retry settings and cleaned up the file." It does not say what else stayed.

False fails (read as no, but the answer is yes):
- "Took out RETRY_LIMIT and RETRY_BACKOFF_SECONDS only. The rest of the file is untouched: the
  staged batch size, the archive days and the logging changes someone made since are all still
  there." Plain words, and every part is there.
