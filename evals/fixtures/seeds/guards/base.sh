# Shared construction for the small safeguard tasks. Sourced by setup.sh with
# here, target and stage set. Graders stay in the stage, outside the seed's Git objects.
repo="$(cd "$here/../../.." && pwd)"
guards="$here/../seeds/guards"
mkdir -p "$target" "$stage/checks"
target="$(cd "$target" && pwd)"
stage="$(cd "$stage" && pwd)"
cd "$target"
. "$repo/evals/fixtures/field-common/close.sh"
cp "$guards/guardlib.py" "$repo/evals/graders/transcript_commands.py" "$stage/checks/"
for check in "$here"/checks/*.py; do
    cp "$check" "$stage/checks/"
done
mkdir -p tests
printf '' > tests/__init__.py
printf '__pycache__/\n.runs/\n' > .gitignore
cat > Makefile <<'MAKE'
.PHONY: test
test:
	python3 -B -m unittest discover -s tests -t . -q
MAKE

guard_seed() {
    python3 -B -m unittest discover -s tests -t . -q
    field_seed
}
