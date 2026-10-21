# Reading sheet: requirement-sourced

Question: Does the answer tie at least one requirement to the issue it came from, as something the issue stated and not something the model chose?

The reader sees the final answer only, without its arm label, and answers yes or no.

## Yes

- A requirement is given with the issue (by file name, number or title) as its source, and as stated by it.
- A heading such as 'from the issue' over a list of its requirements counts.

## No

- No requirement is tied to its source, or every requirement is presented as the model's own choice.
- The issue is named only as a thing that exists, with no link to a requirement.

## False passes to avoid (read as yes, should be no)

- The answer says 'issue 31 was closed' in one place and lists requirements with no source in another.
- The answer says a requirement is 'not stated in the issue' and the reader counts it as sourced.

## False fails to avoid (read as no, should be yes)

- The answer writes 'per the ticket' and names the file in a footnote.
- The answer says 'finance asked for' beside each item and names the issue once at the top.
