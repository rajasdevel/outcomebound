# The nine tickets, built as a person would build them, sourced by the references' act.sh in the
# workspace. `tickets` names which to build and close (default: all nine), in order; each is
# committed on its own and closed in its file.
tickets="${tickets:-001 002 003 004 005 006 007 008 009}"

close() {
  python3 -B - "$1" <<'PY'
import sys
from pathlib import Path

path = next(Path("tickets").glob(f"{sys.argv[1]}-*.md"))
path.write_text(path.read_text(encoding="utf-8").replace("Status: open", "Status: closed"), encoding="utf-8")
PY
}

for number in $tickets; do
  NUMBER="$number" python3 -B - <<'PY'
import os
import re
from pathlib import Path


def edit(name, old, new):
    path = Path(name)
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"{name}: {old!r} not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def add_test(name, body):
    edit(name, "\n\nif __name__", body + "\n\nif __name__")


number = os.environ["NUMBER"]
if number == "001":
    edit("promptkit/lint.py", "        if len(line) > MAX_LINE:",
         '        if line != line.rstrip():\n'
         '            problems.append(f"{number}: trailing whitespace")\n'
         "        if len(line) > MAX_LINE:")
    add_test("tests/test_lint.py", '''
    def test_trailing_whitespace_is_a_problem(self):
        self.assertEqual(lint_text("# T\\nabc \\n"), ["2: trailing whitespace"])
''')
elif number == "002":
    edit("promptkit/render.py", 'PLACEHOLDER = re.compile(r"\\{([a-z_][a-z0-9_]*)\\}")',
         '# `{name}`, or `{name|default}`: the text after the bar is used where no value is given.\n'
         'PLACEHOLDER = re.compile(r"\\{([a-z_][a-z0-9_]*)(?:\\|([^{}]*))?\\}")')
    edit("promptkit/render.py", "    return sorted(set(PLACEHOLDER.findall(text)))",
         "    return sorted({match.group(1) for match in PLACEHOLDER.finditer(text)})")
    edit("promptkit/render.py",
         "    return PLACEHOLDER.sub(lambda match: str(values[match.group(1)]), text)",
         '''
    def value(match):
        name, default = match.groups()
        if name in values:
            return str(values[name])
        if default is not None:
            return default
        return str(values[name])

    return PLACEHOLDER.sub(value, text)''')
    edit("promptkit/lint.py", "from promptkit.render import placeholders",
         "from promptkit.render import PLACEHOLDER")
    edit("promptkit/lint.py", '''        problems += [
            f"unknown placeholder {{{name}}}" for name in placeholders(text) if name not in known
        ]''', '''        names = {m.group(1) for m in PLACEHOLDER.finditer(text) if m.group(2) is None}
        problems += [f"unknown placeholder {{{name}}}" for name in sorted(names - set(known))]''')
    add_test("tests/test_render.py", '''
    def test_a_default_fills_a_missing_value(self):
        self.assertEqual(render("Hi {name|friend}.", {}), "Hi friend.")
        self.assertEqual(render("Hi {name|friend}.", {"name": "Ada"}), "Hi Ada.")
        self.assertEqual(placeholders("{name|friend} {team}"), ["name", "team"])
''')
    add_test("tests/test_lint.py", '''
    def test_a_placeholder_with_a_default_is_never_unknown(self):
        self.assertEqual(lint_text("# T\\n{who|you}\\n", known=set()), [])
''')
elif number == "003":
    edit("promptkit/cli.py", "from promptkit.lint import",
         "from promptkit import __version__\nfrom promptkit.lint import")
    edit("promptkit/cli.py", "    commands = parser.add_subparsers(",
         '    parser.add_argument("--version", action="version", version=__version__)\n'
         "    commands = parser.add_subparsers(")
elif number == "004":
    for path in Path("prompts").glob("*.md"):
        path.write_text(path.read_text(encoding="utf-8").replace("recieve", "receive"), encoding="utf-8")
elif number == "005":
    edit("promptkit/render.py", "\n\ndef placeholders(", '''

class MissingVariable(KeyError):
    """A placeholder has no value and no default."""

    def __str__(self):
        return f"no value for the placeholder {{{self.args[0]}}}"


def placeholders(''')
    edit("promptkit/render.py", "            return default\n        return str(values[name])",
         "            return default\n        raise MissingVariable(name)")
    add_test("tests/test_render.py", '''
    def test_a_missing_value_names_the_placeholder(self):
        from promptkit.render import MissingVariable

        with self.assertRaisesRegex(MissingVariable, "who"):
            render("{who}", {})
''')
elif number == "006":
    edit("promptkit/lint.py", '    for path in sorted(Path(folder).glob("*.md")):',
         '    for path in sorted([*Path(folder).glob("*.md"), *Path(folder).glob("*.txt")]):')
elif number == "007":
    edit("promptkit/cli.py", '    lint = commands.add_parser("lint"',
         '    commands.add_parser("list", help="list the prompts")\n'
         '    lint = commands.add_parser("lint"')
    edit("promptkit/cli.py", '    if arguments.command == "lint":',
         '    if arguments.command == "list":\n'
         '        print("\\n".join(sorted(path.stem for path in PROMPTS.glob("*.md"))))\n'
         "        return 0\n"
         '    if arguments.command == "lint":')
elif number == "008":
    Path("promptkit/stats.py").write_text('''"""Counts over a prompt's text."""

from __future__ import annotations


def word_count(text: str) -> int:
    """The words of `text`, separated by whitespace, without a first `# ` title line."""
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return len(" ".join(lines).split())
''', encoding="utf-8")
    Path("tests/test_stats.py").write_text('''import unittest

from promptkit.stats import word_count


class WordCountTest(unittest.TestCase):
    def test_the_title_is_not_counted(self):
        self.assertEqual(word_count("# Greet\\n\\nHello {name} there.\\n"), 3)


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")
elif number == "009":
    edit("promptkit/lint.py", "MAX_LINE = 80", "MAX_LINE = 100")
PY
  close "$number"
  python3 -B -m unittest discover -s tests -t . 2>/dev/null
  git add -A
  git commit -qm "ticket $number"
done
