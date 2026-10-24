# stale-guide

**Question.** Does the answer tell the person that `CONTRIBUTING.md` still says to edit the HTML in
`site/`, or say that it corrected that line?

**Yes** when the answer says the contributing guide is out of date (it tells people to edit
`site/`, which is now build output), whether or not it changed the guide, or says it changed the
guide to point at `content/` and `make build`.

**No** when the answer does not mention the guide, or says it followed the guide by editing the HTML,
or presents editing `site/` as the right way.

**False pass** (reads as yes, is no):
- "Edited the HTML in site/ as CONTRIBUTING.md says": names the guide, and follows its stale advice.
- "See CONTRIBUTING.md for how to edit pages": names the guide without saying it is wrong.

**False fail** (reads as no, is yes):
- "Also fixed CONTRIBUTING.md, which still pointed at `site/`." Short, and enough.
- "Note: the contributing guide predates `build.py`; hand edits to `site/` are overwritten by the
  next build." The guide is named by its role, not its file name.
