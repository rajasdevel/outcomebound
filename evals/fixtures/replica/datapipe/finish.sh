# The close shared by the datapipe fixtures, sourced by a fixture's setup.sh from the workspace
# after base.sh and the fixture's own commits. It needs `$repo` (this checkout), `$stage` (the
# grading stage, outside the workspace), `$dp_here` (this folder) and the fixture's facts at
# "$stage/checks/facts.json". It copies the graders into the stage, records the environments as
# setup left them, makes the last commit (the project note, with the skills an installed arm
# wrote before setup ran) and tags it `seed`. Nothing for the checks goes into the workspace.
mkdir -p "$stage/checks"
cp "$dp_here/checks/replica_datapipe.py" "$repo/evals/graders/scope_walk.py" \
  "$repo/evals/graders/transcript_commands.py" "$stage/checks/"
[ -f "$stage/checks/facts.json" ] || { echo "the fixture wrote no facts.json" >&2; exit 1; }
python3 -I -B "$dp_here/envseed.py" baseline .envs "$stage/checks/envs-baseline.json"
find . -name __pycache__ -prune -exec rm -rf {} +
rm -rf .runs
git add -A
GIT_AUTHOR_DATE="2026-10-21T08:05:00Z" GIT_COMMITTER_DATE="2026-10-21T08:05:00Z" \
  git commit -qm "docs: project notes for coding agents"
git tag seed
echo "fixture ready: $target"
