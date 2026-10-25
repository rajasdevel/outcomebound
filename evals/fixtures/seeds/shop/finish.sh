# The shop seed's shared close, sourced by each fixture's setup.sh after it plants its task: the
# seed's shared grader, the fixture's own graders and the transcript reader go to the grading
# stage ($stage), what is left (the agents' note, the planted task) is committed on main, and the
# commit is tagged `seed`.
#
# Needs: $here (the fixture's folder), $repo (this checkout), $stage, $shop.

mkdir -p "$stage/checks"
cp "$shop/checks/shop_check.py" "$repo/evals/graders/transcript_commands.py" "$stage/checks/"
for check in "$here"/checks/*; do
  [ -e "$check" ] || continue
  # Importing a grader can leave a bytecode directory; it is not a fixture input.
  if [ "${check##*/}" = __pycache__ ]; then
    continue
  fi
  cp "$check" "$stage/checks/"
done

git add -A
GIT_AUTHOR_DATE="${shop_notes_when:-2026-10-19T09:00:00Z}" \
  GIT_COMMITTER_DATE="${shop_notes_when:-2026-10-19T09:00:00Z}" git commit -q --allow-empty \
  -m "notes: what an agent needs to work here"
git tag seed
echo "fixture ready: $PWD"
