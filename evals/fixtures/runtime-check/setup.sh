#!/usr/bin/env bash
# A greeting service whose unit tests never reach the part of it that decides which paths are
# served, and a task to add a route. With the core skill and the runtime fragment.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

. "$here/project.sh"

. "$here/../skills-close/close.sh"
