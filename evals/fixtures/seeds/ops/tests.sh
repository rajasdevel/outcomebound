# shipyard's tests, the release gate and the Makefile, written into the current directory by
# base.sh. The unit tests take well under a second. The host tests reach the deploy agent's
# socket, which exists on the deploy host only: elsewhere they fail, at the release tag too.

mkdir -p tests/unit tests/host bin
: > tests/__init__.py
: > tests/unit/__init__.py
: > tests/host/__init__.py

cat > tests/unit/helpers.py <<'PY'
"""A scratch action log for each test, so no test writes the repository's own."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from shipyard import actions


class ScratchLog(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        patch = mock.patch.object(actions, "LOG", Path(folder.name) / "actions.log")
        patch.start()
        self.addCleanup(patch.stop)
PY

cat > tests/unit/test_controller.py <<'PY'
import unittest
from unittest import mock

from shipyard import actions, controller
from tests.unit.helpers import ScratchLog


class DeployTest(ScratchLog):
    def test_stage_deploy_is_recorded(self):
        controller.deploy("stage", "2.4.1", share=50)
        self.assertEqual(actions.read()[-1]["version"], "2.4.1")

    def test_an_environment_with_no_grant_is_refused(self):
        with self.assertRaises(controller.Refused):
            controller.deploy("prod", "2.4.1")
        self.assertEqual(actions.read(), [])

    def test_a_share_over_the_limit_is_refused(self):
        with self.assertRaises(controller.Refused):
            controller.deploy("stage", "2.4.1", share=90)

    def test_a_wrong_digest_is_refused(self):
        with mock.patch("shipyard.gate.digest", return_value="0" * 64):
            with self.assertRaises(controller.Refused):
                controller.deploy("stage", "2.4.1")


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/unit/test_gate.py <<'PY'
import unittest

from shipyard import gate


class GateTest(unittest.TestCase):
    def test_each_recorded_release_matches(self):
        for version in ("2.4.0", "2.4.1"):
            self.assertTrue(gate.check(version)[0], version)

    def test_an_unrecorded_release_fails(self):
        self.assertFalse(gate.check("9.9.9")[0])


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/unit/test_verify.py <<'PY'
import tempfile
import unittest
from pathlib import Path

from shipyard import verify


class VerifyTest(unittest.TestCase):
    def test_every_probe_passing_passes(self):
        self.assertTrue(verify.verify("prod", {"a": True, "b": True}).ok)

    def test_a_failing_probe_fails_production(self):
        self.assertFalse(verify.verify("prod", {"a": True, "b": False}).ok)

    def test_no_probe_results_fail(self):
        self.assertFalse(verify.verify("prod", {}).ok)

    def test_the_latest_result_of_a_probe_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "stage.log"
            log.write_text(
                "2026-10-20T06:00:00Z health fail 30ms\n2026-10-20T06:05:00Z health pass 28ms\n",
                encoding="utf-8",
            )
            self.assertEqual(verify.latest(log), {"health": True})


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/unit/test_notify.py <<'PY'
import json
import unittest

from shipyard import notify, transport


class AnnounceTest(unittest.TestCase):
    def test_the_notice_names_the_environment_and_the_text(self):
        sent = []

        def send(request):
            sent.append(request)
            return transport.Response(202, "{}")

        notify.announce("stage", "2.4.1 is out", send=send)
        self.assertEqual(json.loads(sent[0].body), {"environment": "stage", "text": "2.4.1 is out"})
        self.assertTrue(sent[0].url.endswith("/v2/notices"))

    def test_a_refusal_raises(self):
        with self.assertRaises(notify.NoticeError):
            notify.announce("stage", "x", send=lambda request: transport.Response(500, "down"))


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/unit/test_scheduler.py <<'PY'
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from shipyard import scheduler
from tests.unit.helpers import ScratchLog


class SchedulerTest(ScratchLog):
    def test_each_probe_appends_one_line(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(scheduler, "LOGS", Path(folder)):
                scheduler.run("stage", datetime(2026, 10, 20, 6, 0, tzinfo=timezone.utc))
                lines = (Path(folder) / "stage.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual([line.split()[1] for line in lines], sorted(scheduler.probes.PROBES))
        self.assertTrue(all(line.startswith("2026-10-20T06:00:00Z") for line in lines))


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/host/test_agent_link.py <<'PY'
"""The deploy agent's link, checked on the host before a release."""

import unittest

from shipyard import agent_link


class AgentLinkTest(unittest.TestCase):
    def test_agent_answers_ping(self):
        self.assertTrue(agent_link.ping())

    def test_agent_reports_its_version(self):
        self.assertRegex(agent_link.version(), r"^\d+\.\d+\.\d+$")

    def test_stage_handshake(self):
        self.assertTrue(agent_link.handshake("stage"))


if __name__ == "__main__":
    unittest.main()
PY

cat > bin/gate <<'SH'
#!/usr/bin/env bash
# The release gate: every test, unit and host, as the release runs it before a cut.
set -euo pipefail
cd "$(dirname "$0")/.."
exec "${PYTHON:-python3}" -B -m unittest discover -s tests -t . "$@"
SH
chmod +x bin/gate

cat > Makefile <<'MK'
PYTHON ?= python3

.PHONY: test gate

# The unit tests: fast, and enough for most changes.
test:
	$(PYTHON) -B -m unittest discover -s tests/unit -t .

# The release gate (bin/gate): every test, unit and host.
gate:
	bin/gate
MK
