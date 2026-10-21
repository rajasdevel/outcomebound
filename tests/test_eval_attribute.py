"""`evals/attribute.py`: what each kept run's tokens are charged to, read from synthetic native
sessions in the shape Codex writes. No model call."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.eval_helpers import load

ATTRIBUTE = load("eval_attribute", "evals/attribute.py")

PLUGIN_SKILLS = "- acme:capture: Keep notes. (file: r0/acme/capture/SKILL.md)\n"
CATALOG = (
    "<skills_instructions>\n### Available skills\n"
    "- draw: Make images. (file: r1/draw/SKILL.md)\n"
    "- diagnose: Use when a failure's cause is unknown. (file: r2/diagnose/SKILL.md)\n"
)


def message(role: str, text: str) -> dict[str, Any]:
    content = [{"type": "input_text", "text": text}]
    return {
        "type": "response_item",
        "payload": {"type": "message", "role": role, "content": content},
    }


def exec_call(call_id: str, *commands: str) -> dict[str, Any]:
    """One exec script issuing a `tools.exec_command` per command, as Codex records it."""

    script = "".join(
        f'text(await tools.exec_command({{cmd:{json.dumps(cmd)},"max_output_tokens":6000}}));\n'
        for cmd in commands
    )
    payload = {"type": "custom_tool_call", "call_id": call_id, "name": "exec", "input": script}
    return {"type": "response_item", "payload": payload}


def exec_output(call_id: str, *sizes: int) -> dict[str, Any]:
    header = {"type": "input_text", "text": "Script completed\nWall time 0.1 seconds\nOutput:\n"}
    items = [{"type": "input_text", "text": "x" * size} for size in sizes]
    payload = {"type": "custom_tool_call_output", "call_id": call_id, "output": [header, *items]}
    return {"type": "response_item", "payload": payload}


def token_count(
    total: int, inp: int, cached: int = 0, out: int = 0, reasoning: int = 0
) -> dict[str, Any]:
    last = {
        "input_tokens": inp,
        "cached_input_tokens": cached,
        "output_tokens": out,
        "reasoning_output_tokens": reasoning,
        "total_tokens": inp + out,
    }
    info = {"last_token_usage": last, "total_token_usage": {**last, "input_tokens": total}}
    return {"type": "event_msg", "payload": {"type": "token_count", "info": info}}


def plain_session(catalog: str = CATALOG) -> list[dict[str, Any]]:
    """Three model calls: the first reads two files (300 and 100 characters of output), the
    second runs git status, the third answers."""

    return [
        message("developer", catalog),
        message("user", "Task: fix it."),
        exec_call("c1", "cat src/a.py", "rg -n foo src"),
        exec_output("c1", 300, 100),
        token_count(1000, 1000, cached=600),
        exec_call("c2", "git status --short"),
        exec_output("c2", 50),
        token_count(2300, 1300, cached=1000, out=10, reasoning=10),
        token_count(3700, 1400, cached=1200, out=40, reasoning=5),
    ]


def test_increase_is_charged_to_the_previous_calls_tools_by_output_size() -> None:
    calls, _catalog = ATTRIBUTE.session(plain_session())
    assert [call.input for call in calls] == [1000, 1300, 1400]
    # The script's header is shared equally between the two calls it ran.
    assert [tool.output_chars for tool in calls[0].tools] == [323, 123]
    cost, per_tool = ATTRIBUTE.attribution(calls)

    # The 300-token rise into call 1 belongs to call 0's two reads, split by output size and
    # re-sent by the two calls from call 1 on; the 100-token rise into call 2 belongs to git.
    assert cost["preamble"] == 3000
    assert round(cost["read"]) == 600
    assert round(per_tool[0]) == round(600 * 323 / 446)
    assert round(per_tool[1]) == round(600 * 123 / 446)
    assert cost["git"] == 100
    assert sum(cost.values()) == sum(call.input for call in calls)


def test_visible_output_of_the_previous_call_is_charged_to_model_output_first() -> None:
    records = plain_session()
    records[4] = token_count(1000, 1000, out=80, reasoning=30)
    cost, _per_tool = ATTRIBUTE.attribution(ATTRIBUTE.session(records)[0])
    assert cost["model-output"] == 50 * 2
    assert round(cost["read"]) == 250 * 2


def test_a_repeated_token_count_is_one_call() -> None:
    records = plain_session()
    records.insert(5, records[4])
    calls, _catalog = ATTRIBUTE.session(records)
    assert len(calls) == 3


def test_each_tool_of_one_exec_script_takes_its_own_class() -> None:
    calls, _catalog = ATTRIBUTE.session(plain_session())
    assert [tool.cls for tool in calls[0].tools] == ["read", "read"]
    records = [
        exec_call("c1", "cat .outcomebound/fragments/commands.md", "make test-integration"),
        exec_output("c1", 10, 20),
        token_count(5, 5),
    ]
    tools = ATTRIBUTE.session(records)[0][0].tools
    assert [tool.cls for tool in tools] == ["guidance-read", "suite-run"]


def test_classes() -> None:
    def classed(command: str, tool: str = "exec_command") -> str:
        return ATTRIBUTE.classify(tool, command)

    # The suite is executed, not read.
    assert classed("cat tools/run_integration.py") == "read"
    assert classed("cat tests/integration/run_suite.py; git status") == "git"
    assert classed("python3 -B tools/run_integration.py") == "suite-run"
    assert classed("timeout 300 python3 tests/integration/run.py") == "suite-run"
    assert classed("make check && make test > log 2>&1") == "suite-run"
    assert classed("python3 -m unittest discover -s tests/integration") == "suite-run"
    assert classed("make test-unit") == "checks"
    assert classed("python3 -m unittest tests.test_cli") == "checks"
    # Only the OutcomeBound install is guidance; a personal plugin's SKILL.md is a read.
    assert classed("cat .agents/skills/diagnose/SKILL.md") == "guidance-read"
    assert classed("cat .agents/skills/my-own/SKILL.md") == "read"
    assert classed("cat ~/.codex/skills/pdf/SKILL.md") == "read"
    assert classed("outcomebound where") == "guidance-read"
    assert classed("rg -n outcomebound docs") == "read"
    # A here-document is data, not a command.
    assert classed("python3 - <<'PY'\nprint('make test')\nPY") == "other"
    assert classed("bin/envctl status stage") == "env"
    assert classed("python3 bin/envctl logs prod") == "env"
    assert classed("cat > notes.md <<'EOF'\nx\nEOF") == "write"
    assert classed("", "write_stdin") == "poll"
    assert classed("y\n", "write_stdin") == "other"
    assert classed('{"cell_id":"7"}', "wait") == "poll"
    assert classed("apply_patch src/a.py", "apply_patch") == "write"


def test_the_suite_is_read_from_the_replica_bases() -> None:
    suite = ATTRIBUTE.suite_from_sources(
        [
            "test-integration:\n\t$(PYTHON) -B tools/run_integration.py\n"
            "test: unit test-integration\n.PHONY: test-integration\n"
        ]
    )
    assert suite.scripts == frozenset({"tools/run_integration.py"})
    assert suite.targets == frozenset({"test", "test-integration"})
    assert ATTRIBUTE.SUITE.scripts and "test" in ATTRIBUTE.SUITE.targets


def write_run(folder: Path, fixture: str, arm: str, records: list[dict[str, Any]]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    meta = {"fixture": fixture, "arm": arm, "claims": {}, "fixture_repo": str(folder / "gone")}
    (folder / f"{fixture}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    lines = "".join(json.dumps(record) + "\n" for record in records)
    (folder / f"{fixture}.native.jsonl").write_text(lines, encoding="utf-8")


def test_cached_uncached_and_a_catalog_that_differs_are_reported(tmp_path: Path) -> None:
    write_run(tmp_path / "one", "fx", "none", plain_session())
    write_run(tmp_path / "two", "fx", "none", plain_session(CATALOG + PLUGIN_SKILLS))
    runs, skipped = ATTRIBUTE.read_runs([tmp_path / "one", tmp_path / "two"])
    assert skipped == []
    assert runs[0]["input"] == 3700 and runs[0]["cached"] == 2800 and runs[0]["uncached"] == 900
    assert runs[0]["output"] == 50 and runs[0]["reasoning"] == 15
    assert runs[0]["suite_completed"].startswith("UNVERIFIED")
    document = ATTRIBUTE.report(runs, skipped)
    group = document["arms"]["none"]
    assert group["catalog"]["differ"] is True
    assert group["catalog"]["namespaces"] == ["acme"]
    assert group["catalog"]["skill_entries"] == [2, 3]
    assert "FLAG: runs saw different skill lists" in ATTRIBUTE.text(document)


def test_a_guidance_file_read_costs_its_output_times_later_calls(tmp_path: Path) -> None:
    records = [
        exec_call("c1", "cat .outcomebound/fragments/commands.md"),
        exec_output("c1", 400),
        token_count(100, 100),
        token_count(300, 200),
        token_count(600, 300),
    ]
    calls, _catalog = ATTRIBUTE.session(records)
    read = ATTRIBUTE.guidance_reads(calls)
    chars = calls[0].tools[0].output_chars
    assert read == {".outcomebound/fragments/commands.md": chars / 4 * 2}
