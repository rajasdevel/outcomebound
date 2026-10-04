# Versioning

One version number, in `VERSION`, covers the whole distribution: the package, the engine, the
launcher, the skills, the fragments, the templates and the schemas. OutcomeBound follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). The bump depends on what an adopter
must do. It does not depend on which files changed.

## What each release means for you

| Release | For an adopter |
| --- | --- |
| Patch | Fixes and clarifications. Nothing that an install or a command relies on changes. |
| Minor | Additions. Everything that an install or a command relies on keeps working. |
| Major | Something that an install or a command relies on changes in an incompatible way: a verb, a flag, a file format or the shape of a managed block. The changelog section says what to do first. |

Read the section of [CHANGELOG.md](../CHANGELOG.md) for each release that you take. A released
section is never edited.

## How to take a release

1. Install the release with its tag: `uv tool install --force git+https://github.com/rajasdevel/outcomebound@v<version>`.
2. Run `outcomebound adopt .` in your project again.

Until you do step 2, `outcomebound adopt . --check` reads the operating-contract block as stale.
The block carries the version that wrote it.

## How a release is made

This section is for the person who prepares a release of OutcomeBound.

At a release, these places name the same version:

- `VERSION`
- the heading and the link of the changelog section
- the `v=` of the operating-contract block that `adopt` installs
- every install line in the README and in `templates/ci/` (`…/outcomebound@v<VERSION>`)

The person who prepares the release commit runs `make release-check` on it. A maintainer or an
agent can prepare it. The command checks that these places agree and that this repository's own
install is current. It also runs the gate, the quality floor and the test suite, and they must
pass.

You cannot undo the push of a tag. A maintainer pushes it. An agent can push it only where a
grant of a maintainer in `.outcomebound/tag-grants.json` covers that version on that day. The last
line of `make release-check` names the grant, or says that none applies.

After the tag exists, `make release-check TAG=v<VERSION>` and the CI run on the tag check that the
tag is annotated, that it names `VERSION`, and that it points at the release commit.
