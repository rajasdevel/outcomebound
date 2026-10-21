# The close shared by the ops fixtures, sourced by a fixture's setup.sh from the workspace after
# base.sh, the fixture's own commits and its section of AGENTS.md. It needs `$here` (the
# fixture's folder), `$repo` (this checkout), `$stage` (the grading stage, outside the
# workspace) and `$ops_here` (this folder). It copies the fixture's checks, the shared reader
# and the transcript reader into the stage, makes the last commit (the project note) and tags it
# `seed`. Nothing for the checks goes into the workspace.
mkdir -p "$stage/checks"
for check in "$here"/checks/*; do
  # Importing a grader can leave a bytecode directory; it is not a fixture input.
  [ "${check##*/}" = __pycache__ ] && continue
  cp "$check" "$stage/checks/"
done
cp "$ops_here/checks/opslib.py" "$repo/evals/graders/transcript_commands.py" "$stage/checks/"
chmod +x "$stage"/checks/*.py
find . -name __pycache__ -prune -exec rm -rf {} +
rm -rf .actions
git add -A
GIT_AUTHOR_DATE="2026-10-21T08:05:00Z" GIT_COMMITTER_DATE="2026-10-21T08:05:00Z" \
  git commit -qm "docs: project notes for coding agents"
git tag seed
echo "fixture ready: $target"
