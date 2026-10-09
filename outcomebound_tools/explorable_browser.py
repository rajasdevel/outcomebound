"""Running an explorable in a headless Chromium-family browser, and reading what it printed.

What this module decides: which browser is used (`OUTCOMEBOUND_BROWSER` as a path first, then
`google-chrome`, `chromium`, `chromium-browser`, `msedge` and `brave` on PATH, then the install
folders of Chrome, Chromium, Edge and Brave on macOS and Windows); how it is started (headless,
a new profile folder, its own process group, `--dump-dom`, the page's `file://` address and the
`#explorable-check` fragment); that its output is read until the document ends, after which the
whole group is stopped and the profile folder removed; and how the check result in the printed
document is found.

What it does not decide: whether a result is a pass (`explorable_check`). A browser that is not
found, does not print the document in time, or prints no document reads as a reason, never as a
failure of the page.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast

from outcomebound_tools import programs

__all__ = ["BrowserRun", "find_browser", "parse_result", "run_page"]

ENVIRONMENT_VARIABLE = "OUTCOMEBOUND_BROWSER"
PROGRAMS = ("google-chrome", "chromium", "chromium-browser", "msedge", "brave")
MACOS_PATHS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
)
WINDOWS_PATHS = (
    r"Google\Chrome\Application\chrome.exe",
    r"Chromium\Application\chrome.exe",
    r"Microsoft\Edge\Application\msedge.exe",
    r"BraveSoftware\Brave-Browser\Application\brave.exe",
)
WINDOWS_ROOTS = ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
RESULT_ID = "explorable-check-result"
DOCUMENT_END = "</html>"
VIRTUAL_TIME_MS = 10000
REMOVE_TRIES = 5


def find_browser(
    environment: Mapping[str, str] | None = None,
    *,
    platform: str | None = None,
    is_file: Callable[[str], bool] = os.path.isfile,
) -> tuple[str | None, str]:
    """The browser to run, and a sentence saying where it came from or why none was found."""

    environment = os.environ if environment is None else environment
    platform = sys.platform if platform is None else platform
    named = environment.get(ENVIRONMENT_VARIABLE)
    if named:
        if is_file(named):
            return named, f"{ENVIRONMENT_VARIABLE}"
        return None, f"{ENVIRONMENT_VARIABLE} names {named!r}, which is not a file"
    for name in PROGRAMS:
        found = programs.find(name, environment, windows=platform == "win32")
        if found:
            return found, f"{name} on PATH"
    for candidate in _install_candidates(environment, platform):
        if is_file(candidate):
            return candidate, "an install folder"
    return None, "no Chromium-family browser found (a Firefox or Safari cannot print the document)"


def _install_candidates(environment: Mapping[str, str], platform: str) -> list[str]:
    """The install folders' browsers on macOS and Windows, in order."""

    if platform == "darwin":
        return list(MACOS_PATHS)
    if platform != "win32":
        return []
    roots = [environment[name] for name in WINDOWS_ROOTS if environment.get(name)]
    return [os.path.join(root, relative) for root in roots for relative in WINDOWS_PATHS]


@dataclass(frozen=True, slots=True)
class BrowserRun:
    """The document the browser printed, or None and the reason it did not."""

    document: str | None
    reason: str


def _command(browser: str, profile: str, address: str) -> list[str]:
    command = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        # Without these, Chrome on macOS waits on the login keychain for a new profile, about
        # thirty seconds where HOME is not the person's own (observed 2026-10-07).
        "--use-mock-keychain",
        "--password-store=basic",
        f"--user-data-dir={profile}",
        f"--virtual-time-budget={VIRTUAL_TIME_MS}",
    ]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        command.append("--no-sandbox")
    return [*command, "--dump-dom", address]


def _remove(folder: str) -> None:
    """Remove the profile folder, retrying where the filesystem still holds a file."""

    for attempt in range(REMOVE_TRIES):
        shutil.rmtree(folder, ignore_errors=True)
        if not os.path.exists(folder):
            return
        time.sleep(0.2 * (attempt + 1))


def _collect(
    process: subprocess.Popen[bytes], chunks: list[bytes], finished: threading.Event
) -> None:
    """Read the browser's output into `chunks` until the document ends or the pipe closes."""

    # `Popen` with `stdout=PIPE` and no text mode gives a buffered reader, whose `read1` returns
    # what has arrived without waiting for a full buffer.
    stream = cast("io.BufferedReader | None", process.stdout)
    tail = b""
    while stream is not None:
        data = stream.read1(65536)
        if not data:
            break
        chunks.append(data)
        tail = (tail + data)[-64:]
        if DOCUMENT_END.encode() in tail.lower():
            break
    finished.set()


def _wait(process: subprocess.Popen[bytes], finished: threading.Event, timeout: float) -> bool:
    """Whether the document ended, or the browser went, before the limit."""

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if finished.wait(0.1):
            return True
        if process.poll() is not None:
            # The browser is gone; a helper may still hold the pipe, so give the reader a moment.
            finished.wait(1.0)
            return True
    return False


def run_page(browser: str, page: Path, timeout: float) -> BrowserRun:
    """Run `page` with the check fragment and read the document the browser prints."""

    address = page.resolve().as_uri() + "#explorable-check"
    profile = tempfile.mkdtemp(prefix="explorable-profile-")
    chunks: list[bytes] = []
    finished = threading.Event()
    try:
        process = subprocess.Popen(
            _command(browser, profile, address),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            **programs.new_group(),
        )
    except OSError as error:
        _remove(profile)
        return BrowserRun(None, f"the browser could not start ({error})")
    programs.track_tree(process)
    reader = threading.Thread(target=_collect, args=(process, chunks, finished), daemon=True)
    reader.start()
    arrived = _wait(process, finished, timeout)
    programs.stop_tree(process)
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(10)
    reader.join(5)
    _remove(profile)
    text = b"".join(chunks).decode("utf-8", errors="replace")
    if DOCUMENT_END in text.lower():
        return BrowserRun(text, "")
    if not arrived:
        return BrowserRun(None, f"the browser printed no document within the {timeout:g} s limit")
    return BrowserRun(None, "the browser exited without printing the document")


class _ResultFinder(HTMLParser):
    """Each element whose id is the result's, and the text of the first one if it is a script."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.count = 0
        self.script = False
        self.text: list[str] = []
        self._collecting = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if dict(attrs).get("id") != RESULT_ID:
            return
        self.count += 1
        if self.count == 1 and tag == "script":
            self.script = True
            self._collecting = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._collecting = False

    def handle_data(self, data: str) -> None:
        if self._collecting:
            self.text.append(data)


def parse_result(document: str) -> tuple[dict[str, Any] | None, str]:
    """The check result in a printed document, or None and why it is not there. The document
    must hold exactly one element with the result's id, so that a second one in the page's
    content cannot stand in for the runtime's."""

    finder = _ResultFinder()
    finder.feed(document)
    finder.close()
    if finder.count == 0:
        return None, "the page wrote no check result"
    if finder.count > 1:
        return None, f"the document holds {finder.count} elements with the id {RESULT_ID}, not one"
    if not finder.script:
        return None, "the check result element is not a script element"
    try:
        result = json.loads("".join(finder.text))
    except json.JSONDecodeError:
        return None, "the check result is not JSON"
    if not isinstance(result, dict) or result.get("done") is not True:
        return None, "the check result is not complete (`done` is not true)"
    return result, ""
