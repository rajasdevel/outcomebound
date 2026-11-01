"""The long-session protocol checker accepts the documented records and refuses broken ones."""

import pytest

from evals import session_protocol as P

DECLARED = ("opener", "directive", "ruling", "nudge")


@pytest.mark.parametrize("mode", ["content", "files_with_matches", "count"])
def test_search_output_modes_are_accepted(mode):
    record = {
        "kind": "tool",
        "tool": "Grep",
        "session_id": "s",
        "child": False,
        "output_mode": mode,
    }
    P.action(record)


@pytest.mark.parametrize("mode", [None, "filenames", True, 1, []])
def test_invalid_search_output_modes_are_refused(mode):
    with pytest.raises(P.ProtocolError, match="output_mode"):
        P.action(
            {"kind": "tool", "tool": "Grep", "session_id": "s", "child": False, "output_mode": mode}
        )


def test_a_turn_gets_its_defaults():
    turn = P.next_turn({"label": "ruling", "message": "Use B."}, DECLARED)
    assert turn == {
        "label": "ruling",
        "message": "Use B.",
        "required": False,
        "clarification": False,
        "wait_seconds": 0,
    }


@pytest.mark.parametrize(
    "document",
    [
        {"label": "approve", "message": "yes"},
        {"label": "ruling", "message": " "},
        {"label": "ruling", "message": "x", "extra": 1},
        {"label": "ruling", "message": "x", "wait_seconds": 9000},
        {"end": True},
        {"end": True, "reason": "done", "protocol_defect": "yes"},
    ],
)
def test_broken_outputs_are_refused(document):
    with pytest.raises(P.ProtocolError):
        P.next_turn(document, DECLARED)


def test_an_end_keeps_the_protocol_defect_flag():
    assert P.next_turn({"end": True, "reason": "?", "protocol_defect": True}, DECLARED)[
        "protocol_defect"
    ]


def _turn(number, actions):
    return {
        "turn": number,
        "label": "opener",
        "message": "m",
        "answer": "a",
        "answer_path": "/a",
        "session_id": "s",
        "required": True,
        "clarification": False,
        "actions": actions,
    }


def test_turns_and_actions_documents():
    command = {
        "kind": "command",
        "session_id": "s",
        "child": False,
        "command": "ls",
        "cwd": "/w",
        "argv": ["ls"],
    }
    child = {"kind": "tool", "session_id": "c", "child": True, "tool": "spawn_agent"}
    assert len(P.turns({"version": 1, "turns": [_turn(1, [command, child])]})) == 1
    assert len(P.actions({"version": 1, "actions": [dict(command, turn=1)]})) == 1
    with pytest.raises(P.ProtocolError):
        P.turns({"version": 1, "turns": [_turn(2, [])]})
    with pytest.raises(P.ProtocolError):
        P.actions({"version": 1, "actions": [command]})


@pytest.mark.parametrize("paths", [[], ["/workspace/record.json"], ["C:\\workspace\\record.json"]])
def test_tool_paths_are_absolute_strings(paths):
    P.action(
        {
            "kind": "tool",
            "tool": "Read",
            "session_id": "s",
            "child": False,
            "paths": paths,
            "status": "ok",
        }
    )


@pytest.mark.parametrize("paths", [None, "file.py", ["relative.py"], [1], ["/bad\0path"]])
def test_broken_tool_paths_are_refused(paths):
    with pytest.raises(P.ProtocolError, match="paths"):
        P.action(
            {"kind": "tool", "tool": "Read", "session_id": "s", "child": False, "paths": paths}
        )


def test_declared_labels():
    assert P.labels(["opener", "nudge"]) == ("opener", "nudge")
    for bad in ([], ["Opener"], ["a", "a"]):
        with pytest.raises(P.ProtocolError):
            P.labels(bad)


@pytest.mark.parametrize("ending", [False, True])
@pytest.mark.parametrize("unmatched", [False, True])
def test_unmatched_metadata_survives_output_and_history(ending, unmatched):
    document = (
        {"end": True, "reason": "done"} if ending else {"label": "ruling", "message": "Use B."}
    )
    result = P.next_turn({**document, "unmatched": unmatched}, DECLARED)
    assert result["unmatched"] is unmatched
    row = {**_turn(1, []), "unmatched": unmatched}
    assert P.turns({"version": 1, "turns": [row]})[0]["unmatched"] is unmatched


