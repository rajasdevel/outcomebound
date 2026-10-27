#!/usr/bin/env python3
"""The `docker`, `docker-compose` and `df` stubs: a container engine that is not one.

The runner places this file and its three launchers, read-only, outside the workspace, first on
the call's PATH, where a fixture's `suite.json` names them (`stubs: ["docker", "docker-compose",
"df"]`). A launcher passes its own name as the first argument. The real engine is never reached:
nothing here starts a process but a Python interpreter, and that only inside the workspace or a
copy of it.

The engine keeps its state in the workspace, in `.dockerd/state.json` (Git excludes the folder),
found by walking up from the working directory. `seed <spec.json> <workspace>` writes the first
state from a compact spec (see `seed_state`); a fixture's setup runs it. The state holds images
with labels and sizes, containers, volumes with labels and data, the build cache, the engine's
disk and the host's disk, and a clock that moves a few seconds with every call, so a run is
repeatable. Every call appends one line to `.dockerd/log.jsonl`: its argv, its exit status and the
effects it had (a build, a run, a removal, a prune, a measurement), which a fixture's checks read
with the end state.

What it models is what an agent plausibly runs: `build`, `run` (with `-v`, `--mount`, `--rm`,
`--label`, `-d`), `compose up/down/run/ps/build`, `ps`, `images`, `volume ls/inspect/rm/prune`,
`image rm/prune`, `container rm/prune`, `builder prune`, `system df/prune`, `context ls`, `info`
and `inspect`. A command it does not know succeeds with no effect and is logged as unsupported.
A prune asks before it acts and reads the answer from standard input, as the real one does, so
a call with `-f` acts and a call without it, in a run whose input is empty, stops.

A container "runs" a command only when the program is Python (and `pytest`, `coverage`), `echo`,
`true`, `false` or `df`: Python runs on the host in the folder the container's working directory
maps to, a mounted folder or the copy of the build context an image holds. Any other program
succeeds with no effect, and with `-d` a container that runs one stays "running". `df` in a
container prints the engine's disk; the `df` stub prints the host's.

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import fcntl as _fcntl

    FCNTL: Any = _fcntl
except ImportError:  # pragma: no cover - the stubs run on POSIX
    FCNTL = None

STATE_DIR = ".dockerd"
STATE_FILE = "state.json"
LOG_FILE = "log.jsonl"
ROOT_ENV = "DOCKERD_ROOT"
TICK = 17
VERSION = "27.3.1"
ENDPOINT = "unix:///run/engine/docker.sock"
SKIP_DIRS = {".git", STATE_DIR, "__pycache__", ".venv", "node_modules", ".mypy_cache"}
PULLABLE = {
    "python": 126_000_000,
    "alpine": 8_000_000,
    "node": 240_000_000,
    "ubuntu": 78_000_000,
    "debian": 117_000_000,
    "postgres": 431_000_000,
    "redis": 117_000_000,
    "nginx": 188_000_000,
    "busybox": 4_000_000,
    "mariadb": 400_000_000,
    "mongo": 800_000_000,
    "golang": 800_000_000,
    "rust": 1_500_000_000,
    "mysql": 600_000_000,
    "ruby": 1_000_000_000,
}
NAMES = ("quirky", "eager", "brave", "calm", "keen", "witty")
SURNAMES = ("turing", "hopper", "lovelace", "knuth", "ritchie", "liskov")
SIZE_UNITS = {"B": 1, "KB": 10**3, "MB": 10**6, "GB": 10**9, "TB": 10**12}


class Exit(Exception):
    """End the call with this status after the state is saved."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


def fail(message: str, code: int = 1) -> Exit:
    print(message, file=sys.stderr)
    return Exit(code)


# --- small helpers ---------------------------------------------------------------------------


def human(n: int) -> str:
    for unit, size in (("GB", 10**9), ("MB", 10**6), ("kB", 10**3)):
        if n >= size:
            return f"{n / size:.3g}{unit}"
    return f"{n}B"


def parse_size(text: Any) -> int:
    if isinstance(text, int):
        return text
    found = re.fullmatch(r"\s*([\d.]+)\s*([kKMGT]?B)\s*", str(text))
    if not found:
        raise ValueError(f"not a size: {text!r}")
    return int(float(found[1]) * SIZE_UNITS[found[2].upper()])


def ago(seconds: int) -> str:
    for name, size in (
        ("year", 31_536_000),
        ("month", 2_592_000),
        ("week", 604_800),
        ("day", 86_400),
        ("hour", 3600),
        ("minute", 60),
    ):
        if seconds >= size:
            count = seconds // size
            return f"{count} {name}{'s' if count != 1 else ''} ago"
    return f"{max(seconds, 1)} seconds ago"


def iso(ts: int) -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def digest_of(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "unreadable"


def table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(w, len(cell)) for w, cell in zip(widths, row, strict=True)]
    for line in [headers, *rows]:
        cells = [cell.ljust(w + 3) for cell, w in zip(line, widths, strict=True)]
        print("".join(cells).rstrip())


def make_spec(valued: str, boolean: str) -> dict[str, tuple[str, bool]]:
    """Flag table from space-separated groups like `v/volume`: spelling -> (canonical, valued)."""

    spec: dict[str, tuple[str, bool]] = {}
    for group, takes in ((valued, True), (boolean, False)):
        for item in group.split():
            names = item.split("/")
            canonical = max(names, key=len)
            for name in names:
                spec[("-" if len(name) == 1 else "--") + name] = (canonical, takes)
    return spec


def _long_option(token: str, argv: list[str], at: int, spec: dict, opts: dict) -> int:
    name, eq, value = token.partition("=")
    canonical, takes = spec.get(name, (name.lstrip("-"), False))
    if takes and not eq:
        value = argv[at] if at < len(argv) else ""
        at += 1
    opts.setdefault(canonical, []).append(value if (takes or eq) else True)
    return at


def _short_options(token: str, argv: list[str], at: int, spec: dict, opts: dict) -> int:
    for pos in range(1, len(token)):
        canonical, takes = spec.get("-" + token[pos], (token[pos], False))
        if not takes:
            opts.setdefault(canonical, []).append(True)
            continue
        value = token[pos + 1 :]
        if not value:
            value = argv[at] if at < len(argv) else ""
            at += 1
        opts.setdefault(canonical, []).append(value)
        break
    return at


def parse_args(
    argv: list[str], spec: dict[str, tuple[str, bool]], intermixed: bool = True
) -> tuple[dict[str, list[Any]], list[str]]:
    opts: dict[str, list[Any]] = {}
    rest: list[str] = []
    at = 0
    while at < len(argv):
        word = argv[at]
        at += 1
        if word == "--":
            rest += argv[at:]
            break
        if not word.startswith("-") or word == "-":
            rest.append(word)
            if not intermixed:
                rest += argv[at:]
                break
        elif word.startswith("--"):
            at = _long_option(word, argv, at, spec, opts)
        else:
            at = _short_options(word, argv, at, spec, opts)
    return opts, rest


def flag(opts: dict, name: str) -> bool:
    return any(v is True or v == "true" for v in opts.get(name, []))


def values(opts: dict, name: str) -> list[str]:
    return [str(v) for v in opts.get(name, []) if v is not True]


def last(opts: dict, name: str, default: str = "") -> str:
    found = values(opts, name)
    return found[-1] if found else default


# --- templates and listings -------------------------------------------------------------------

TEMPLATE = re.compile(r"\{\{\s*(json\s+)?(\.[\w.]*)\s*\}\}")


def lookup(obj: Any, path: str) -> Any:
    current = obj
    for part in path.strip(".").split("."):
        if not part:
            continue
        current = current.get(part) if isinstance(current, dict) else None
    return current


def show(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "<no value>"
    if isinstance(value, dict):
        return "map[" + " ".join(f"{k}:{v}" for k, v in sorted(value.items())) + "]"
    if isinstance(value, list):
        return "[" + " ".join(str(v) for v in value) + "]"
    return str(value)


def render(fmt: str, obj: Any) -> str:
    fmt = fmt.replace("\\t", "\t").replace("\\n", "\n")

    def one(found: re.Match) -> str:
        value = lookup(obj, found[2])
        return json.dumps(value, separators=(",", ":")) if found[1] else show(value)

    return TEMPLATE.sub(one, fmt)


def emit(rows: list[dict], columns: list[tuple[str, str]], opts: dict) -> None:
    fmt = last(opts, "format")
    if fmt in ("json", "{{json .}}"):
        for row in rows:
            print(json.dumps(row, separators=(",", ":")))
    elif fmt.startswith("table"):
        body = fmt[5:].strip()
        names = [m[2].strip(".") for m in TEMPLATE.finditer(body)]
        table(
            [n.upper() for n in names],
            [[render(body, row).split("\t")[i] for i in range(len(names))] for row in rows],
        )
    elif fmt:
        for row in rows:
            print(render(fmt, row))
    elif flag(opts, "quiet"):
        for row in rows:
            print(row["ID"])
    else:
        table([h for h, _ in columns], [[str(row.get(k, "")) for _, k in columns] for row in rows])


# --- a small YAML reader, enough for Compose files -----------------------------------------


def _split_flow(text: str) -> list[str]:
    parts, depth, quote, current = [], 0, "", ""
    for char in text:
        if quote:
            quote = "" if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
            continue
        current += char
    if current.strip():
        parts.append(current.strip())
    return parts


def yaml_scalar(text: str) -> Any:
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        return [yaml_scalar(part) for part in _split_flow(text[1:-1])]
    if text.startswith("{") and text.endswith("}"):
        pairs = [part.partition(":") for part in _split_flow(text[1:-1])]
        return {k.strip(): yaml_scalar(v) for k, _, v in pairs}
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "~", ""):
        return None
    return int(text) if re.fullmatch(r"-?\d+", text) else text


def _strip_comment(line: str) -> str:
    quote = ""
    for index, char in enumerate(line):
        if quote:
            quote = "" if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or line[index - 1] in " \t"):
            return line[:index]
    return line


def _key_value(text: str) -> tuple[str, str] | None:
    found = re.match(r"^(\"[^\"]*\"|'[^']*'|[^\s:\"'\[{][^:]*?)\s*:(?:\s+(.*))?$", text)
    if not found:
        return None
    return found[1].strip("\"'"), (found[2] or "").strip()


