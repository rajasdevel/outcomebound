# The close shared by the onboarding fixtures, sourced from a fixture's setup.sh in the workspace
# after the setup plants the project in `target/project/`. It needs `$here` (the fixture's folder),
# `$repo` (this checkout) and the workspace as the current folder. It makes the project its own
# Git repository, with a seed commit that holds no OutcomeBound install, and records that commit
# in `target-seed.txt`; copies the graders into `checks/`; writes the workspace note that points at
# the project; installs the core skill (none in the kernel-off arm); and makes the workspace's seed
# commit and tag. The arm's own install sits at the workspace root, never in the project.
project=target/project
(
    cd "$project"
    git init -q .
    git symbolic-ref HEAD refs/heads/main
    git config user.email eval@example.invalid
    git config user.name "OutcomeBound eval"
    git config commit.gpgsign false
    rm -f .git/hooks/*.sample
    git add -A
    git commit -qm "seed project"
    git tag seed
)
git -C "$project" rev-parse 'refs/tags/seed^{commit}' > target-seed.txt
if [ -e "$project/.outcomebound" ]; then
    echo "the project must start without an OutcomeBound install" >&2
    exit 1
fi

cat > AGENTS.md <<'NOTE'
# Onboarding workspace

The project to work on is `target/project/`. It is a separate Git repository and the only target.
Use the `outcomebound` command on PATH. No network and no installation are needed.

If `.agents/skills/adopt-outcomebound/SKILL.md` exists, read that skill before you start.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
printf 'target/\n' > .gitignore

mkdir -p checks
for check in "$here"/checks/*; do
    # Importing a grader can leave a bytecode directory; it is not a fixture input.
    if [ "${check##*/}" = __pycache__ ]; then
        continue
    fi
    cp "$check" checks/
done
cp "$repo/evals/graders/onboard.py" "$repo/evals/graders/new_project.py" \
  "$repo/evals/graders/scope_walk.py" "$repo/evals/graders/transcript_commands.py" checks/
chmod +x checks/*

bash "$repo/evals/fixtures/core-skill.sh" "$repo" AGENTS.md

git init -q .
git symbolic-ref HEAD refs/heads/main
git config user.email eval@example.invalid
git config user.name "OutcomeBound eval"
git config commit.gpgsign false
rm -f .git/hooks/*.sample
printf '__pycache__/\n' >> .git/info/exclude
git add -A
git commit -qm "seed"
git tag seed
echo "fixture ready: $target"
