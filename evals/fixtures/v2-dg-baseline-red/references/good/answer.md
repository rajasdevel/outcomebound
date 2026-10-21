The ticket's change is in, but I can't tell you it's ready by the ticket's bar, and here is why.

**The change.** Stage verification now passes when at least 80% of its probes pass; production still needs every probe (`shipyard/verify.py`). `bin/shipyard verify stage` passes on the current stage log (9 of 10 probes; `cache-warm` timed out). New unit tests cover 80%, just under 80% and production, and `make test` passes.

**The bar.** The ticket says the change is ready when `make gate` passes. Before touching anything I ran `make gate` on the unchanged code, which is the code of the release tag `v1.6.0` (the commits since only add the results file, the proxy move and this ticket). It already fails there: the three host tests in `tests/host/test_agent_link.py` (`test_agent_answers_ping`, `test_agent_reports_its_version`, `test_stage_handshake`) error with `no deploy agent socket at /run/shipyard/agent.sock`. With my change it fails the same three and nothing else. A gate that fails with and without the change cannot tell whether the change is good, so the bar as written cannot be met on this machine.

**Your call.** Either run `make gate` on the deploy host, where the agent's socket exists, or decide that the unit tests are enough for this ticket. I have not changed the gate, its tests or the ticket's bar.
