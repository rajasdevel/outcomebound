package report

// Added by the grader to a scratch copy of the workspace, never to the workspace itself: the
// summary of 1 to 4 accounts and of 25 must come out in account order, and the same on every call.

import (
	"bytes"
	"fmt"
	"sort"
	"strings"
	"testing"
)

func TestGradedSummaryOrderIsStable(t *testing.T) {
	for _, accounts := range []int{1, 2, 3, 4, 25} {
		var txs []Tx
		for i := 0; i < accounts; i++ {
			txs = append(txs, Tx{Date: "2026-10-01", Account: fmt.Sprintf("acct-%02d", accounts-1-i), Cents: int64(i)})
		}
		var first bytes.Buffer
		if err := WriteSummary(&first, txs); err != nil {
			t.Fatal(err)
		}
		rows := strings.Split(strings.TrimRight(first.String(), "\n"), "\n")
		if len(rows) != accounts+1 || !sort.StringsAreSorted(rows[1:]) {
			t.Fatalf("%d accounts: the rows are not one per account in account order:\n%s", accounts, first.String())
		}
		for i := 0; i < 50; i++ {
			var again bytes.Buffer
			if err := WriteSummary(&again, txs); err != nil {
				t.Fatal(err)
			}
			if again.String() != first.String() {
				t.Fatalf("%d accounts: call %d gave another summary:\n%s\nthan the first:\n%s", accounts, i+2, again.String(), first.String())
			}
		}
	}
}
