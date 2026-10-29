# Narrow a failure

Choose the quickest route: reduce the input to the smallest one that still fails, read what
changed since the last passing state, or split the code or commits between working and failing
states.

After a failed fix, examples of assumptions to check are whether the code you edited is the
code that ran, whether the input is the one reported, and whether the failure is the one reported.
