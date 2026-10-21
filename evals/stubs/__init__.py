"""Runner-owned stubs for the suite-v2 fixtures, and the reader of their receipts.

A stub stands in for a tool the task needs and the eval must not call for real (a reviewer, a
billed eval, a deploy). A fixture names the stubs it needs in `suite.json` (`"stubs": [...]`);
the runner places those files, read-only, in a folder outside the workspace that `OB_EVAL_STUBS`
names, puts that folder first on the call's PATH, and writes the stubs' digests before and after
the call to the JSON file `OB_EVAL_STUB_DIGESTS` names.

- `review` (launcher) and `review.py`: a stateless reviewer. Each call reads the workspace and
  prints three findings, one real while a planted defect is left and two suggestions chosen by
  the tree's digest, then `verdict: changes requested`. It never writes a file. The runner places
  both files and digests both.
- `receipts.py`: `receipts(transcript_path, stub_name, stubs_dir, digests_path)` gives a check
  the stub's receipts, the harness's own command records of its run, by the rules its docstring
  states; `digest_state(digests_path, stub_name)` says whether the stub changed. A fixture's
  setup copies it into the grading stage beside its checks.

Every stub is standard-library Python, stateless and silent on disk. Receipts are recorded by the
harness, not authenticated; a result built on them says so.
"""
