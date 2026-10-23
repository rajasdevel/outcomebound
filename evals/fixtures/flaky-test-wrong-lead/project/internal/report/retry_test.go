package report

import "testing"

// retry runs check up to attempts times and fails the test only when every attempt fails.
func retry(t *testing.T, attempts int, check func() error) {
	t.Helper()
	var err error
	for i := 0; i < attempts; i++ {
		if err = check(); err == nil {
			return
		}
	}
	t.Fatalf("failed %d times in a row: %v", attempts, err)
}
