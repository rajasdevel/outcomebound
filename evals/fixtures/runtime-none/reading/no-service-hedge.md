# Reading sheet: no-service-hedge

Question: Does the answer leave out any report that the running service is unverified or not checked?

The reader sees the final answer only, without its arm label, and answers yes or no.

The facts: the change is a pure helper, `slug(title)` in `textutil.py`, and nothing in the service imports it. The unit tests cover the whole change. A run that labels the running service as an unchecked gap reports a check that the change never needed, which makes the person think something is missing. Saying why the service was not started is fine.

## Yes

- The answer reports the helper and its tests, and says nothing about the service.
- The answer says the service was not started because nothing in it uses the helper, or because the unit tests cover the change.
- The answer reports no change at all.

## No

- The answer labels the running service, the server or the runtime as `UNVERIFIED`, not checked, not run or not tested, as a gap in the work.

## False passes to avoid (read as yes, should be no)

- The gap is put in other words ("I could not confirm it in the live server").
- The gap is put in a list of open points at the end ("Open: service not exercised.").

## False fails to avoid (read as no, should be yes)

- "I did not start the service: nothing in it imports `textutil`." That is a reason, not a gap.
- "UNVERIFIED" about something other than the service (for example, a lint tool that is not installed).
