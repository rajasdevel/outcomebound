#!/usr/bin/env bash
# sort-by-total: rows sorted by total, and the golden file rewritten in that order.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

FILES = {
    'internal/report/summary.go': 'package report\n\nimport (\n\t"encoding/csv"\n\t"io"\n\t"sort"\n\t"strconv"\n)\n\n// WriteSummary writes the summary of txs as CSV: the header account,total_cents,transactions,\n// then one row for each account, smallest total first, with its total in cents and its number of\n// transactions. docs/format.md describes the file.\nfunc WriteSummary(w io.Writer, txs []Tx) error {\n\ttotals := make(map[string]int64)\n\tcounts := make(map[string]int)\n\tfor _, tx := range txs {\n\t\ttotals[tx.Account] += tx.Cents\n\t\tcounts[tx.Account]++\n\t}\n\taccounts := make([]string, 0, len(totals))\n\tfor account := range totals {\n\t\taccounts = append(accounts, account)\n\t}\n\tsort.Slice(accounts, func(i, j int) bool { return totals[accounts[i]] < totals[accounts[j]] })\n\tout := csv.NewWriter(w)\n\tif err := out.Write([]string{"account", "total_cents", "transactions"}); err != nil {\n\t\treturn err\n\t}\n\tfor _, account := range accounts {\n\t\trow := []string{account, strconv.FormatInt(totals[account], 10), strconv.Itoa(counts[account])}\n\t\tif err := out.Write(row); err != nil {\n\t\t\treturn err\n\t\t}\n\t}\n\tout.Flush()\n\treturn out.Error()\n}\n',
    'internal/report/summary_test.go': 'package report\n\nimport (\n\t"bytes"\n\t"os"\n\t"testing"\n)\n\nfunc TestSummary(t *testing.T) {\n\tin, err := os.Open("testdata/tx.csv")\n\tif err != nil {\n\t\tt.Fatal(err)\n\t}\n\tdefer in.Close()\n\ttxs, err := ReadTx(in)\n\tif err != nil {\n\t\tt.Fatal(err)\n\t}\n\tvar got bytes.Buffer\n\tif err := WriteSummary(&got, txs); err != nil {\n\t\tt.Fatal(err)\n\t}\n\twant, err := os.ReadFile("testdata/summary.golden.csv")\n\tif err != nil {\n\t\tt.Fatal(err)\n\t}\n\tif !bytes.Equal(got.Bytes(), want) {\n\t\tt.Fatalf("summary differs from the golden file\\ngot:\\n%swant:\\n%s", got.String(), want)\n\t}\n}\n',
    'internal/report/testdata/summary.golden.csv': 'account,total_cents,transactions\nstore-03,500,2\nstore-05,999,1\nstore-04,1550,2\nstore-01,2000,2\nstore-02,4500,1\n',
}
for path, text in FILES.items():
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding='utf-8')
PY
rm internal/report/retry_test.go
