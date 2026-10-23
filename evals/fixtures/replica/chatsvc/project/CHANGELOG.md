# Changelog

## 1.8.0 (unreleased)

- Added: `envctl promote` ships what one environment serves to the other.
- Changed: the docs check also reads every route of `config/chatsvc.ini`.

## 1.7.0 (2026-10-08)

- Fixed: long answers stopped at 1,024 tokens; the output buffer now follows `max_tokens`
  (`truncated-answer`).
- Added: `python3 -m chatsvc.feedback summary --by-conversation`.

## 1.6.1 (2026-09-24)

- Fixed: embedding requests over 16 inputs were refused by the provider; they are split into
  batches.

## 1.6.0 (2026-09-10)

- Added: answers stream to the widget as they are generated.
- Added: feedback labels, set by triage.

## 1.5.1 (2026-08-20)

- Fixed: sign-in on mobile returned to the sign-in page (`login-loop`).

## 1.5.0 (2026-08-01)

- Added: the embeddings route, `/v1/embed`.

## 1.4.0 (2026-07-10)

- Changed: provider calls use pooled keys, with retries that wait as the provider asks.
