import json
import subprocess
import sys
import tempfile
from pathlib import Path


def require(condition, context):
    if not condition:
        raise ValueError(context)


CASE = globals().get("CASE")
root = Path.cwd()


def event(key, version, value, deleted=False):
    return {"key": key, "version": version, "value": value, "deleted": deleted}


def action(key, version, name):
    return {"key": key, "version": version, "action": name}


with tempfile.TemporaryDirectory() as temp:
    p = Path(temp)
    db = p / "state.sqlite"
    source = p / "events.jsonl"

    def call(command, rows=None, raw=None):
        if command != "inspect":
            source.write_text(
                raw if raw is not None else "".join(json.dumps(row) + "\n" for row in rows)
            )
        argv = [sys.executable, "-B", "-m", "datapipe.reconcile", command]
        if command != "inspect":
            argv.append(str(source))
        original = source.read_bytes() if command != "inspect" else None
        done = subprocess.run([*argv, "--db", str(db)], cwd=root, capture_output=True, text=True)
        if original is not None:
            require(source.read_bytes() == original, "input file was mutated")
        return done

    def ok(command, rows=None):
        done = call(command, rows)
        require(done.returncode == 0, done.stderr)
        return json.loads(done.stdout)

    initial = [event("a", 1, 7), event("b", 1, 11)]
    expected = {
        "actions": [action("a", 1, "insert"), action("b", 1, "insert")],
        "active_count": 2,
        "total_value": 18,
    }
    require(
        ok("inspect") == {"items": [], "active_count": 0, "total_value": 0},
        "grader observation failed",
    )
    require(not db.exists(), "grader observation failed")
    require(ok("plan", initial) == expected, "grader observation failed")
    require(not db.exists(), "grader observation failed")
    require(ok("apply", initial) == expected, "grader observation failed")
    before = db.read_bytes()
    later = [event("a", 2, 9), event("b", 2, 0, True), event("a", 1, 7), event("a", 0 + 1, 7)]
    expected_later = {
        "actions": [
            action("a", 2, "update"),
            action("b", 2, "delete"),
            action("a", 1, "duplicate"),
            action("a", 1, "duplicate"),
        ],
        "active_count": 1,
        "total_value": 9,
    }
    if CASE == "planning":
        require(ok("plan", later) == expected_later, "grader observation failed")
        require(db.read_bytes() == before, "grader observation failed")
        require(
            sorted(x.name for x in p.iterdir()) == ["events.jsonl", "state.sqlite"],
            "grader observation failed",
        )
    if CASE == "restart":
        require(ok("apply", later) == expected_later, "grader observation failed")
        require(
            ok("apply", [event("b", 1, 11), event("a", 2, 9)])
            == {
                "actions": [action("b", 1, "duplicate"), action("a", 2, "duplicate")],
                "active_count": 1,
                "total_value": 9,
            },
            "grader observation failed",
        )
        require(
            ok("apply", [event("a", 4, 13), event("a", 3, 12)])
            == {
                "actions": [action("a", 4, "update"), action("a", 3, "stale")],
                "active_count": 1,
                "total_value": 13,
            },
            "grader observation failed",
        )
        state = ok("inspect")
        require(
            state
            == {
                "items": [event("a", 4, 13), event("b", 2, 0, True)],
                "active_count": 1,
                "total_value": 13,
            },
            "grader observation failed",
        )
    if CASE == "rollback":
        failed = call("apply", [event("c", 1, 100), event("a", 1, 99)])
        require((failed.returncode, failed.stdout) == (2, ""), "grader observation failed")
        require(
            json.loads(failed.stderr) == {"code": "E102", "line": 2}, "grader observation failed"
        )
        require(db.read_bytes() == before, "grader observation failed")
        require(
            ok("apply", [event("c", 1, 100)])["actions"] == [action("c", 1, "insert")],
            "grader observation failed",
        )
    if CASE == "validation":
        invalid = [
            True,
            [],
            event("a", True, 7),
            event("a", 2, False),
            event("a", -1, 7),
            event("", 2, 7),
            event("a", 2, -1),
            {**event("a", 2, 7), "extra": 1},
            {**event("a", 2, 7), "deleted": 1},
            {"key": "a", "version": 2},
        ]
        for bad in invalid:
            done = call("apply", [event("c", 1, 100), bad])
            require((done.returncode, done.stdout) == (2, ""), (bad, done.stdout, done.stderr))
            require(
                json.loads(done.stderr) == {"code": "E102", "line": 2}, "grader observation failed"
            )
            require(db.read_bytes() == before, "grader observation failed")
        done = call("apply", raw="\n{bad json}\n")
        require(json.loads(done.stderr) == {"code": "E102", "line": 2}, "grader observation failed")
        require(db.read_bytes() == before, "grader observation failed")
