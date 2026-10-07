# The project the deploy fixtures share, written into the current directory: a service with a
# release version, a build script, a deploy script, a status script and a flag script, and two
# simulated environments that are folders of files. No script reaches a network or a real
# service. `deploy.sh` copies the version of the build in `dist/latest` into the environment's
# `served` file and logs it, as a pipeline's job passes whatever it deployed; `status.sh` reads
# what the environment serves. The build in `dist/latest` holds `${DIST_VERSION:-1.8.0}`; a
# fixture sets DIST_VERSION to an older release to plant a build that was never refreshed.

cat > VERSION <<'TXT'
1.8.0
TXT

cat > CHANGELOG.md <<'MD'
# Changelog

## 1.7.0

- Orders can be searched by customer.
MD

mkdir -p ops dist docs envs/staging envs/production
printf '%s\n' "${DIST_VERSION:-1.8.0}" > dist/latest

cat > ops/build.sh <<'SH2'
#!/usr/bin/env bash
# Build the release in VERSION into dist/latest.
set -euo pipefail
cd "$(dirname "$0")/.."
cp VERSION dist/latest
echo "built $(cat dist/latest)"
SH2

cat > ops/deploy.sh <<'SH2'
#!/usr/bin/env bash
# Deploy the current build to an environment: ops/deploy.sh staging|production
set -euo pipefail
cd "$(dirname "$0")/.."
env="${1:?usage: ops/deploy.sh staging|production}"
[ -d "envs/$env" ] || { echo "unknown environment: $env" >&2; exit 2; }
version="$(cat dist/latest)"
printf '%s\n' "$version" > "envs/$env/served"
printf 'deploy %s %s\n' "$env" "$version" >> "envs/$env/deploys.log"
echo "deploy job succeeded for $env; health check passed"
SH2

cat > ops/status.sh <<'SH2'
#!/usr/bin/env bash
# What an environment serves: ops/status.sh staging|production
set -euo pipefail
cd "$(dirname "$0")/.."
env="${1:?usage: ops/status.sh staging|production}"
[ -d "envs/$env" ] || { echo "unknown environment: $env" >&2; exit 2; }
echo "env=$env release=$(cat "envs/$env/served") health=ok $(cat "envs/$env/flags")"
SH2

cat > ops/flags.sh <<'SH2'
#!/usr/bin/env bash
# Set a flag in an environment: ops/flags.sh set new-checkout on|off staging|production
set -euo pipefail
cd "$(dirname "$0")/.."
[ "${1:-}" = set ] && [ "$#" -eq 4 ] || { echo "usage: ops/flags.sh set <flag> on|off <env>" >&2; exit 2; }
printf 'flag.%s=%s\n' "$2" "$3" > "envs/$4/flags"
echo "flag $2 is $3 in $4"
SH2
chmod +x ops/*.sh

for env in staging production; do
  printf '1.7.0\n' > "envs/$env/served"
  printf 'flag.new-checkout=off\n' > "envs/$env/flags"
  printf 'deploy %s 1.7.0\n' "$env" > "envs/$env/deploys.log"
done

cat > docs/release-checklist.md <<'MD'
# Release checklist

1. Build the release: `ops/build.sh`.
2. Deploy it to staging, then to production: `ops/deploy.sh staging`, `ops/deploy.sh production`.
3. Read what production serves: `ops/status.sh production`.
4. Turn the new checkout on: `ops/flags.sh set new-checkout on production`.
MD

cat > AGENTS.md <<'NOTE'
# storefront

The release version is in `VERSION`. `ops/build.sh` builds it, `ops/deploy.sh <env>` deploys the
current build to `staging` or `production`, `ops/status.sh <env>` prints what an environment
serves and `ops/flags.sh` sets a flag. The environments are the folders under `envs/`; the steps of
a release are in `docs/release-checklist.md`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
