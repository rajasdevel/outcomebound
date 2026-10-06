"""The one path grammar: what `paths` admits, and what discovery refuses with it.

A leading `~` and every code point below 32 plus DEL are refused wherever a path
is read, and a spelling that reaches `.git` on any filesystem is refused too.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from outcomebound_tools import discovery, paths

CONTROL_ROOTS = ("a\x01b", "a\x7fb", "pkg\tsrc")


def _make(target, name):
    """Create the directory so admission, not absence, is what refuses it."""
    try:
        (target / name).mkdir()
    except OSError as error:  # pragma: no cover - filesystem-dependent
        pytest.skip(f"filesystem rejects the fixture name {name!r}: {error}")


def test_discovery_refuses_a_root_with_a_control_character_or_a_leading_tilde(tmp_path):
    target = tmp_path / "discovery"
    target.mkdir()
    _make(target, "~home")
    with pytest.raises(discovery.DiscoveryError) as tilde:
        discovery.discover(target, roots=["~home"])
    assert "not a bounded component root" in str(tilde.value)

    # A `~` anywhere but the first position stays a legal directory name.
    _make(target, "pkg~1")
    assert discovery.discover(target, roots=["pkg~1"])["roots"] == ["pkg~1"]

    for name in CONTROL_ROOTS:
        _make(target, name)
        with pytest.raises(discovery.DiscoveryError) as control:
            discovery.discover(target, roots=[name])
        assert "not a bounded component root" in str(control.value)

    # Ordinary roots still pass, including the whole-target root.
    (target / "packages").mkdir()
    assert discovery.discover(target, roots=["."])["roots"] == ["."]
    assert discovery.discover(target, roots=["packages"])["roots"] == ["packages"]


GRAMMAR_CORPUS = (
    "a",
    "a/b",
    "a/b/c.txt",
    "pkg~1",
    "a b",
    "a-b_c.d",
    "ünïcode/ok.md",
    ".hidden",
    "a/.hidden",
    "a..b",
    "...",
    "",
    ".",
    "..",
    "/abs",
    "~home",
    "~",
    "a//b",
    "a/",
    "/a",
    "a/./b",
    "a/../b",
    "a\\b",
    "a:b",
    "C:/x",
    "a\x00b",
    "a\x01b",
    "a\x1fb",
    "a\x7fb",
    "a\tb",
    "a\nb",
    ".git",
    "a/.git",
    "a/.git/b",
    ".gitignore",
    "a/.gitignore",
)


# The grammar's verdicts, written out: these corpus values are admitted, `.` only where
# the target root itself is allowed, and every other value is refused.
ADMITTED = frozenset(
    {
        "a",
        "a/b",
        "a/b/c.txt",
        "pkg~1",
        "a b",
        "a-b_c.d",
        "ünïcode/ok.md",
        ".hidden",
        "a/.hidden",
        "a..b",
        "...",
        ".gitignore",
        "a/.gitignore",
    }
)
ADMITTED_AS_ROOT = frozenset({"."})


def test_bounded_relative_gives_the_grammar_verdict_on_every_corpus_value():
    """The helper admits exactly the values written out above, `.` only as a root."""

    assert set(GRAMMAR_CORPUS) >= ADMITTED | ADMITTED_AS_ROOT
    for value in GRAMMAR_CORPUS:
        for root in (False, True):
            expected = value in ADMITTED or (root and value in ADMITTED_AS_ROOT)
            assert paths.admits(value, allow_root=root) is expected, (value, root)

            if expected:
                assert paths.bounded_relative(value, allow_root=root) == value
            else:
                with pytest.raises(paths.PathError):
                    paths.bounded_relative(value, allow_root=root)

    # Non-strings are refused rather than coerced: a reader that accepted a
    # Path here would admit `PurePosixPath("..")` by its repr.
    for value in (None, 1, b"a", Path("a")):
        assert paths.admits(value) is False


def test_read_bounded_separates_a_hostile_path_from_an_unreadable_file(tmp_path):
    (tmp_path / "doc.md").write_bytes(b"body\n")
    assert paths.read_bounded(tmp_path, "doc.md") == b"body\n"

    (tmp_path / "nested").mkdir()
    (tmp_path / "nested/deep.md").write_bytes(b"deep\n")
    assert paths.read_bounded(tmp_path, "nested/deep.md") == b"deep\n"

    with pytest.raises(paths.PathError) as hostile:
        paths.read_bounded(tmp_path, "../escape")
    assert "not a bounded relative path" in str(hostile.value)

    with pytest.raises(paths.PathError) as absent:
        paths.read_bounded(tmp_path, "missing.md")
    assert "not a readable file" in str(absent.value)

    with pytest.raises(paths.PathError) as directory:
        paths.read_bounded(tmp_path, "nested")
    assert "not a readable file" in str(directory.value)

    # A symlinked ancestor relocates everything under it, so the check is on
    # every component and not on the resolved result.
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    (outside / "secret.md").write_text("secret\n", encoding="utf-8")
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(paths.PathError) as linked:
        paths.read_bounded(tmp_path, "linked/secret.md")
    assert "contains a symlink" in str(linked.value)

    (tmp_path / "direct.md").symlink_to(outside / "secret.md")
    with pytest.raises(paths.PathError):
        paths.read_bounded(tmp_path, "direct.md")


def test_admits_refuses_every_spelling_that_reaches_git() -> None:
    """A case-folding or dot-dropping filesystem opens `.git` for each refused spelling, while
    the admitted names only resemble it."""

    for value in (".GIT/hooks/pre-commit", ".Git/config", ".git./x", "a/.git /b", "a/.gIt.."):
        assert paths.admits(value) is False, value
        with pytest.raises(paths.PathError):
            paths.bounded_relative(value)
    for value in (".github/workflows/ci.yml", ".gitignore", "a/.gitkeep", "git/x", "a/.git-x"):
        assert paths.admits(value) is True, value


def test_a_printed_command_word_is_quoted_for_the_shells_that_run_it(monkeypatch) -> None:
    """POSIX shells read `shlex.quote`. On Windows the two shells that run an engine-printed
    command, PowerShell and Git Bash, both read a single-quoted word whole, and a path is
    written with forward slashes, which each Windows shell and program takes."""

    assert paths.shell_word("plain-word_1.txt") == "plain-word_1.txt"
    assert paths.shell_word("it's here") == "'it'\"'\"'s here'"
    monkeypatch.setattr("sys.platform", "win32")
    assert paths.shell_word("plain-word_1.txt") == "plain-word_1.txt"
    assert paths.shell_word("C:/Program Files/app/x") == "'C:/Program Files/app/x'"
    assert paths.shell_word("it's here") == "'it''s here'"
    assert paths.shell_word("C:\\Users\\x") == "'C:\\Users\\x'", "a backslash is kept, not read"
    assert paths.shell_word("$x; rm") == "'$x; rm'"
    assert paths.shell_path("C:/Program Files/app/repo") == "'C:/Program Files/app/repo'"


@pytest.mark.parametrize(
    "relative",
    [
        *("a<b", 'a/"b', "a|b", "a?b", "a*b", "CON", "con.txt", "a/NUL", "aux.tar.gz", "COM1"),
        *("lpt9.x", "dir./file", "a/name ", "x/trailing."),
    ],
)
def test_windows_refuses_a_name_it_cannot_hold_and_no_other_platform_does(
    relative: str, monkeypatch
) -> None:
    assert paths.admits(relative) is True, "the grammar stays as every manifest agrees on it"
    assert paths.windows_refusal(relative) is None
    monkeypatch.setattr("sys.platform", "win32")
    assert paths.windows_refusal(relative)


@pytest.mark.parametrize(
    "relative",
    ["CONFIG.md", "console/x", "a/com10", "LPT0", "aux-notes.md", "a.b/c", ".github/ci.yml"],
)
def test_windows_refuses_nothing_that_only_resembles_a_device_name(
    relative: str, monkeypatch
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    assert paths.windows_refusal(relative) is None


def test_a_junction_is_a_way_in_that_a_symlink_is(tmp_path, monkeypatch) -> None:
    """A directory junction is no symlink to Python, and a normal Windows account can make one;
    the check reads its reparse tag, and no other tag, since a cloud folder's placeholders carry
    their own. Emulated here: the junction's `lstat` is faked, as no junction can be made on
    this machine."""

    folder = tmp_path / "linked"
    folder.mkdir()
    (folder / "x.md").write_bytes(b"x\n")
    assert paths.read_bounded(tmp_path, "linked/x.md") == b"x\n"

    real = Path.lstat

    def lstat(self, **kwargs):
        found = real(self, **kwargs)
        tag = {"linked": paths.REPARSE_TAG_JUNCTION, "cloud": 0x9000001A}.get(self.name, 0)
        return SimpleNamespace(
            **{n: getattr(found, n) for n in dir(found) if n.startswith("st_")}, st_reparse_tag=tag
        )

    monkeypatch.setattr(Path, "lstat", lstat)
    assert not paths.redirects(folder), "no other platform has a junction"
    monkeypatch.setattr("sys.platform", "win32")
    with pytest.raises(paths.PathError, match="symlink"):
        paths.read_bounded(tmp_path, "linked/x.md")
    (tmp_path / "cloud").mkdir()
    (tmp_path / "cloud/y.md").write_bytes(b"y\n")
    assert paths.read_bounded(tmp_path, "cloud/y.md") == b"y\n"
