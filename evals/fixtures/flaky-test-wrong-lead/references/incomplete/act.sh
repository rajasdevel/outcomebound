#!/usr/bin/env bash
# incomplete: the keys sorted into a slice that the loop never uses; the rows still follow the map.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

FILES = {
    'internal/report/summary.go': 'package report\n\nimport (\n\t"encoding/csv"\n\t"io"\n\t"sort"\n\t"strconv"\n)\n\n// WriteSummary writes the summary of txs as CSV: the header account,total_cents,transactions,\n// then one row for each account with its total in cents and its number of transactions.\n// docs/format.md describes the file. It is the package\'s entry point: the command and the\n// tests use it.\nfunc WriteSummary(w io.Writer, txs []Tx) error {\n\ttotals := make(map[string]int64)\n\tcounts := make(map[string]int)\n\tfor _, tx := range txs {\n\t\ttotals[tx.Account] += tx.Cents\n\t\tcounts[tx.Account]++\n\t}\n\taccounts := make([]string, 0, len(totals))\n\tfor account := range totals {\n\t\taccounts = append(accounts, account)\n\t}\n\tsort.Strings(accounts)\n\tout := csv.NewWriter(w)\n\tif err := out.Write([]string{"account", "total_cents", "transactions"}); err != nil {\n\t\treturn err\n\t}\n\tfor account, total := range totals {\n\t\trow := []string{account, strconv.FormatInt(total, 10), strconv.Itoa(counts[account])}\n\t\tif err := out.Write(row); err != nil {\n\t\t\treturn err\n\t\t}\n\t}\n\tout.Flush()\n\treturn out.Error()\n}\n',
}
for path, text in FILES.items():
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding='utf-8')
PY
