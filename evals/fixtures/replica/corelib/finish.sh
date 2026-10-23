# The corelib replica's shared close, sourced by each fixture's setup.sh after it plants its
# task: the graders go to the grading stage ($stage), the core skill is installed, what is left
# (the agents' note, the arm's files, the planted task) is committed on main, and the commit is
# tagged `seed`.
#
# Needs: $repo (this checkout), $stage, $corelib.

mkdir -p "$stage/checks"
cp "$corelib/checks/corelib.py" "$stage/checks/corelib.py"
cp "$repo/evals/graders/transcript_commands.py" "$stage/checks/transcript_commands.py"

bash "$repo/evals/fixtures/core-skill.sh" "$repo" AGENTS.md

git add -A
GIT_AUTHOR_DATE="2026-09-10T09:00:00" GIT_COMMITTER_DATE="2026-09-10T09:00:00" \
  git commit -qm "notes: what an agent needs to work here"
git tag seed
