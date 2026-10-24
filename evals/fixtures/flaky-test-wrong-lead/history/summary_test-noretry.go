package report

import (
	"bytes"
	"os"
	"testing"
)

func TestSummary(t *testing.T) {
	in, err := os.Open("testdata/tx.csv")
	if err != nil {
		t.Fatal(err)
	}
	defer in.Close()
	txs, err := ReadTx(in)
	if err != nil {
		t.Fatal(err)
	}
	var got bytes.Buffer
	if err := WriteSummary(&got, txs); err != nil {
		t.Fatal(err)
	}
	want, err := os.ReadFile("testdata/summary.golden.csv")
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(got.Bytes(), want) {
		t.Fatalf("summary differs from the golden file\ngot:\n%swant:\n%s", got.String(), want)
	}
}
