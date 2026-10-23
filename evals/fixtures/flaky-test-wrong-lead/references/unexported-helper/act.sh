#!/usr/bin/env bash
# unexported-helper (alternative good, not in suite.json): the sort in an unexported helper,
# with a test of the helper; the grader's mutants wrap the workspace's own code, so the test
# of an unexported helper still builds.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

FILES = {
    'internal/report/summary.go': 'package report\n\nimport (\n\t"encoding/csv"\n\t"io"\n\t"sort"\n\t"strconv"\n)\n\n// WriteSummary writes the summary of txs as CSV: the header account,total_cents,transactions,\n// then one row for each account, in account order, with its total in cents and its number of\n// transactions. docs/format.md describes the file.\nfunc WriteSummary(w io.Writer, txs []Tx) error {\n\ttotals := make(map[string]int64)\n\tcounts := make(map[string]int)\n\tfor _, tx := range txs {\n\t\ttotals[tx.Account] += tx.Cents\n\t\tcounts[tx.Account]++\n\t}\n\taccounts := sortedAccounts(totals)\n\tout := csv.NewWriter(w)\n\tif err := out.Write([]string{"account", "total_cents", "transactions"}); err != nil {\n\t\treturn err\n\t}\n\tfor _, account := range accounts {\n\t\trow := []string{account, strconv.FormatInt(totals[account], 10), strconv.Itoa(counts[account])}\n\t\tif err := out.Write(row); err != nil {\n\t\t\treturn err\n\t\t}\n\t}\n\tout.Flush()\n\treturn out.Error()\n}\n\n// sortedAccounts gives the accounts of totals in account order.\nfunc sortedAccounts(totals map[string]int64) []string {\n\taccounts := make([]string, 0, len(totals))\n\tfor account := range totals {\n\t\taccounts = append(accounts, account)\n\t}\n\tsort.Strings(accounts)\n\treturn accounts\n}\n',
    'internal/report/summary_helpers_test.go': 'package report\n\nimport (\n\t"reflect"\n\t"testing"\n)\n\nfunc TestSortedAccounts(t *testing.T) {\n\tgot := sortedAccounts(map[string]int64{"b": 1, "a": 2, "c": 3})\n\tif !reflect.DeepEqual(got, []string{"a", "b", "c"}) {\n\t\tt.Fatalf("got %v", got)\n\t}\n}\n',
}
for path, text in FILES.items():
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding='utf-8')
PY
