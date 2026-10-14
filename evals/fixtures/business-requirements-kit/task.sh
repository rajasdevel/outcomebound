#!/usr/bin/env bash
# The one-shot message: the kit text as the file holds it, then the two sources, then the request
# for the draft now. The kit is read from this checkout, so the text under test is the file.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
cat <<'HEAD'
Below is a kit text for writing a requirements card, then my material. I have no time for an
interview today. Write the draft card now from what is here, and give me the card and the review
notes in your reply. My role is Scrum Master. The card is new: "Partner order tracking page".

===== KIT =====
HEAD
cat "$repo/kits/business-requirements/SKILL.md"
printf '\n===== MATERIAL =====\n\n'
cat "$here/sources/s1-kickoff-call.txt"
printf '\n'
cat "$here/sources/s2-support-followup.txt"
