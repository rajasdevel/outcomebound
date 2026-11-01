import hashlib
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


def call(*args):
    return subprocess.run(
        [sys.executable, "-B", "-m", "tally.bundles", *map(str, args)],
        cwd=root,
        capture_output=True,
        text=True,
    )


def ok(*args):
    done = call(*args)
    require(done.returncode == 0, done.stderr)
    return json.loads(done.stdout)


def refused(code, *args):
    done = call(*args)
    require((done.returncode, done.stdout) == (2, ""), (done.returncode, done.stdout, done.stderr))
    require(json.loads(done.stderr)["code"] == code, done.stderr)


with tempfile.TemporaryDirectory() as temp:
    p = Path(temp)
    source = p / "a.csv"
    source.write_text(
        "day,project,person,minutes,note\n2026-02-01,alpha,member,10,\n2026-02-02,beta,member,20,\n2026-02-03,alpha,other,30,\n"
    )
    original = source.read_bytes()
    s = ok(
        "build",
        source,
        source,
        "--out",
        p / "one",
        "--since",
        "2026-02-02",
        "--until",
        "2026-02-03",
    )
    require(
        s
        == {
            "entry_count": 2,
            "duplicate_count": 3,
            "total_minutes": 50,
            "by": "project",
            "rows": [
                {"key": "alpha", "entry_count": 1, "total_minutes": 30},
                {"key": "beta", "entry_count": 1, "total_minutes": 20},
            ],
        },
        s,
    )
    require(
        sorted(path.name for path in (p / "one").iterdir())
        == ["entries.csv", "manifest.json", "summary.json"],
        "bundle files",
    )
    manifest = json.loads((p / "one" / "manifest.json").read_text())
    expected_digests = {
        name: hashlib.sha256((p / "one" / name).read_bytes()).hexdigest()
        for name in ("entries.csv", "summary.json")
    }
    require(manifest == {"schema": 1, "files": expected_digests}, "manifest digests")
    require(
        json.loads((p / "one" / "summary.json").read_text()) == s,
        "summary artifact differs from stdout",
    )
    require(ok("verify", p / "one") == {"valid": True}, "grader observation failed")
    require(source.read_bytes() == original, "grader observation failed")
    refused("E104", "build", source, "--out", p / "one")
    refused(
        "E104",
        "build",
        source,
        "--out",
        p / "reverse",
        "--since",
        "2026-02-03",
        "--until",
        "2026-02-01",
    )
    refused("E101", "build", p / "absent.csv", "--out", p / "missing")
    require(
        not (p / "reverse").exists() and (not (p / "missing").exists()), "grader observation failed"
    )
    if CASE == "integrity":
        summary_path = p / "one" / "summary.json"
        summary = json.loads(summary_path.read_text())
        summary["total_minutes"] = 999
        summary_path.write_text(json.dumps(summary))
        manifest_path = p / "one" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["summary.json"] = hashlib.sha256(summary_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        refused("E102", "verify", p / "one")
        ok("build", source, "--out", p / "link")
        entry = p / "link" / "entries.csv"
        entry.unlink()
        entry.symlink_to(source)
        refused("E102", "verify", p / "link")
        ok("build", source, "--out", p / "corrupt")
        (p / "corrupt" / "entries.csv").write_text("bad")
        refused("E102", "verify", p / "corrupt")
    if CASE == "diff":
        other = p / "b.csv"
        other.write_text("day,project,person,minutes,note\n2026-02-01,gamma,member,9,\n")
        ok("build", other, "--out", p / "two")
        require(
            ok("diff", p / "one", p / "two")
            == {
                "by": "project",
                "rows": [
                    {
                        "key": "alpha",
                        "before_minutes": 30,
                        "after_minutes": 0,
                        "delta_minutes": -30,
                    },
                    {"key": "beta", "before_minutes": 20, "after_minutes": 0, "delta_minutes": -20},
                    {"key": "gamma", "before_minutes": 0, "after_minutes": 9, "delta_minutes": 9},
                ],
            },
            "grader observation failed",
        )
        ok("build", other, "--out", p / "person", "--by", "person")
        refused("E104", "diff", p / "one", p / "person")
    if CASE == "groups":
        for by, keys in [
            ("person", ["member", "other"]),
            ("week", ["2026-W05", "2026-W06"]),
            ("day", ["2026-02-01", "2026-02-02", "2026-02-03"]),
        ]:
            result = ok("build", source, "--out", p / by, "--by", by)
            require([row["key"] for row in result["rows"]] == keys, result)
        empty = p / "empty.csv"
        empty.write_text("day,project,person,minutes,note\n")
        require(ok("build", empty, "--out", p / "empty")["rows"] == [], "grader observation failed")
        bad = p / "bad.csv"
        bad.write_text("day,project,person,minutes,note\n2026-02-01,alpha,member,-1,\n")
        refused("E102", "build", bad, "--out", p / "bad")
        require(not (p / "bad").exists(), "grader observation failed")
        missing_column = p / "missing-column.csv"
        missing_column.write_text("day,project,person,note\n2026-02-01,alpha,member,\n")
        refused("E102", "build", missing_column, "--out", p / "missing-column")
        require(not (p / "missing-column").exists(), "partial output on invalid columns")

    require(not list(p.glob(".bundle-*")), "grader observation failed")