@pytest.mark.parametrize("unmatched", [None, 1, "true"])
def test_unmatched_must_be_boolean(unmatched):
    for document in ({"label": "ruling", "message": "Use B."}, {"end": True, "reason": "done"}):
        with pytest.raises(P.ProtocolError, match="unmatched"):
            P.next_turn({**document, "unmatched": unmatched}, DECLARED)
    with pytest.raises(P.ProtocolError, match="unmatched"):
        P.turns({"version": 1, "turns": [{**_turn(1, []), "unmatched": unmatched}]})


@pytest.mark.parametrize(
    ("status", "code"),
    [("ok", 0), ("failed", 7), ("failed", None), ("refused", None), ("unknown", None)],
)
def test_command_status_and_exit_code_are_checked(status, code):
    P.action(
        {
            "kind": "command",
            "session_id": "s",
            "child": False,
            "command": "check",
            "cwd": "/w",
            "status": status,
            "exit_code": code,
        }
    )


@pytest.mark.parametrize(
    ("status", "code"),
    [
        ("succeeded", 0),
        (True, 0),
        ("ok", None),
        ("ok", 1),
        ("failed", 0),
        ("refused", 0),
        ("unknown", 0),
        ("failed", True),
    ],
)
def test_false_command_outcomes_are_refused(status, code):
    with pytest.raises(P.ProtocolError):
        P.action(
            {
                "kind": "command",
                "session_id": "s",
                "child": False,
                "command": "check",
                "cwd": "/w",
                "status": status,
                "exit_code": code,
            }
        )


@pytest.mark.parametrize("argv,runs", [(["git", "status"], []), (None, None)])
def test_command_segments_accept_resolved_and_unknown_effects(argv, runs):
    P.action(
        {
            "kind": "command",
            "session_id": "s",
            "child": False,
            "command": "command",
            "cwd": "/w",
            "segments": [
                {
                    "argv": argv,
                    "cwd": "/w",
                    "status": "unknown",
                    "reads": ["/w/a"],
                    "writes": ["/w/b"],
                    "runs": runs,
                }
            ],
        }
    )


@pytest.mark.parametrize(
    "change",
    [
        {"argv": "git status"},
        {"argv": [1]},
        {"argv": ["bad\0arg"]},
        {"cwd": "relative"},
        {"cwd": None},
        {"reads": ["relative"]},
        {"reads": None},
        {"writes": [1]},
        {"status": "refused"},
        {"status": True},
        {"runs": "git status"},
        {"runs": [[]]},
        {"runs": [[1]]},
        {"runs": [["bad\0arg"]]},
        {"extra": True},
    ],
)
def test_command_segments_refuse_invalid_fields(change):
    segment = {
        "argv": ["git", "status"],
        "cwd": "/w",
        "status": "ok",
        "reads": [],
        "writes": [],
        "runs": [],
        **change,
    }
    with pytest.raises(P.ProtocolError, match="segment"):
        P.action(
            {
                "kind": "command",
                "session_id": "s",
                "child": False,
                "command": "git status",
                "cwd": "/w",
                "segments": [segment],
            }
        )


@pytest.mark.parametrize("segments", [None, {}, [None], [{"argv": ["git"]}]])
def test_command_segments_refuse_invalid_containers(segments):
    with pytest.raises(P.ProtocolError, match="segment"):
        P.action(
            {
                "kind": "command",
                "session_id": "s",
                "child": False,
                "command": "git status",
                "cwd": "/w",
                "segments": segments,
            }
        )


@pytest.mark.parametrize("label", ["WORDING only", "COMMAND TEXT only"])
def test_diagnostic_risk_labels_are_optional_and_kept(label):
    plan = {
        "claims": [
            {"name": "observed", "risk": "effect", "required": True},
            {"name": "hint", "risk": label + ": static evidence", "required": False},
        ]
    }
    assert P.diagnostics(plan) == {"hint": label}
    plan["claims"][1]["required"] = True
    with pytest.raises(P.ProtocolError, match="not required"):
        P.diagnostics(plan)
