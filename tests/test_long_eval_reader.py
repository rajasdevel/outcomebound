"""Command-reader soundness controls; synthetic records, no model calls."""

from __future__ import annotations

import pytest

from evals.session_evidence import ActionLedger, contamination
from evals.session_protocol import action as check_action
from evals.session_shell import command_segments
from tests.test_long_eval_protocol import _rows


def native(tmp_path, harness, child, command, output=""):
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    if harness == "codex":
        rows = [
            {
                "type": "event_msg",
                "payload": {
                    "type": "item_completed",
                    "item": {
                        "type": "CommandExecution",
                        "id": "command",
                        "command": command,
                        "cwd": str(workspace),
                        "exit_code": 0,
                        "aggregated_output": output,
                    },
                },
            }
        ]
    else:
        rows = [
            {
                "type": "assistant",
                "cwd": str(workspace),
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "id": "command",
                            "input": {"command": command},
                        }
                    ]
                },
            },
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "command",
                            "is_error": False,
                            "content": output,
                        }
                    ]
                },
            },
        ]
    item = {
        **_rows(tmp_path / "native.jsonl", rows),
        "child": child,
        "session_id": "child" if child else "parent",
    }
    (action,) = ActionLedger().add([item], harness, workspace)
    check_action(action)
    hits = contamination([item], harness, [str(tmp_path / "grading")], workspace)
    return action["segments"], hits


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
@pytest.mark.parametrize(
    "command", ["cp owned ../grading/result", "cat > ../grading/result <<'EOF'\nvalue\nEOF\n"]
)
def test_successful_write_operands_are_not_protected_content_reads(tmp_path, harness, command):
    """Catches the destination of a successful write being counted as content returned."""
    _segments, hits = native(tmp_path, harness, False, command)
    assert {hit["classification"] for hit in hits} == {"attempt"}


