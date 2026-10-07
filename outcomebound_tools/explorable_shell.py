"""The explorable's shell: the engine's own parts of a page, joined to a source, and read again.

What this module decides: where the shell's parts come from (`templates/explorable/`: the frame
`shell.html`, the stylesheet, the runtime and the library pins `libraries.json`); how a page is
joined from them and a source (every shell value escaped, the stylesheet and the runtime inlined
byte for byte); the Content-Security-Policy the pins make; the page's configuration; and how a
page is matched against the frame again, so that `check` can say which shell part differs.

What it does not decide: what a source holds (`explorable_source`), how a brief is drawn
(`decision_brief_html`), or what a verdict reads (`explorable_check`).
"""

from __future__ import annotations

import html
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from outcomebound_tools import home, textio

__all__ = [
    "GENERATOR",
    "KIND_LABELS",
    "Parts",
    "ShellError",
    "build_page",
    "built_time",
    "differences",
    "engine_version",
    "library_config",
    "match",
    "policy",
    "template",
]

TEMPLATES = home.ROOT / "templates" / "explorable"
GENERATOR = "outcomebound explorable"
KIND_LABELS = {
    "decision": "Decision explorable",
    "learning": "Learning explorable",
    "interview": "Interview explorable",
}
_SLOT = re.compile(r"\{(\w+)\}")
_BUILT = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
_BRIEFS = '<section class="xp-briefs" id="explorable-briefs".*?</section>'
_ID = re.compile(r"[a-z][a-z0-9-]*")


class ShellError(ValueError):
    """The engine's own shell cannot be read or used: a fault in the engine, not in a source."""


def template(name: str) -> str:
    """One of the engine's templates as text, UTF-8, LF line ends."""

    try:
        return textio.read_text(TEMPLATES / name)
    except (OSError, UnicodeDecodeError) as error:
        raise ShellError(
            f"the template templates/explorable/{name} cannot be read: {error}"
        ) from error


def libraries() -> dict[str, dict[str, Any]]:
    """The pins, from `libraries.json`."""

    try:
        pins = json.loads(template("libraries.json"))
    except json.JSONDecodeError as error:
        raise ShellError(f"templates/explorable/libraries.json is not JSON: {error}") from error
    return dict(pins)


