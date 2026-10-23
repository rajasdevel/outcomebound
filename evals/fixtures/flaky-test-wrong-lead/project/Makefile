# The build cache stays in the checkout, so a sandbox that cannot write the home folder can build.
GOCACHE ?= $(CURDIR)/.cache/go-build
GOTOOLCHAIN ?= local
GOPROXY ?= off
export GOCACHE GOTOOLCHAIN GOPROXY

.PHONY: test build

test:
	go test ./...

build:
	go build -o widgets ./cmd/widgets
