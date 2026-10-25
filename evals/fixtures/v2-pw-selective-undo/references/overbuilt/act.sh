#!/usr/bin/env bash
set -euo pipefail
git apply -R .agents/work/retry-settings.patch
# More than the undo: a check and a test that no retry setting comes back.
mkdir -p tests
printf 'def no_retry(settings):\n    return not hasattr(settings, "RETRY_LIMIT")\n' > app/settings_check.py
printf 'from app import settings\nfrom app.settings_check import no_retry\n\nassert no_retry(settings)\n' \
  > tests/test_settings.py
