#!/usr/bin/env bash
# process-document: the good option, plus a design note and a decision record for it, as
# CONTRIBUTING.md invites.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../option.sh
. "$here/../option.sh"
add_option "qty < ?" None
mkdir -p docs/design docs/decisions
printf '# 0002 Reorder list\n\n## Context\n\nThe shop needs to see what to reorder.\n\n## Design\n\n`list --below N` keeps the items with fewer than N units.\n' \
  > docs/design/0002-reorder-list.md
printf '# 0002 A below option on list\n\n- Status: accepted\n- Context: the reorder list.\n- Decision: filter in the store.\n- Consequences: none.\n' \
  > docs/decisions/0002-below-option.md
python3 -B -m unittest discover -s tests >/dev/null 2>&1
