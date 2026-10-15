"""Pack each kit under kits/ into OUT_DIR/<name>.zip, whose one entry is <name>/SKILL.md.

Usage: python3 scripts/build-kits.py OUT_DIR

The archives are deterministic: every entry carries the fixed date 1980-01-01 and the same
permissions, and the same source gives the same bytes. Standard library only.
"""

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KITS = ROOT / "kits"
EPOCH = (1980, 1, 1, 0, 0, 0)
MODE = 0o644 << 16


def build(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for folder in sorted(path for path in KITS.iterdir() if path.is_dir()):
        source = folder / "SKILL.md"
        if not source.is_file():
            raise FileNotFoundError(f"build-kits: {folder.name} has no SKILL.md")
        info = zipfile.ZipInfo(f"{folder.name}/SKILL.md", date_time=EPOCH)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = MODE
        archive = out_dir / f"{folder.name}.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr(info, source.read_bytes())
        written.append(archive)
    return written


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python3 scripts/build-kits.py OUT_DIR", file=sys.stderr)
        return 2
    for archive in build(Path(argv[1])):
        print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
