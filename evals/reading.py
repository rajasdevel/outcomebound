#!/usr/bin/env python3
"""Blind reading of the report items of kept eval runs, with no model call.

A report item is what a run's final answer must tell the person (`report` in a fixture's
`suite.json`). A person reads the answers blind: without the arm, the run or the workspace path.

- `python3 evals/reading.py export RESULTS_DIR [RESULTS_DIR ...] --out DIR [--seed N]` finds
  every `<fixture>.meta.json` under the folders whose fixture has report items, and writes
  `DIR/sheet.md` and `DIR/key.json`. The sheet groups the answers by fixture and report item,
  each item with its question and its reading sheet (`reading/<item>.md`); each answer has a
  random id, in a random order, with the run's workspace path replaced by `<workspace>`, and
  a line `- [<item>] <id>:` for the reader's yes, no or unclear. Where the fixture names stubs,
  each answer is followed by the outputs of the run's receipts of them (the harness's records,
  `evals/stubs/receipts.py`), in order, by the stub's name alone, or `no receipt`. The key maps
  each id to its run and stays closed until the readings are imported.
- `python3 evals/reading.py import SHEET --key KEY [--reader NAME]` reads a filled sheet (the
  reader from `--reader`, else the sheet's `reader:` line) and writes each run's verdicts to
  `<fixture>.readings.json` beside its meta file, keeping other readers' verdicts. It refuses,
  writing nothing, where a line of the sheet lacks a verdict or names an id the key lacks.
- `python3 evals/reading.py spotcheck KEY --share 0.2 --seed N [--out FILE]` picks that share of
  the key's ids, rounded up, within each fixture, and writes a sheet of them for a second reader.
- `python3 evals/reading.py agree KEY [--readers A B]` compares two readers over the runs both
  read, lists every disagreement and each fixture and item that must be read again (a
  disagreement on an item sends all of that item's readings back); exit 1 where any differ.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import math
import random
import re
import shlex
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "evals" / "fixtures"
VERDICTS = ("yes", "no", "unclear")
WORKSPACE = "<workspace>"
LINE = re.compile(r"^- \[(?P<item>[^\]\s]+)\] (?P<id>[0-9a-f]{8,}):[ \t]*(?P<verdict>\S*)\s*$")
READER = re.compile(r"^reader:[ \t]*(?P<name>\S+)\s*$", re.MULTILINE)
FENCE = re.compile(r"^(`{3,}|~{3,})")


NO_RECEIPT = "no receipt"


class ReadingError(Exception):
    """Something this tool refuses; nothing was written."""


def suite_report(fixture: str, fixtures: Path = FIXTURES) -> dict[str, dict[str, Any]]:
    path = fixtures / fixture / "suite.json"
    if not path.is_file():
        return {}
    report = json.loads(path.read_text(encoding="utf-8")).get("report") or {}
    return report if isinstance(report, dict) else {}


def suite_stubs(fixture: str, fixtures: Path = FIXTURES) -> list[str]:
    """The runner-owned stubs the fixture names (`stubs` in its `suite.json`)."""

    path = fixtures / fixture / "suite.json"
    if not path.is_file():
        return []
    names = json.loads(path.read_text(encoding="utf-8")).get("stubs") or []
    return [name for name in names if isinstance(name, str)] if isinstance(names, list) else []


def runs(directories: list[Path]) -> list[Path]:
    """Every meta file under the folders, in a fixed order."""

    found: set[Path] = set()
    for directory in directories:
        found.update(path.resolve() for path in directory.rglob("*.meta.json"))
    return sorted(found)


def blind(answer: str, meta: dict[str, Any]) -> str:
    """The answer with the run's workspace path, in every spelling, replaced by `<workspace>`."""

    repo = meta.get("fixture_repo")
    if not repo:
        return answer
    spellings = {str(repo), str(Path(repo).resolve())}
    spellings |= {spelling.removeprefix("/private") for spelling in list(spellings)}
    for spelling in sorted(spellings, key=len, reverse=True):
        answer = answer.replace(spelling, WORKSPACE)
    return answer


def fenced(text: str) -> str:
    """`text` in a code fence longer than any run of backticks inside it."""

    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{text.rstrip()}\n{fence}"


def answer_path(meta_path: Path) -> Path:
    return meta_path.with_name(meta_path.name.replace(".meta.json", ".answer.md"))


def readings_path(meta_path: Path) -> Path:
    return meta_path.with_name(meta_path.name.replace(".meta.json", ".readings.json"))


