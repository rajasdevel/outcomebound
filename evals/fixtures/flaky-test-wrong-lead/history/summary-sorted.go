package report

import (
	"encoding/csv"
	"io"
	"sort"
	"strconv"
)

type accountSummary struct {
	account string
	total   int64
	count   int
}

// WriteSummary writes the summary of txs as CSV: the header account,total_cents,transactions,
// then one row for each account with its total in cents and its number of transactions.
// docs/format.md describes the file. It is the package's entry point: the command and the
// tests use it.
func WriteSummary(w io.Writer, txs []Tx) error {
	var rows []accountSummary
	for _, tx := range txs {
		i := sort.Search(len(rows), func(i int) bool { return rows[i].account >= tx.Account })
		if i == len(rows) || rows[i].account != tx.Account {
			rows = append(rows, accountSummary{})
			copy(rows[i+1:], rows[i:])
			rows[i] = accountSummary{account: tx.Account}
		}
		rows[i].total += tx.Cents
		rows[i].count++
	}
	out := csv.NewWriter(w)
	if err := out.Write([]string{"account", "total_cents", "transactions"}); err != nil {
		return err
	}
	for _, row := range rows {
		line := []string{row.account, strconv.FormatInt(row.total, 10), strconv.Itoa(row.count)}
		if err := out.Write(line); err != nil {
			return err
		}
	}
	out.Flush()
	return out.Error()
}
