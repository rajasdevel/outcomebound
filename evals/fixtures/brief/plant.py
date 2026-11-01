"""Copy this fixture's additions into a generated replica workspace."""

import shutil
import sys
from pathlib import Path

source = Path(sys.argv[1]) / "project"
for path in sorted(source.rglob("*")):
    if path.is_file():
        target = Path(str(path.relative_to(source)).removesuffix(".in"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
