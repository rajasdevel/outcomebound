# Long corelib fixtures

The offline corelib base extends the replica without changing it. It has released CLI and
library behavior, caller tests, current docs, deterministic history and a worked compatibility
catalog. It contains no session work plan or future ticket contracts. Setup needs Bash, Git
and Python 3.10 or later. It adds no delay. The slow polling integration suite is preserved.

The [release storyline](../../session-release-prep/README.md) and
[split storyline](../../session-resume/README.md) define disclosure boundaries, expected call
ranges and every claim. Contracts arrive in messages, including pasted reproductions. Each
storyline has later changes that revise earlier committed work and independent parts suitable
for delegation. The split checkpoint remains the third ticket disposition commit.

The simulated person uses frozen facts, answers, message history and public Git state. Required
messages arrive in order. Optional replies share one allowance, with required slots reserved.
Only invalid protocol inputs cause a protocol defect. Prose diagnostics are WORDING only.
Required claims read effects, structured fields, checks re-run on delivered content and turn metadata.

Graders consume OB_TURNS and OB_ACTIONS, including child actions once. Deliverable checks run in disposable copies. Ref receipts establish tag and push effects from the start of
the granting turn. Recovery requires the resumed work to use the fact in the progress record. The recovered
record must be delivered after the resume. A command that names or reads the file is only a
COMMAND TEXT diagnostic. Recovery rework compares dependency bytes at execution time, so later source
changes cannot excuse an earlier repeated check.

References run no model. Their turns come from reference_records.py around actual local
commands and effects. Each good reference passes every required claim; do-less and do-more each fail
required claims. Run the fixture's reference/good.sh, do-less.sh or do-more.sh on a fresh setup,
with workspace and artifact directories. --through N stops at a message boundary.

Model-call counts, cost, natural compaction and the field shape remain UNVERIFIED until a
measured run. No artificial wait, call quota or forced compaction creates that evidence.

The [shared evidence rules](../common/README.md) define re-executed checks, process observations and diagnostics.