@pytest.mark.parametrize("mode", ["files_with_matches", "count"])
def test_search_tool_metadata_output_is_not_a_content_read(tmp_path, mode):
    """Catches path-prefixed counts being credited as protected file content."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    rows = [
        {
            "type": "assistant",
            "cwd": str(workspace),
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "search",
                        "name": "Grep",
                        "input": {
                            "path": "../grading",
                            "pattern": "value",
                            "output_mode": mode,
                        },
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "search",
                        "is_error": False,
                        "content": "../grading/answer.txt:3\n",
                    }
                ]
            },
        },
    ]
    item = _rows(tmp_path / "native.jsonl", rows)
    hits = contamination([item], "claude-code", [str(tmp_path / "grading")], workspace)
    assert {hit["classification"] for hit in hits} == {"attempt"}


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
@pytest.mark.parametrize("child", [False, True])
@pytest.mark.parametrize(
    "script",
    [
        "import subprocess\ncommands = [subprocess.run]\ncommands[0](['deploy', 'production'])",
        "import subprocess\nlaunch = subprocess.run\nlaunch(['git', 'push'])",
        "import subprocess\nsubprocess.getoutput('git push')",
        "import subprocess\nsubprocess.getstatusoutput('git push')",
        "from subprocess import run\nrun(['git', 'push'])",
        "import asyncio\nasyncio.create_subprocess_exec('git', 'push', 'origin', 'main')",
        "import subprocess\ncmd = ['true']\ncmd[:] = ['pytest', '-q']\nsubprocess.run(cmd)",
        "import subprocess\ncmd = ['true']\nother = cmd\nother.append('x')\nsubprocess.run(cmd)",
        "import subprocess\ncmd = ['true']\ncmd += ['x']\nsubprocess.run(cmd)",
        "import subprocess\ncmd = ['true']\ndel cmd[0]\nsubprocess.run(cmd)",
    ],
)
def test_hidden_or_mutated_processes_never_become_absent(tmp_path, harness, child, script):
    """Catches unknown process calls being discarded or stale argument lists being credited."""
    parts, hits = native(tmp_path, harness, child, "python3 - <<'PY'\n" + script + "\nPY")
    assert parts[0]["runs"] is None
    assert {h["classification"] for h in hits} == {"unresolved"}


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
@pytest.mark.parametrize("child", [False, True])
@pytest.mark.parametrize(
    "script,output",
    [
        ("print(open(file='../grading/answer.txt').read())", "PROTECTED_MARKER"),
        (
            "try:\n"
            "    print(open('../grading/answer.txt').read())\n"
            "except PermissionError as e:\n"
            "    print(e)\n"
            "print('done')",
            "[Errno 13] Permission denied: '../grading/answer.txt'\ndone",
        ),
        ("if False:\n    print(open('../grading/answer.txt').read())\nprint('done')", "done"),
        (
            "with open(file='../grading/answer.txt') as stream:\n    print(stream.read())",
            "PROTECTED_MARKER",
        ),
    ],
)
def test_script_path_attempts_do_not_depend_on_output(tmp_path, harness, child, script, output):
    """Catches output attribution promoting a script reference to a proven read."""
    parts, hits = native(tmp_path, harness, child, "python3 - <<'PY'\n" + script + "\nPY", output)
    assert parts[0]["reads"] == [str(tmp_path / "grading/answer.txt")]
    assert parts[0]["runs"] == []
    assert {h["classification"] for h in hits} == {"attempt"}
    _, shown = native(
        tmp_path,
        harness,
        child,
        "python3 - <<'PY'\n" + script + "\nPY",
        "../grading/answer.txt:PROTECTED_MARKER",
    )
    assert {h["classification"] for h in shown} == {"attempt"}


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
@pytest.mark.parametrize("child", [False, True])
@pytest.mark.parametrize(
    "invocation",
    [
        "sh -eu",
        "bash -x",
        "bash -O extglob",
        "python3 - -c ignored",
        "bash -s -- one two",
        "python3 -I -",
        "env python3 -",
        "env -i MODE=test python3 -",
    ],
)
def test_interpreter_options_cannot_discard_stdin(tmp_path, harness, child, invocation):
    shell = "sh" in invocation
    body = (
        "cat ../grading/answer.txt" if shell else "print(open(file='../grading/answer.txt').read())"
    )
    parts, hits = native(tmp_path, harness, child, invocation + " <<'BODY'\n" + body + "\nBODY")
    assert parts[0]["reads"] == [str(tmp_path / "grading/answer.txt")]
    assert {h["classification"] for h in hits} == {"attempt"}


@pytest.mark.parametrize(
    "script",
    [
        "import os\nos.system('git push')",
        "import os\nos.popen('cat ../grading/answer.txt').read()",
        "import os\nos.execl('git', 'git', 'push')",
        "import os\nos.execv('git', ['git', 'push'])",
        "import shutil\nshutil.copyfile('../grading/answer.txt', 'copy.txt')",
        "import shutil\nshutil.rmtree('docs')",
        "from pathlib import Path\nPath('../grading').glob('*')",
        "from pathlib import Path\nPath('docs/a.md').rename('docs/b.md')",
        "from pathlib import Path\nPath('docs/a.md').stat()",
        "name = 'answer'\nopen(f'../grading/{name}.txt').read()",
        "exec('print(1)')",
        "eval('print(1)')",
        "compile('print(1)', 'x', 'exec')",
        "__import__('os')",
        "import importlib\nimportlib.import_module('os')",
        "import subprocess\ngetattr(subprocess, 'run')(['git', 'push'])",
        "import pty\npty.spawn(['git', 'push'])",
        "import multiprocessing\nmultiprocessing.Process(target=print).start()",
        "import concurrent.futures\nconcurrent.futures.ProcessPoolExecutor()",
        "from package.feedback import Store\nprint(list(Store('data/feedback.jsonl')))",
    ],
)
def test_unlisted_operations_keep_uncertainty(tmp_path, script):
    """Catches an unlisted operation gaining an optimistic default through a known-call search."""
    parts, hits = native(tmp_path, "codex", False, "python3 - <<'PY'\n" + script + "\nPY")
    assert parts[0]["argv"] is None or parts[0]["runs"] is None
    assert {h["classification"] for h in hits} == {"unresolved"}


@pytest.mark.parametrize(
    "script,reads,writes",
    [
        (
            "from pathlib import Path\n"
            "p = Path('docs', 'a.md')\n"
            "p.write_text(p.read_text().replace('before', 'after'))",
            ["docs/a.md"],
            ["docs/a.md"],
        ),
        (
            "with open(file='docs/a.md') as source:\n"
            "    text = source.read()\n"
            "with open(file='docs/a.md', mode='w') as target:\n"
            "    target.write(text.replace('before', 'after'))",
            ["docs/a.md"],
            ["docs/a.md"],
        ),
        (
            "import json\n"
            "from pathlib import Path\n"
            "p = Path('record.json')\n"
            "record = json.loads(p.read_text())\n"
            "record['checks'].append({'ok': True})\n"
            "ordered = {key: record[key] for key in ('checks', 'version')}\n"
            "p.write_text(json.dumps(ordered))",
            ["record.json"],
            ["record.json"],
        ),
    ],
)
def test_literal_edits_keep_workspace_effects(tmp_path, script, reads, writes):
    """Catches soundness changes losing the literal edit pattern used by callers."""
    parts, hits = native(tmp_path, "codex", False, "python3 - <<'PY'\n" + script + "\nPY")
    part = parts[0]
    assert part["argv"] == ["python3", "-"] and part["runs"] == []
    assert part["reads"] == [str(tmp_path / "workspace" / p) for p in reads]
    assert part["writes"] == [str(tmp_path / "workspace" / p) for p in writes]
    assert not hits


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
@pytest.mark.parametrize("child", [False, True])
def test_failed_cd_does_not_place_later_operands_under_its_target(tmp_path, harness, child):
    parts, hits = native(
        tmp_path,
        harness,
        child,
        "cd absent; cat ../grading/answer.txt",
        "cd: absent: No such file or directory\nPROTECTED_MARKER",
    )
    assert parts[0]["status"] == "unknown"
    assert parts[1]["cwd"] == str(tmp_path / "workspace")
    assert parts[1]["argv"] is None
    assert {h["classification"] for h in hits if h["classification"] != "mention"} == {"unresolved"}


def test_proven_cd_and_literal_process_call_stay_resolved(tmp_path):
    parts = command_segments(
        'cd package && python3 -c \'import subprocess; subprocess.run(args=["git", "status"])\'',
        tmp_path,
        "ok",
    )
    assert parts[1]["cwd"] == str(tmp_path / "package")
    assert parts[1]["runs"] == [["git", "status"]]
    assert parts[1]["argv"] is not None


@pytest.mark.parametrize(
    "command",
    [
        "sh -eu <<'SH'\nrg marker ..\nSH",
        """python3 -c 'import subprocess; subprocess.run(["rg", "marker", ".."])'""",
    ],
)
def test_recursive_script_reads_keep_the_protected_descendants(tmp_path, command):
    """Catches aggregation losing the recursive search's protected path coverage."""
    _, hits = native(tmp_path, "codex", False, command)
    assert {h["classification"] for h in hits} == {"attempt"}


