"""The upstream check: README link parsing and a recorded `gh api` reading, with no network."""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent


def _load() -> ModuleType:
    path = ROOT / ".agents" / "tools" / "upstream-check"
    loader = importlib.machinery.SourceFileLoader("upstream_check", str(path))
    spec = importlib.util.spec_from_loader("upstream_check", loader)
    assert spec is not None, str(path)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


CHECK = _load()

README = """# Name

[a/not-credit](https://github.com/a/not-credit) sits before the section.

## Acknowledgements

Ideas come from [obra/superpowers](https://github.com/obra/superpowers),
[mattpocock/skills](https://github.com/mattpocock/skills), and again
[obra/superpowers](https://github.com/obra/superpowers/); also
[x/y.z](https://github.com/x/y.z). Our research is at
[r](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/skills.md).

## License

[b/after](https://github.com/b/after)
"""

TREE = {
    "truncated": False,
    "tree": [
        {"path": "README.md", "type": "blob"},
        {"path": "skills/diagnose/SKILL.md", "type": "blob"},
        {"path": "skills/tdd/SKILL.md", "type": "blob"},
        {"path": "other/thing/SKILL.md", "type": "blob"},
        {"path": "docs/guide.md", "type": "blob"},
    ],
}

COMMITS = {
    "skills": [
        {
            "sha": "bbbbbbbbbbbb",
            "html_url": "https://github.com/o/r/commit/bbbbbbbbbbbb",
            "commit": {"message": "second\n\nbody", "committer": {"date": "2026-09-03T10:00:00Z"}},
        },
        {
            "sha": "aaaaaaaaaaaa",
            "html_url": "https://github.com/o/r/commit/aaaaaaaaaaaa",
            "commit": {"message": "first", "committer": {"date": "2026-09-01T10:00:00Z"}},
        },
    ],
    "other/thing": [
        {
            "sha": "bbbbbbbbbbbb",
            "html_url": "https://github.com/o/r/commit/bbbbbbbbbbbb",
            "commit": {"message": "second\n\nbody", "committer": {"date": "2026-09-03T10:00:00Z"}},
        },
    ],
}


def test_readme_repos_reads_only_the_credits_and_skips_our_own() -> None:
    assert CHECK.readme_repos(README) == ["obra/superpowers", "mattpocock/skills", "x/y.z"]


def test_the_real_readme_names_credited_repositories() -> None:
    repos = CHECK.readme_repos((ROOT / "README.md").read_text(encoding="utf-8"))
    assert repos and all("/" in repo and "rajasdevel" not in repo for repo in repos)


def test_skill_dirs_are_those_holding_a_skill_file_and_the_skills_root() -> None:
    assert CHECK.skill_dirs(TREE) == ["other/thing", "skills", "skills/diagnose", "skills/tdd"]


def test_candidates_from_a_recorded_response_are_deduplicated_and_dated() -> None:
    calls: list[str] = []

    def gh(endpoint: str) -> object:
        calls.append(endpoint)
        if "/git/trees/" in endpoint:
            return TREE
        path = endpoint.split("path=")[1].split("&")[0]
        return COMMITS.get(path, [])

    lines, notes = CHECK.candidates("o/r", "2026-08-31", gh)
    assert notes == []
    assert lines == [
        "o/r  2026-09-01  aaaaaaa  first  https://github.com/o/r/commit/aaaaaaaaaaaa",
        "o/r  2026-09-03  bbbbbbb  second  https://github.com/o/r/commit/bbbbbbbbbbbb",
    ]
    assert all("since=2026-08-31T00:00:00Z" in c for c in calls if "/commits" in c)


def test_a_truncated_tree_is_noted() -> None:
    def gh(endpoint: str) -> object:
        return {"truncated": True, "tree": []} if "/git/trees/" in endpoint else []

    lines, notes = CHECK.candidates("o/r", "2026-08-31", gh)
    assert lines == [] and "truncated" in notes[0]


def _page(count: int, start: int = 0) -> list[dict]:
    return [
        {
            "sha": f"{start + n:012x}",
            "html_url": "u",
            "commit": {
                "message": "m",
                "committer": {"date": f"2026-09-{1 + n % 28:02d}T10:00:00Z"},
            },
        }
        for n in range(count)
    ]


def test_commits_past_the_first_hundred_are_read_and_a_reached_page_limit_is_noted() -> None:
    def gh(endpoint: str) -> object:
        if "/git/trees/" in endpoint:
            return {"truncated": False, "tree": [{"path": "skills/a/SKILL.md"}]}
        page = int(endpoint.split("&page=")[1])
        return _page(100, page * 1000) if page <= 2 else _page(5, page * 1000)

    lines, notes = CHECK.candidates("o/r", "2026-08-31", gh)
    assert len(lines) == 205 and notes == []

    def endless(endpoint: str) -> object:
        if "/git/trees/" in endpoint:
            return {"truncated": False, "tree": [{"path": "skills/a/SKILL.md"}]}
        page = int(endpoint.split("&page=")[1])
        return _page(100, page * 1000)

    lines, notes = CHECK.candidates("o/r", "2026-08-31", endless)
    assert len(lines) == 100 * CHECK.MAX_PAGES and "page limit" in notes[0]


def test_a_directory_name_is_url_encoded_in_the_query() -> None:
    seen: list[str] = []

    def gh(endpoint: str) -> object:
        seen.append(endpoint)
        if "/git/trees/" in endpoint:
            return {"truncated": False, "tree": [{"path": "a&b #c/SKILL.md"}]}
        return []

    CHECK.candidates("o/r", "2026-08-31", gh)
    assert "path=a%26b%20%23c&" in seen[-1]


def test_a_subject_with_control_characters_prints_escaped() -> None:
    commit = {
        "sha": "abcdef0123",
        "html_url": "u",
        "commit": {"message": "x\x1b[31mred\x07", "committer": {"date": "2026-09-01"}},
    }
    line = CHECK.commit_line("o/r", commit)
    assert "\x1b" not in line and "\x07" not in line and "\\x1b[31mred\\x07" in line