class _Yaml:
    def __init__(self, text: str) -> None:
        self.lines = []
        for raw in text.splitlines():
            line = _strip_comment(raw).rstrip()
            if line.strip():
                self.lines.append((len(line) - len(line.lstrip(" ")), line.strip()))
        self.at = 0

    def block(self, indent: int) -> Any:
        if self.at >= len(self.lines):
            return None
        if self.lines[self.at][1].startswith("- ") or self.lines[self.at][1] == "-":
            return self.sequence(self.lines[self.at][0])
        return self.mapping(indent)

    def scalar_block(self, indent: int, folded: bool) -> str:
        rows = []
        while self.at < len(self.lines) and self.lines[self.at][0] > indent:
            rows.append(self.lines[self.at][1])
            self.at += 1
        return (" " if folded else "\n").join(rows)

    def value(self, indent: int, text: str) -> Any:
        if text in ("|", ">", "|-", ">-"):
            return self.scalar_block(indent, text.startswith(">"))
        if text:
            return yaml_scalar(text)
        if self.at < len(self.lines):
            next_indent, next_text = self.lines[self.at]
            if next_indent > indent or (next_indent == indent and next_text.startswith("- ")):
                return self.block(next_indent)
        return None

    def mapping(self, indent: int) -> dict:
        result: dict[str, Any] = {}
        while self.at < len(self.lines):
            here, text = self.lines[self.at]
            pair = _key_value(text)
            if here < indent or pair is None or (here > indent and result):
                break
            self.at += 1
            result[pair[0]] = self.value(here, pair[1])
        return result

    def sequence(self, indent: int) -> list:
        result: list[Any] = []
        while self.at < len(self.lines):
            here, text = self.lines[self.at]
            if here != indent or not (text.startswith("- ") or text == "-"):
                break
            rest = text[1:].strip()
            if rest and _key_value(rest) and not rest.startswith(('"', "'")):
                self.lines[self.at] = (here + 2, rest)
                result.append(self.mapping(here + 2))
                continue
            self.at += 1
            result.append(self.value(here, rest))
        return result


def parse_yaml(text: str) -> Any:
    reader = _Yaml(text)
    return reader.block(reader.lines[0][0]) if reader.lines else None


# --- the engine ------------------------------------------------------------------------------


class Engine:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.dir = root / STATE_DIR
        self.state: dict[str, Any] = json.loads((self.dir / STATE_FILE).read_text(encoding="utf-8"))
        self.effects: list[dict[str, Any]] = []

    # persistence
    def save(self) -> None:
        text = json.dumps(self.state, indent=1, sort_keys=True)
        scratch = self.dir / (STATE_FILE + ".new")
        scratch.write_text(text, encoding="utf-8")
        os.replace(scratch, self.dir / STATE_FILE)

    def log(self, argv: list[str], code: int) -> None:
        line = {
            "n": self.state["calls"],
            "argv": argv,
            "cwd": str(Path.cwd()),
            "exit": code,
            "effects": self.effects,
        }
        with (self.dir / LOG_FILE).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line) + "\n")

    def effect(self, op: str, **fields: Any) -> None:
        self.effects.append({"op": op, **fields})

    @property
    def now(self) -> int:
        return int(self.state["clock"])

    def tick(self, seconds: int = TICK) -> None:
        self.state["clock"] = self.now + seconds

    def next_id(self, kind: str) -> str:
        self.state["seq"] += 1
        return digest_of(kind, self.state["seq"], self.now)

    # lookups
    def images(self) -> list[dict]:
        return self.state["images"]

    def containers(self) -> list[dict]:
        return self.state["containers"]

    def volumes(self) -> list[dict]:
        return self.state["volumes"]

    @staticmethod
    def normal_ref(ref: str) -> str:
        for prefix in ("docker.io/library/", "docker.io/", "library/"):
            if ref.startswith(prefix):
                ref = ref[len(prefix) :]
        last_part = ref.rsplit("/", 1)[-1]
        return ref if ":" in last_part or "@" in ref else ref + ":latest"

    def find_image(self, ref: str) -> dict | None:
        wanted = self.normal_ref(ref)
        bare = ref.removeprefix("sha256:")
        for image in self.images():
            if wanted in image["tags"]:
                return image
        matches = [
            i for i in self.images() if bare and i["id"].removeprefix("sha256:").startswith(bare)
        ]
        return matches[0] if len(matches) == 1 and len(bare) >= 4 else None

    def find_container(self, ref: str) -> dict | None:
        ref = ref.lstrip("/")
        for cont in self.containers():
            if cont["name"] == ref:
                return cont
        found = [c for c in self.containers() if ref and c["id"].startswith(ref)]
        return found[0] if len(found) == 1 else None

    def find_volume(self, name: str) -> dict | None:
        return next((v for v in self.volumes() if v["name"] == name), None)

    def users_of_image(self, image: dict) -> list[dict]:
        return [c for c in self.containers() if c["image"] == image["id"]]

    def users_of_volume(self, volume: dict) -> list[dict]:
        return [
            c
            for c in self.containers()
            if any(m.get("name") == volume["name"] for m in c["mounts"])
        ]

    # sizes
    def image_total(self) -> int:
        return sum(i["size"] for i in self.images())

    def container_total(self) -> int:
        return sum(c.get("size", 0) for c in self.containers())

    def volume_total(self) -> int:
        return sum(v["size"] for v in self.volumes())

    def engine_used(self) -> int:
        cache = self.state["cache"]["size"]
        base = self.state["engine"]["base"]
        return base + self.image_total() + self.container_total() + self.volume_total() + cache

    def short(self, ident: str) -> str:
        return ident.removeprefix("sha256:")[:12]

    # images
    def image_name(self, image: dict) -> str:
        return image["tags"][0] if image["tags"] else "<none>"

    def pull(self, ref: str) -> dict:
        repo = ref.split("@")[0].rsplit(":", 1)[0] if ":" in ref.rsplit("/", 1)[-1] else ref
        base = repo.removeprefix("docker.io/").removeprefix("library/")
        if "/" not in base and base not in PULLABLE:
            print(f"Unable to find image '{self.normal_ref(ref)}' locally", file=sys.stderr)
            raise fail(
                f"docker: Error response from daemon: pull access denied for {base}, repository "
                "does not exist or may require 'docker login': denied: requested access to the "
                "resource is denied.",
                125,
            )
        tag = self.normal_ref(ref)
        print(f"Unable to find image '{tag}' locally", file=sys.stderr)
        print(f"{tag.rsplit(':', 1)[1]}: Pulling from {base}", file=sys.stderr)
        print(f"Status: Downloaded newer image for {tag}", file=sys.stderr)
        image = self.new_image([tag], PULLABLE.get(base, 150_000_000), {})
        image["cmd"] = ["python3"] if base == "python" else []
        self.effect("pull", image=tag, id=image["id"])
        return image

    def new_image(self, tags: list[str], size: int, labels: dict) -> dict:
        for other in self.images():
            other["tags"] = [t for t in other["tags"] if t not in tags]
        image = {
            "id": "sha256:" + self.next_id("image"),
            "tags": list(tags),
            "labels": dict(labels),
            "size": size,
            "created": self.now,
            "workdir": "/",
            "cmd": [],
            "entrypoint": [],
            "env": [],
            "rootfs": "",
        }
        self.images().append(image)
        return image

    def resolve_or_pull(self, ref: str) -> dict:
        return self.find_image(ref) or self.pull(ref)

    # removal
    def drop_rootfs(self, image: dict) -> None:
        if image.get("rootfs"):
            shutil.rmtree(self.dir / image["rootfs"], ignore_errors=True)

    def remove_container(self, cont: dict, force: bool = False, anon: bool = False) -> None:
        if cont["status"] == "running" and not force:
            raise fail(
                "Error response from daemon: cannot remove container "
                f'"/{cont["name"]}": container is running: stop the container before removing '
                "or force remove"
            )
        self.containers().remove(cont)
        self.effect(
            "remove",
            kind="container",
            id=cont["id"],
            name=cont["name"],
            labels=cont["labels"],
            size=cont.get("size", 0),
        )
        if anon:
            for mount in cont["mounts"]:
                volume = self.find_volume(mount.get("name", ""))
                if volume and volume.get("anonymous") and not self.users_of_volume(volume):
                    self.remove_volume(volume)

    def remove_image(self, image: dict, ref: str = "", force: bool = False) -> list[str]:
        wanted = self.normal_ref(ref) if ref else ""
        if wanted in image["tags"] and len(image["tags"]) > 1:
            image["tags"].remove(wanted)
            self.effect("untag", id=image["id"], tag=wanted)
            return [f"Untagged: {wanted}"]
        users = self.users_of_image(image)
        busy = [c for c in users if c["status"] == "running" or not force]
        if busy:
            state = "running" if any(c["status"] == "running" for c in busy) else "stopped"
            hint = "cannot be forced" if state == "running" else "must be forced"
            raise fail(
                f"Error response from daemon: conflict: unable to delete {self.short(image['id'])} "
                f"({hint}) - image is being used by {state} container {self.short(busy[0]['id'])}"
            )
        said = [f"Untagged: {tag}" for tag in image["tags"]]
        self.images().remove(image)
        self.drop_rootfs(image)
        self.effect(
            "remove",
            kind="image",
            id=image["id"],
            name=self.image_name(image),
            labels=image["labels"],
            size=image["size"],
        )
        return [*said, f"Deleted: {image['id']}"]

    def remove_volume(self, volume: dict) -> None:
        users = self.users_of_volume(volume)
        if users:
            ids = ", ".join(c["id"] for c in users)
            raise fail(
                f"Error response from daemon: remove {volume['name']}: volume is in use - [{ids}]"
            )
        self.volumes().remove(volume)
        self.effect(
            "remove",
            kind="volume",
            name=volume["name"],
            labels=volume["labels"],
            size=volume["size"],
            anonymous=bool(volume.get("anonymous")),
        )

    # filters
    def passes(self, kind: str, obj: dict, filters: list[str]) -> bool:
        return all(self.one_filter(kind, obj, item) for item in filters)

    def one_filter(self, kind: str, obj: dict, item: str) -> bool:
        key, _, wanted = item.partition("=")
        labels = obj.get("labels", {})
        if key == "label":
            name, _, val = wanted.partition("=")
            return name in labels and (not val or labels[name] == val)
        if key == "label!":
            name, _, val = wanted.partition("=")
            return not (name in labels and (not val or labels[name] == val))
        if key == "until":
            return obj.get("created", 0) < self.now - duration(wanted)
        if key == "dangling":
            return (not obj.get("tags")) == (wanted == "true") if kind == "image" else True
        if key == "status":
            return obj.get("status") == wanted
        if key == "name":
            return wanted in str(obj.get("name", ""))
        if key == "reference":
            return any(fnmatch_ref(t, wanted) for t in obj.get("tags", []))
        return True

    # views
    def container_row(self, cont: dict) -> dict:
        age = ago(self.now - cont["created"])
        return {
            "ID": cont["id"][:12],
            "Image": cont.get("image_name", ""),
            "Command": '"' + " ".join(cont["cmd"])[:20] + '"',
            "CreatedAt": iso(cont["created"]),
            "RunningFor": age,
            "Ports": "",
            "Status": self.container_status(cont),
            "State": cont["status"],
            "Names": cont["name"],
            "Labels": ",".join(f"{k}={v}" for k, v in sorted(cont["labels"].items())),
            "Mounts": ",".join(m.get("source", "") for m in cont["mounts"]),
            "Size": human(cont.get("size", 0)),
        }

    def container_status(self, cont: dict) -> str:
        if cont["status"] == "running":
            return "Up " + ago(self.now - cont.get("started", cont["created"])).removesuffix(" ago")
        if cont["status"] == "exited":
            return f"Exited ({cont.get('exit', 0)}) " + ago(self.now - cont.get("finished", 0))
        return "Created"

    def image_rows(self, show_all: bool = True) -> list[dict]:
        rows = []
        for image in self.images():
            for tag in image["tags"] or ["<none>:<none>"]:
                repo, _, version = tag.rpartition(":")
                rows.append(
                    {
                        "ID": self.short(image["id"]),
                        "Repository": repo,
                        "Tag": version,
                        "CreatedSince": ago(self.now - image["created"]),
                        "CreatedAt": iso(image["created"]),
                        "Size": human(image["size"]),
                    }
                )
        return rows

    # usage numbers
    def usage(self) -> dict[str, tuple[int, int, int, int]]:
        """(total, active, size, reclaimable) for images, containers, volumes and cache."""

        images = self.images()
        used = [i for i in images if self.users_of_image(i)]
        conts = self.containers()
        running = [c for c in conts if c["status"] == "running"]
        vols = self.volumes()
        in_use = [v for v in vols if self.users_of_volume(v)]
        cache = self.state["cache"]
        return {
            "Images": (
                len(images),
                len(used),
                self.image_total(),
                sum(i["size"] for i in images if i not in used),
            ),
            "Containers": (
                len(conts),
                len(running),
                self.container_total(),
                sum(c.get("size", 0) for c in conts if c["status"] != "running"),
            ),
            "Local Volumes": (
                len(vols),
                len(in_use),
                self.volume_total(),
                sum(v["size"] for v in vols if v not in in_use),
            ),
            "Build Cache": (cache["records"], 0, cache["size"], cache["size"]),
        }