def library_config(pins: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """The pins as the page's configuration holds them: each without its package and version."""

    pins = libraries() if pins is None else pins
    return {
        name: {key: value for key, value in pin.items() if key not in ("package", "version")}
        for name, pin in pins.items()
    }


def policy(pins: Mapping[str, Mapping[str, Any]] | None = None) -> str:
    """The Content-Security-Policy: nothing loads but inline script and style, `data:` and
    `blob:` images, `data:` fonts, and scripts from each pin's own package path."""

    pins = libraries() if pins is None else pins
    paths = " ".join(
        f"https://cdn.jsdelivr.net/npm/{pin['package']}@{pin['version']}/" for pin in pins.values()
    )
    return (
        f"default-src 'none'; script-src 'unsafe-inline' {paths}; style-src 'unsafe-inline'; "
        "img-src data: blob:; font-src data:; form-action 'none'; base-uri 'none'"
    )


def pin_paths(pins: Mapping[str, Mapping[str, Any]] | None = None) -> list[str]:
    """Each package path the policy lets a script load from."""

    pins = libraries() if pins is None else pins
    return [
        f"https://cdn.jsdelivr.net/npm/{pin['package']}@{pin['version']}/" for pin in pins.values()
    ]


def engine_version() -> str:
    """The engine's version, from `VERSION`, or `unknown`."""

    try:
        return (home.ROOT / "VERSION").read_text(encoding="utf-8").strip() or "unknown"
    except (OSError, UnicodeDecodeError):
        return "unknown"


def built_time(environment: Mapping[str, str] | None = None) -> str:
    """The build time in UTC: from `SOURCE_DATE_EPOCH` where it is set, else now. Raises
    `ShellError` for an epoch that is not whole seconds."""

    environment = os.environ if environment is None else environment
    given = environment.get("SOURCE_DATE_EPOCH")
    if given is None or given == "":
        moment = datetime.now(timezone.utc)
    else:
        try:
            moment = datetime.fromtimestamp(int(given), timezone.utc)
        except (ValueError, OverflowError, OSError) as error:
            raise ShellError(f"SOURCE_DATE_EPOCH {given!r} is not whole seconds") from error
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def escape(text: str) -> str:
    """`text` for an element's content or a double-quoted attribute value."""

    return html.escape(text, quote=False).replace('"', "&quot;")


def _json(document: Mapping[str, Any]) -> str:
    """`document` as JSON for a script element: every `<` is escaped, so no text in it can end,
    hide or open an element, and the config never holds what `check` refuses there."""

    return json.dumps(document, ensure_ascii=False).replace("<", "\\u003c")


def build_page(
    header: Mapping[str, Any],
    content: str,
    briefs_html: str,
    briefs: list[dict[str, Any]],
    built: str,
) -> str:
    """The page: the shell with the header's values, the briefs' drawing and the content in its
    slots. The stylesheet and the runtime go in byte for byte."""

    stylesheet, runtime = template("explorable.css"), template("explorable.js")
    if "</style" in stylesheet.lower() or "</script" in runtime.lower():
        raise ShellError(
            "the shared stylesheet or runtime holds a closing tag, which ends its element"
        )
    version = engine_version()
    config = {
        "id": header["id"],
        "kind": header["kind"],
        "title": header["title"],
        "built": built,
        "generator": f"{GENERATOR} {version}",
        "libraries": library_config(),
        "briefs": briefs,
    }
    values = {
        "policy": escape(policy()),
        "version": escape(version),
        "kind": escape(header["kind"]),
        "kind_label": KIND_LABELS[header["kind"]],
        "title": escape(header["title"]),
        "stylesheet": stylesheet,
        "config": _json(config),
        "runtime": runtime,
        "built": built,
        "briefs": briefs_html,
        "content": content,
    }
    return _SLOT.sub(lambda found: values[found.group(1)], template("shell.html"))


@dataclass(frozen=True, slots=True)
class Parts:
    """What a page holds in each slot of the shell, each occurrence of a slot in order, and the
    line its briefs and content start on."""

    values: dict[str, list[str]]
    region_line: int

    @property
    def briefs(self) -> str:
        return self.values["briefs"][0]

    @property
    def content(self) -> str:
        return self.values["content"][0]


def _pattern() -> tuple[re.Pattern[str], list[tuple[str, str]]]:
    """The shell as a regular expression: its text exact, each slot a group, named in order."""

    shell = template("shell.html")
    pieces: list[str] = []
    groups: list[tuple[str, str]] = []
    last = 0
    for found in _SLOT.finditer(shell):
        pieces.append(re.escape(shell[last : found.start()]))
        slot = found.group(1)
        name = f"g{len(groups)}"
        groups.append((name, slot))
        body = f"(?:{_BRIEFS})?" if slot == "briefs" else ".*?"
        pieces.append(f"(?P<{name}>{body})")
        last = found.end()
    pieces.append(re.escape(shell[last:]))
    return re.compile(r"\A" + "".join(pieces) + r"\Z", re.DOTALL), groups


def match(page: str) -> Parts | None:
    """The page's slots, or None where the page does not hold the shell's frame."""

    pattern, groups = _pattern()
    found = pattern.match(page)
    if found is None:
        return None
    values: dict[str, list[str]] = {}
    for name, slot in groups:
        values.setdefault(slot, []).append(found.group(name))
    first = next(name for name, slot in groups if slot == "briefs")
    return Parts(values, page.count("\n", 0, found.start(first)) + 1)


def _same(parts: Parts, slot: str, problems: list[str]) -> str:
    """The one value a repeated slot holds; a defect where its places disagree."""

    seen = parts.values[slot]
    if len(set(seen)) > 1:
        problems.append(f"the {slot} is not the same everywhere the shell puts it")
    return seen[0]


def _config(parts: Parts, problems: list[str]) -> Mapping[str, Any]:
    try:
        config = json.loads(parts.values["config"][0])
    except json.JSONDecodeError:
        problems.append("the configuration is not JSON")
        return {}
    if not isinstance(config, dict):
        problems.append("the configuration is not an object")
        return {}
    return config


def differences(parts: Parts) -> list[str]:
    """Each way the page's shell parts differ from the engine's, as a short phrase."""

    problems: list[str] = []
    if html.unescape(parts.values["policy"][0]) != policy():
        problems.append("the Content-Security-Policy differs from the one the pins make")
    if parts.values["stylesheet"][0] != template("explorable.css"):
        problems.append("the stylesheet differs from the engine's explorable.css")
    if parts.values["runtime"][0] != template("explorable.js"):
        problems.append("the runtime differs from the engine's explorable.js")
    config = _config(parts, problems)
    if re.search(r"<!--|</|<script", parts.values["config"][0], re.IGNORECASE):
        problems.append("the configuration holds markup that can end or hide its element")
    if config.get("libraries") != library_config():
        problems.append("the library pins differ from the engine's libraries.json")
    _identity(parts, config, problems)
    return problems


def _identity(parts: Parts, config: Mapping[str, Any], problems: list[str]) -> None:
    """The kind, title, build time, generator and id, which the page holds in several places."""

    kind = html.unescape(_same(parts, "kind", problems))
    title = html.unescape(_same(parts, "title", problems))
    built = _same(parts, "built", problems)
    version = parts.values["version"][0]
    if kind not in KIND_LABELS or config.get("kind") != kind:
        problems.append("the kind is not one of the three, or differs between the page's places")
    elif parts.values["kind_label"][0] != KIND_LABELS[kind]:
        problems.append("the kind's label differs from the engine's")
    if config.get("title") != title:
        problems.append("the title differs between the page and its configuration")
    if not _BUILT.fullmatch(built) or config.get("built") != built:
        problems.append("the build time is malformed or differs from the configuration's")
    if (
        not re.fullmatch(r"[A-Za-z0-9.+-]+", version)
        or config.get("generator") != f"{GENERATOR} {version}"
    ):
        problems.append("the generator is not `outcomebound explorable <version>`")
    if not isinstance(config.get("id"), str) or not _ID.fullmatch(config["id"]):
        problems.append("the page's id is missing or malformed")
    if not isinstance(config.get("briefs"), list):
        problems.append("the configuration holds no list of briefs")
    _markup(parts, problems)


def _markup(parts: Parts, problems: list[str]) -> None:
    markup = [
        slot
        for slot in ("policy", "version", "kind", "title", "built")
        if any("<" in v for v in parts.values[slot])
    ]
    if markup:
        problems.append(f"markup in the shell's {', '.join(markup)}")
