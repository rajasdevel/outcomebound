#!/usr/bin/env bash
# word-characters: the pattern \W+ keeps the underscore, which is not a letter or a digit.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../slug.sh"
write_slug '\W+'
add_slug_tests
unit_tests
