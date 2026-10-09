# Start a project from an idea

Use this reference when work starts from an idea and the repository is empty or does not exist
yet. The route ends at a walking skeleton: the thinnest real path through the layers the outcome
needs, with a Done command that can fail. From there the [lifecycle reference](lifecycle.md)
carries the work. Every stage below says when it adds nothing; a small idea skips most of them.
Stopping the idea, or changing it, is a result: report it as one.

Where the idea will be kept and the folder has no `AGENTS.md` with the OutcomeBound block, set it
up first: `git init`, then `outcomebound adopt .` with the harness in use; Done reads `UNVERIFIED`
until the skeleton has a Done command. A throwaway needs no install: its Done command can live in
the working note.

## Size the idea by who depends on it

Take the kind the person names; where they do not, take the one the facts show and name it in your
report as an assumption they may reverse.

| Kind | Such as | Keep |
| --- | --- | --- |
| throwaway | a one-off script, a spike | a Done command with one check; say it is throwaway; no frame, probe, spec or CI |
| personal | the person's own tool, kept for months | the outcome, the appetite and the no-gos; the skeleton with its Done and start commands; a probe only for a doubt about feasibility |
| shared | others depend on it, or it holds personal data, money or accounts | every stage, with the quality dimensions of the lifecycle reference |
| regulated | a failure harms someone or breaks a law: health, finance, safety, infrastructure | every stage, and a decision brief to the person for each compliance choice |

## Frame it

Write one working note, or the area's spec where the `spec` mechanism applies, with:

- the outcome: who it is for and what becomes observably true for them;
- what they do today instead, and any existing tool that already does it, found by a search;
- the appetite: the time or money the person will spend before it must show value, in their words;
- the no-gos: what is out of scope, and the bounds on spending, accounts, personal data and what
  becomes public;
- the bar for a first version that counts as done;
- the assumptions the outcome rests on, riskiest first: those that would end the idea if false and
  that nothing yet shows;
- a stop rule: the result that ends or changes the idea, in the person's terms;
- the strongest case against building it.

Ask only what changes these, as `gather-requirements` says. Your own agreement, and the answers of a
user an agent simulates, are hypotheses, never evidence that people want it: a claim that users want
it reads `UNVERIFIED` until a person reports what users did or said. End the frame with your
recommendation: build, probe first, or stop. Spending, accounts and publishing are the person's
(`decision-brief`).

Skip when: the idea is throwaway, or the person has already settled the outcome, the bar and the
bounds; for a personal tool, the outcome, the appetite and the no-gos are the whole frame.

## Probe what could end it

For each assumption that would end the idea and that nothing shows, write the question and the
result that passes in the working note before the first line of probe code, so the bar cannot bend
to the result. Then build the smallest probe that answers it: a
spike, a throwaway prototype the person shows to users, a measurement, or an explorable where the
answer turns on prices or values (`explorable`). Record each as question, probe, result (`PASS`,
`FAIL` or `UNVERIFIED`) and the decision it led to. Probe code stays in the working area, marked
throwaway, and never becomes the product: the skeleton is built fresh. A result that meets the stop
rule ends or changes the idea, and you report it as such.

A probe that needs people, such as a prototype shown to users or a trial with real customers, is the
person's to run. Write it up with its question and the result that passes, and hand it to them;
build no skeleton until its result is in or the person says to build without it. A request to start
the project asks for this route; it does not waive the probes.

Skip when: every assumption that could end the idea already has evidence.

## Decide what is hard to undo

Put the choices that later work cannot easily undo in one decision table in the area's design
(`bash "$(outcomebound home)/scripts/new-spec.sh" <slug>`), each with the choice, the alternative
rejected, its owner and whether it can be undone. They are usually: where data lives and who owns
its schema; authentication and the trust boundary; hosting and what it spends; the language and
framework, the one the people who keep it can run for its lifespan, new technology only where the
idea needs it; module boundaries, one deployable first; license and visibility; and, for a feature
that calls a model, the provider and how its output is evaluated. Settle each as
`gather-requirements` settles a gap. Then ask what the likeliest reason is that this fails in its first months, and turn each answer
into a no-go, a bound or a check of the skeleton.

Skip when: the idea is throwaway or personal; a line in the working note per choice is enough.

## Build the walking skeleton

Build the thinnest path from the user's action through each layer the outcome needs and back, and
to the delivery destination where one is in scope and the person granted it. For a feature that
calls a model, write its evaluation tasks and their grader first, and commit them before the code
that calls the model. Report each line of its bar as `PASS`, `FAIL` or `UNVERIFIED`:

1. One Done command passes on a clean checkout: format, lint, type checks, tests and build, failing
   when any of them fails.
2. A defect you plant makes Done fail, and removing it makes Done pass again.
3. One test goes through the real boundary: a request to the running service, a browser, the
   command as a user runs it.
4. CI runs the same Done command. The file in place is a static `PASS`; a green run stays
   `UNVERIFIED` until the person pushes, since enabling CI, the first push and branch protection
   are theirs.
5. Secrets and dependencies: an example environment file that holds names only, a secret scan, a
   lockfile, and each new dependency's name checked in its registry before it is installed.
6. One command starts the app or service.
7. For a feature that calls a model: evaluation tasks drawn from its expected use and a grader,
   committed before the code that calls the model.
8. Where delivery is in scope and the person deployed, or granted the deploy and the account it
   needs, the deployed version observed at its destination; else `UNVERIFIED`, with what would
   settle it.

Offer the quality floor (`outcomebound floor --help`): from the first commit, it has nothing old to
grandfather. Then record Done with `outcomebound adopt . --done '<command>'`.

Skip when: the idea is throwaway (line 1 only), or personal (CI and delivery optional).

## Hand it to the lifecycle

Build the first features as thin slices that each reach the user, riskiest first. Cut tickets only
where separate outcomes need tracking (`slice-tickets`); where the build spans sessions, the goal
envelope's feature list gives each item a pass flag. Trim the design as the code grows: delete what
the code now shows. Continue with the [lifecycle reference](lifecycle.md).

Skip when: the skeleton is the whole outcome.
