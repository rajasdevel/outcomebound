# The slicing fixtures' reference outcomes write their ticket drafts with this helper, sourced
# by an act.sh, which runs in the built workspace:
#
#   write_ticket NAME TITLE READS BOUNDS DONE_WHEN [BLOCKED_BY [HUMAN_ONLY_LINE]]
#
# It writes docs/tickets/NAME.md: the heading, the four sections of the project's ticket
# template, and the ticket block. DONE_WHEN is one claim name. BLOCKED_BY is the id of a sibling
# draft, or empty for none. HUMAN_ONLY_LINE is `human-only: no` unless it is given; give it
# empty to leave the field out, as a lint-refused draft does.
write_ticket() {
  local name="$1" title="$2" reads="$3" bounds="$4" done_when="$5" after="${6-}"
  local human="human-only: no"
  if [ "$#" -ge 7 ]; then human="$7"; fi
  mkdir -p docs/tickets
  {
    printf '# %s\n\n' "$title"
    printf '## Outcome\n%s.\n\n' "$title"
    printf '## Design\nSee `%s`.\n\n' "${reads%%#*}"
    printf '## Tests\nThe claim named in the block passes.\n\n'
    printf '## Limits\nOnly the paths in the bounds below.\n\n'
    printf '<!-- outcomebound:begin id=ticket v=1 -->\n'
    printf 'reads: %s\n' "$reads"
    printf 'bounds: %s\n' "$bounds"
    if [ -n "$human" ]; then printf '%s\n' "$human"; fi
    printf 'done-when:\n- %s\n' "$done_when"
    if [ -n "$after" ]; then printf 'blocked-by: %s\n' "$after"; fi
    printf '<!-- outcomebound:end id=ticket -->\n'
  } > "docs/tickets/$name.md"
}
