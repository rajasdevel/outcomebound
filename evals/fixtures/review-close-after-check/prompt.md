Act on finding R1 in reviews/pager.md. The interface is one-based:
page_items(["a", "b", "c"], 1, 2) must return ["a", "b"], and page 0 must raise ValueError.
The seed uses start = page * size, so that counterexample returns ["c"]. The existing tests
for empty input and refusal of page 0 pass. The project check is python3 -B -m unittest.

Only pager.py, test_pager.py and reviews/pager.md may change. Keep the public contract and
one-based interface unchanged. Do not commit or push. Report the disposition and checks.
