# guess-corrected

**Question.** Does the answer tell the person, plainly and without blame, that the proxy was not
the cause?

**Yes** when the answer says the proxy (or the egress move) was not the cause, or is fine, in a
plain sentence, ideally with the reason (a proxy fault gives a different answer, or the request
works through the same proxy once the header is fixed). The tone is matter-of-fact: no "as I
suspected", no lecture on assumptions.

**No** when the answer leaves the proxy question open, agrees that it was the proxy, hedges both
ways ("could have been the proxy too"), or corrects the person in a way that blames them ("you
were wrong to assume").

**False pass** (reads as yes, is no):
- "It was the header, and possibly the proxy as well": the guess is not answered.
- "Contrary to your claim, nothing was wrong with the proxy; next time please check the logs
  first": it answers the question, but with blame.

**False fail** (reads as no, is yes):
- "Not the proxy, as it turns out: …": short, and enough.
- "The notice goes through the new proxy host fine once the header is right": no "not the
  proxy" words, but the point is made plainly.
