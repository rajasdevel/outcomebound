# The close shared by the field fixtures, sourced from a fixture's setup.sh in the workspace after the
# setup plants its files. It needs `$repo` (this checkout) and `$stage` (the grading stage, outside
# the workspace). `field_close GRADER...` copies the named files of `evals/graders/` and the shared
# walkers into the grading stage's `checks/`, installs the core skill (none in the kernel-off arm),
# and makes the seed commit and its tag. Nothing for the checks goes into the workspace.
field_close() {
    mkdir -p "$stage/checks"
    local name
    for name in "$@" scope_walk.py transcript_commands.py allowed_paths.sh; do
        cp "$repo/evals/graders/$name" "$stage/checks/"
    done
    chmod +x "$stage"/checks/*
    bash "$repo/evals/fixtures/core-skill.sh" "$repo" AGENTS.md
    git init -q .
    git symbolic-ref HEAD refs/heads/main
    git config user.email eval@example.invalid
    git config user.name "OutcomeBound eval"
    git config commit.gpgsign false
    rm -f .git/hooks/*.sample
    printf '__pycache__/\n' >> .git/info/exclude
}

# Commit what the setup planted as the seed, and tag it.
field_seed() {
    git add -A
    git commit -qm "seed"
    git tag seed
    echo "fixture ready: $target"
}
