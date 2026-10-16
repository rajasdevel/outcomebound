#!/bin/sh
# The suite as CI's container job runs it: inside python:3.13-slim (root, no make, no ps) or
# python:3.13-alpine (busybox sh, musl), from the checkout in the current directory. CI runs this
# file, and `make test-containers` runs it in a copy of HEAD on a developer's machine, so the two
# cannot drift apart. Arguments go to pytest after the job's own; with none, the whole suite runs.
set -eu

case "${1:-}" in
    -h | --help)
        echo "usage: sh scripts/container-suite.sh [pytest arguments]"
        sed -n '2,5s/^# //p' "$0"
        exit 0
        ;;
esac

if ! command -v git >/dev/null 2>&1; then
    if command -v apk >/dev/null 2>&1; then
        apk add --no-cache git >/dev/null
    else
        apt-get update -qq && apt-get install -y -qq git >/dev/null
    fi
fi

# One retry: a connection reset while the development tools download is not a test result.
python -m pip install -q -r requirements-dev.txt || python -m pip install -q -r requirements-dev.txt

# The checkout belongs to another user than the container's root, and Git refuses such a
# repository as dubious ownership. The suite runs under a home of its own, which hides a
# `--global` setting, so the exception is made for the whole machine, in /etc/gitconfig. This is
# the job's own trust in its own checkout; the engine never makes it.
git config --system --add safe.directory "$(pwd)"

# A text read or write that names no encoding fails the suite (pytest.ini), here as on every
# platform: the default is UTF-8 here and the code page on Windows.
export PYTHONWARNDEFAULTENCODING=1
exec python -m pytest -o addopts="" -q -rfEs --tb=line -n auto -p no:cacheprovider "$@"
