# The ledger seed's shared close, sourced by each fixture's setup.sh after it plants its task:
# the fixture's graders, the seed's shared grader and the transcript reader go to the grading
# stage ($stage), the core skill is installed, what is left (the agents' note, the arm's files,
# the planted task) is committed on main, and the commit is tagged `seed`. State a past session
# left uncommitted is written by the fixture after this.
#
# Needs: $here (the fixture's folder), $repo (this checkout), $stage, $ledger.

mkdir -p "$stage/checks"
for check in "$here"/checks/*; do
  # Importing a grader can leave a bytecode directory; it is not a fixture input.
  if [ "${check##*/}" = __pycache__ ]; then
    continue
  fi
  cp "$check" "$stage/checks/"
done
cp "$ledger/checks/ledger_seed.py" "$repo/evals/graders/transcript_commands.py" "$stage/checks/"

bash "$repo/evals/fixtures/core-skill.sh" "$repo" AGENTS.md

git add -A
# A fixture whose planted history runs later sets ledger_notes_when after its last commit.
GIT_AUTHOR_DATE="${ledger_notes_when:-2026-09-10T09:00:00Z}" \
  GIT_COMMITTER_DATE="${ledger_notes_when:-2026-09-10T09:00:00Z}" git commit -q --allow-empty \
  -m "notes: what an agent needs to work here"
git tag seed
