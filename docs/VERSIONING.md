# Versioning

`VERSION` versions the whole distribution: the package, the engine, the launcher, the skills,
fragments, templates and schemas. OutcomeBound follows Semantic Versioning, judged by what an adopter must
do, not by which files changed.

| Release | For an adopter |
| --- | --- |
| Patch | Fixes and clarifications; nothing an install or a command relies on changes. |
| Minor | Additions; everything an install or a command relies on keeps working. |
| Major | Something an install or a command relies on changes incompatibly — a verb, a flag, a file format, a managed block's shape — and the changelog section says what to do first. |

Taking any release is installing it (`uv tool install --force` with its tag) and running
`outcomebound adopt` again; until then, `outcomebound adopt . --check` reads the
operating-contract block as stale.

At a release, `VERSION`, the changelog section's heading and link, the `v=` of the
operating-contract block that `adopt` installs, and every install line in the README and in
`templates/ci/` (`…/outcomebound@v<VERSION>`) name the same version.

Whoever prepares the release commit, a maintainer or an agent, runs `make release-check` on it:
those agree, this repository's install is current, and gate, floor and suite pass. Pushing the
tag cannot be undone. It is a maintainer's act, or an agent's where a maintainer's grant in
`.outcomebound/tag-grants.json` covers that version today, which the last line of
`make release-check` names. `make release-check TAG=v<VERSION>` and CI's tag run then check
that the tag is annotated, names `VERSION` and sits on the release commit.
