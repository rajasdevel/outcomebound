# The chatsvc replica's shared close, sourced by each fixture's setup.sh after it planted its
# task: every file folded into the last commit and tagged `seed`, the environments as the team
# left them (stage and prod both serve v1.7.0), and the shared graders and the baseline they
# compare against, written to the grading stage. The fixture adds its own graders after this.
python3 -B "$chatsvc/chatsvc_build.py" finish "$PWD"
rm -f .git/hooks/*.sample
printf '__pycache__/\n' >> .git/info/exclude
bin/envctl deploy prod --ref v1.7.0 --confirm prod > /dev/null
bin/envctl deploy stage --ref v1.7.0 > /dev/null
mkdir -p "$stage/checks"
cp "$chatsvc"/checks/*.py "$stage/checks/"
cp "$repo/evals/graders/transcript_commands.py" "$stage/checks/transcript_commands.py"
python3 -B "$stage/checks/snapshot.py" "$stage/checks/baseline.json"
echo "fixture ready: $target"