def duration(text: str) -> int:
    total = 0
    for count, unit in re.findall(r"(\d+)([smhd])", text):
        total += int(count) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return total


def fnmatch_ref(tag: str, pattern: str) -> bool:
    import fnmatch

    return fnmatch.fnmatch(tag, pattern) or fnmatch.fnmatch(tag.rsplit(":", 1)[0], pattern)


# --- building images ------------------------------------------------------------------------


def logical_lines(text: str) -> list[str]:
    lines, buffer = [], ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if not buffer and (not stripped or stripped.startswith("#")):
            continue
        if stripped.endswith("\\"):
            buffer += stripped[:-1] + " "
            continue
        lines.append((buffer + stripped).strip())
        buffer = ""
    return lines


def command_list(text: str) -> list[str]:
    text = text.strip()
    if text.startswith("["):
        try:
            return [str(item) for item in json.loads(text)]
        except ValueError:
            pass
    return ["/bin/sh", "-c", text]


def ignored_patterns(context: Path) -> list[str]:
    path = context / ".dockerignore"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def is_ignored(rel: str, patterns: list[str]) -> bool:
    import fnmatch

    ignored = False
    for pattern in patterns:
        negate = pattern.startswith("!")
        body = pattern.lstrip("!").strip("/")
        hit = fnmatch.fnmatch(rel, body) or rel.startswith(body + "/") or rel.split("/")[0] == body
        if hit:
            ignored = not negate
    return ignored


def context_files(context: Path) -> list[str]:
    patterns = ignored_patterns(context)
    found: list[str] = []
    for folder, subfolders, names in os.walk(context):
        subfolders[:] = sorted(d for d in subfolders if d not in {".git", STATE_DIR})
        for name in sorted(names):
            rel = os.path.relpath(os.path.join(folder, name), context).replace(os.sep, "/")
            if not is_ignored(rel, patterns):
                found.append(rel)
    return found


class Stage:
    """The state of one Dockerfile stage while it is read."""

    def __init__(self) -> None:
        self.base = ""
        self.workdir = "/"
        self.cmd: list[str] = []
        self.entrypoint: list[str] = []
        self.labels: dict[str, str] = {}
        self.env: list[str] = []
        self.copies: list[tuple[list[str], str, str]] = []
        self.runs = 0


def absolute(workdir: str, path: str) -> str:
    return path if path.startswith("/") else os.path.normpath(os.path.join(workdir, path))


def read_labels(rest: str) -> dict[str, str]:
    labels = {}
    for word in shlex.split(rest):
        key, eq, val = word.partition("=")
        if eq:
            labels[key] = val
    return labels


def apply_instruction(stage: Stage, word: str, rest: str) -> None:
    if word == "WORKDIR":
        stage.workdir = absolute(stage.workdir, rest.strip())
    elif word in ("COPY", "ADD"):
        parts = [p for p in shlex.split(rest) if not p.startswith("--")]
        if "--from" not in rest and len(parts) >= 2:
            stage.copies.append((parts[:-1], parts[-1], stage.workdir))
    elif word == "RUN":
        stage.runs += 1
    elif word == "CMD":
        stage.cmd = command_list(rest)
    elif word == "ENTRYPOINT":
        stage.entrypoint = command_list(rest)
    elif word == "LABEL":
        stage.labels.update(read_labels(rest))
    elif word == "ENV":
        stage.env.append(rest)


def read_dockerfile(path: Path) -> Stage:
    stage = Stage()
    for line in logical_lines(path.read_text(encoding="utf-8", errors="replace")):
        word, _, rest = line.partition(" ")
        word = word.upper()
        if word == "FROM":
            stage = Stage()
            tokens = [t for t in rest.split() if not t.startswith("--")]
            stage.base = tokens[0] if tokens else ""
        else:
            apply_instruction(stage, word, rest)
    return stage


def copy_into(rootfs: Path, context: Path, stage: Stage, files: list[str]) -> int:
    copied = 0
    for sources, dest, workdir in stage.copies:
        target_dir = absolute(workdir, dest)
        many = (
            len(sources) > 1
            or dest in (".", "..")
            or dest.endswith("/")
            or any(src in (".", "./") or (context / src).is_dir() for src in sources)
        )
        for rel in files:
            if not any(match_source(rel, src) for src in sources):
                continue
            tail = rel_to_source(rel, sources)
            where = os.path.join(target_dir, tail) if many else target_dir
            target = rootfs / where.lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(context / rel, target)
            copied += target.stat().st_size
    return copied


def match_source(rel: str, src: str) -> bool:
    import fnmatch

    src = src.removeprefix("./").rstrip("/")
    return src in ("", ".") or rel == src or rel.startswith(src + "/") or fnmatch.fnmatch(rel, src)


def rel_to_source(rel: str, sources: list[str]) -> str:
    for src in sources:
        src = src.removeprefix("./").rstrip("/")
        if src not in ("", ".") and rel.startswith(src + "/"):
            return rel[len(src) + 1 :]
    return rel


def build_image(
    engine: Engine,
    context: Path,
    dockerfile: Path,
    tags: list[str],
    labels: dict[str, str],
) -> dict:
    if not dockerfile.is_file():
        raise fail(
            f"ERROR: failed to solve: failed to read dockerfile: open {dockerfile.name}: "
            "no such file or directory"
        )
    stage = read_dockerfile(dockerfile)
    base = engine.find_image(stage.base) if stage.base and stage.base != "scratch" else None
    if stage.base and stage.base != "scratch" and base is None and "$" not in stage.base:
        base = engine.pull(stage.base)
    files = context_files(context)
    image = engine.new_image([engine.normal_ref(t) for t in tags], 0, {})
    rel = f"images/{engine.short(image['id'])}/rootfs"
    copied = copy_into(engine.dir / rel, context, stage, files) if stage.copies else 0
    size = (base["size"] if base else 0) + copied + stage.runs * 40_000_000
    image.update(
        size=size,
        labels={**(base["labels"] if base else {}), **stage.labels, **labels},
        workdir=stage.workdir,
        cmd=stage.cmd or (base["cmd"] if base else []),
        entrypoint=stage.entrypoint or (base["entrypoint"] if base else []),
        env=stage.env,
        rootfs=rel if stage.copies else "",
    )
    cache = engine.state["cache"]
    added = copied + stage.runs * 12_000_000 + 4_000_000
    cache["size"] += added
    cache["dangling"] = cache.get("dangling", 0) + added // 4
    cache["records"] += 2 + stage.runs
    engine.effect(
        "build",
        id=image["id"],
        tags=image["tags"],
        context=str(context),
        dockerfile=dockerfile.name,
        files=len(files),
    )
    return image


# --- running containers ------------------------------------------------------------------


def split_volume(spec: str) -> tuple[str, str, str]:
    parts = spec.split(":")
    if len(parts) == 1:
        return "", parts[0], ""
    return parts[0], parts[1], parts[2] if len(parts) > 2 else ""


def volume_mount(engine: Engine, spec: str, base: Path) -> dict:
    source, target, mode = split_volume(spec)
    return mount_from_source(engine, source, target, mode, base)


def mount_from_source(engine: Engine, source: str, target: str, mode: str, base: Path) -> dict:
    if source.startswith(("/", "~", ".")):
        host = Path(os.path.expanduser(source))
        host = host if host.is_absolute() else (base / host)
        return {"type": "bind", "source": os.path.normpath(host), "target": target, "mode": mode}
    if source:
        if engine.find_volume(source) is None:
            engine.volumes().append(new_volume(engine, source, {}, False))
            engine.effect("create", kind="volume", name=source)
        return {"type": "volume", "name": source, "source": source, "target": target, "mode": mode}
    name = engine.next_id("volume")
    engine.volumes().append(new_volume(engine, name, {}, True))
    engine.effect("create", kind="volume", name=name, anonymous=True)
    return {"type": "volume", "name": name, "source": name, "target": target, "mode": mode}


def new_volume(engine: Engine, name: str, labels: dict, anonymous: bool) -> dict:
    return {
        "name": name,
        "labels": labels,
        "size": 0,
        "created": engine.now,
        "data": {},
        "anonymous": anonymous,
    }


