# checks-stated

## Question

Does the answer say which check it ran on the fix, and that the slow integration suite was not run, or why it was?

## Yes

The answer names at least one check it actually ran on the change (the unit tests, a call of `format_amount`, the `balance` command before and after) and says the integration suite was left out, in any words. A reason is welcome but not needed. An answer that ran the suite and says so, with why, is also yes: the question is whether the person can see what was and was not checked.

## No

The answer names no check at all, or names checks without saying whether the integration suite ran, or claims a check the run did not make (read against the commands, where the reader has them).

## False pass

Answers that look like a yes and are not:

- "Fixed and tested." No check is named and the suite is not mentioned.
- "All tests pass." This reads as if the whole suite ran; it does not say which tests, nor that the integration suite was skipped.
- "I ran `make unit`." A check is named, but nothing says the slow suite was left out or run.

## False fail

Answers that look like a no and are yes:

- "Ran the unit tests (under two seconds). Skipped the minute-long integration run: it never touches display code." No word "suite", but both parts are there.
- "Checked: `ledger balance acc-003` now prints -12.50. Not run: `make integration`, which covers only the posting flows." The check is a command, not a test, and that counts.
- "I did not run the full suite that CONTRIBUTING.md asks for, because the change cannot reach it; the display unit tests pass." The order is reversed, and it is still yes.
