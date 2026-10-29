# Shared setup, sourced by each long datapipe fixture with $mode, $here, $target and $stage.
repo="$(cd "$here/../../.." && pwd)"
long_dp="$here/../session/datapipe"
target="$(mkdir -p "$target" && cd "$target" && pwd)"
stage="$(mkdir -p "$stage/checks" && cd "$stage" && pwd)"
cd "$target"
# shellcheck source=../../replica/datapipe/base.sh
. "$here/../replica/datapipe/base.sh"
# shellcheck source=extend.sh
. "$long_dp/extend.sh"
export GIT_AUTHOR_DATE="2026-10-20T09:00:00Z" GIT_COMMITTER_DATE="2026-10-20T09:00:00Z"
python3 -I -B "$long_dp/seed.py" story "$mode"
if [ "$mode" = incident ]; then
  scenario="$here/../replica-io-triage/scenario.json"
else
  scenario="$dp_here/scenario-quiet.json"
fi
python3 -I -B "$dp_here/envseed.py" seed "$scenario" .envs
python3 -I -B "$long_dp/seed.py" facts "$stage" "$repo"
# shellcheck source=../../replica/datapipe/finish.sh
. "$dp_here/finish.sh"
python3 -I -B "$long_dp/seed.py" cleanup "$stage"
cp "$long_dp/checks/long_datapipe.py" "$long_dp/checks/probe.py" "$long_dp/checks/next_turn.py" "$stage/checks/"
cp "$here/checks/grade_$mode.py" "$stage/checks/grade.py"
cp "$long_dp/checks/dialogue.py" "$stage/checks/"
cp "$here/person.json" "$stage/person.json"

cp "$repo/evals/session_protocol.py" "$repo/evals/fixtures/session/common/"*.py "$stage/checks/"
cp "$here/session.json" "$stage/checks/session.json"

python3 -I -B "$repo/evals/fixtures/session/common/instrument.py" hooks