def _read(meta_path: Path) -> dict[str, Any]:
    return json.loads(meta_path.read_text(encoding="utf-8"))


def sheet(key: dict[str, Any], ids: list[str]) -> str:
    """The reading sheet of `ids`: per fixture and report item, the question, the item's reading
    sheet, then each answer in the order given with its line to fill."""

    fixtures = Path(key.get("fixtures") or FIXTURES)
    by_fixture: defaultdict[str, list[str]] = defaultdict(list)
    for answer_id in ids:
        by_fixture[key["ids"][answer_id]["fixture"]].append(answer_id)
    lines = [
        "# Blind reading sheet",
        "",
        "Fill `reader:` with your name, then after each `- [item] id:` write yes, no or unclear.",
        "Read each item's sheet first. The arm and the run are in the key; do not open it.",
        "",
        "reader: ",
        "",
    ]
    for fixture in sorted(by_fixture):
        items = key["items"][fixture]
        stubs = suite_stubs(fixture, fixtures)
        for item, entry in items.items():
            guide = fixtures / fixture / "reading" / f"{item}.md"
            lines += [f"## {fixture}: {item}", "", f"**Question:** {entry['question']}", ""]
            lines += [guide.read_text(encoding="utf-8").rstrip() if guide.is_file() else
                      "(no reading sheet)", ""]  # fmt: skip
            for answer_id in by_fixture[fixture]:
                run = key["ids"][answer_id]
                text = blind(_text(Path(run["answer"])), _read(Path(run["meta"])))
                lines += [f"### {answer_id}", "", fenced(text or "(empty answer)"), ""]
                if stubs:
                    meta_path = Path(run["meta"])
                    lines += [receipts_block(meta_path, _read(meta_path), stubs), ""]
                lines += [f"- [{item}] {answer_id}: ", ""]
    return "\n".join(lines) + "\n"


