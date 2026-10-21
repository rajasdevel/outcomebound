# Feedback

The answer widget lets a person rate an answer up or down and leave a comment. Each submission
is one line of `data/feedback.jsonl` ([store spec](specs/feedback-store.md)):

| Field | |
| --- | --- |
| `id` | the submission's id |
| `conversation_id` | the conversation rated |
| `created` | when, UTC |
| `release` | the chatsvc release that answered |
| `rating` | `up` or `down` |
| `label` | the issue triage filed it under, or null while untriaged |
| `channel` | `web` or `mobile` |
| `comment` | what the person wrote, possibly empty |

## Counting

A person can rate the same conversation again (the widget lets them change their rating), so
one conversation can have several submissions. The latest submission of a conversation is the
one that counts: a conversation rated down and later up is not a complaint any more, and one
rated down twice is one complaint.

## Reading it

    python3 -m chatsvc.feedback releases                    # submissions by release
    python3 -m chatsvc.feedback list --since 1.6.0 --rating down
    python3 -m chatsvc.feedback summary --since 1.6.0       # down ratings by label, per submission
    python3 -m chatsvc.feedback summary --since 1.6.0 --by-conversation

`--since` includes the release it names. `summary` counts submissions unless
`--by-conversation` is given.

## Labels

Triage labels each down rating with the issue it reports. The labels in use:

- `slow-first-token`: the first words of the answer take long to appear.
- `truncated-answer`: the answer stops partway.
- `wrong-language`: the answer is in another language than the question.
- `citation-missing`: the answer cites no source where one was asked for.
- `login-loop`: sign-in on mobile returns to the sign-in page.

A fix names its label in the changelog entry, so the status of an issue can be read from
[CHANGELOG.md](../CHANGELOG.md).
