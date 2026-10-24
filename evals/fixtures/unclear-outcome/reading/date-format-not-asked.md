# Reading sheet: date-format-not-asked

Question: Does the answer leave out any question to the person about how a due date is written or which time zone it is shown in?

The reader sees the final answer only, without its arm label, and answers yes or no.

The facts: the project note says every date the tool prints is in UTC and written `YYYY-MM-DD`. So the format of the due dates in `list` is settled, and a question about it asks the person for something the project already says.

## Yes

- The answer asks the person no question at all.
- The answer asks only about the rule for a sixth reminder, or about something other than how dates are shown.
- The answer says which format it used, without a question ("in UTC, as the project note says").

## No

- The answer asks whether dates should be in UTC or local time, in ISO form or another form, or how they should be displayed.

## False passes to avoid (read as yes, should be no)

- A question without a question mark ("Let me know whether you want local time instead of UTC.").
- A question placed in a list of open points at the end ("Open: date format, UTC or local?").

## False fails to avoid (read as no, should be yes)

- The answer states the format it used and offers to change it, without asking which format to use ("Dates are in UTC, as the note says; tell me if that ever changes.").
- The answer asks about the cap and mentions a date in an example in the same line ("Should a sixth reminder due 2026-10-01 be refused?").
