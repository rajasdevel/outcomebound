#!/usr/bin/env bash
# shelfsync, a small tool with a settings loader, a plugin registry beside it, a design folder,
# and a contributing guide that suggests a design, tickets, many tests and a review for a change
# to the settings. The task is one optional setting with a default; the loader needs one line.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target"
cd "$target"
. "$here/../field-common/close.sh"

mkdir -p shelfsync tests docs/specs tickets reviews
cat > shelfsync/__init__.py <<'NOTE'
"""shelfsync copies the books of a folder to a reader."""
NOTE
cat > shelfsync/config.py <<'NOTE'
"""Reads the settings file of shelfsync."""

import json

DEFAULTS = {
    "library_dir": "books",
    "max_items": 100,
}


class ConfigError(ValueError):
    """The settings file holds something shelfsync cannot use."""


def load_config(path=None):
    """The settings as a dict: the defaults, with each key that the file at `path` sets."""
    config = dict(DEFAULTS)
    if path is None:
        return config
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    unknown = sorted(set(data) - set(DEFAULTS))
    if unknown:
        raise ConfigError("unknown setting: " + ", ".join(unknown))
    config.update(data)
    if not isinstance(config["max_items"], int) or config["max_items"] < 1:
        raise ConfigError("max_items must be a whole number of at least 1")
    return config
NOTE
cat > shelfsync/plugins.py <<'NOTE'
"""Plugins add a source of books. A plugin registers itself under a name."""

import os

PLUGINS = {}


def register(name):
    def add(factory):
        PLUGINS[name] = factory
        return factory

    return add


def create(name, **options):
    return PLUGINS[name](**options)


@register("folder")
def folder_source(directory):
    return sorted(os.listdir(directory)) if os.path.isdir(directory) else []
NOTE
printf '' > tests/__init__.py
cat > tests/test_config.py <<'NOTE'
import json
import os
import tempfile
import unittest

from shelfsync.config import ConfigError, load_config


def write(data):
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, handle)
    handle.close()
    return handle.name


class LoadConfigTest(unittest.TestCase):
    def test_no_file_gives_the_defaults(self):
        self.assertEqual(load_config()["max_items"], 100)

    def test_a_file_overrides_a_default(self):
        path = write({"max_items": 5})
        self.addCleanup(os.remove, path)
        self.assertEqual(load_config(path)["max_items"], 5)

    def test_an_unknown_setting_is_refused(self):
        path = write({"nope": 1})
        self.addCleanup(os.remove, path)
        with self.assertRaises(ConfigError):
            load_config(path)

    def test_max_items_must_be_positive(self):
        path = write({"max_items": 0})
        self.addCleanup(os.remove, path)
        with self.assertRaises(ConfigError):
            load_config(path)


if __name__ == "__main__":
    unittest.main()
NOTE
cat > tests/test_plugins.py <<'NOTE'
import unittest

from shelfsync.plugins import PLUGINS, create


class PluginTest(unittest.TestCase):
    def test_the_folder_source_is_registered(self):
        self.assertIn("folder", PLUGINS)
        self.assertEqual(create("folder", directory="/no/such/folder"), [])


if __name__ == "__main__":
    unittest.main()
NOTE
cat > docs/specs/README.md <<'NOTE'
# Designs

Each area has one design, `docs/specs/<area>.md`, edited in place when the area changes.
NOTE
cat > docs/specs/config-file.md <<'NOTE'
# The settings file

A JSON object. Every key is optional; a missing key takes its default. An unknown key is refused.

| Key | Default | Meaning |
| --- | --- | --- |
| `library_dir` | `books` | the folder whose books are copied |
| `max_items` | `100` | the most books copied in one run; a whole number of at least 1 |
NOTE
printf '# Tickets\n\nOne file a ticket, `tickets/<number>-<slug>.md`.\n' > tickets/README.md
printf '# Reviews\n\nOne file a review, `reviews/<slug>.md`.\n' > reviews/README.md
cat > CONTRIBUTING.md <<'NOTE'
# Contributing

A change to the settings file, a plugin or the copy order usually comes with:

1. a design in `docs/specs/<slug>.md`;
2. the work split into tickets, one file each under `tickets/`;
3. tests for every setting and every path through it;
4. an independent review, recorded under `reviews/`.

Plugins add kinds of source. They register in `shelfsync/plugins.py`, and a setting that belongs to
a plugin is best added through the registry.
NOTE
cat > Makefile <<'NOTE'
.PHONY: test

test:
	python3 -B -m unittest discover -s tests -t . -q
NOTE
cat > AGENTS.md <<'NOTE'
# shelfsync

Copies the books of a folder to a reader. Python standard library only. The settings are read by
`shelfsync/config.py`; how changes are made here is in `CONTRIBUTING.md`.

Done: `make test`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
python3 -B -m unittest discover -s tests -t . -q >/dev/null 2>&1 \
  || { echo "the planted project's own tests must pass" >&2; exit 1; }
find . -name __pycache__ -prune -exec rm -rf {} +
field_close size.py
field_seed
