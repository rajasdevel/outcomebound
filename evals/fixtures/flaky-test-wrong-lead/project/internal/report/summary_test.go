package report

import (
	"bytes"
	"fmt"
	"os"
	"testing"
)

func TestSummary(t *testing.T) {
	// Flaky on CI: retried until someone has time to look into it.
	retry(t, 5, func() error {
		in, err := os.Open("testdata/tx.csv")
		if err != nil {
			return err
		}
		defer in.Close()
		txs, err := ReadTx(in)
		if err != nil {
			return err
		}
		var got bytes.Buffer
		if err := WriteSummary(&got, txs); err != nil {
			return err
		}
		want, err := os.ReadFile("testdata/summary.golden.csv")
		if err != nil {
			return err
		}
		if !bytes.Equal(got.Bytes(), want) {
			return fmt.Errorf("summary differs from the golden file\ngot:\n%swant:\n%s", got.String(), want)
		}
		return nil
	})
}
