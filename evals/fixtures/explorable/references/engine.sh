# shellcheck shell=bash
# Shared by the references: `engine` runs this checkout's engine, found from the reference folder
# the self-test names (evals/fixtures/<fixture>/references/<name>). Bytecode is not written.
engine() {
  PYTHONPATH="$(cd "${OB_EVAL_REFERENCE_DIR:?the self-test names the reference folder}/../../../../.." && pwd)" \
    python3 -B -m outcomebound_tools "$@"
}
