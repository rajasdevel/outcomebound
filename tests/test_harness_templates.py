"""The harness ask-rule examples parse, ask and never allow.

Each file is an example a project copies; `adopt` installs none of them. The syntax
follows the harness's own documentation, which `templates/harness/README.md` cites.
"""

import ast
import json
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent / "templates" / "harness"
PREFIX_RULE_KEYS = {"pattern", "decision", "justification", "match", "not_match"}


def test_claude_code_settings_only_ask():
    data = json.loads((HARNESS / "claude-code.settings.json").read_text(encoding="utf-8"))
    assert set(data) == {"permissions"}
    permissions = data["permissions"]
    assert set(permissions) == {"ask"}
    assert permissions["ask"]
    for rule in permissions["ask"]:
        assert rule.startswith("Bash(") and rule.endswith(")"), rule


def test_codex_rules_are_prompting_prefix_rules():
    tree = ast.parse((HARNESS / "codex.rules").read_text(encoding="utf-8"))
    assert tree.body
    for node in tree.body:
        assert isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        call = node.value
        assert isinstance(call.func, ast.Name) and call.func.id == "prefix_rule"
        assert not call.args
        keywords = {k.arg: ast.literal_eval(k.value) for k in call.keywords}
        assert set(keywords) <= PREFIX_RULE_KEYS
        pattern = keywords["pattern"]
        assert pattern and all(isinstance(word, str) and word for word in pattern)
        assert keywords["decision"] == "prompt"


def test_readme_states_the_coverage_limit_and_sources():
    text = (HARNESS / "README.md").read_text(encoding="utf-8")
    assert "script" in text and "never installs" in text
    assert "code.claude.com/docs/en/permissions" in text
    assert "learn.chatgpt.com/docs/agent-configuration/rules" in text
