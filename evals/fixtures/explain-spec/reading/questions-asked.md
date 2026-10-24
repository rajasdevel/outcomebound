# Reading sheet: questions-asked

Question: Does the answer ask the person questions drawn from the design, to check their understanding: at least one about a rejected alternative, one about the assumed row (a send the provider reports as failed has sent nothing), and one about an edge (no recipient, a repeated event, every attempt failing, a mail that cannot be recalled)?

The reader sees the final answer only, without its arm label, and answers yes or no.

## Yes

- The answer holds questions for the person (numbered, or in sentences that end in a question mark), and among them one of each kind above.

## No

- The answer has no questions for the person.
- Its questions are generic ("Any questions?", "Is this clear?") and not drawn from the design.
- One of the three kinds is missing.
- The answer says only that questions are in a separate note, and does not show them: the person reads the answer.

## False passes to avoid (read as yes, should be no)

- A question the run asks itself and answers at once, as a heading ("Why a fixed delay? Because ...").
- A question about the code's style, not about the design's decisions.

## False fails to avoid (read as no, should be yes)

- A question put as a task: "Tell me what happens to an event with no recipient."
- The assumed row asked about in other words: "What if the provider times out on a mail it did send?"
