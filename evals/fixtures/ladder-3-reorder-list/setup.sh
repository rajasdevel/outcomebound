#!/usr/bin/env bash
# Rung 3 of the ladder: a new option across the command line and the store, ordinary work
# with a clear end state; the project's documents invite the same process as every rung.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"
# shellcheck source=../ladder/base.sh
. "$here/../ladder/base.sh"
:
# shellcheck source=../ladder/finish.sh
. "$here/../ladder/finish.sh"
