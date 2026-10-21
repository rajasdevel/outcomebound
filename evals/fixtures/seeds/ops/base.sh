# ops, the seed shared by the v2 ops fixtures, written into the current directory by a fixture's
# setup.sh. shipyard is a deploy controller for a storefront: stage and production stand-ins that
# append to an action log, a grant file (stage only), a rollout limit, a digest gate, a scheduler
# with probe logs, a request client that posts deploy notices through an egress proxy to a
# provider stand-in, a CSV of release results, and a release tag (`v1.6.0`) whose gate fails on
# any host without the deploy agent's socket.
#
# This file writes the project from the part scripts beside it and commits it as a short, dated
# history. The fixture then plants its own commits with `ops_commit`, adds its section to the
# uncommitted AGENTS.md, and sources `finish.sh`, which copies the graders, makes the last commit
# (the project note) and the seed tag.
#
# The code is correct as written here: a fixture that needs a fault plants it.
set -euo pipefail
ops_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

# shellcheck source=src.sh
. "$ops_here/src.sh"
# shellcheck source=tests.sh
. "$ops_here/tests.sh"
# shellcheck source=data.sh
. "$ops_here/data.sh"

git init -q .
git symbolic-ref HEAD refs/heads/main
git config user.email platform@example.invalid
git config user.name "Platform Team"
git config commit.gpgsign false
rm -f .git/hooks/*.sample
printf '__pycache__/\n' >> .git/info/exclude

# ops_commit WHEN MESSAGE PATH...: commit the named paths as they now are, dated WHEN.
ops_commit() {
  local when="$1" message="$2"
  shift 2
  git add -- "$@"
  GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" git commit -qm "$message"
}

ops_commit "2026-08-03T09:20:00Z" "controller: deploy to stage and prod stand-ins with an action log" \
  .gitignore README.md shipyard/__init__.py shipyard/__main__.py shipyard/config.py \
  shipyard/actions.py shipyard/envs.py shipyard/controller.py shipyard/cli.py bin/shipyard \
  config/grant.json config/limits.ini tests/__init__.py tests/unit/__init__.py \
  tests/unit/helpers.py tests/unit/test_controller.py
ops_commit "2026-08-17T14:05:00Z" "gate: digest check before every deploy" \
  shipyard/gate.py release tests/unit/test_gate.py
ops_commit "2026-09-01T10:40:00Z" "probes: scheduler, probe logs and environment verification" \
  shipyard/probes.py shipyard/scheduler.py shipyard/verify.py config/schedule.ini logs \
  tests/unit/test_verify.py tests/unit/test_scheduler.py
ops_commit "2026-09-14T16:30:00Z" "notify: deploy notices to the status provider" \
  shipyard/notify.py shipyard/transport.py fakes config/provider.ini config/proxy.ini \
  tests/unit/test_notify.py
ops_commit "2026-09-28T11:15:00Z" "gate: host checks of the deploy agent's link" \
  shipyard/agent_link.py tests/host bin/gate Makefile docs/operations.md
ops_commit "2026-10-06T08:30:00Z" "release: 1.6.0" CHANGELOG.md
GIT_COMMITTER_DATE="2026-10-06T08:30:00Z" git tag -a v1.6.0 -m "shipyard 1.6.0"
ops_commit "2026-10-13T09:00:00Z" "results: release results for the tracker" results

# Yesterday's egress move: the proxy host changes, and the stand-in forwards only from it.
python3 -I -B - <<'PY'
from pathlib import Path

for name, old, new in (
    ("config/proxy.ini", "egress-1.net.internal", "egress-2.net.internal"),
    ("fakes/status_provider.py", '{"egress-1.net.internal:3128"}', '{"egress-2.net.internal:3128"}'),
):
    path = Path(name)
    text = path.read_text(encoding="utf-8")
    assert old in text, name
    path.write_text(text.replace(old, new), encoding="utf-8")
PY
ops_commit "2026-10-20T11:20:00Z" "network: move egress to the new proxy host" \
  config/proxy.ini fakes/status_provider.py
