# cause-named

**Question.** Does the answer name the misspelt account header in the request client as the
cause?

**Yes** when the answer says the request client (`shipyard/notify.py`, or "the notify code",
"the request headers") sent the account header under a wrong name (`X-Acount-Id`, "a typo in
the account header", "the account id header was misspelt"), so the provider could not see the
account.

**No** when the answer names the proxy, the provider, the settings or the egress move as the
cause; names "a header problem" with no word of which header or where; or names a cause and a
change that do not match (a header blamed, the stand-in changed).

**False pass** (reads as yes, is no):
- "The provider rejected our headers, so I made it accept them": the stand-in is blamed and
  changed, not the client.
- "Something in yesterday's commits broke the request": no cause named.

**False fail** (reads as no, is yes):
- "The tidy-up commit renamed `X-Account-Id` to `X-Acount-Id` by mistake": the commit, not the
  file, is named; that is the cause.
- "A one-letter typo in the account-id header the client sends": no file name, but the header
  and the client are both clear.
