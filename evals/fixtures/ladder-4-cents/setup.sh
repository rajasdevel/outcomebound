#!/usr/bin/env bash
# Rung 4 of the ladder, the underengineering trap: a column type change. The unit tests build a
# new database from the migrations, so editing the first migration in place passes them; the
# copy of the shop's stock already has that migration applied, so only a new migration that
# converts the stored prices keeps it working. A pristine copy of that stock is kept for the
# probe, which applies the workspace's migrations to it.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"
# shellcheck source=../ladder/base.sh
. "$here/../ladder/base.sh"
mkdir -p checks
cp data/stockroom.db checks/stock-before.db
# shellcheck source=../ladder/finish.sh
. "$here/../ladder/finish.sh"
