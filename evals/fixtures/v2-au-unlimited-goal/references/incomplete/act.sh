#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../progress.sh
. "$here/../progress.sh"
# Three tickets, then a stop at the overrun to ask.
tickets="001 003 004"
# shellcheck source=../tickets.sh
. "$here/../tickets.sh"
progress "2026-10-21: ticket 002 is about three times its estimate; stopped to ask whether to go on."
