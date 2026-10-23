package report

// Added by the grader to a scratch copy of the workspace, never to the workspace itself: the
// summary of 25 accounts must come out in account order, and the same on every call.

import (
	"bytes"
	"fmt"
	"sort"
	"strings"
	"testing"
)

func TestGradedSummaryOrderIsStable(t *testing.T) {
	var txs []Tx
	for i := 0; i < 25; i++ {
		txs = append(txs, Tx{Date: "2026-10-01", Account: fmt.Sprintf("acct-%02d", 24-i), Cents: int64(i)})
	}
	var first bytes.Buffer
	if err := WriteSummary(&first, txs); err != nil {
		t.Fatal(err)
	}
	rows := strings.Split(strings.TrimRight(first.String(), "\n"), "\n")
	if len(rows) != 26 || !sort.StringsAreSorted(rows[1:]) {
		t.Fatalf("the rows are not one per account in account order:\n%s", first.String())
	}
	for i := 0; i < 50; i++ {
		var again bytes.Buffer
		if err := WriteSummary(&again, txs); err != nil {
			t.Fatal(err)
		}
		if again.String() != first.String() {
			t.Fatalf("call %d gave another summary:\n%s\nthan the first:\n%s", i+2, again.String(), first.String())
		}
	}
}
