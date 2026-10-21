Where the 0.4.0 release stands: four of the six TODO items are done and committed on `main`; two wait on you.

Done (one commit, tests pass):
- 2: `render()` now raises `promptkit.render.MissingVariable`, which names the placeholder, instead of a bare `KeyError`.
- 3: `python3 -m promptkit --version` prints the version.
- 4: "recieve" corrected to "receive" in `prompts/greet.md` and `prompts/followup.md`.
- 6: the version is 0.4.0, and CHANGELOG.md has a 0.4.0 section.

Not done, and why:
- 1, push `main` and `v0.4.0` to `origin`: `release/grants.json` holds no grant for this push, and AGENTS.md says only you write that file. I did not push or tag. To unblock: add a grant for the push of `main` and `v0.4.0`, or push them yourself (`git tag v0.4.0 && git push origin main v0.4.0`).
- 5, publish to the index: `tools/publish.sh` needs the index token, and the project rule is that only you enter credentials. I did not run it with a token or write one. To unblock: run `tools/publish.sh` with your token after the push.
