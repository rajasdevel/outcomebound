"""Where this engine's own files are: `ROOT`, which `outcomebound home` prints.

Run from a checkout, the contract, templates, skills, fragments, schemas and adapters sit at the
checkout's root, beside this package. Installed as a package, the same tree ships inside it as
`_home/`, so a module that reads the engine's own files reads them from `ROOT` either way.

Standard library only, and no OutcomeBound import: every module that reads the engine's files
imports this one.
"""

from __future__ import annotations

from pathlib import Path

_PACKAGE = Path(__file__).resolve().parent
_BUNDLED = _PACKAGE / "_home"
# A checkout wins over a stray `_home/` inside it: only an installed package has no contract
# beside it.
_CHECKOUT = (_PACKAGE.parent / "OutcomeBound.md").is_file()
ROOT = _PACKAGE.parent if _CHECKOUT or not _BUNDLED.is_dir() else _BUNDLED
