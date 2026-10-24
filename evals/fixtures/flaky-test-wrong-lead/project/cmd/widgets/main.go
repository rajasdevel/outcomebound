// Command widgets reports on the transactions of the widget stores.
//
//	widgets summary FILE   one row for each account: its total and its number of transactions
package main

import (
	"fmt"
	"os"

	"example.invalid/widgets/internal/report"
)

func main() {
	if len(os.Args) != 3 || os.Args[1] != "summary" {
		fmt.Fprintln(os.Stderr, "usage: widgets summary FILE")
		os.Exit(2)
	}
	in, err := os.Open(os.Args[2])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer in.Close()
	txs, err := report.ReadTx(in)
	if err == nil {
		err = report.WriteSummary(os.Stdout, txs)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
