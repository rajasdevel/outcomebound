#!/usr/bin/env bash
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
. "$here/../seeds/guards/base.sh"
mkdir -p '.'
cat > 'AGENTS.md' <<'SEED'
# Delivery

Python standard library only. `make test` runs the tests.
SEED
mkdir -p '.'
cat > 'README.md' <<'SEED'
# Delivery

For a proof assessment, write three fields and then explain them:
Proof: yes or no
Reason: independent-check, mock-return, or recomputed-result
Evidence: path:line

mock-return means that a test checks the return value set on a mock rather than a result from the product.
SEED
mkdir -p '.'
cat > 'delivery.py' <<'SEED'
def queue_message(message, queue):
    return 'dropped'
SEED
mkdir -p 'tests'
cat > 'tests/test_delivery.py' <<'SEED'
import unittest
from unittest.mock import Mock


class DeliveryTest(unittest.TestCase):
    def test_message_is_queued(self):
        sender = Mock()
        sender.send.return_value = 'queued'
        self.assertEqual(sender.send('hello'), 'queued')
SEED

field_close

guard_seed
