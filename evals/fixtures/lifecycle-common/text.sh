# Shared by the two composable-lifecycle fixtures, sourced from a fixture's setup.sh.
#
# `lifecycle_text <repo>` prints `new` where the checkout under test carries the composable
# lifecycle text (it ships the `land-change` skill) and `before` where it does not. A fixture builds
# the project's `local` fragment from it: the same project in both, and in `new` only the lines
# the composable lifecycle reads (`Exposure`, `Streams`, `Gates`, `Leave when`, `Better means`).
# `OB_LIFECYCLE_TEXT=new` or `=before` overrides the reading, for a test of one side.
lifecycle_text() {
    local repo="${1:?usage: lifecycle_text <repo>}"
    case "${OB_LIFECYCLE_TEXT:-}" in
        new | before)
            printf '%s\n' "$OB_LIFECYCLE_TEXT"
            return 0
            ;;
        "") ;;
        *)
            echo "OB_LIFECYCLE_TEXT must be new or before" >&2
            return 1
            ;;
    esac
    if [ -f "$repo/skills/land-change/SKILL.md" ]; then
        printf 'new\n'
    else
        printf 'before\n'
    fi
}
