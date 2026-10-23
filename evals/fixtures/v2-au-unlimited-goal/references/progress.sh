# progress LINE...: append each LINE under GOAL.md's Progress, as a bullet.
progress() {
  local line
  for line in "$@"; do
    printf -- '- %s\n' "$line" >> GOAL.md
  done
}
