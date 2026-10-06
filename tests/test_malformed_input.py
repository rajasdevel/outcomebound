"""Every parser rejects garbage with its own typed error — never a silent pass.

A truncated or hostile artifact fails at its parser, so it never reaches a caller as a
partially parsed object.
"""

import subprocess
from pathlib import Path

import pytest

from outcomebound_tools.identity import (
    IdentityConflict,
    IdentityError,
    find_managed_blocks,
    format_managed_block,
    has_unclosed_fence,
    parse_managed_block,
)
from outcomebound_tools.validation import PlanError, load_plan
from tests.portable import engine

GARBAGE = (
    "",
    "\x00\x01\x02",
    "not json at all",
    "{",
    "[]",
    "null",
    '{"format_version": 1',
    '{"format_version": 1, "artifacts": "not-a-list"}',
    '{"version": 1, "claims": []}',
    '{"version": 1, "boundaries": []}',
    "\ufeff{}",
    "0" * 4096,
)

SENTINEL_GARBAGE = (
    "",
    "body only",
    "<!-- outcomebound:begin id=operating-contract v=1.0.0 -->",
    "<!-- outcomebound:end id=operating-contract -->",
    "<!-- outcomebound:end id=operating-contract -->\nbody\n"
    "<!-- outcomebound:begin id=operating-contract v=1.0.0 -->",
    "<!-- outcomebound:begin id=operating-contract v=1.0.0 -->\nbody\n"
    "<!-- somethingelse:end id=operating-contract -->",
    "<!-- outcomebound:begin id=operating-contract v=1.0.0 -->\nbody\n"
    "<!-- outcomebound:end id=other-contract -->",
)


def _write(tmp_path: Path, payload: str) -> Path:
    path = tmp_path / "artifact.json"
    path.write_text(payload, encoding="utf-8", errors="surrogatepass")
    return path


@pytest.mark.parametrize("payload", GARBAGE)
def test_validation_plan_parser_raises_plan_error(tmp_path, payload):
    with pytest.raises(PlanError):
        load_plan(_write(tmp_path, payload))


@pytest.mark.parametrize("payload", SENTINEL_GARBAGE)
def test_sentinel_parser_raises_identity_error(payload):
    with pytest.raises(IdentityError):
        parse_managed_block(payload)


BEGIN = "<!-- outcomebound:begin id={id} v=1.0.0 -->"
END = "<!-- outcomebound:end id={id} -->"


def block(block_id: str, body: str = "body") -> str:
    return f"{BEGIN.format(id=block_id)}\n{body}\n{END.format(id=block_id)}"


def test_fenced_candidates_ignored_and_unfenced_duplicates_refuse():
    """A fenced candidate is not a block; a duplicate unfenced one refuses.

    The two halves are one guarantee: the reader decides what counts as a
    managed block, so documentation that quotes a sentinel is inert while real
    corruption still fails closed.
    """

    fenced = f"intro\n\n```markdown\n{block('operating-contract')}\n```\n"
    assert find_managed_blocks(fenced) == []

    real = block("project-guidance", "guidance")
    both = fenced + "\n" + real + "\n"
    (found,) = find_managed_blocks(both)
    assert (found.id, found.body) == ("project-guidance", "guidance")
    assert both[found.begin_offset : found.end_offset] == real

    with pytest.raises(IdentityConflict):
        find_managed_blocks(real + "\n\n" + real)


def test_fence_grammar_follows_the_contract():
    """Up to three leading spaces; three or more markers; matched closer."""

    for fence in ("```", "~~~", "   ```", "````````", "```markdown"):
        closer = fence.strip()[0] * max(3, len(fence.strip()))
        text = f"{fence}\n{block('operating-contract')}\n{closer}\n"
        assert find_managed_blocks(text) == [], fence
    # Four leading spaces is an indented code block, not a fence opener, so the
    # candidate stays unfenced and is read.
    assert len(find_managed_blocks(f"    ```\n{block('a')}\n    ```\n")) == 1
    # A shorter closer does not close the fence; the rest of the file is fenced.
    assert find_managed_blocks(f"````\n{block('a')}\n```\n{block('b')}\n") == []
    # An unclosed fence runs to the end of the document.
    assert find_managed_blocks(f"```\n{block('a')}\n") == []
    # A tilde fence is not closed by backticks.
    assert find_managed_blocks(f"~~~\n{block('a')}\n```\n") == []


def test_reader_stays_whitespace_tolerant_and_reports_host_order():
    """The reader's whitespace-tolerant grammar reads blocks other writers reformatted."""

    tolerant = (
        "<!--   outcomebound:begin id=operating-contract "
        "hash=abc123 v=1.0.0   -->\nkernel\n"
        "<!--\toutcomebound:end id=operating-contract -->"
    )
    later = block("project-guidance", "guidance")
    blocks = find_managed_blocks(f"{tolerant}\n\n{later}\n")
    assert [b.id for b in blocks] == ["operating-contract", "project-guidance"]
    assert [b.hash for b in blocks] == ["abc123", None]
    assert [b.version for b in blocks] == ["1.0.0", "1.0.0"]
    assert [b.body for b in blocks] == ["kernel", "guidance"]
    assert blocks[0].begin_offset == 0
    assert blocks[0].end_offset == len(tolerant)
    assert blocks[0].brand == "outcomebound" and blocks[0].block_id == "operating-contract"
    assert blocks[0].content_hash == blocks[0].hash


