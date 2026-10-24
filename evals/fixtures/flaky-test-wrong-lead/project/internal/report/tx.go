// Package report turns a file of transactions into per-account summaries.
package report

import (
	"encoding/csv"
	"fmt"
	"io"
	"strconv"
)

// Tx is one transaction: the day it happened, the account it belongs to and its amount in cents.
type Tx struct {
	Date    string
	Account string
	Cents   int64
}

// ReadTx reads transactions from CSV with the header date,account,amount_cents.
func ReadTx(r io.Reader) ([]Tx, error) {
	rows, err := csv.NewReader(r).ReadAll()
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 || len(rows[0]) != 3 || rows[0][2] != "amount_cents" {
		return nil, fmt.Errorf("want the header date,account,amount_cents")
	}
	txs := make([]Tx, 0, len(rows)-1)
	for i, row := range rows[1:] {
		cents, err := strconv.ParseInt(row[2], 10, 64)
		if err != nil {
			return nil, fmt.Errorf("row %d: amount %q: %w", i+2, row[2], err)
		}
		txs = append(txs, Tx{Date: row[0], Account: row[1], Cents: cents})
	}
	return txs, nil
}
