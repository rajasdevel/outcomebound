package report

import (
	"strings"
	"testing"
)

func TestReadTx(t *testing.T) {
	txs, err := ReadTx(strings.NewReader("date,account,amount_cents\n2026-10-01,acct-1,250\n"))
	if err != nil {
		t.Fatal(err)
	}
	if len(txs) != 1 || txs[0] != (Tx{Date: "2026-10-01", Account: "acct-1", Cents: 250}) {
		t.Fatalf("got %+v", txs)
	}
}

func TestReadTxRefusesAnotherHeader(t *testing.T) {
	if _, err := ReadTx(strings.NewReader("day,who,amount\n")); err == nil {
		t.Fatal("want an error for another header")
	}
}
