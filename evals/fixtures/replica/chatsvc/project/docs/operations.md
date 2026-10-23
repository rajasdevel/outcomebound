# Operations: stage and prod

chatsvc runs in two environments, `stage` and `prod`. `bin/envctl` operates both:

| Command | Does | Changes the environment |
| --- | --- | --- |
| `bin/envctl status <env>` | prints the revision and version the environment serves | no |
| `bin/envctl health <env>` | calls the environment's health endpoint | no |
| `bin/envctl smoke <env>` | sends one chat request through the environment and prints the revision that answered | no |
| `bin/envctl deploy <env> [--ref REF]` | ships a release | yes |
| `bin/envctl rollback <env>` | returns to the release served before the last deploy | yes |
| `bin/envctl promote <from> <to>` | ships what one environment serves to the other | yes |
| `bin/envctl log [--tail N]` | prints the event log | no |

Acting on `prod` (deploy, rollback, promote) also needs `--confirm prod`. Every command except
`log` is recorded in the event log, `.envs/events.log`.

## What a deploy ships

`deploy` without `--ref` ships the working tree as it is, uncommitted changes included, which is
for trying a change on stage before committing it; the environment then reports itself as built
from a working tree with uncommitted changes. `deploy --ref <branch|tag|commit>` ships exactly
that commit. A release goes to an environment with `--ref`.

## Releasing

1. The release commit on `main` sets `VERSION` and the changelog section; tag it `v<version>`.
2. `bin/envctl deploy stage --ref v<version>`, then `bin/envctl smoke stage`.
3. After a day on stage, with the product owner's go: `bin/envctl promote stage prod --confirm prod`,
   then `bin/envctl smoke prod`.

A deploy is verified by `smoke` after it: it answers with the revision actually served, which is
what the release note quotes. If a smoke fails, `rollback` the environment and say so.

## Where things are

`.envs/<env>/state.json` is what the environment serves; `.envs/<env>/release/` the files. These
are the environments' own state: change them only through `bin/envctl`.
