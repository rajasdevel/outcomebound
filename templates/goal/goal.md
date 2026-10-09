# Goal: <what is observably true when this is done, and for whom>

> For you, the person, and not pasted: delete this note, then paste all the lines that are left as
> one block, as the run's first message (the `/goal` text where the harness has one), never a path
> to a file that holds it. Some harnesses, and the reviewers that approve a run's requests, honor
> authority only from the person's own messages. Keep what is for you, such as how to start the
> run, outside that block.

- Done when: <the checks that end it, such as every accepted item closed and the project's checks green at the default branch's tip>.
- Authorized: <paths>; commit; <push to the default branch once those checks pass, per ticket or per batch of tickets; unstated, per ticket>; <tracker acts>; <model or eval runs, and the operator's cap on them only if they set one>.
- Not authorized: <such as tags, releases, other repositories, force pushes>; changing, skipping or deleting a check that Done when names, to make it pass; and every credential act, which is the person's: unlocking a keychain or other credential store, adding a key to an SSH agent, logging in, and reading or printing a secret. On such a need, ask the person and do not do it.
- Decide yourself: every choice inside Authorized, one line each in its commit message.
- Decisions: <id: answer, or none>. The run starts without answers: an item whose brief is unanswered does every part the answer does not decide and stays open with the brief named; every other item proceeds.
- Tickets: <none, or one line per accepted ticket: its number and its outcome in one sentence, so that this block is the breakdown the person accepts>.
- Order: <none, or the order the items are built in, such as the tracker's blocked-by order>.
- Follow-ups: <none, or: issues you file, with `discovered-from`, for work an accepted item or the Done when checks need, inside Authorized, are accepted by this envelope; build one before the item it unblocks, else after the accepted items>.
- Hold an item, never the run, for: an act outside Authorized<; a judgment the person reserved>; a check you cannot make green inside Authorized. Record the hold when it starts, on that item and under Progress, and not again on a later turn, with the output, what you tried and what would settle it; where the person decides, name the brief by its id there and put the brief itself in the handoff. Then continue with every item that does not depend on it.
- A continuation turn does not ask a held question again; when only held items are left, it ends that turn with the goal unchanged, and an answer the person gives later resumes the items that wait on it.
- Keep this goal's objective as the person wrote it: never replace it with your own text.
- End the run only when every item is closed and the checks under Done when pass, or no item left can proceed; the turn that ends it shows each Done-when check's command and its result, since a harness may judge the goal from the transcript alone.
- Handoff: <path, such as `.agents/handoffs/<date>-<task>.md` where the workspace fragment is installed>, kept current as the run goes: the next step first; what landed, each check's verdict, each held item and why, and only the decisions this goal left the person, as decision briefs; as long as it needs.

## Progress

- <date>: landed … · next … · blocked on …
