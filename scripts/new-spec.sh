#!/usr/bin/env bash
# OutcomeBound new-spec — scaffold an optional durable design.
#
# Usage: bash scripts/new-spec.sh <slug> [--with-plan] [target-dir]
#
# TARGET defaults to $PWD, so the script scaffolds into the repository the
# operator is standing in rather than into the engine checkout.
#
# Creates a draft `design.md`. A `plan.md` is added only when sequencing,
# coordination, or resumability earns it. A scaffold is intentionally incomplete;
# creation never claims the design is useful or validated.
#
# IDEMPOTENT / fail-safe: refuses to overwrite an existing spec dir (an existing
# spec is human-owned state; clobbering it would lose decisions).
#
# Exit: 0 = scaffolded · 1 = bad usage or spec already exists.
set -euo pipefail

print_help() {
  cat <<'EOF'
usage: bash scripts/new-spec.sh <slug> [--with-plan] [target-dir]

Scaffolds an optional durable design at <target-dir>/docs/specs/<slug>/ (target-dir defaults
to $PWD, the repository the operator is standing in). Always creates a draft design.md;
--with-plan also adds plan.md, only when sequencing, coordination, or resumability earns it.
A scaffold is intentionally incomplete — creation never claims the design is useful or
validated. Refuses to overwrite an existing spec directory (idempotent; an existing spec is
human-owned state).
Exit: 0 = scaffolded · 1 = bad usage or the spec directory already exists.
EOF
}

for arg in "$@"; do
  case "$arg" in
    -h|--help) print_help; exit 0 ;;
  esac
done

SLUG="${1:-}"
MODE=""
TARGET=""
shift || true
while [ "$#" -gt 0 ]; do
  case "$1" in
    --with-plan) MODE="--with-plan"; shift ;;
    -*) echo "BLOCKED: unknown option '$1' (expected --with-plan)." >&2; exit 1 ;;
    *)
      # A second positional is a mistake, not a second target: silently
      # scaffolding into the last one wins would put the spec somewhere the
      # operator never named.
      if [ -n "$TARGET" ]; then
        echo "BLOCKED: only one target directory may be given ('$TARGET' and '$1')." >&2
        exit 1
      fi
      TARGET="$1"; shift ;;
  esac
done
TARGET="${TARGET:-$PWD}"
if [ -z "$SLUG" ]; then
  echo "usage: bash scripts/new-spec.sh <slug> [--with-plan] [target-dir]" >&2
  exit 1
fi

# slug hygiene: lowercase, hyphen, and dot (a version-bearing slug such as
# `api-v2.1` is a real spec name, not a malformed one).
if ! printf '%s' "$SLUG" | grep -qE '^[a-z0-9][a-z0-9.-]*$'; then
  echo "BLOCKED: slug '$SLUG' must be lowercase-hyphen-dot (^[a-z0-9][a-z0-9.-]*\$)." >&2
  exit 1
fi

SPEC_DIR="$TARGET/docs/specs/$SLUG"
if [ -e "$SPEC_DIR" ]; then
  echo "BLOCKED: '$SPEC_DIR' already exists — refusing to overwrite (idempotent)." >&2
  exit 1
fi

# Single source of truth: scaffold from templates/spec/. Only identity
# placeholders are substituted; decision placeholders remain honestly unfilled.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TPL_DIR="$script_dir/../templates/spec"
FILES=(design.md)
if [ "$MODE" = "--with-plan" ]; then
  FILES+=(plan.md)
fi
for f in "${FILES[@]}"; do
  [ -f "$TPL_DIR/$f" ] || { echo "BLOCKED: missing template $TPL_DIR/$f" >&2; exit 1; }
done
mkdir -p "$SPEC_DIR"
for f in "${FILES[@]}"; do
  sed -e "s/<slug>/$SLUG/g" "$TPL_DIR/$f" > "$SPEC_DIR/$f"
done

if [ "$MODE" = "--with-plan" ]; then
  echo "scaffolded $SPEC_DIR/design.md and optional plan.md (status: draft; fill before checking)"
else
  echo "scaffolded $SPEC_DIR/design.md (status: draft; no plan selected)"
fi
