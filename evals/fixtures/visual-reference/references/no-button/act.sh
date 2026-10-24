#!/usr/bin/env bash
# no-button: the card has the name, the price and the features, but no button: the button text in
# the design was read as part of the picture and left out. Its tests do not look for a button.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CARD_BUTTON=""
# shellcheck source=../write_card.sh
. "$here/../write_card.sh"
python3 -B -m unittest