@pytest.mark.parametrize(
    "text",
    (
        BEGIN.format(id="a") + "\nbody\n",
        "body\n" + END.format(id="a"),
        BEGIN.format(id="a") + "\n" + block("b") + "\n" + END.format(id="a"),
        BEGIN.format(id="a") + "\nbody\n" + END.format(id="b"),
        END.format(id="a") + "\nbody\n" + BEGIN.format(id="a"),
        "<!-- outcomebound:begin id=a -->\nbody\n" + END.format(id="a"),
        "<!-- outcomebound:begin id=a  v=1.0.0 -->\nbody\n" + END.format(id="a"),
        "<!-- outcomebound:end id=A -->",
    ),
)
def test_unfenced_corruption_is_never_silently_ignored(text):
    with pytest.raises(IdentityError):
        find_managed_blocks(text)


def test_empty_and_blockless_documents_are_not_errors():
    """Absence is a legitimate answer for a presence check; corruption is not."""

    assert find_managed_blocks("") == []
    assert find_managed_blocks("just prose about outcomebound\n") == []


def test_new_emission_is_single_spaced_and_the_reader_round_trips_it():
    """The emitted form, read back through the same reader that gates it."""

    rendered = format_managed_block("project-guidance", "1.0.0", "guidance", content_hash="a1b2")
    lines = rendered.splitlines()
    assert lines[0] == "<!-- outcomebound:begin id=project-guidance hash=a1b2 v=1.0.0 -->"
    assert lines[-1] == "<!-- outcomebound:end id=project-guidance -->"
    (block,) = find_managed_blocks(rendered)
    assert (block.id, block.hash, block.version, block.body) == (
        "project-guidance",
        "a1b2",
        "1.0.0",
        "guidance",
    )
    assert (block.begin_offset, block.end_offset) == (0, len(rendered))


@pytest.mark.parametrize(
    "text, unclosed",
    (
        (f"```\n{block('a')}\n```\n", False),
        (f"~~~\n{block('a')}\n~~~\n", False),
        ("prose with no fence at all\n", False),
        ("", False),
        (f"```\n{block('a')}\n", True),
        (f"~~~\n{block('a')}\n", True),
        # A closer shorter than its opener does not close anything.
        (f"````\n{block('a')}\n```\n", True),
        # ...and a longer one does.
        (f"```\n{block('a')}\n`````\n", False),
        # A tilde fence is not closed by backticks.
        (f"~~~\n{block('a')}\n```\n", True),
        # Four spaces is an indented code block, so there is no fence to close.
        (f"    ```\n{block('a')}\n", False),
        # Three spaces still opens one.
        (f"   ```\n{block('a')}\n", True),
        ("```\r\nfenced\r\n```\r\n", False),
        ("```\r\nfenced\r\n", True),
    ),
)
def test_has_unclosed_fence_reads_the_readers_own_fence_grammar(text, unclosed):
    """One fence grammar answers both "what is fenced?" and "is one open?".

    A reader can only say "no managed block here" about the rest of a document
    an unclosed fence swallows, and that answer is indistinguishable from real
    absence, so a writer that appends on absence would add a second block after
    a truncated example. A writer therefore has to ask this question separately,
    and it must be the SAME scanner, or it would refuse over fences the reader
    never saw.
    """

    assert has_unclosed_fence(text) is unclosed
    if unclosed:
        # The swallowed region is exactly what the reader stops seeing.
        assert find_managed_blocks(text) == []


@pytest.mark.parametrize(
    "text",
    (
        # A begin sentinel whose closing `-->` never arrived.
        "# host\n<!-- outcomebound:begin id=operating-contract v=1.0.0\nbody\n",
        # ...and the end sentinel's own truncation.
        block("a") + "\n<!-- outcomebound:end id=a\n",
        # Truncated, then a well-formed block: the corruption still decides.
        "<!-- outcomebound:begin id=a v=1.0.0\n" + block("b") + "\n",
        # The opener is the last line, with no newline after it at all.
        "# host\n<!-- outcomebound:begin id=a v=1.0.0",
    ),
)
def test_a_truncated_begin_sentinel_raises_instead_of_reading_as_absent(text):
    """A sentinel that lost its `-->` is corruption, never absence.

    Were a half-written sentinel to match nothing, `find_managed_blocks` would
    answer `[]`, the same answer a clean host gives. Every writer that appends
    on absence would then append a SECOND block beside the corrupt one,
    producing a host each later reader refuses.
    """

    with pytest.raises(IdentityError):
        find_managed_blocks(text)


def test_a_truncated_sentinel_inside_a_fence_is_still_only_documentation():
    """The fence exclusion holds for a truncated sentinel: a quoted example is inert,
    closed or not."""

    fenced = "intro\n\n```markdown\n<!-- outcomebound:begin id=a v=1.0.0\n```\n"
    assert find_managed_blocks(fenced) == []


ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "host",
    (
        "# Project\n\n<!-- outcomebound:begin id=operating-contract v=1.0.0\nOLD BODY\n",
        "# Project\n\n"
        + block("operating-contract", "OLD BODY")
        + "\n<!-- outcomebound:end id=operating-contract\n",
    ),
)
def test_adopt_refuses_a_host_with_a_truncated_sentinel_instead_of_appending(tmp_path, host):
    """A host whose sentinel lost its `-->` is corruption adoption must not write over.

    Read as holding no block, such a host would look like a target with nothing
    installed, and adoption would APPEND a second `operating-contract` begin
    sentinel beside the corrupt one, at exit 0, leaving a host every later
    reader refuses.
    """

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "AGENTS.md").write_text(host, encoding="utf-8")
    before = _tree(tmp_path)

    result = subprocess.run(engine("adopt", tmp_path), capture_output=True, text=True, cwd=ROOT)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "malformed managed block sentinel" in result.stderr
    assert _tree(tmp_path) == before, "a refusal wrote to the target"


def _tree(target: Path) -> dict:
    return {
        str(path.relative_to(target)): path.read_bytes()
        for path in sorted(target.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(target).parts
    }