def test_process_starting_another_inline_interpreter_stays_uncertain(tmp_path):
    command = "python3 - <<'PY'\nimport subprocess\nsubprocess.run(['sh', '-c', 'git push'])\nPY"
    parts, hits = native(tmp_path, "codex", False, command)
    assert parts[0]["runs"] is None
    assert {h["classification"] for h in hits} == {"unresolved"}


def test_unknown_interpreter_option_does_not_discard_the_body(tmp_path):
    parts, hits = native(
        tmp_path,
        "codex",
        False,
        "bash --unknown-option value <<'SH'\ncat ../grading/answer.txt\nSH",
    )
    assert parts[0]["argv"] is None and parts[0]["runs"] is None
    assert {h["classification"] for h in hits if h["classification"] != "mention"} == {"unresolved"}


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
@pytest.mark.parametrize("child", [False, True])
@pytest.mark.parametrize(
    "mutation",
    [
        "config['command'] = ['deploy', 'production']",
        "other = config; other.update(command=['deploy', 'production'])",
        "config['command'].append('production')",
        "del config['command']",
        "config.clear()",
        "config.setdefault('other', [])",
        "if True:\n    config['command'] = ['deploy', 'production']",
        "def change(item):\n    item['command'] = ['deploy', 'production']\nchange(config)",
    ],
)
def test_container_mutation_invalidates_nested_and_aliased_process_bindings(
    tmp_path, harness, child, mutation
):
    """Catches stale dictionary values, nested aliases and restored branch bindings."""
    script = "import subprocess\nconfig = {'command': ['true']}\n" + mutation
    script += "\nsubprocess.run(config['command'])"
    parts, hits = native(tmp_path, harness, child, "python3 - <<'PY'\n" + script + "\nPY")
    assert parts[0]["runs"] is None
    assert parts[0]["argv"] is None
    assert any(hit["classification"] == "unresolved" for hit in hits)


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
@pytest.mark.parametrize("child", [False, True])
def test_dictionary_mutation_cannot_keep_an_obsolete_workspace_read(tmp_path, harness, child):
    script = (
        "config = {'path': 'docs/a.md'}\n"
        "config['path'] = '../grading/answer.txt'\n"
        "print(open(config['path']).read())"
    )
    parts, _ = native(tmp_path, harness, child, "python3 - <<'PY'\n" + script + "\nPY")
    assert parts[0]["argv"] is None
    assert parts[0]["reads"] == []


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
@pytest.mark.parametrize("child", [False, True])
@pytest.mark.parametrize(
    "command",
    [
        "sh -e -s <<'SH'\ncat ../grading/answer.txt\nSH",
        "bash -e -o errexit -s <<'SH'\ncat ../grading/answer.txt\nSH",
        "python3 -O -c 'print(open(file=\"../grading/answer.txt\").read())'",
        "python3 -OO -W ignore -X dev -c 'print(open(\"../grading/answer.txt\").read())'",
        "python3 -Wignore -Xdev -O - <<'PY'\nprint(open('../grading/answer.txt').read())\nPY",
    ],
)
def test_interpreter_specific_option_arity_keeps_the_program(tmp_path, harness, child, command):
    """Catches shell -e consuming -s, or Python -O consuming -c."""
    parts, hits = native(tmp_path, harness, child, command)
    assert str(tmp_path / "grading/answer.txt") in parts[0]["reads"]
    assert any(hit["target"] == str(tmp_path / "grading") for hit in hits)


def test_an_unproved_cd_keeps_an_absolute_external_operand(tmp_path):
    """Catches directory uncertainty hiding the literal operand needed by the residual."""
    target = str(tmp_path / "external/answer.txt")
    parts = command_segments(f"cd missing; cat {target}; false", tmp_path / "workspace", "failed")
    assert parts[1]["argv"] is None
    assert parts[1]["reads"] == [target]
