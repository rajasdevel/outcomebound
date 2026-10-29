"""Build a deterministic service history without a seed copy of the later work."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPLICA = HERE.parents[1] / "replica" / "chatsvc"


def legacy():
    spec = importlib.util.spec_from_file_location("chatsvc_build", REPLICA / "chatsvc_build.py")
    if spec is None or spec.loader is None:
        raise ImportError("chatsvc_build")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def commit(target: Path, message: str, hour: int) -> None:
    module = legacy()
    module.git(target, "add", "-A")
    module.git(target, "commit", "-q", "-m", message, when=f"2026-10-20T{hour:02}:00:00")


def write(target, name, text):
    path = target / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_files(target: Path) -> None:
    for source in sorted((HERE / "project").rglob("*")):
        if source.is_file():
            name = source.relative_to(HERE / "project").as_posix().removesuffix(".in")
            dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(source.read_bytes())


def compatibility_cases(target):
    """A wire compatibility corpus consumed through the service and offline jobs.

    Each row varies an actual wire input: alias, token count, role, Unicode text or caller.
    Expected values are literals from the released v1 protocol, not calls to the service.
    """
    models = ((None, "chat-large-3"), ("large", "chat-large-3"), ("small", "chat-small-3"))
    rows: list[dict[str, object]] = []
    for (requested, resolved), tokens, role, content, caller in product(
        models,
        (1, 512, 4096),
        ("user", "assistant", "system"),
        ("hello", "comma, colon: and slash/", "line one\nline two", "snowman \u2603"),
        ("console", "worker"),
    ):
        body = {"messages": [{"role": role, "content": content}], "max_tokens": tokens}
        if requested is not None:
            body["model"] = requested
        rows.append(
            {
                "id": f"wire-{len(rows) + 1:04}",
                "path": "/v1/chat",
                "key": caller,
                "body": body,
                "expected": {
                    "status": 200,
                    "model": resolved,
                    "provider_path": f"/v1/models/{resolved}:generate",
                    "max_tokens": tokens,
                },
            }
        )
    # Two complete representations serve different existing clients: JSONL for ingestion,
    # Python literals for a reviewable regression suite that runs without loading a manifest.
    write(
        target,
        "traffic/compatibility.jsonl",
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
    )
    write(
        target,
        "tests/wire_examples.py",
        '"""Released v1 wire examples. Expected fields come from the protocol."""\n\nCASES = '
        + json.dumps(rows, ensure_ascii=False, indent=2).replace("null", "None")
        + "\n",
    )


def history(target):
    module = legacy()
    module.git(target, "init", "-q", "-b", "main")
    module.git(target, "config", "user.email", "eval@example.invalid")
    module.git(target, "config", "user.name", "OutcomeBound eval")
    module.git(target, "config", "commit.gpgsign", "false")
    for name, data in module.project_files().items():
        # The live export is not checked into this service. It arrives with an operator request.
        if name == "data/feedback.jsonl":
            data = (
                json.dumps(
                    {
                        "id": "bootstrap",
                        "conversation_id": "bootstrap",
                        "created": "2026-08-01T00:00:00Z",
                        "release": "1.5.0",
                        "rating": "up",
                        "label": None,
                        "channel": "web",
                        "comment": "",
                    }
                )
                + "\n"
            ).encode("utf-8")
        if name == "AGENTS.md":
            data = data.replace(
                b"the feedback export, refreshed daily.",
                b"a bootstrap example for the store smoke check; live exports are not committed.",
            )
        if name == "docs/releases.md":
            data = b"# Released service\n\n1.7.0: correct usage accounting for empty responses.\n"
        module.write(target, name, data)
    write(target, "VERSION", "1.7.0\n")
    commit(target, "Service: released chat, feedback, embeddings and environment tools", 8)
    module.git(target, "tag", "v1.7.0")
    install_files(target)
    compatibility_cases(target)
    commit(target, "Jobs: add offline batch ingestion and released wire examples", 10)
    subprocess.run(
        [
            sys.executable,
            "-B",
            str(REPLICA.parent.parent / "replica-provider-429/plant_v2_route.py"),
        ],
        cwd=target,
        check=True,
    )
    # The copied capture belongs to the short replica task. It is not this session's incident.
    (target / "traffic/v2-2026-10-20.jsonl").unlink()
    write(target, "VERSION", "1.8.0\n")
    commit(target, "Routes: begin fast transport beside the released service", 15)


def main():
    history(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    main()
