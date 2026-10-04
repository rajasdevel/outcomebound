# The ladder's shared close, sourced by each rung's setup.sh from the workspace after the rung
# plants its task: the graders, the core skill, then the seed commit and its tag.
mkdir -p checks
cp "$here"/checks/* checks/
cp "$here/../ladder/footprint.py" "$here/../ladder/no_process_document.py" \
  "$here/../ladder/cli_probe.py" checks/
cp "$repo/evals/graders/transcript_commands.py" checks/transcript_commands.py

bash "$repo/evals/fixtures/core-skill.sh" "$repo" AGENTS.md

git init -q .
git config user.email eval@example.invalid
git config user.name "OutcomeBound eval"
git config commit.gpgsign false
rm -f .git/hooks/*.sample
printf '__pycache__/\n' >> .git/info/exclude
git add -A
git commit -qm "seed"
git tag seed
echo "fixture ready: $target"
