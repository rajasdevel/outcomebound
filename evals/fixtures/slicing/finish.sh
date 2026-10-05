# The slicing fixtures' shared close, sourced by each setup.sh from the workspace after it writes
# its project: the graders, the core skill, then the first commit. The setup tags `seed` itself,
# after any later commit its history needs.
mkdir -p checks
cp "$repo/evals/graders/drafts.py" "$repo/evals/graders/ticket_cut.py" checks/
chmod +x checks/*

# The core skill, where the note names it and where codex looks for skills;
# none in the kernel-off arm.
bash "$repo/evals/fixtures/core-skill.sh" "$repo" AGENTS.md

git init -q .
git symbolic-ref HEAD refs/heads/main
git config user.email eval@example.invalid
git config user.name "OutcomeBound eval"
git config commit.gpgsign false
# The sample hooks Git installs are inert, and removing them lets the graders
# treat any entry under .git/hooks as what it is: something a run put there.
rm -f .git/hooks/*.sample
# Bytecode and check logs are byproducts of running a check, not edits.
printf '__pycache__/\n.outcomebound-checks/\n' >> .git/info/exclude
git add -A
git commit -qm "${first_commit:-seed}"
