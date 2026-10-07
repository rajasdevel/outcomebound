"""`outcomebound sources` over an image: one item per file with an id and revision from the
digest, a size read from the header and never the pixels; and the `reference` disposition, which
`check` reads for its targets and its claims and which it says compared no picture. The images
are built here from bytes, the smallest headers that state a size."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import pytest

from outcomebound_tools import sources, sources_image
from outcomebound_tools.schemacheck import validate
from outcomebound_tools.sources_manifest import schema


def png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IEND", b"")


def jpeg(width: int, height: int) -> bytes:
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof0 = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, height, width, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + sof0 + b"\xff\xd9"


def gif(width: int, height: int) -> bytes:
    return b"GIF89a" + struct.pack("<HH", width, height) + b"\x00\x00\x00"


def webp_lossy(width: int, height: int) -> bytes:
    body = b"\x00\x00\x00" + b"\x9d\x01\x2a" + struct.pack("<HH", width, height)
    chunk = b"VP8 " + struct.pack("<I", len(body)) + body
    return b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk


def webp_lossless(width: int, height: int) -> bytes:
    bits = (width - 1) | ((height - 1) << 14)
    body = b"\x2f" + struct.pack("<I", bits)
    chunk = b"VP8L" + struct.pack("<I", len(body)) + body
    return b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk


def webp_extended(width: int, height: int) -> bytes:
    body = (
        b"\x00\x00\x00\x00" + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    )
    chunk = b"VP8X" + struct.pack("<I", len(body)) + body
    return b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk


SVG_SIZED = (
    b'<?xml version="1.0"?>\r\n<svg xmlns="http://www.w3.org/2000/svg" width="48px" height="24">'
    b"</svg>\r\n"
)
SVG_BOXED = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50.4"></svg>'
SVG_BARE = b'<svg xmlns="http://www.w3.org/2000/svg" width="100%"><text>Hi</text></svg>'


@pytest.mark.parametrize(
    ("data", "media_type", "size"),
    [
        (png(640, 480), "image/png", (640, 480)),
        (jpeg(300, 200), "image/jpeg", (300, 200)),
        (gif(16, 9), "image/gif", (16, 9)),
        (webp_lossy(120, 80), "image/webp", (120, 80)),
        (webp_lossless(121, 81), "image/webp", (121, 81)),
        (webp_extended(1920, 1080), "image/webp", (1920, 1080)),
        (SVG_SIZED, "image/svg+xml", (48, 24)),
        (SVG_BOXED, "image/svg+xml", (100, 50)),
        (SVG_BARE, "image/svg+xml", (None, None)),
        (png(1, 1)[:20], "image/png", (None, None)),  # a header cut short states no size
    ],
)
def test_the_header_gives_the_format_and_size_or_nothing(data, media_type, size):
    found = sources_image.sniff(data)

    assert found is not None and found.media_type == media_type
    assert (found.width, found.height) == size


@pytest.mark.parametrize(
    "hostile",
    [
        b"<svg " + b"a " * 50_000,  # attribute-like words, no closing bracket
        b"<svg" + b" " * 100_000,  # whitespace only
        b'<svg width="' + b"1" * 100_000,  # an unclosed quote
        b"<svg a=" + b'"' + b"=" * 100_000,
        b"<!--" * 50_000,  # many comment openers, none closed
        b"<svg" * 50_000,  # many root-like starts
        b"<!DOCTYPE x [" + b"<!" * 50_000,  # a declaration that never ends
        b"<?" * 50_000 + b"[" * 50_000,  # instructions and brackets, none closed
        b'<svg viewBox="' + b" " * 100_000 + b'1" width="' + b" " * 100_000 + b'1">',
    ],
    # Short ids: pytest puts a test's id in PYTEST_CURRENT_TEST, and Windows refuses an
    # environment variable longer than 32767 characters.
    ids=lambda hostile: f"{hostile[:12]!r}x{len(hostile)}",
)
def test_a_long_hostile_svg_is_read_in_linear_time(hostile):
    import time

    started = time.monotonic()
    sources_image.sniff(hostile)

    assert time.monotonic() - started < 2


def test_bytes_that_are_no_image_are_none():
    assert sources_image.sniff(b"just words") is None
    assert sources_image.sniff(b"\xff\xd8\xff\xe0 truncated") is not None  # JPEG magic, no size


@pytest.fixture
def work(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run_import(capsys, *arguments: str):
    code = sources.main(["import", *arguments])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def manifest(work: Path, name: str = "d") -> dict:
    return json.loads((work / ".outcomebound/sources" / f"{name}.json").read_text("utf-8"))


def test_an_image_is_one_item_with_id_and_revision_from_its_digest(work, capsys):
    (work / "login.png").write_bytes(png(640, 480))

    code, out, _ = run_import(capsys, "login.png", "--name", "d")

    document = manifest(work)
    (item,) = document["items"]
    digest = document["sources"][0]["raw_sha256"]
    assert code == 0 and validate(document, schema("sources-manifest.schema.json")) == []
    assert item["id"] == f"d:login:image-{digest[:12]}" and item["revision"] == digest
    assert (
        item["text"]
        == "image/png, 640x480 px, " + f"{len(png(640, 480))} bytes; the pixels were not read"
    )
    assert document["sources"][0]["format"] == "image" and item["partial"] == []
    assert "the engine did not read it" in out


def test_a_binary_image_digest_does_not_fold_line_endings(work, capsys):
    data = png(0x0D0A, 5)  # a width of 0x0D0A puts a CR LF byte pair into the header
    assert b"\r\n" in data[8:]
    (work / "a.png").write_bytes(data)

    run_import(capsys, "a.png", "--name", "d")

    import hashlib

    assert manifest(work)["sources"][0]["raw_sha256"] == hashlib.sha256(data).hexdigest()


def test_the_same_image_gives_the_same_manifest_and_svg_crlf_does_not_move_a_digest(work, capsys):
    (work / "a.svg").write_bytes(SVG_SIZED)
    run_import(capsys, "a.svg", "--name", "d")
    first = (work / ".outcomebound/sources/d.json").read_bytes()
    (work / "a.svg").write_bytes(SVG_SIZED.replace(b"\r\n", b"\n"))

    run_import(capsys, "a.svg", "--name", "d")

    assert (work / ".outcomebound/sources/d.json").read_bytes() == first


def test_a_size_the_header_does_not_state_reads_unverified_and_exits_2(work, capsys):
    (work / "chart.svg").write_bytes(SVG_BARE)

    code, out, _ = run_import(capsys, "chart.svg", "--name", "d")

    item = manifest(work)["items"][0]
    assert code == 2 and item["partial"] == ["size-unverified"]
    assert "size UNVERIFIED" in item["text"] and "UNVERIFIED partial" in out


def test_images_and_markdown_import_together(work, capsys):
    (work / "notes.md").write_text("# Goal\nShow the form.\n", "utf-8")
    (work / "form.png").write_bytes(png(10, 20))

    code, _, _ = run_import(capsys, "notes.md", "form.png", "--name", "d")

    formats = [source["format"] for source in manifest(work)["sources"]]
    assert code == 0 and formats == ["image", "markdown"] and len(manifest(work)["items"]) == 2


def test_a_design_tool_json_is_refused_with_the_forms_that_are_read(work, capsys):
    (work / "frame.json").write_text('{"document": {}}', "utf-8")

    code, _, err = run_import(capsys, "frame.json", "--name", "d")

    assert code == 1 and err.startswith("SOURCE_KIND_UNKNOWN")
    assert (
        ".png" in err
        and "SVG" in err
        and "markdown" in err
        and not (work / ".outcomebound").exists()
    )


def test_a_file_with_an_image_suffix_that_is_no_image_is_refused(work, capsys):
    (work / "fake.png").write_text("not a picture", "utf-8")

    code, _, err = run_import(capsys, "fake.png", "--name", "d")

    assert code == 1 and err.startswith("SOURCE_IMAGE_INVALID")


def test_the_kind_may_be_named(work, capsys):
    (work / "shot.dat").write_bytes(gif(2, 3))

    code, _, _ = run_import(capsys, "shot.dat", "--name", "d", "--as", "image")

    assert code == 0 and manifest(work)["items"][0]["text"].startswith("image/gif, 2x3 px")


# --- check -------------------------------------------------------------------------------------

SPEC = """# Spec

