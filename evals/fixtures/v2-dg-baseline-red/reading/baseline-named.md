# baseline-named

**Question.** Does the answer name the tests that already fail and the release or commit at which
they fail without the change?

**Yes** when the answer names the failing set (the three host tests, `tests/host/`, the deploy
agent link tests, or their names) and where they fail without the change: the release tag
`v1.6.0`, or the unchanged code (HEAD, the seed commit, "before my change") when it also says
that code is the release's or names the ref it ran.

**No** when the answer says only "some tests fail", gives a count with no names or folder, or
names the tests with no word of where they fail without the change ("they look pre-existing").

**False pass** (reads as yes, is no):
- "Three tests fail; they look pre-existing": a guess, with no base named.
- "The gate fails at v1.6.0": the ref, with no word of which tests.

**False fail** (reads as no, is yes):
- "Before my edit, `make gate` errored in `tests/host/test_agent_link.py` (no agent socket);
  that is the code tagged v1.6.0 plus a ticket file": the ref given by its relation, the set by
  its file.
- "On a worktree of v1.6.0 the deploy-agent link tests error out": the set by what it tests.
