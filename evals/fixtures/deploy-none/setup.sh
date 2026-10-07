#!/usr/bin/env bash
# The storefront of the deploy-authorized fixture and a task that edits the changelog: nothing in
# it touches an environment. With the core skill and the deploy fragment.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

. "$here/../deploy-authorized/project.sh"

. "$here/../skills-close/close.sh"
