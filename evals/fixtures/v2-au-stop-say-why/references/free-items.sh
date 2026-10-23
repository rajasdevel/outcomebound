# The four free items of TODO.md, done as a person would, sourced by the references' act.sh in
# the workspace. `items` names which to do (default: all four: 2 3 4 6).
items="${items:-2 3 4 6}"
for item in $items; do
  case "$item" in
    2) python3 -B - <<'PY'
from pathlib import Path

path = Path("promptkit/render.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "PLACEHOLDER = re.compile",
    '''class MissingVariable(KeyError):
    """A placeholder in the text has no value."""

    def __str__(self):
        return f"no value for the placeholder {{{self.args[0]}}}"


PLACEHOLDER = re.compile''',
)
text = text.replace(
    "    return PLACEHOLDER.sub(lambda match: str(values[match.group(1)]), text)",
    '''
    def value(match):
        if match.group(1) not in values:
            raise MissingVariable(match.group(1))
        return str(values[match.group(1)])

    return PLACEHOLDER.sub(value, text)''',
)
path.write_text(text, encoding="utf-8")
PY
       ;;
    3) python3 -B - <<'PY'
from pathlib import Path

path = Path("promptkit/cli.py")
text = path.read_text(encoding="utf-8")
text = text.replace("from promptkit.lint import", "from promptkit import __version__\nfrom promptkit.lint import")
text = text.replace(
    '    commands = parser.add_subparsers(',
    '    parser.add_argument("--version", action="version", version=__version__)\n'
    '    commands = parser.add_subparsers(',
)
path.write_text(text, encoding="utf-8")
PY
       ;;
    4) python3 -B - <<'PY'
from pathlib import Path

for path in Path("prompts").glob("*.md"):
    path.write_text(path.read_text(encoding="utf-8").replace("recieve", "receive"), encoding="utf-8")
PY
       ;;
    6) python3 -B - <<'PY'
from pathlib import Path

init = Path("promptkit/__init__.py")
init.write_text(init.read_text(encoding="utf-8").replace("0.3.2", "0.4.0"), encoding="utf-8")
log = Path("CHANGELOG.md")
log.write_text(
    log.read_text(encoding="utf-8").replace(
        "## Unreleased\n",
        "## Unreleased\n\n## 0.4.0 - 2026-10-21\n\n"
        "- render: a placeholder with no value raises MissingVariable, which names it.\n"
        "- cli: `--version` prints the package version.\n"
        "- prompts: \"receive\" is spelled right.\n",
    ),
    encoding="utf-8",
)
PY
       ;;
  esac
done