def parse_mount_option(engine: Engine, text: str, base: Path) -> dict:
    fields = dict(part.partition("=")[::2] for part in text.split(","))
    source = fields.get("source", fields.get("src", ""))
    target = fields.get("target", fields.get("destination", fields.get("dst", "")))
    mode = "ro" if "readonly" in fields or "ro" in fields else ""
    if fields.get("type", "volume") == "bind":
        return mount_from_source(
            engine, source if source.startswith(("/", ".")) else "/" + source, target, mode, base
        )
    return mount_from_source(engine, source, target, mode, base)


def program_name(word: str) -> str:
    return Path(word).name


def finite_program(name: str) -> bool:
    return bool(re.fullmatch(r"python[\d.]*|pytest|py\.test|coverage|echo|true|false|df", name))


class Runner:
    """Runs a container's command, as far as the engine models it."""

    def __init__(self, engine: Engine, cont: dict) -> None:
        self.engine = engine
        self.cont = cont
        self.maps = self.path_maps()
        self.output: list[str] = []
        self.info: dict[str, Any] = {"kind": "none", "ran": False}

    def path_maps(self) -> list[tuple[str, str]]:
        maps = [(m["target"], m["source"]) for m in self.cont["mounts"] if m["type"] == "bind"]
        image = next((i for i in self.engine.images() if i["id"] == self.cont["image"]), None)
        if image and image.get("rootfs"):
            maps.append(("/", str(self.engine.dir / image["rootfs"])))
        return sorted(maps, key=lambda pair: -len(pair[0]))

    def host_path(self, path: str) -> str | None:
        for prefix, host in self.maps:
            if prefix == "/":
                candidate = os.path.normpath(host + "/" + path.lstrip("/"))
                if os.path.exists(candidate):
                    return candidate
            elif path == prefix or path.startswith(prefix.rstrip("/") + "/"):
                return os.path.normpath(host + path[len(prefix) :])
        return None

    def translate(self, word: str) -> str:
        head, eq, tail = word.partition("=")
        for part, joiner in ((tail, eq), (word, "")):
            if part.startswith("/"):
                mapped = self.host_path(part)
                if mapped:
                    return head + joiner + mapped if joiner else mapped
        return word

    def workdir(self) -> Path:
        want = self.cont["workdir"] or "/"
        mapped = self.host_path(want)
        if mapped and os.path.isdir(mapped):
            return Path(mapped)
        scratch = self.engine.dir / "tmp" / self.cont["id"][:12]
        scratch.mkdir(parents=True, exist_ok=True)
        return scratch

    def source_files(self, cwd: Path) -> dict[str, str]:
        files: dict[str, str] = {}
        for folder, subfolders, names in os.walk(cwd):
            subfolders[:] = sorted(d for d in subfolders if d not in SKIP_DIRS)
            for name in sorted(names):
                if name.endswith(".py") and len(files) < 500:
                    path = Path(folder) / name
                    files[os.path.relpath(path, cwd).replace(os.sep, "/")] = sha_file(path)
        return files

    def container_paths(self, text: str) -> str:
        """The output as the container would print it: host paths back to container paths."""

        for prefix, host in sorted(self.maps, key=lambda pair: -len(pair[1])):
            text = text.replace(host, "" if prefix == "/" else prefix.rstrip("/"))
        return text

    def where(self, cwd: Path) -> str:
        here = str(cwd)
        for prefix, host in self.maps:
            if here == host or here.startswith(host + os.sep):
                return "image" if prefix == "/" else "mount"
        return "none"

    def script(self) -> str:
        argv = list(self.cont["entrypoint"]) + list(self.cont["cmd"])
        if len(argv) == 3 and program_name(argv[0]) in ("sh", "bash") and argv[1] in ("-c", "-lc"):
            return argv[2]
        return shlex.join(argv)

    def run(self) -> int:
        cwd = self.workdir()
        script = self.script()
        code = 0
        try:
            parts = re.split(r"\s*(&&|;)\s*", script.strip())
        except ValueError:
            return 0
        joiner = ";"
        for part in parts:
            if part in ("&&", ";"):
                joiner = part
                continue
            if not part or (joiner == "&&" and code != 0):
                continue
            code, cwd = self.simple(part, cwd, code)
        return code

    def simple(self, text: str, cwd: Path, code: int) -> tuple[int, Path]:
        try:
            words = shlex.split(text)
        except ValueError:
            return 0, cwd
        while words and re.fullmatch(r"[A-Za-z_]\w*=.*", words[0]):
            words.pop(0)
        if not words:
            return code, cwd
        name = program_name(words[0])
        if name == "cd" and len(words) > 1:
            mapped = self.host_path(absolute(self.cont["workdir"] or "/", words[1]))
            return 0, Path(mapped) if mapped and os.path.isdir(mapped) else cwd
        if not finite_program(name):
            self.output.append("")
            return 0, cwd
        return self.program(name, [self.translate(w) for w in words[1:]], cwd), cwd

    def program(self, name: str, args: list[str], cwd: Path) -> int:
        if name in ("true", "false"):
            return 0 if name == "true" else 1
        if name == "echo":
            self.output.append(" ".join(args) + "\n")
            return 0
        if name == "df":
            self.output.append(engine_df(self.engine, args))
            self.info.update(kind="df", ran=True)
            return 0
        return self.python(name, args, cwd)

    def python(self, name: str, args: list[str], cwd: Path) -> int:
        if name in ("pytest", "py.test"):
            argv = [sys.executable, "-B", "-m", "pytest", *args]
        elif name == "coverage":
            argv = [sys.executable, "-B", "-m", "coverage", *args]
        else:
            argv = [sys.executable, "-B", *args]
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        kind = "test" if re.search(r"unittest|pytest|nose|test", " ".join(argv[2:])) else "python"
        try:
            done = subprocess.run(
                argv,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
                stdin=subprocess.DEVNULL,
            )
            text, code = done.stdout + done.stderr, done.returncode
        except (OSError, subprocess.SubprocessError) as problem:
            text, code = f"{problem}\n", 127
        self.output.append(self.container_paths(text))
        mode = self.where(cwd)
        self.info.update(
            kind=kind,
            ran=True,
            exit=code,
            source={"root": str(cwd), "mode": mode, "files": self.source_files(cwd)},
        )
        return code


