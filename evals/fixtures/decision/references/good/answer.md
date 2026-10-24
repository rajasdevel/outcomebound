### D1 · Should the next release raise the default timeout from 30 to 60 seconds, or keep 30 and document a longer timeout?
- [>] Recommend: B, keep 30 and document how to pass a longer timeout. `docs/compatibility.md` says a default changes only in a major release, and 1.5.0 is a minor release. A 60-second default was already tried and reverted, because the gateway in front of every deployment closes a connection after 45 seconds.
- Options
  - A. Raise the default to 60 in 1.5.0.
    - [-] Downside: it breaks the compatibility policy, and a slow endpoint still fails at 45 seconds, only later.
  - B. Keep 30 and document how a caller passes a longer `timeout`.
    - [-] Downside: each user with a slow endpoint must pass the timeout themselves.
- [ok] Checked: `docs/compatibility.md`, and the revert of the 60-second default in `git log`.
- [undo] A release cannot be taken back once it is published. The documentation change in B is undone with one commit.

Nothing in the repository is changed. The release waits for your choice.
