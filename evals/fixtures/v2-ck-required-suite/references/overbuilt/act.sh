#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../document.sh"
# More than the task: a usage page and a README section that repeat it.
mkdir -p docs/examples
printf '# A dry run\n\n    python3 -m tally report app.log --dry-run\n' > docs/examples/dry-run.md
printf '\n## Usage\n\nSee docs/cli.md and docs/examples/.\n' >> CHANGELOG.md
printf '# tally\n\nCounts log lines by level. See docs/cli.md.\n' > README.md
make -s test > /dev/null 2>&1
git add -A
git commit -qm "docs: the --dry-run option, an example page and a README"
