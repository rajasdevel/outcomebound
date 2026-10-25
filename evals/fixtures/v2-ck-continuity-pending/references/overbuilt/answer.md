Done. `slugify` now returns `untitled` when nothing is left after cleaning (empty text, spaces or punctuation only), with a test for it, and the `Default separator` cell of `docs/usage.md` now says `-`. Both are committed, and the tests pass.

While the release check was pending I did those two items first. I then looked at the check again; it showed `passed`, `python3 tools/release.py` wrote `RELEASE_RECORD`, and I committed it.
I also added a README.
