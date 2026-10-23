package report

import (
	"encoding/csv"
	"io"
	"strconv"
)

// WriteSummary writes the summary of txs as CSV: the header account,total_cents,transactions,
// then one row for each account with its total in cents and its number of transactions.
// docs/format.md describes the file. It is the package's entry point: the command and the
// tests use it.
func WriteSummary(w io.Writer, txs []Tx) error {
	totals := make(map[string]int64)
	counts := make(map[string]int)
	for _, tx := range txs {
		totals[tx.Account] += tx.Cents
		counts[tx.Account]++
	}
	out := csv.NewWriter(w)
	if err := out.Write([]string{"account", "total_cents", "transactions"}); err != nil {
		return err
	}
	for account, total := range totals {
		row := []string{account, strconv.FormatInt(total, 10), strconv.Itoa(counts[account])}
		if err := out.Write(row); err != nil {
			return err
		}
	}
	out.Flush()
	return out.Error()
}