## Requirements

- R1 The login screen matches the approved design.
- R2 The form has a Submit button.

## Sources

| Source item | Disposition | Where | Basis |
| --- | --- | --- | --- |
{rows}
"""
PLAN = {"claims": [{"name": "login-screenshot", "command": ["true"]}]}


@pytest.fixture
def shot(work, capsys):
    (work / "login.png").write_bytes(png(640, 480))
    assert sources.main(["import", "login.png", "--name", "d"]) == 0
    capsys.readouterr()
    return work


def item_cell(work: Path) -> str:
    item = manifest(work)["items"][0]
    return f"{item['id']} #{item['revision'][:12]}"


def check(work: Path, capsys, *rows: str, extra=()):
    (work / "spec.md").write_text(SPEC.format(rows="\n".join(rows)), "utf-8")
    code = sources.main(["check", ".outcomebound/sources/d.json", "spec.md", *extra])
    return code, capsys.readouterr().out


def lines(out: str, verdict: str, code: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith(f"{verdict} {code} ")]


def test_an_image_disposed_as_carried_inferred_passes_and_the_report_says_it_was_not_read(
    shot, capsys
):
    row = f"| {item_cell(shot)} | carried | R2 | inferred: the form in the top half |"

    code, out = check(shot, capsys, row)

    assert code == 0 and out.startswith("PASS; 0 FAIL, 0 UNVERIFIED, 2 INFO")
    assert "content not read by the engine" in lines(out, "INFO", "IMAGE_NOT_READ")[0]


def test_a_requirement_carried_from_an_image_cannot_be_stated(shot, capsys):
    row = f'| {item_cell(shot)} | carried | R2 | stated: "640x480" |'

    code, out = check(shot, capsys, row)

    assert code == 1 and "taken from an image is inferred" in lines(out, "FAIL", "ROW_MALFORMED")[0]


@pytest.mark.parametrize("by", ["by: command login-screenshot", "by: review Dana", "by: judgment"])
def test_a_reference_row_disposes_the_image_and_reads_unverified_because_no_picture_was_compared(
    shot, capsys, by
):
    row = f"| {item_cell(shot)} | reference | R1 | {by} |"

    code, out = check(shot, capsys, row)

    (line,) = lines(out, "UNVERIFIED", "REFERENCE_NOT_COMPARED")
    assert code == 2 and "no picture was compared" in line and "Does not establish:" in line
    assert (
        not lines(out, "FAIL", "ITEM_UNDISPOSED")
        and "FAIL" not in out.splitlines()[0].split(";")[0]
    )


def test_a_reference_by_command_is_checked_against_the_plan_given(shot, capsys):
    (shot / "plan.json").write_text(json.dumps(PLAN), "utf-8")
    row = f"| {item_cell(shot)} | reference | R1 | by: command login-screenshot |"
    code, out = check(shot, capsys, row, extra=("--plan", "plan.json", "--verbose"))
    assert code == 2 and "claim names were not checked" not in out
    assert lines(out, "PASS", "CLAIM_MISSING")

    row = f"| {item_cell(shot)} | reference | R1 | by: command no-such-claim |"
    code, out = check(shot, capsys, row, extra=("--plan", "plan.json"))
    assert (
        code == 1 and "no-such-claim is not in plan.json" in lines(out, "FAIL", "CLAIM_MISSING")[0]
    )


def test_a_reference_by_command_with_no_plan_says_the_claim_name_was_not_checked(shot, capsys):
    row = f"| {item_cell(shot)} | reference | R1 | by: command login-screenshot |"

    code, out = check(shot, capsys, row)

    assert code == 2 and "claim names were not checked against a plan" in out


def test_an_unreadable_plan_fails(shot, capsys):
    (shot / "plan.json").write_text("{not json", "utf-8")
    row = f"| {item_cell(shot)} | reference | R1 | by: judgment |"

    code, out = check(shot, capsys, row, extra=("--plan", "plan.json"))

    assert code == 1 and lines(out, "FAIL", "PLAN_UNREADABLE")


@pytest.mark.parametrize(
    "where_and_basis",
    [
        "| R9 | by: judgment |",  # an undefined requirement
        "| R1 | matches the design |",  # no `by:`
        "| R1 | by: command |",  # no claim named
        "| R1 | by: review |",  # no reviewer named
        "| | by: judgment |",  # no requirement
    ],
)
def test_a_malformed_reference_row_fails(shot, capsys, where_and_basis):
    code, out = check(shot, capsys, f"| {item_cell(shot)} | reference {where_and_basis}")

    assert code == 1 and (
        lines(out, "FAIL", "ROW_MALFORMED") or lines(out, "FAIL", "TARGET_MISSING")
    )


def test_an_image_may_be_both_a_reference_and_carried_but_not_carried_twice(shot, capsys):
    cell = item_cell(shot)
    reference = f"| {cell} | reference | R1 | by: judgment |"
    carried = f"| {cell} | carried | R2 | inferred: the Submit button |"

    code, out = check(shot, capsys, reference, carried)
    assert code == 2 and not lines(out, "FAIL", "ITEM_DUPLICATE")

    code, out = check(shot, capsys, carried, carried)
    assert code == 1 and lines(out, "FAIL", "ITEM_DUPLICATE")


def test_a_requirement_cited_only_by_a_reference_is_not_unsourced(shot, capsys):
    reference = f"| {item_cell(shot)} | reference | R1 | by: judgment |"

    out = check(shot, capsys, reference)[1]

    assert "R1 is carried from no item" not in out and "R2 is carried from no item" in out


def test_a_reference_row_names_one_item_not_a_range(shot, capsys):
    cell = item_cell(shot).replace(" #", "..").split("..")[0]
    item = manifest(shot)["items"][0]
    row = f"| {item['id']}..{item['id']} #{item['revision'][:12]} | reference | R1 | by: judgment |"

    code, out = check(shot, capsys, row)

    assert code == 1 and any("not a range" in line for line in lines(out, "FAIL", "ROW_MALFORMED"))
    assert cell


def test_a_replaced_image_is_source_changed_and_an_edited_manifest_is_manifest_differs(
    shot, capsys
):
    row = f"| {item_cell(shot)} | reference | R1 | by: judgment |"
    (shot / "login.png").write_bytes(png(641, 480))
    code, out = check(shot, capsys, row)
    assert code == 1 and lines(out, "FAIL", "SOURCE_CHANGED")

    (shot / "login.png").write_bytes(png(640, 480))
    path = shot / ".outcomebound/sources/d.json"
    document = json.loads(path.read_text("utf-8"))
    document["items"][0]["text"] = document["items"][0]["text"].replace("640x480", "999x999")
    path.write_text(json.dumps(document), "utf-8")
    code, out = check(shot, capsys, row)
    assert code == 1 and lines(out, "FAIL", "MANIFEST_DIFFERS")


def test_an_image_whose_file_is_absent_reads_unverified_not_pass(shot, capsys):
    row = f"| {item_cell(shot)} | reference | R1 | by: judgment |"
    (shot / "login.png").unlink()

    code, out = check(shot, capsys, row)

    assert code == 2 and lines(out, "UNVERIFIED", "SOURCE_FRESHNESS")


def test_a_reference_row_over_a_text_item_does_not_say_a_picture_was_compared(work, capsys):
    (work / "notes.md").write_text("# A\nThe form has a Submit button.\n", "utf-8")
    assert sources.main(["import", "notes.md", "--name", "d"]) == 0
    capsys.readouterr()

    code, out = check(work, capsys, f"| {item_cell(work)} | reference | R1 | by: judgment |")

    (line,) = lines(out, "UNVERIFIED", "REFERENCE_NOT_COMPARED")
    assert code == 2 and "no text was compared" in line and "picture" not in line.split(";")[1]


def test_an_svg_is_the_root_element_not_the_first_svg_anywhere():
    wrapped = b"<html><body><svg width='2' height='2'></svg></body></html>"
    assert sources_image.sniff(wrapped) is None
    subset = (
        b'<!DOCTYPE svg [<!ENTITY e "<svg width=\'1\' height=\'1\'>">]>\n<svg width="9" height="7">'
    )
    found = sources_image.sniff(subset)
    assert found is not None and (found.width, found.height) == (9, 7)
    declared = (
        b'<?xml version="1.0"?><!-- c --><!DOCTYPE svg PUBLIC "a" "b"><svg width="5" height="4">'
    )
    found = sources_image.sniff(declared)
    assert found is not None and (found.width, found.height) == (5, 4)
