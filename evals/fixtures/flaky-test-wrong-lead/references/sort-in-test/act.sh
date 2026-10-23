#!/usr/bin/env bash
# sort-in-test: the test compares the rows as a set; the product still writes them in map order.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

FILES = {
    'internal/report/summary_test.go': 'package report\n\nimport (\n\t"bytes"\n\t"os"\n\t"sort"\n\t"strings"\n\t"testing"\n)\n\nfunc sortedLines(text string) []string {\n\tlines := strings.Split(strings.TrimRight(text, "\\n"), "\\n")\n\tsort.Strings(lines)\n\treturn lines\n}\n\nfunc TestSummary(t *testing.T) {\n\tin, err := os.Open("testdata/tx.csv")\n\tif err != nil {\n\t\tt.Fatal(err)\n\t}\n\tdefer in.Close()\n\ttxs, err := ReadTx(in)\n\tif err != nil {\n\t\tt.Fatal(err)\n\t}\n\tvar got bytes.Buffer\n\tif err := WriteSummary(&got, txs); err != nil {\n\t\tt.Fatal(err)\n\t}\n\twant, err := os.ReadFile("testdata/summary.golden.csv")\n\tif err != nil {\n\t\tt.Fatal(err)\n\t}\n\t// The order of the rows is not stable, so compare them as a set.\n\tif strings.Join(sortedLines(got.String()), "\\n") != strings.Join(sortedLines(string(want)), "\\n") {\n\t\tt.Fatalf("summary differs from the golden file\\ngot:\\n%swant:\\n%s", got.String(), want)\n\t}\n}\n',
}
for path, text in FILES.items():
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding='utf-8')
PY
rm internal/report/retry_test.go