def _stub_receipts() -> Any:
    """The module that finds a run's stub receipts (`evals/stubs/receipts.py`), loaded from its
    file as the graders load it."""

    spec = importlib.util.spec_from_file_location(
        "reading_stub_receipts", REPO / "evals" / "stubs" / "receipts.py"
    )
    if spec is None or spec.loader is None:
        raise ReadingError("evals/stubs/receipts.py cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _saved_transcript(meta_path: Path, post_checks: str) -> str:
    """The run's saved command transcript, without the post-checks' output, with the commands'
    outputs taken from its events where it kept none; empty where there is none."""

    path = meta_path.with_name(meta_path.name.replace(".meta.json", ".transcript.txt"))
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace").split(post_checks)[0]
    sys.path.insert(0, str(REPO))
    try:
        from evals.codex_events import with_outputs

        return with_outputs(text)
    except Exception:  # an unreadable old record shows no output
        return text
    finally:
        sys.path.remove(str(REPO))


def _bare(command: str, stub: str) -> str:
    """The stub's invocation as its name and plain words, with no path and no `2>&1`."""

    try:
        words = shlex.split(command.strip().removesuffix("2>&1"))
    except ValueError:
        return stub
    return shlex.join([stub, *words[1:]])


def receipts_block(meta_path: Path, meta: dict[str, Any], stubs: list[str]) -> str:
    """The outputs of the run's receipts of its fixture's stubs, in order, as a labelled fenced
    block with no path, run or arm in it; `no receipt` where the run holds none."""

    kept = meta["stubs"] if isinstance(meta.get("stubs"), dict) else {}
    folder, digests = kept.get("dir"), kept.get("digests")
    parts: list[tuple[int, str]] = []
    if folder and isinstance(digests, dict):
        module = _stub_receipts()
        transcript = _saved_transcript(meta_path, module.POST_CHECKS)
        with tempfile.TemporaryDirectory() as scratch:
            work = Path(scratch)
            (work / "transcript.txt").write_text(transcript, encoding="utf-8")
            (work / "digests.json").write_text(json.dumps(digests), encoding="utf-8")
            for stub in stubs:
                found = module.receipts(
                    work / "transcript.txt", stub, folder, work / "digests.json"
                )
                for receipt in found.receipts:
                    output = receipt.output if receipt.output is not None else "(no output kept)"
                    text = blind(output.replace(str(folder), "<stubs>"), meta)
                    parts.append((receipt.position, f"$ {_bare(receipt.invocation, stub)}\n{text}"))
    body = "\n\n".join(text for _, text in sorted(parts)) or NO_RECEIPT
    return f"**Receipts (stub outputs):**\n\n{fenced(body)}"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def export(directories: list[Path], out: Path, seed: int | None, fixtures: Path = FIXTURES) -> int:
    """Write the sheet and the key; the number of answers on the sheet."""

    # The ids and order come from the system's randomness; a seed fixes them for a test.
    rng = random.Random(seed) if seed is not None else random.SystemRandom()  # noqa: S311
    key: dict[str, Any] = {"ids": {}, "items": {}, "fixtures": str(fixtures), "made": _now()}
    for meta_path in runs(directories):
        meta = _read(meta_path)
        fixture = str(meta.get("fixture"))
        items = suite_report(fixture, fixtures)
        if not items:
            continue
        answer_id = f"{rng.getrandbits(32):08x}"
        while answer_id in key["ids"]:
            answer_id = f"{rng.getrandbits(32):08x}"
        key["items"][fixture] = items
        key["ids"][answer_id] = {
            "meta": str(meta_path),
            "answer": str(answer_path(meta_path)),
            "fixture": fixture,
            "arm": meta.get("arm"),
            "repetition": meta.get("repetition"),
        }
    ids = list(key["ids"])
    rng.shuffle(ids)
    key["order"] = ids
    out.mkdir(parents=True, exist_ok=True)
    (out / "sheet.md").write_text(sheet(key, ids), encoding="utf-8")
    (out / "key.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    return len(ids)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def outside_fences(text: str) -> list[str]:
    """The lines of `text` outside its code fences, so an answer's own text never reads as a
    verdict or a reader."""

    kept, inside = [], ""
    for line in text.splitlines():
        found = FENCE.match(line)
        if found and not inside:
            inside = found[1]
        elif found and line.strip() == inside:
            inside = ""
        elif not inside:
            kept.append(line)
    return kept


def parse(text: str) -> tuple[str, list[tuple[str, str, str]]]:
    """The sheet's reader and each `(id, item, verdict)` line outside the answer fences."""

    lines = outside_fences(text)
    entries = [
        (match["id"], match["item"], match["verdict"].lower())
        for match in (LINE.match(line) for line in lines)
        if match
    ]
    reader = READER.search("\n".join(lines))
    return (reader["name"] if reader else ""), entries


def import_sheet(sheet_path: Path, key: dict[str, Any], reader: str = "") -> int:
    """Write each run's verdicts from the filled sheet; the number of runs written."""

    found_reader, entries = parse(sheet_path.read_text(encoding="utf-8"))
    reader = reader or found_reader
    if not reader:
        raise ReadingError("no reader: fill the sheet's reader: line or pass --reader")
    problems = []
    verdicts: defaultdict[str, dict[str, str]] = defaultdict(dict)
    for answer_id, item, verdict in entries:
        run = key["ids"].get(answer_id)
        if run is None:
            problems.append(f"{answer_id}: not in the key")
        elif item not in key["items"].get(run["fixture"], {}):
            problems.append(f"{answer_id}: {item} is not a report item of {run['fixture']}")
        elif verdict not in VERDICTS:
            problems.append(
                f"{answer_id} {item}: {verdict or 'no verdict'}, not yes, no or unclear"
            )
        else:
            verdicts[answer_id][item] = verdict
    if not entries:
        problems.append("no verdict lines")
    if problems:
        raise ReadingError("; ".join(problems))
    for answer_id, items in verdicts.items():
        meta_path = Path(key["ids"][answer_id]["meta"])
        path = readings_path(meta_path)
        record = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        record.setdefault("fixture", key["ids"][answer_id]["fixture"])
        record.setdefault("readers", {})[reader] = {
            "items": {**record.get("readers", {}).get(reader, {}).get("items", {}), **items},
            "read_at": _now(),
            "sheet_id": answer_id,
        }
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return len(verdicts)


def spotcheck(key: dict[str, Any], share: float, seed: int) -> list[str]:
    """`share` of the key's ids within each fixture, rounded up, picked with `seed`."""

    rng = random.Random(seed)  # noqa: S311 - a seeded sample the maintainer can reproduce
    by_fixture: defaultdict[str, list[str]] = defaultdict(list)
    for answer_id in key.get("order") or sorted(key["ids"]):
        by_fixture[key["ids"][answer_id]["fixture"]].append(answer_id)
    picked = []
    for fixture in sorted(by_fixture):
        ids = sorted(by_fixture[fixture])
        picked += rng.sample(ids, min(len(ids), math.ceil(share * len(ids))))
    return picked


def readings(key: dict[str, Any]) -> dict[str, dict[str, dict[str, str]]]:
    """For each id, each reader's item verdicts, from the runs' readings files."""

    found = {}
    for answer_id, run in key["ids"].items():
        path = readings_path(Path(run["meta"]))
        record = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        found[answer_id] = {
            reader: entry.get("items", {}) for reader, entry in record.get("readers", {}).items()
        }
    return found


def agree(key: dict[str, Any], pair: tuple[str, str] | None) -> dict[str, Any]:
    """The agreement of two readers: counts, every disagreement, and the items to read again."""

    read = readings(key)
    names = sorted({reader for entry in read.values() for reader in entry})
    if pair is None:
        if len(names) != 2:
            raise ReadingError(
                f"readers found: {', '.join(names) or 'none'}; name two with --readers"
            )
        pair = (names[0], names[1])
    first, second = pair
    compared, differ = 0, []
    for answer_id in sorted(read):
        a, b = read[answer_id].get(first, {}), read[answer_id].get(second, {})
        for item in sorted(set(a) & set(b)):
            compared += 1
            if a[item] != b[item]:
                fixture = key["ids"][answer_id]["fixture"]
                differ.append({"id": answer_id, "fixture": fixture, "item": item,
                               first: a[item], second: b[item]})  # fmt: skip
    again = sorted({(entry["fixture"], entry["item"]) for entry in differ})
    return {
        "readers": [first, second],
        "compared": compared,
        "agreed": compared - len(differ),
        "disagreements": differ,
        "read_again": [{"fixture": fixture, "item": item} for fixture, item in again],
    }


def _key(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        raise ReadingError(f"cannot read the key {path}: {problem}") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evals/reading.py", description="Blind reading of report items; see the docstring."
    )
    verbs = parser.add_subparsers(dest="verb", required=True)
    out = verbs.add_parser("export", help="write a blind sheet and its key")
    out.add_argument("results", nargs="+", metavar="RESULTS_DIR", type=Path)
    out.add_argument("--out", required=True, type=Path, metavar="DIR")
    out.add_argument("--seed", type=int, default=None, help="fix the ids and order (tests)")
    take = verbs.add_parser("import", help="write a filled sheet's verdicts beside each run")
    take.add_argument("sheet", type=Path, metavar="SHEET")
    take.add_argument("--key", required=True, type=Path)
    take.add_argument("--reader", default="")
    spot = verbs.add_parser("spotcheck", help="a sheet of a sample for a second reader")
    spot.add_argument("key", type=Path, metavar="KEY")
    spot.add_argument("--share", type=float, default=0.2)
    spot.add_argument("--seed", type=int, required=True)
    spot.add_argument("--out", type=Path, default=None, metavar="FILE")
    both = verbs.add_parser("agree", help="compare two readers")
    both.add_argument("key", type=Path, metavar="KEY")
    both.add_argument("--readers", nargs=2, default=None, metavar=("A", "B"))
    both.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.verb == "export":
            count = export(args.results, args.out, args.seed)
            print(f"reading: {count} answers on {args.out / 'sheet.md'}; "
                  f"the key {args.out / 'key.json'} stays closed until import")  # fmt: skip
            return 0
        key = _key(args.key)
        if args.verb == "import":
            print(
                f"reading: wrote the verdicts of {import_sheet(args.sheet, key, args.reader)} runs"
            )
            return 0
        if args.verb == "spotcheck":
            if not 0 < args.share <= 1:
                parser.error("--share is above 0 and at most 1")
            picked = spotcheck(key, args.share, args.seed)
            target = args.out or args.key.with_name("spotcheck-sheet.md")
            target.write_text(sheet(key, picked), encoding="utf-8")
            print(f"reading: {len(picked)} of {len(key['ids'])} answers on {target}")
            return 0
        result = agree(key, tuple(args.readers) if args.readers else None)
    except ReadingError as problem:
        sys.stderr.write(f"reading: refused, nothing written: {problem}\n")
        return 2
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        first, second = result["readers"]
        print(
            f"{first} and {second}: {result['agreed']} of {result['compared']} item readings agree"
        )
        for entry in result["disagreements"]:
            print(f"  differ {entry['id']} {entry['fixture']} {entry['item']}: "
                  f"{first} {entry[first]}, {second} {entry[second]}")  # fmt: skip
        for entry in result["read_again"]:
            print(f"  read again: every reading of {entry['fixture']} {entry['item']}")
    return 1 if result["disagreements"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
