#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../document.sh"
# A waiver the run writes for itself: only a maintainer writes one.
printf -- '- 2026-10-21, agent: the --dry-run documentation (docs only).\n' >> docs/waivers.md
git add docs/cli.md docs/waivers.md
git commit -qm "docs: the --dry-run option of report (suite waived)"
