# The engine seed's shared close, sourced by each fixture's setup.sh after it plants its task.
# It copies the graders to the grading stage ($stage): the seed's shared checks, the fixture's own
# (`$here/checks`), the stub receipt reader and the transcript reader. It gives the bare remote
# `origin` (`.remotes/origin.git`, kept out of Git's view) the history so far, so that a push of
# the work to come is a fast-forward, and records the remote's refs in the stage. Then it commits
# what is left (the task the fixture planted) as `$task_message` and tags the commit `seed`.
#
# Needs: $repo (this checkout), $here (the fixture's folder), $stage, $engine, $task_message.

mkdir -p "$stage/checks"
cp "$engine/checks/enginecheck.py" "$repo/evals/stubs/receipts.py" \
  "$repo/evals/graders/transcript_commands.py" "$stage/checks/"
for check in "$here"/checks/*; do
  # Importing a grader can leave a bytecode directory; it is not a fixture input.
  if [ "${check##*/}" = __pycache__ ]; then
    continue
  fi
  cp "$check" "$stage/checks/"
done

git init -q --bare -b main .remotes/origin.git
git push -q .remotes/origin.git main:main
git remote add origin .remotes/origin.git
git --git-dir .remotes/origin.git for-each-ref --format='%(refname) %(objectname)' \
  > "$stage/checks/remote-refs.txt"

git add -A
GIT_AUTHOR_DATE="2026-10-01T09:00:00Z" GIT_COMMITTER_DATE="2026-10-01T09:00:00Z" \
  git commit -q --allow-empty -m "$task_message"
git tag seed
echo "fixture ready: $target"
