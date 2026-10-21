# The chatsvc replica's shared start, sourced by each fixture's setup.sh from the workspace:
# the project with its history up to the start of 1.8.0. The fixture then plants its own task,
# and sources finish.sh. Needs $repo, $target and $stage set by the caller.
#
# chatsvc is a chat service in front of a model provider (an offline stand-in here), with
# nginx-style limits, a feedback store, specs, a slow integration suite and `bin/envctl`, which
# operates simulated stage and prod environments under `.envs/`.
chatsvc="$repo/evals/fixtures/replica/chatsvc"
python3 -B "$chatsvc/chatsvc_build.py" history "$PWD"
