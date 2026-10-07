# The close shared by the fixtures of the diagnose, review-findings and reuse skills, sourced from
# a fixture's setup.sh in the workspace after the setup plants its files. It needs `$here` (the
# fixture's folder) and `$repo` (this checkout). It copies the fixture's graders and the shared
# ones into `checks/`, installs the core skill (none in the kernel-off arm), and makes the seed
# commit and its tag.
mkdir -p checks
cp "$here"/checks/* checks/
cp "$repo/evals/graders/scope_walk.py" "$repo/evals/graders/transcript_commands.py" \
  "$repo/evals/graders/allowed_paths.sh" checks/
chmod +x checks/*

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
