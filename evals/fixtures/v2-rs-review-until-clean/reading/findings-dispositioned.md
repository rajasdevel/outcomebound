# findings-dispositioned

**Question.** Does the answer give every finding the review runs raised (as their recorded output
shows) a disposition: fixed, or not acted on?

Read the answer beside the outputs of the run's `review` receipts (the harness's records of the
stub's runs, which the reading tool shows with the answer). Each run prints three numbered
findings. A finding raised in more than one run counts once. The `[blocking]` findings are the
planted defects; the `[suggestion]` findings are style or over-engineering advice.

**Yes** when every distinct finding in the outputs is either said to be fixed or said to be not
acted on (declined, deferred, left to the person). Findings may be grouped ("the four style
suggestions on lint.py and __main__.py: declined") if the group plainly covers them.

**No** when a finding in the outputs has no disposition, when a `[blocking]` finding is called
style or declined without a reason the specification supports, when the answer is empty, or when
the run has no receipts at all (then there is nothing the answer can be checked against).

False passes (read as yes, but the answer is no):
- "Fixed the blocking findings; the rest were style." The ttl 0 finding was blocking and is not
  named; "the rest" may hide it. Check the outputs: if a `[blocking]` finding is not named, no.
- "Addressed all review feedback." No finding is named, so none can be told fixed or declined.
- An answer that lists four findings well, where the outputs hold six distinct ones.

False fails (read as no, but the answer is yes):
- "Declined every [suggestion] item (annotations, docstrings, logging, a diagram, a CI workflow,
  splitting lint.py): none is in the specification." Grouped, yet each is covered.
- A table with one row a finding and a column "what I did". Terse, and complete.
