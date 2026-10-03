#!/usr/bin/env bash
# Build one hand-off fixture: `build.sh <base> <variant> <target>`.
#
# The shared repository (base.sh), then, for the spec variant only, the package's fixed tests
# and stubs (<base>/spec.sh), then the core skill, then the seed commit and its tag. Every
# variant of a base builds the same repository but the spec variant, whose seed is the ticket's
# branch as the spec package leaves it: its tests committed and failing. Git runs without the
# global and system configs, so an inherited hooksPath or excludesFile cannot change what the
# checks later see.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
base="${1:?usage: build.sh <base> <variant> <target>}"
variant="${2:?usage: build.sh <base> <variant> <target>}"
target="${3:?usage: build.sh <base> <variant> <target>}"
case "$variant" in
  ticket | design | spec) ;;
  *) echo "build.sh: no variant $variant" >&2; exit 2 ;;
esac
[ -f "$here/$base/ticket.md" ] || { echo "build.sh: no base $base" >&2; exit 2; }
mkdir -p "$target"
cd "$target"

# shellcheck source=base.sh
. "$here/base.sh"
if [ "$variant" = spec ]; then
  . "$here/$base/spec.sh"
fi

# The core skill, where the note names it and where codex looks for skills;
# none in the kernel-off arm.
bash "$repo/evals/fixtures/core-skill.sh" "$repo" AGENTS.md

git init -q .
git symbolic-ref HEAD refs/heads/main
git config user.email eval@example.invalid
git config user.name "OutcomeBound eval"
git config commit.gpgsign false
# The sample hooks Git installs are inert, and removing them lets the graders
# treat any entry under .git/hooks as what it is: something a run put there.
rm -f .git/hooks/*.sample
printf '__pycache__/\n' >> .git/info/exclude
git add -A
git commit -qm "seed"
git tag seed
echo "fixture ready: $target"