def engine_df(engine: Engine, args: list[str]) -> str:
    total, used = engine.state["engine"]["total"], engine.engine_used()
    avail = max(total - used, 0)
    engine.effect("measure", what="engine-df")
    percent = f"{100 * used // max(total, 1)}%"
    if any(a.startswith("-") and "h" in a for a in args):
        cells = [f"{n / 2**30:.0f}G" for n in (total, used, avail)]
        head = "Filesystem      Size  Used Avail Use% Mounted on"
    else:
        cells = [str(n // 1024) for n in (total, used, avail)]
        head = "Filesystem     1K-blocks     Used Available Use% Mounted on"
    return f"{head}\noverlay  {'  '.join(cells)}  {percent} /\n"


# --- the commands ---------------------------------------------------------------------------

RUN_SPEC = make_spec(
    "v/volume mount e/env env-file name w/workdir entrypoint l/label u/user p/publish network "
    "net hostname cpus m/memory platform pull restart add-host dns cap-add tmpfs shm-size "
    "log-driver group-add",
    "d/detach rm i/interactive t/tty init privileged read-only P/publish-all q/quiet",
)
BUILD_SPEC = make_spec(
    "t/tag f/file label build-arg target platform progress cache-from cache-to o/output "
    "network secret ssh shm-size",
    "q/quiet no-cache pull rm load push",
)
LIST_SPEC = make_spec("f/filter format", "a/all q/quiet no-trunc s/size l/latest")
PRUNE_SPEC = make_spec("filter keep-storage reserved-space", "a/all f/force volumes")
RM_SPEC = make_spec("", "f/force v/volumes l/link")
INSPECT_SPEC = make_spec("f/format type", "s/size")
COMPOSE_SPEC = make_spec(
    "f/file p/project-name profile env-file project-directory ansi progress parallel",
    "dry-run compatibility all-resources verbose",
)
UP_SPEC = make_spec(
    "scale t/timeout timeout exit-code-from attach wait-timeout pull",
    "d/detach build no-build force-recreate no-recreate abort-on-container-exit remove-orphans "
    "wait no-deps v/renew-anon-volumes V no-start no-color quiet-pull",
)
DOWN_SPEC = make_spec("rmi t/timeout timeout", "v/volumes remove-orphans")
CRUN_SPEC = make_spec(
    "e/env v/volume entrypoint w/workdir u/user name l/label p/publish",
    "rm d/detach no-deps T/no-tty i/interactive build quiet-pull remove-orphans use-aliases",
)
GLOBAL_VALUED = {"--context", "-c", "-H", "--host", "--config", "-l", "--log-level"}


class Cli:
    def __init__(self, engine: Engine, personality: str) -> None:
        self.engine = engine
        self.personality = personality

    # dispatch
    def go(self, argv: list[str]) -> None:
        argv = list(argv)
        while argv and argv[0].startswith("-") and argv[0] not in ("--version", "-v", "--help"):
            argv = argv[2:] if argv[0] in GLOBAL_VALUED else argv[1:]
        if not argv:
            return
        if argv[0] == "compose":
            self.compose(argv[1:])
            return
        key = argv[0]
        groups = {
            "container",
            "image",
            "volume",
            "network",
            "builder",
            "buildx",
            "system",
            "context",
        }
        rest = argv[1:]
        if key in groups and rest:
            key, rest = f"{key} {rest[0]}", rest[1:]
        handler = ROUTES.get(key)
        if handler is None:
            self.engine.effect("unsupported", words=argv[:3])
            return
        getattr(self, handler)(rest)

    # --- listings
    def ps(self, args: list[str]) -> None:
        opts, _ = parse_args(args, LIST_SPEC)
        conts = [
            c
            for c in self.engine.containers()
            if (flag(opts, "all") or c["status"] == "running")
            and self.engine.passes("container", c, values(opts, "filter"))
        ]
        rows = [self.engine.container_row(c) for c in conts]
        emit(
            rows,
            [
                ("CONTAINER ID", "ID"),
                ("IMAGE", "Image"),
                ("COMMAND", "Command"),
                ("CREATED", "RunningFor"),
                ("STATUS", "Status"),
                ("PORTS", "Ports"),
                ("NAMES", "Names"),
            ],
            opts,
        )

    def images(self, args: list[str]) -> None:
        opts, rest = parse_args(args, LIST_SPEC)
        engine = self.engine
        chosen = [
            i
            for i in engine.images()
            if engine.passes("image", i, values(opts, "filter"))
            and (not rest or any(fnmatch_ref(t, rest[0]) for t in i["tags"]))
        ]
        rows = []
        for image in chosen:
            for tag in image["tags"] or ["<none>:<none>"]:
                repo, _, version = tag.rpartition(":")
                rows.append(
                    {
                        "ID": engine.short(image["id"]),
                        "Repository": repo,
                        "Tag": version,
                        "CreatedSince": ago(engine.now - image["created"]),
                        "CreatedAt": iso(image["created"]),
                        "Size": human(image["size"]),
                        "Labels": image["labels"],
                    }
                )
        emit(
            rows,
            [
                ("REPOSITORY", "Repository"),
                ("TAG", "Tag"),
                ("IMAGE ID", "ID"),
                ("CREATED", "CreatedSince"),
                ("SIZE", "Size"),
            ],
            opts,
        )

    def volume_ls(self, args: list[str]) -> None:
        opts, _ = parse_args(args, LIST_SPEC)
        chosen = []
        for vol in self.engine.volumes():
            used = bool(self.engine.users_of_volume(vol))
            wanted = values(opts, "filter")
            dangling = [w for w in wanted if w.startswith("dangling=")]
            ok = all((w.endswith("true")) == (not used) for w in dangling)
            rest = [w for w in wanted if not w.startswith("dangling=")]
            if ok and self.engine.passes("volume", vol, rest):
                chosen.append(vol)
        rows = [
            {"ID": v["name"], "Name": v["name"], "Driver": "local", "Labels": v["labels"]}
            for v in chosen
        ]
        emit(rows, [("DRIVER", "Driver"), ("VOLUME NAME", "Name")], opts)

    def volume_inspect(self, args: list[str]) -> None:
        opts, rest = parse_args(args, INSPECT_SPEC)
        out = []
        for name in rest:
            vol = self.engine.find_volume(name)
            if vol is None:
                print(f"Error response from daemon: get {name}: no such volume", file=sys.stderr)
                continue
            out.append(
                {
                    "CreatedAt": iso(vol["created"]),
                    "Driver": "local",
                    "Labels": vol["labels"] or None,
                    "Mountpoint": f"/var/lib/docker/volumes/{name}/_data",
                    "Name": name,
                    "Options": None,
                    "Scope": "local",
                }
            )
        self.print_objects(out, last(opts, "format"))
        if len(out) != len(rest):
            raise Exit(1)

    def print_objects(self, objects: list[dict], fmt: str) -> None:
        if fmt:
            for obj in objects:
                print(render(fmt, obj))
        else:
            print(json.dumps(objects, indent=4))

    def inspect(self, args: list[str]) -> None:
        opts, rest = parse_args(args, INSPECT_SPEC)
        out = []
        for ref in rest:
            obj = self.inspect_one(ref)
            if obj is None:
                print(f"Error: No such object: {ref}", file=sys.stderr)
            else:
                out.append(obj)
        self.print_objects(out, last(opts, "format"))
        if len(out) != len(rest):
            raise Exit(1)

    def inspect_one(self, ref: str) -> dict | None:
        engine = self.engine
        cont = engine.find_container(ref)
        if cont:
            return {
                "Id": cont["id"],
                "Name": "/" + cont["name"],
                "Created": iso(cont["created"]),
                "Image": cont["image"],
                "State": {
                    "Status": cont["status"],
                    "Running": cont["status"] == "running",
                    "ExitCode": cont.get("exit", 0),
                },
                "Config": {"Image": cont.get("image_name", ""), "Labels": cont["labels"]},
                "Mounts": [
                    {
                        "Type": m["type"],
                        "Name": m.get("name", ""),
                        "Source": m["source"],
                        "Destination": m["target"],
                    }
                    for m in cont["mounts"]
                ],
            }
        image = engine.find_image(ref)
        if image:
            return {
                "Id": image["id"],
                "RepoTags": image["tags"],
                "Created": iso(image["created"]),
                "Size": image["size"],
                "Config": {"Labels": image["labels"] or None, "WorkingDir": image["workdir"]},
            }
        vol = engine.find_volume(ref)
        if vol:
            return {"Name": vol["name"], "Labels": vol["labels"] or None, "Driver": "local"}
        return None

    # --- removal
    def rm(self, args: list[str]) -> None:
        opts, rest = parse_args(args, RM_SPEC)
        bad = 0
        for ref in rest:
            cont = self.engine.find_container(ref)
            if cont is None:
                print(f"Error response from daemon: No such container: {ref}", file=sys.stderr)
                bad += 1
                continue
            try:
                self.engine.remove_container(cont, flag(opts, "force"), flag(opts, "volumes"))
                print(ref)
            except Exit:
                bad += 1
        if bad:
            raise Exit(1)

    def rmi(self, args: list[str]) -> None:
        opts, rest = parse_args(args, RM_SPEC)
        bad = 0
        for ref in rest:
            image = self.engine.find_image(ref)
            if image is None:
                print(f"Error response from daemon: No such image: {ref}", file=sys.stderr)
                bad += 1
                continue
            try:
                for line in self.engine.remove_image(image, ref, flag(opts, "force")):
                    print(line)
            except Exit:
                bad += 1
        if bad:
            raise Exit(1)

    def volume_rm(self, args: list[str]) -> None:
        _, rest = parse_args(args, RM_SPEC)
        bad = 0
        for name in rest:
            vol = self.engine.find_volume(name)
            if vol is None:
                print(f"Error response from daemon: get {name}: no such volume", file=sys.stderr)
                bad += 1
                continue
            try:
                self.engine.remove_volume(vol)
                print(name)
            except Exit:
                bad += 1
        if bad:
            raise Exit(1)

    def volume_create(self, args: list[str]) -> None:
        opts, rest = parse_args(args, make_spec("d/driver l/label o/opt name", ""))
        name = rest[0] if rest else self.engine.next_id("volume")
        labels = dict(item.partition("=")[::2] for item in values(opts, "label"))
        if self.engine.find_volume(name) is None:
            self.engine.volumes().append(new_volume(self.engine, name, labels, not rest))
            self.engine.effect("create", kind="volume", name=name, labels=labels)
        print(name)

    # --- prune
    def confirm(self, warning: str, opts: dict) -> bool:
        if flag(opts, "force"):
            return True
        print(warning)
        print("Are you sure you want to continue? [y/N] ", end="", flush=True)
        return sys.stdin.readline().strip().lower() in ("y", "yes")

    def prune_containers(self, filters: list[str]) -> list[dict]:
        gone = [
            c
            for c in list(self.engine.containers())
            if c["status"] != "running" and self.engine.passes("container", c, filters)
        ]
        for cont in gone:
            self.engine.remove_container(cont, anon=True)
        return gone

    def prune_images(self, filters: list[str], everything: bool) -> list[dict]:
        gone = []
        for image in list(self.engine.images()):
            if self.engine.users_of_image(image) or not self.engine.passes("image", image, filters):
                continue
            if image["tags"] and not everything:
                continue
            self.engine.remove_image(image, force=True)
            gone.append(image)
        return gone

    def prune_volumes(self, filters: list[str], everything: bool) -> list[dict]:
        gone = []
        for vol in list(self.engine.volumes()):
            if self.engine.users_of_volume(vol) or not self.engine.passes("volume", vol, filters):
                continue
            if not vol.get("anonymous") and not everything:
                continue
            self.engine.remove_volume(vol)
            gone.append(vol)
        return gone

    def prune_cache(self, everything: bool, filters: list[str]) -> int:
        cache = self.engine.state["cache"]
        before = cache["size"]
        dangling = min(cache.get("dangling", 0), before)
        freed = before if everything else dangling
        if any(f.startswith("until=") for f in filters):
            freed //= 2
        cache["size"] = before - freed
        cache["dangling"] = 0 if everything else max(dangling - freed, 0)
        cache["records"] = int(cache["records"] * cache["size"] / max(before, 1))
        if freed:
            self.engine.effect("remove", kind="cache", name="build-cache", size=freed, labels={})
        return freed

    def record_prune(self, kind: str, opts: dict, gone: list[str], reclaimed: int) -> None:
        self.engine.effect(
            "prune",
            kind=kind,
            all=flag(opts, "all"),
            filters=values(opts, "filter"),
            removed=gone,
            reclaimed=reclaimed,
        )

    def stopped(self, opts: dict, kind: str) -> None:
        self.engine.effect(
            "prune", kind=kind, all=flag(opts, "all"), filters=values(opts, "filter"), aborted=True
        )

    def container_prune(self, args: list[str]) -> None:
        opts, _ = parse_args(args, PRUNE_SPEC)
        if not self.confirm("WARNING! This will remove all stopped containers.", opts):
            self.stopped(opts, "container")
            return
        gone = self.prune_containers(values(opts, "filter"))
        self.record_prune("container", opts, [c["name"] for c in gone], 0)
        if gone:
            print("Deleted Containers:")
            for cont in gone:
                print(cont["id"])
        print("\nTotal reclaimed space: 0B")

    def image_prune(self, args: list[str]) -> None:
        opts, _ = parse_args(args, PRUNE_SPEC)
        kind = "all unused images" if flag(opts, "all") else "dangling images"
        if not self.confirm(f"WARNING! This will remove {kind}.", opts):
            self.stopped(opts, "image")
            return
        gone = self.prune_images(values(opts, "filter"), flag(opts, "all"))
        size = sum(i["size"] for i in gone)
        self.record_prune("image", opts, [self.engine.image_name(i) for i in gone], size)
        for image in gone:
            print(f"deleted: {image['id']}")
        print(f"\nTotal reclaimed space: {human(size)}")

    def volume_prune(self, args: list[str]) -> None:
        opts, _ = parse_args(args, PRUNE_SPEC)
        what = (
            "all volumes not used by at least one container"
            if flag(opts, "all")
            else ("anonymous volumes not used by at least one container")
        )
        if not self.confirm(f"WARNING! This will remove {what}.", opts):
            self.stopped(opts, "volume")
            return
        gone = self.prune_volumes(values(opts, "filter"), flag(opts, "all"))
        size = sum(v["size"] for v in gone)
        self.record_prune("volume", opts, [v["name"] for v in gone], size)
        if gone:
            print("Deleted Volumes:")
            for vol in gone:
                print(vol["name"])
        print(f"\nTotal reclaimed space: {human(size)}")

    def builder_prune(self, args: list[str]) -> None:
        opts, _ = parse_args(args, PRUNE_SPEC)
        what = "all build cache" if flag(opts, "all") else "dangling build cache"
        if not self.confirm(f"WARNING! This will remove {what}.", opts):
            self.stopped(opts, "cache")
            return
        freed = self.prune_cache(flag(opts, "all"), values(opts, "filter"))
        self.record_prune("cache", opts, [], freed)
        print(f"Total:\t{human(freed)}")

    def network_prune(self, args: list[str]) -> None:
        opts, _ = parse_args(args, PRUNE_SPEC)
        if self.confirm(
            "WARNING! This will remove all custom networks not used by at least one container.",
            opts,
        ):
            self.record_prune("network", opts, [], 0)

    def system_prune(self, args: list[str]) -> None:
        opts, _ = parse_args(args, PRUNE_SPEC)
        parts = ["all stopped containers", "all networks not used by at least one container"]
        if flag(opts, "volumes"):
            parts.append("all anonymous volumes not used by at least one container")
        parts.append(
            "all images without at least one container associated to them"
            if flag(opts, "all")
            else "all dangling images"
        )
        parts.append("all build cache" if flag(opts, "all") else "unused build cache")
        warning = "WARNING! This will remove:\n" + "\n".join(f"  - {p}" for p in parts)
        if not self.confirm(warning, opts):
            self.stopped(opts, "system")
            return
        filters = values(opts, "filter")
        containers = self.prune_containers(filters)
        images = self.prune_images(filters, flag(opts, "all"))
        volumes = self.prune_volumes(filters, flag(opts, "all")) if flag(opts, "volumes") else []
        freed = self.prune_cache(flag(opts, "all"), filters)
        total = sum(i["size"] for i in images) + sum(v["size"] for v in volumes) + freed
        names = (
            [c["name"] for c in containers]
            + [self.engine.image_name(i) for i in images]
            + [v["name"] for v in volumes]
        )
        self.record_prune("system", opts, names, total)
        print(f"Total reclaimed space: {human(total)}")

    # --- usage and information
    def system_df(self, args: list[str]) -> None:
        opts, _ = parse_args(args, make_spec("format", "v/verbose"))
        self.engine.effect("measure", what="system-df")
        usage = self.engine.usage()
        rows = []
        for kind, (total, active, size, reclaim) in usage.items():
            share = f" ({100 * reclaim // size}%)" if size and kind != "Build Cache" else ""
            rows.append([kind, str(total), str(active), human(size), human(reclaim) + share])
        table(["TYPE", "TOTAL", "ACTIVE", "SIZE", "RECLAIMABLE"], rows)
        if flag(opts, "verbose"):
            self.verbose_usage()

    def verbose_usage(self) -> None:
        engine = self.engine
        print("\nImages space usage:\n")
        table(
            ["REPOSITORY", "TAG", "IMAGE ID", "CREATED", "SIZE", "CONTAINERS"],
            [
                [
                    i["tags"][0].rpartition(":")[0] if i["tags"] else "<none>",
                    i["tags"][0].rpartition(":")[2] if i["tags"] else "<none>",
                    engine.short(i["id"]),
                    ago(engine.now - i["created"]),
                    human(i["size"]),
                    str(len(engine.users_of_image(i))),
                ]
                for i in engine.images()
            ],
        )
        print("\nContainers space usage:\n")
        table(
            ["CONTAINER ID", "IMAGE", "SIZE", "STATUS", "NAMES"],
            [
                [
                    c["id"][:12],
                    c.get("image_name", ""),
                    human(c.get("size", 0)),
                    c["status"],
                    c["name"],
                ]
                for c in engine.containers()
            ],
        )
        print("\nLocal Volumes space usage:\n")
        table(
            ["VOLUME NAME", "LINKS", "SIZE"],
            [
                [v["name"], str(len(engine.users_of_volume(v))), human(v["size"])]
                for v in engine.volumes()
            ],
        )
        cache = engine.state["cache"]
        print(f"\nBuild cache usage: {human(cache['size'])}\n")

    def buildx_du(self, args: list[str]) -> None:
        self.engine.effect("measure", what="build-cache")
        cache = self.engine.state["cache"]
        print(f"Reclaimable:\t{human(cache['size'])}\nTotal:\t\t{human(cache['size'])}")

    def info(self, args: list[str]) -> None:
        engine = self.engine
        print(
            "Client:\n Version:    "
            + VERSION
            + f"\n Context:    {engine.state['context']['name']}\n"
        )
        print("Server:")
        print(f" Containers: {len(engine.containers())}")
        print(f"  Running: {sum(c['status'] == 'running' for c in engine.containers())}")
        print(f" Images: {len(engine.images())}")
        print(
            f" Server Version: {VERSION}\n Storage Driver: overlayfs\n"
            " Docker Root Dir: /var/lib/docker"
        )
        print(" Operating System: Linux engine VM\n CPUs: 8\n Total Memory: 15.6GiB")

    def version(self, args: list[str]) -> None:
        print(
            f"Client:\n Version:           {VERSION}\n\n"
            f"Server: Engine\n Version:          {VERSION}"
        )

    def short_version(self, args: list[str]) -> None:
        print(f"Docker version {VERSION}, build ce12230")

    def context_ls(self, args: list[str]) -> None:
        opts, _ = parse_args(args, make_spec("format", "q/quiet"))
        current = self.engine.state["context"]["name"]
        if flag(opts, "quiet"):
            print("default")
            print(current)
            return
        table(
            ["NAME", "DESCRIPTION", "DOCKER ENDPOINT", "ERROR"],
            [
                ["default", "Current DOCKER_HOST based configuration", ENDPOINT, ""],
                [f"{current} *", self.engine.state["context"]["description"], ENDPOINT, ""],
            ],
        )

    def context_show(self, args: list[str]) -> None:
        print(self.engine.state["context"]["name"])

    # --- build, pull, tag
    def build(self, args: list[str]) -> None:
        opts, rest = parse_args(args, BUILD_SPEC)
        context = Path(rest[0] if rest else ".").resolve()
        named = last(opts, "file")
        dockerfile = Path.cwd() / named if named else context / "Dockerfile"
        labels = dict(item.partition("=")[::2] for item in values(opts, "label"))
        tags = values(opts, "tag")
        image = build_image(self.engine, context, dockerfile, tags, labels)
        self.engine.tick(2 * TICK)
        if flag(opts, "quiet"):
            print(image["id"])
            return
        print(
            f"[+] Building 2.1s (8/8) FINISHED  docker:{self.engine.state['context']['name']}",
            file=sys.stderr,
        )
        print(" => [internal] load build definition from " + dockerfile.name, file=sys.stderr)
        print(" => exporting to image", file=sys.stderr)
        for tag in image["tags"]:
            print(f" => => naming to docker.io/library/{tag}", file=sys.stderr)

    def pull(self, args: list[str]) -> None:
        _, rest = parse_args(args, make_spec("platform", "q/quiet a/all-tags"))
        for ref in rest:
            if self.engine.find_image(ref) is None:
                self.engine.pull(ref)
            else:
                print(f"Status: Image is up to date for {self.engine.normal_ref(ref)}")

    def tag(self, args: list[str]) -> None:
        if len(args) < 2:
            raise fail('"docker tag" requires exactly 2 arguments.')
        image = self.engine.find_image(args[0])
        if image is None:
            raise fail(f"Error response from daemon: No such image: {args[0]}")
        new = self.engine.normal_ref(args[1])
        for other in self.engine.images():
            other["tags"] = [t for t in other["tags"] if t != new]
        image["tags"].append(new)

    # --- containers
    def run(self, args: list[str]) -> None:
        opts, rest = parse_args(args, RUN_SPEC, intermixed=False)
        if not rest:
            raise fail('docker: "docker run" requires at least 1 argument.', 125)
        cont = self.create_container(opts, rest[0], rest[1:])
        self.start_container(cont, flag(opts, "detach"), flag(opts, "rm"))

    def create(self, args: list[str]) -> None:
        opts, rest = parse_args(args, RUN_SPEC, intermixed=False)
        if not rest:
            raise fail('"docker create" requires at least 1 argument.')
        cont = self.create_container(opts, rest[0], rest[1:])
        print(cont["id"])

    def create_container(self, opts: dict, image_ref: str, command: list[str]) -> dict:
        engine = self.engine
        image = engine.resolve_or_pull(image_ref)
        name = last(opts, "name") or self.fresh_name()
        if any(c["name"] == name for c in engine.containers()):
            raise fail(
                f'docker: Error response from daemon: Conflict. The container name "/{name}" is '
                "already in use.",
                125,
            )
        base = Path.cwd()
        mounts = [volume_mount(engine, v, base) for v in values(opts, "volume")]
        mounts += [parse_mount_option(engine, m, base) for m in values(opts, "mount")]
        entry = last(opts, "entrypoint")
        cont = {
            "id": engine.next_id("container"),
            "name": name,
            "image": image["id"],
            "image_name": image_ref,
            "status": "created",
            "exit": 0,
            "labels": {
                **image.get("labels", {}),
                **dict(item.partition("=")[::2] for item in values(opts, "label")),
            },
            "mounts": mounts,
            "cmd": command if entry else (command or list(image["cmd"])),
            "entrypoint": shlex.split(entry) if entry else list(image["entrypoint"]),
            "workdir": last(opts, "workdir") or image["workdir"],
            "created": engine.now,
            "size": 0,
            "output": "",
        }
        engine.containers().append(cont)
        engine.effect("create", kind="container", id=cont["id"], name=name, image=image_ref)
        return cont

    def fresh_name(self) -> str:
        seq = self.engine.state["seq"]
        name = f"{NAMES[seq % 6]}_{SURNAMES[seq // 6 % 6]}"
        taken = {c["name"] for c in self.engine.containers()}
        return name if name not in taken else f"{name}_{seq}"

    def start_container(
        self, cont: dict, detach: bool = False, remove: bool = False, announce: bool = True
    ) -> int:
        engine = self.engine
        cont["status"], cont["started"] = "running", engine.now
        runner = Runner(engine, cont)
        code = runner.run()
        text = "".join(runner.output)
        finite = runner.info["ran"] or finite_program(
            program_name((cont["entrypoint"] + cont["cmd"] + [""])[0])
        )
        if not finite and detach:
            engine.effect("run", id=cont["id"], name=cont["name"], status="running", **runner.info)
            if announce:
                print(cont["id"])
            return 0
        cont["status"], cont["exit"], cont["finished"] = "exited", code, engine.now
        cont["output"] = text
        if not detach:
            sys.stdout.write(text)
        mounts = [
            {"host": m["source"], "target": m["target"]}
            for m in cont["mounts"]
            if m["type"] == "bind"
        ]
        engine.effect(
            "run",
            id=cont["id"],
            name=cont["name"],
            image=cont.get("image_name", ""),
            command=cont["entrypoint"] + cont["cmd"],
            mounts=mounts,
            **{"exit": code, "status": "exited", "removed": remove, **runner.info},
        )
        engine.tick(TICK)
        if detach and announce:
            print(cont["id"])
        if remove:
            engine.remove_container(cont, anon=True)
        if code and not detach:
            raise Exit(code)
        return code

    def stop(self, args: list[str]) -> None:
        _, rest = parse_args(args, make_spec("t/time s/signal", ""))
        for ref in rest:
            cont = self.engine.find_container(ref)
            if cont is None:
                print(f"Error response from daemon: No such container: {ref}", file=sys.stderr)
                continue
            if cont["status"] == "running":
                cont["status"], cont["finished"] = "exited", self.engine.now
                self.engine.effect("stop", id=cont["id"], name=cont["name"])
            print(ref)

    def start(self, args: list[str]) -> None:
        _, rest = parse_args(args, make_spec("", "a/attach i/interactive"))
        for ref in rest:
            cont = self.engine.find_container(ref)
            if cont is None:
                print(f"Error response from daemon: No such container: {ref}", file=sys.stderr)
                continue
            self.start_container(cont, detach=True)

    def logs(self, args: list[str]) -> None:
        _, rest = parse_args(args, make_spec("n/tail since until", "f/follow t/timestamps"))
        cont = self.engine.find_container(rest[0]) if rest else None
        if cont is None:
            raise fail(f"Error response from daemon: No such container: {rest[0] if rest else ''}")
        sys.stdout.write(cont.get("output", ""))

    def exec_(self, args: list[str]) -> None:
        self.engine.effect("exec", words=args[:4])

    # --- compose
    def compose(self, args: list[str]) -> None:
        opts, rest = parse_args(args, COMPOSE_SPEC, intermixed=False)
        if not rest:
            return
        verb, tail = rest[0], rest[1:]
        if verb == "ls":
            self.compose_ls(tail)
            return
        if verb in ("version",):
            print("Docker Compose version v2.29.7")
            return
        project = Project.load(self.engine, opts)
        handler = {
            "up": self.compose_up,
            "down": self.compose_down,
            "run": self.compose_run,
            "ps": self.compose_ps,
            "build": self.compose_build,
            "config": self.compose_config,
            "stop": self.compose_stop,
            "rm": self.compose_rm,
            "start": self.compose_up,
            "logs": self.compose_logs,
        }.get(verb)
        if handler is None:
            self.engine.effect("unsupported", words=["compose", *rest[:2]])
            return
        handler(project, tail)

    def compose_ls(self, args: list[str]) -> None:
        names = sorted(
            {c["labels"].get("com.docker.compose.project", "") for c in self.engine.containers()}
            - {""}
        )
        table(["NAME", "STATUS", "CONFIG FILES"], [[n, "", ""] for n in names])

    def compose_config(self, project: Project, args: list[str]) -> None:
        opts, _ = parse_args(args, make_spec("format o/output", "services q/quiet volumes"))
        if flag(opts, "services"):
            for name in project.services:
                print(name)
        elif not flag(opts, "quiet"):
            print(f"name: {project.name}\nservices:")
            for name in project.services:
                print(f"  {name}: {{}}")

    def compose_ps(self, project: Project, args: list[str]) -> None:
        opts, _ = parse_args(args, make_spec("format filter status", "a/all q/quiet services"))
        conts = [
            c
            for c in self.engine.containers()
            if c["labels"].get("com.docker.compose.project") == project.name
            and (flag(opts, "all") or c["status"] == "running")
        ]
        rows = [self.engine.container_row(c) for c in conts]
        emit(rows, [("NAME", "Names"), ("IMAGE", "Image"), ("STATUS", "Status")], opts)

    def compose_build(self, project: Project, args: list[str]) -> None:
        _, wanted = parse_args(
            args, make_spec("build-arg m/memory ssh", "no-cache pull q/quiet push")
        )
        for name, service in project.services.items():
            if (not wanted or name in wanted) and service.get("build") is not None:
                project.build_service(self.engine, name)

    def compose_up(self, project: Project, args: list[str]) -> None:
        opts, wanted = parse_args(args, UP_SPEC)
        order = project.closure(wanted, flag(opts, "no-deps"))
        project.ensure_resources(self.engine)
        for name in order:
            project.prepare_image(self.engine, name, flag(opts, "build"))
            cont = project.container_for(self.engine, name)
            if cont and cont["status"] == "running":
                print(f" Container {cont['name']}  Running", file=sys.stderr)
                continue
            if cont is None:
                cont = project.new_container(self.engine, name, {"detach": flag(opts, "detach")})
                print(f" Container {cont['name']}  Created", file=sys.stderr)
            self.start_container(cont, detach=True, announce=False)
            print(f" Container {cont['name']}  Started", file=sys.stderr)
        self.engine.tick(TICK)

    def compose_run(self, project: Project, args: list[str]) -> None:
        opts, rest = parse_args(args, CRUN_SPEC, intermixed=False)
        if not rest:
            raise fail("service name required")
        name, command = rest[0], rest[1:]
        if name not in project.services:
            raise fail(f"no such service: {name}")
        project.ensure_resources(self.engine)
        if not flag(opts, "no-deps"):
            for dep in project.closure([name], False)[:-1]:
                project.prepare_image(self.engine, dep, False)
                cont = project.container_for(self.engine, dep)
                if cont is None:
                    cont = project.new_container(self.engine, dep, {"detach": True})
                if cont["status"] != "running":
                    self.start_container(cont, detach=True, announce=False)
        project.prepare_image(self.engine, name, flag(opts, "build"))
        cont = project.new_container(
            self.engine, name, {"oneoff": True, "command": command, "extra": opts}
        )
        self.start_container(
            cont, detach=flag(opts, "detach"), remove=flag(opts, "rm"), announce=False
        )

    def compose_stop(self, project: Project, args: list[str]) -> None:
        for cont in project.containers(self.engine):
            if cont["status"] == "running":
                cont["status"], cont["finished"] = "exited", self.engine.now
                self.engine.effect("stop", id=cont["id"], name=cont["name"])

    def compose_rm(self, project: Project, args: list[str]) -> None:
        for cont in project.containers(self.engine):
            if cont["status"] != "running":
                self.engine.remove_container(cont, anon=True)

    def compose_logs(self, project: Project, args: list[str]) -> None:
        for cont in project.containers(self.engine):
            sys.stdout.write(cont.get("output", ""))

    def compose_down(self, project: Project, args: list[str]) -> None:
        opts, _ = parse_args(args, DOWN_SPEC)
        engine = self.engine
        for cont in project.containers(engine):
            engine.remove_container(cont, force=True, anon=True)
            print(f" Container {cont['name']}  Removed", file=sys.stderr)
        if flag(opts, "volumes"):
            for vol in list(engine.volumes()):
                if vol["labels"].get("com.docker.compose.project") == project.name:
                    engine.remove_volume(vol)
        mode = last(opts, "rmi")
        if mode:
            project.remove_images(engine, mode)
        engine.effect("down", project=project.name)


class Project:
    """A Compose project: its services and where they run."""

    def __init__(self, name: str, folder: Path, document: dict) -> None:
        self.name = name
        self.folder = folder
        self.services: dict[str, dict] = document.get("services") or {}
        self.volumes: dict[str, Any] = document.get("volumes") or {}

    @classmethod
    def load(cls, engine: Engine, opts: dict) -> Project:
        files = values(opts, "file")
        names = ("compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml")
        if not files:
            here = Path.cwd()
            for folder in (here, *here.parents):
                found = [folder / n for n in names if (folder / n).is_file()]
                if found:
                    files = [str(found[0])]
                    break
        if not files:
            raise fail("no configuration file provided: not found")
        merged: dict[str, Any] = {"services": {}, "volumes": {}}
        folder = Path(files[0]).resolve().parent
        for item in files:
            path = Path(item)
            if not path.is_file():
                raise fail(f"open {item}: no such file or directory")
            document = parse_yaml(path.read_text(encoding="utf-8", errors="replace")) or {}
            for key in ("services", "volumes"):
                merged[key].update(document.get(key) or {})
            if document.get("name"):
                merged["name"] = document["name"]
        raw = (
            last(opts, "project-name")
            or os.environ.get("COMPOSE_PROJECT_NAME")
            or merged.get("name")
            or folder.name
        )
        name = re.sub(r"[^a-z0-9_-]", "", str(raw).lower())
        return cls(name, folder, merged)

    def closure(self, wanted: list[str], no_deps: bool) -> list[str]:
        chosen: list[str] = []

        def visit(name: str) -> None:
            if name in chosen or name not in self.services:
                return
            if not no_deps:
                deps = self.services[name].get("depends_on") or []
                for dep in deps if isinstance(deps, list) else list(deps):
                    visit(str(dep))
            chosen.append(name)

        for name in wanted or list(self.services):
            visit(name)
        return chosen

    def image_name(self, name: str) -> str:
        service = self.services[name]
        return str(service.get("image") or f"{self.name}-{name}")

    def build_service(self, engine: Engine, name: str) -> dict:
        build = self.services[name].get("build")
        spec = build if isinstance(build, dict) else {"context": build}
        context = (self.folder / str(spec.get("context") or ".")).resolve()
        dockerfile = context / str(spec.get("dockerfile") or "Dockerfile")
        image = build_image(engine, context, dockerfile, [self.image_name(name)], {})
        engine.tick(2 * TICK)
        print(f" Image {self.image_name(name)}  Built", file=sys.stderr)
        return image

    def prepare_image(self, engine: Engine, name: str, rebuild: bool) -> None:
        service = self.services[name]
        have = engine.find_image(self.image_name(name))
        if service.get("build") is not None and (rebuild or have is None):
            self.build_service(engine, name)
        elif have is None:
            engine.pull(self.image_name(name))

    def ensure_resources(self, engine: Engine) -> None:
        for key, spec in self.volumes.items():
            spec = spec if isinstance(spec, dict) else {}
            if spec.get("external"):
                continue
            real = str(spec.get("name") or f"{self.name}_{key}")
            if engine.find_volume(real) is None:
                labels = {
                    "com.docker.compose.project": self.name,
                    "com.docker.compose.volume": key,
                }
                engine.volumes().append(new_volume(engine, real, labels, False))
                engine.effect("create", kind="volume", name=real, labels=labels)

    def volume_name(self, key: str) -> str:
        spec = self.volumes.get(key)
        if isinstance(spec, dict) and spec.get("name"):
            return str(spec["name"])
        return f"{self.name}_{key}" if key in self.volumes else key

    def mounts(self, engine: Engine, service: dict) -> list[dict]:
        mounts = []
        for item in service.get("volumes") or []:
            if isinstance(item, dict):
                source, target = str(item.get("source", "")), str(item.get("target", ""))
                mode = "ro" if item.get("read_only") else ""
            else:
                source, target, mode = split_volume(str(item))
            if source and not source.startswith(("/", ".", "~")):
                source = self.volume_name(source)
            mounts.append(mount_from_source(engine, source, target, mode, self.folder))
        return mounts

    def labels(self, name: str, oneoff: bool) -> dict:
        service_labels = self.services[name].get("labels") or {}
        if isinstance(service_labels, list):
            service_labels = dict(str(i).partition("=")[::2] for i in service_labels)
        return {
            **service_labels,
            "com.docker.compose.project": self.name,
            "com.docker.compose.service": name,
            "com.docker.compose.oneoff": "True" if oneoff else "False",
            "com.docker.compose.project.working_dir": str(self.folder),
        }

    def containers(self, engine: Engine) -> list[dict]:
        return [
            c
            for c in list(engine.containers())
            if c["labels"].get("com.docker.compose.project") == self.name
        ]

    def container_for(self, engine: Engine, name: str) -> dict | None:
        wanted = f"{self.name}-{name}-1"
        return next((c for c in engine.containers() if c["name"] == wanted), None)

    def new_container(self, engine: Engine, name: str, how: dict) -> dict:
        service = self.services[name]
        image = engine.resolve_or_pull(self.image_name(name))
        command = how.get("command") or as_words(service.get("command")) or list(image["cmd"])
        entry = as_words(service.get("entrypoint")) or list(image["entrypoint"])
        oneoff = bool(how.get("oneoff"))
        title = (
            f"{self.name}-{name}-run-{engine.next_id('run')[:12]}"
            if oneoff
            else f"{self.name}-{name}-1"
        )
        mounts = self.mounts(engine, service)
        extra = how.get("extra") or {}
        mounts += [volume_mount(engine, v, Path.cwd()) for v in values(extra, "volume")]
        cont = {
            "id": engine.next_id("container"),
            "name": title,
            "image": image["id"],
            "image_name": self.image_name(name),
            "status": "created",
            "exit": 0,
            "labels": {**image.get("labels", {}), **self.labels(name, oneoff)},
            "mounts": mounts,
            "cmd": command,
            "entrypoint": entry,
            "workdir": last(extra, "workdir")
            or str(service.get("working_dir") or image["workdir"]),
            "created": engine.now,
            "size": 0,
            "output": "",
        }
        engine.containers().append(cont)
        engine.effect(
            "create", kind="container", id=cont["id"], name=title, image=cont["image_name"]
        )
        return cont

    def remove_images(self, engine: Engine, mode: str) -> None:
        for name, service in self.services.items():
            if mode == "local" and service.get("image"):
                continue
            image = engine.find_image(self.image_name(name))
            if image and not engine.users_of_image(image):
                engine.remove_image(image, force=True)


def as_words(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return shlex.split(value) if isinstance(value, str) else []


ROUTES = {
    "run": "run",
    "container run": "run",
    "create": "create",
    "container create": "create",
    "ps": "ps",
    "container ls": "ps",
    "container list": "ps",
    "container ps": "ps",
    "images": "images",
    "image ls": "images",
    "image list": "images",
    "rm": "rm",
    "container rm": "rm",
    "container remove": "rm",
    "rmi": "rmi",
    "image rm": "rmi",
    "image remove": "rmi",
    "image prune": "image_prune",
    "container prune": "container_prune",
    "volume ls": "volume_ls",
    "volume list": "volume_ls",
    "volume inspect": "volume_inspect",
    "volume rm": "volume_rm",
    "volume remove": "volume_rm",
    "volume prune": "volume_prune",
    "volume create": "volume_create",
    "network prune": "network_prune",
    "builder prune": "builder_prune",
    "buildx prune": "builder_prune",
    "buildx du": "buildx_du",
    "system df": "system_df",
    "system prune": "system_prune",
    "system info": "info",
    "info": "info",
    "context ls": "context_ls",
    "context list": "context_ls",
    "context show": "context_show",
    "inspect": "inspect",
    "image inspect": "inspect",
    "container inspect": "inspect",
    "build": "build",
    "image build": "build",
    "buildx build": "build",
    "builder build": "build",
    "pull": "pull",
    "image pull": "pull",
    "tag": "tag",
    "image tag": "tag",
    "stop": "stop",
    "container stop": "stop",
    "kill": "stop",
    "container kill": "stop",
    "start": "start",
    "container start": "start",
    "restart": "start",
    "logs": "logs",
    "container logs": "logs",
    "exec": "exec_",
    "container exec": "exec_",
    "version": "version",
    "--version": "short_version",
    "-v": "short_version",
}


# --- the host's disk ------------------------------------------------------------------------


def host_df(engine: Engine, args: list[str]) -> None:
    host = engine.state["host"]
    total, used = host["total"], host["used"]
    avail = total - used
    engine.effect("measure", what="host-df")
    opts, paths = parse_args(
        args, make_spec("t/type x/exclude B/block-size", "h H k m g P i T a l")
    )
    for path in paths:
        if not os.path.exists(path):
            print(f"df: {path}: No such file or directory", file=sys.stderr)
            raise Exit(1)
    if any(flag(opts, key) for key in ("h", "H")):
        unit, label = 2**30, "Gi"
        cells = [
            f"{total / unit:.0f}{label}",
            f"{used / unit:.0f}{label}",
            f"{avail / unit:.1f}{label}",
        ]
        head = "Filesystem        Size    Used   Avail Capacity  Mounted on"
    else:
        block = 1024 if flag(opts, "k") or flag(opts, "P") else 512
        cells = [str(total // block), str(used // block), str(avail // block)]
        head = f"Filesystem   {block}-blocks      Used Available Capacity  Mounted on"
    percent = f"{100 * used // max(total, 1)}%"
    print(head)
    print(f"/dev/disk3s5s1  {'  '.join(cells)}  {percent}  /")


def real_df(args: list[str]) -> None:
    here = os.path.dirname(os.path.abspath(sys.argv[0]))
    path = os.pathsep.join(
        p for p in os.environ.get("PATH", "").split(os.pathsep) if os.path.abspath(p) != here
    )
    found = shutil.which("df", path=path)
    if found is None:
        raise fail("df: not available", 127)
    done = subprocess.run([found, *args], check=False)
    raise Exit(done.returncode)


# --- seeding and main -------------------------------------------------------------------------


def seed_state(spec: dict, workspace: Path) -> None:
    """Write `.dockerd/state.json` and an empty log in `workspace` from a compact spec."""

    import calendar
    import time

    clock = calendar.timegm(time.strptime(spec["clock"], "%Y-%m-%dT%H:%M:%SZ"))
    state: dict[str, Any] = {
        "calls": 0,
        "seq": 0,
        "clock": clock,
        "context": spec.get("context", {"name": "desktop-linux", "description": "Docker Desktop"}),
        "engine": {
            "total": parse_size(spec["engine"]["total"]),
            "base": parse_size(spec["engine"]["base"]),
        },
        "host": {
            "total": parse_size(spec["host"]["total"]),
            "used": parse_size(spec["host"]["used"]),
        },
        "images": [],
        "containers": [],
        "volumes": [],
        "cache": {
            "size": parse_size(spec.get("cache", {}).get("size", 0)),
            "dangling": parse_size(spec.get("cache", {}).get("dangling", 0)),
            "records": spec.get("cache", {}).get("records", 0),
        },
    }
    folder = workspace / STATE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    holder = Engine.__new__(Engine)
    holder.state, holder.effects, holder.root, holder.dir = state, [], workspace, folder
    for item in spec.get("images", []):
        image = holder.new_image(item["tags"], parse_size(item["size"]), item.get("labels", {}))
        image["created"] = clock - int(item.get("age_days", 0)) * 86400
        image["cmd"] = item.get("cmd", [])
        image["workdir"] = item.get("workdir", "/")
    by_tag = {t: i for i in state["images"] for t in i["tags"]}
    for item in spec.get("containers", []):
        image = by_tag[holder.normal_ref(item["image"])]
        stamp = clock - int(item.get("age_days", 0)) * 86400
        state["containers"].append(
            {
                "id": holder.next_id("container"),
                "name": item["name"],
                "image": image["id"],
                "image_name": item["image"],
                "status": item.get("status", "exited"),
                "exit": item.get("exit", 0),
                "labels": item.get("labels", {}),
                "mounts": item.get("mounts", []),
                "cmd": item.get("cmd", []),
                "entrypoint": [],
                "workdir": "/",
                "created": stamp,
                "started": stamp,
                "finished": stamp,
                "size": parse_size(item.get("size", 0)),
                "output": "",
            }
        )
    for item in spec.get("volumes", []):
        volume = new_volume(holder, item["name"], item.get("labels", {}), False)
        volume.update(
            size=parse_size(item.get("size", 0)),
            data=item.get("data", {}),
            created=clock - int(item.get("age_days", 0)) * 86400,
        )
        state["volumes"].append(volume)
    holder.save()
    (folder / LOG_FILE).write_text("", encoding="utf-8")


def find_root() -> Path | None:
    override = os.environ.get(ROOT_ENV)
    if override:
        return Path(override)
    try:
        here = Path.cwd().resolve()
    except OSError:
        return None
    return next((p for p in (here, *here.parents) if (p / STATE_DIR / STATE_FILE).is_file()), None)


def locked(root: Path) -> Any:
    handle = (root / STATE_DIR / "lock").open("w", encoding="utf-8")
    if FCNTL is not None:
        FCNTL.flock(handle, FCNTL.LOCK_EX)
    return handle


def call(personality: str, argv: list[str], root: Path) -> int:
    handle = locked(root)
    engine = Engine(root)
    engine.state["calls"] += 1
    engine.tick()
    code = 0
    try:
        if personality == "df":
            host_df(engine, argv)
        else:
            Cli(engine, personality).go(
                ["compose", *argv] if personality == "docker-compose" else argv
            )
    except Exit as stop:
        code = stop.code
    except Exception as problem:  # the stub's own fault must not read as a traceback
        engine.effect("stub-error", error=repr(problem))
        print("Error response from daemon: internal error", file=sys.stderr)
        code = 1
    finally:
        engine.save()
        engine.log([personality, *argv], code)
        handle.close()
    return code


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[0] == "seed":
        seed_state(json.loads(Path(argv[1]).read_text(encoding="utf-8")), Path(argv[2]))
        return 0
    personality, rest = (argv[0], argv[1:]) if argv else ("docker", [])
    if rest[:1] in (["--version"], ["-v"]) and personality == "docker":
        print(f"Docker version {VERSION}, build ce12230")
        return 0
    root = find_root()
    if root is None:
        if personality == "df":
            real_df(rest)
        print(
            f"Cannot connect to the Docker daemon at {ENDPOINT}. Is the docker daemon running?",
            file=sys.stderr,
        )
        return 1
    return call(personality, rest, root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
