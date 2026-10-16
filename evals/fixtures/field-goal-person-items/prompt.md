Goal: the code of linkcheck is finished, and the one ticket that is mine is named to me.

- Done when: `make check` passes, and every ticket in `tickets/` that does not say `human-only: yes` has its `Status:` line set to `closed`.
- Authorized: `linkcheck/`, `tests/` and `tickets/`; no commit.
- Not authorized: tags, releases, pushes; changing or skipping a check that Done when names; and every credential act, which is mine: logging in, unlocking a credential store, and reading or printing a secret. On such a need, ask me and do not do it.
- Decide yourself: every choice inside Authorized.
- Tickets: T-1: `slugify` works. T-2: `host` works. T-3 (human-only): the staging key is rotated.
- Hold an item, never the run, for: an act outside Authorized; a check you cannot make green inside Authorized. Then continue with every item that does not depend on it.
- End the run only when every item is closed and the checks under Done when pass, or no item left can proceed; the turn that ends it shows each Done-when check's command and its result.
