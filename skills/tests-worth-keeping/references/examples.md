# Examples of weak tests

A test cannot fail when its assertion recomputes the expected value the way the code does,
asserts what a test double was told to return, or compares a value with itself.

A test pins implementation when it asserts the order of calls on collaborators, private state,
or exact message wording that is not part of the contract. It fails on a refactor with no
observable change.
