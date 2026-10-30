# Build this session's history separately from the sealed replica history.
chatsvc="$repo/evals/fixtures/replica/chatsvc"
python3 -B "$repo/evals/fixtures/session/chatsvc/build.py" "$PWD"
python3 -I -B "$repo/evals/fixtures/session/common/instrument.py"
