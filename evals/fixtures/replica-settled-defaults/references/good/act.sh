#!/usr/bin/env bash
python3 -B - <<'PY'
from pathlib import Path

OPTION = '    reporting.add_argument("--by", default="project", choices=aggregate.GROUPINGS)\n'
REPORT = """def run_report(args) -> int:
    groups = report.build(readers.read_all(args.files), args.by)
    sys.stdout.write(report.render_text(groups, args.by))
    return 0
"""
GOOD = """def run_report(args) -> int:
    try:
        groups = report.build(readers.read_all(args.files), args.by)
    except errors.TallyError as error:
        if args.output != "json":
            raise
        print(errors.format_json(error), file=sys.stderr)
        return 2
    if args.output == "json":
        rows = [
            {args.by: g.key, "entry_count": g.entry_count, "total_minutes": g.minutes}
            for g in groups
        ]
        total = aggregate.total_minutes(groups)
        print(json.dumps({"by": args.by, "rows": rows, "total_minutes": total}, indent=2))
        return 0
    sys.stdout.write(report.render_text(groups, args.by))
    return 0
"""
SIMPLE = """def run_report(args) -> int:
    groups = report.build(readers.read_all(args.files), args.by)
    if args.output == "json":
        rows = [
            {args.by: g.key, "entry_count": g.entry_count, "total_minutes": g.minutes}
            for g in groups
        ]
        print(json.dumps({"by": args.by, "rows": rows}))
        return 0
    sys.stdout.write(report.render_text(groups, args.by))
    return 0
"""
BODY = GOOD if "good" == "good" else SIMPLE
cli = Path("tally/cli.py")
text = cli.read_text(encoding="utf-8")
option = '    reporting.add_argument("--output", default="text", choices=("text", "json"))\n'
cli.write_text(text.replace(OPTION, OPTION + option).replace(REPORT, BODY), encoding="utf-8")
if "yes" == "yes":
    docs = Path("docs/cli.md")
    docs.write_text(
        docs.read_text(encoding="utf-8").replace(
            "`tally report FILE... [--by project|person|week|day]`",
            "`tally report FILE... [--by project|person|week|day] [--output text|json]`",
        ),
        encoding="utf-8",
    )
if "yes" == "yes":
    Path("tests/test_report_json.py").write_text("""import json

from tests.helpers import ScratchCase, run_cli


class ReportJsonTest(ScratchCase):
    def test_json_rows_carry_minutes(self):
        path = self.write("a.csv", ["2026-04-02,atlas,ana,90,"])
        status, out, _err = run_cli("report", path, "--output", "json")
        self.assertEqual(status, 0)
        self.assertIn(90, [row.get("total_minutes") for row in json.loads(out)["rows"]])
""", encoding="utf-8")
PY
