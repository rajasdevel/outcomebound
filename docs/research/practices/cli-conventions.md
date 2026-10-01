---
last_checked: 2026-09-22
volatility: STABLE (the published guidance of §2 and the traps of §3) / VOLATILE (§1 what each tool does, at its default branch on the day read)
sources:
  - https://clig.dev/
  - https://no-color.org/
  - https://force-color.org/
  - https://www.ietf.org/archive/id/draft-inadarei-api-health-check-06.txt
  - https://www.gnu.org/prep/standards/standards.html
  - https://raw.githubusercontent.com/freebsd/freebsd-src/main/include/sysexits.h
  - https://docs.pytest.org/en/stable/reference/exit-codes.html
  - https://github.com/git/git/blob/master/Documentation/git-bisect.adoc
  - https://rustc-dev-guide.rust-lang.org/diagnostics.html
  - https://github.com/rust-lang/rfcs/blob/master/text/1644-default-and-expanded-rustc-errors.md
  - https://web.archive.org/web/2019id_/https://medium.com/@jdxcode/12-factor-cli-apps-dd3c227a0e46
  - https://github.com/github/scripts-to-rule-them-all
  - https://code.claude.com/docs/en/commands
  - https://docs.python.org/3/library/subprocess.html
  - https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file
---

# Check commands and CLI conventions

How a command that checks a project, installs into it or runs its checks should report, write and
run.

Re-check when a surveyed tool changes its doctor or check command, or a guidance page (clig.dev,
no-color.org, force-color.org) is revised. The guidance of §2, the corrections, and the sources of
every finding added after the catalog was read were re-read on 2026-10-01 and carry that date.

This reference answers how a command that checks a project or an installation should report: what
developer tools' `doctor`, `check` and `diagnose` commands do, and what published CLI guidance says
about output, exit codes, machine-readable reports, remedies, deliberately skipped checks and colour.
It surveys forty-seven tools read from their own documentation and source, and the bodies of guidance
behind them, and adds what agent readers need from the same output, and the traps met when a tool
writes into a project, updates files it installed, or runs a project's commands under a time limit.
It is for anyone designing a command whose verdict a person, a script, CI or a coding agent will act
on, or a tool that installs into a repository.

**Evidence classes.** (S) a standard or convention document (GNU Coding Standards, BSD `sysexits.h`,
the IETF health-check draft, no-color.org); (L) a tool's own documentation or source, or a lab's
guidance; (P) practitioner guidance (clig.dev, "12 Factor CLI Apps", compiler-message design); (M)
measured; (A) one observation; (O) an observation or measurement recorded in one project's own
engine, reviews and probes. The tool catalog was read on 2026-09-22 from each tool's docs and
source on its default branch; quotations are verbatim; a behaviour read only from source, not
observed at run time, is marked. Bracketed ids resolve in
[`_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl).

## Key findings

**C1. The field's minimum contract is four parts.** One row per check with a leading status marker and
a title; an explicit "nothing wrong" sentence ("Your system is ready to brew.", "No problems found",
"All checks passed"); a closing tally when there are problems ("Doctor found issues in 2
categories", "3/5 checks passed"); and `-v` for detail. A tool that omits any of these reads as
unfinished to someone who has used the others. (L, across the 47 tools)

**C2. Keep "could not check" apart from "found a problem".** Most tools use three levels (ok, warn,
error); only chezmoi separates "the check could not be completed" (`failed`) from "a definite
problem" (`error`). Tools whose job is to find things split nothing found, something found and
could not do the job as exit 0, 1 and 2 (grep, diff); git bisect reserves 125 for "cannot be tested";
pytest 5 for "no tests collected". The IETF health format's `warn` means "healthy, with some concerns"
and, like `pass`, must be served with an HTTP status in the 2xx–3xx range (`fail` takes 4xx–5xx); used
for a check that could not run, it counts missing evidence as success. (S, L)

**C3. Exit codes: zero on success, non-zero mapped to the important failure modes, never a count, and
documented.** Exit status is 8 bits, so 256 errors read as success (GNU §4.2). Only 9 of the 47 tools
state their exit semantics in help or man text, and of those bundler's stated semantics disagree with
its source (§1, Limits). (S, L)

**C4. Fail on definite problems; let CI opt into failing on warnings.** Warnings-fail is the minority
and draws the loudest complaint: Homebrew exits non-zero on any finding while its banner tells the
user to ignore them. The newer designs (mise, chezmoi, pnpm, WP-CLI's doctor, Flutter) fail only on
errors; `poetry check --strict` ("Fail if check reports warnings.") is the clean opt-in, and
`composer validate --strict` ("Return a non-zero exit code for warnings as well as errors")
[as-of 2026-10-01] a second. (L)

**C5. Put the remedy on the finding record, the same in text and JSON.** Homebrew's `remediation`
(commands and text, rendered "You can solve this by running:"), pnpm's `fix`, Expo's `advice[]` and
bit's `cure` carry the next command with the status; tools without remedies (nix, chezmoi, bundler)
leave the user searching. A remedy is one concrete statement, never a question ("did you mean" is
discouraged by the rustc guide). (L, P)

**C6. JSON is the same record as the text, one document on stdout.** mise's source: "Both outputs
render `self.warnings`, so a check only one path runs is a hole in the other." Bolted-on JSON
accretes traps: Homebrew's is hidden, flyctl's is a flat string map "depended on in production",
`gh auth status --json` always exits 0, and rustc's JSON lines are, in its guide's words, "not valid
JSON". (L)

**C7. Observing and repairing are separate acts.** Every tool read except Sapling makes repair opt-in
(`--fix` confirming with default no, `--interactive`, `--android-licenses`, Claude Code's `/doctor`
asking before changing anything); mise's source: "`doctor` is not a command that should remove
files." (L)

**C8. Do not call a dump a doctor.** cdk, tilt and dvc use the name for environment listings with no
verdict; Nix renamed `nix doctor` to `nix config check` and put the dump under `nix config show`.
Keep inventory sections apart from the verdict rows. (L)

**C9. Record a deliberate "not set up" in project configuration and show it on every run, with its
reason.** Flutter persists feature flags and lists the non-default ones; mise prints an
`ignored_config_files` section ("(none)" when empty); WP-CLI's doctor records `skipped_checks`; Expo
records per-check `enabled` and `exclude`, and for two of its checks prints on every run that the
check is disabled and how to re-enable it, while a disabled check of its React Native Directory is
simply not run [as-of 2026-10-01]. None of the doctor tools records why; among lint systems, Rust's
`#[allow(lint, reason = "…")]` shows the reason when the lint fires anyway, and `#[expect(lint)]`
turns a stale silence into a diagnostic. (L)

**C10. Report on stdout, messages on stderr; honour colour conventions.** Human-readable first,
`--json` on request; print something even on success; put the most important information last;
disable colour when a stream is not a TTY, when `NO_COLOR` is set and non-empty, when `TERM=dumb`, or
on `--no-color`; no animations off a TTY. (P, S)

**C11. Agent readers need the same output quieter and bounded.** One line or nothing on success;
only the failures, each with its reason and fix; bounded length; no prompts; `--help`; structured
output on request; meaningful exit codes; idempotent commands with a dry run. Error messages that
carry the fix steer the agent's next attempt [deterministic-2, other-labs-23]. In one CI job a check
command printed its whole JSON report, 8,791 lines and 95% of that job's log (O): one line per
check, with the JSON written to a file or printed on request, keeps a log readable. (L, P, A, O)

**C12. A report must never turn absence into a pass.** An absent field means "never observed", an
empty list "observed none"; a check that did not run reads n/a, never 0; a capability counts only
when a check proved it; a layer that is not enabled is skipped, not failed; controls the check cannot
see are listed as not verified [repo-readiness-audits-9, -11, -16, -20]. (A, P)

**C13. A network check must be switchable off, and its failure must read as unverified.** pnpm
`--offline`, chezmoi `--no-network`, and Composer's `COMPOSER_DISABLE_NETWORK` with a `SKIP` line
carrying its reason are the models; npm's registry check cannot be disabled, and Expo's API checks
fail the run unless `EXPO_DOCTOR_WARN_ON_NETWORK_ERRORS` downgrades network-only failures to a
warning. (L)

**C14. A tool that writes into a project writes only what it owns, and atomically.** It records only
the files it wrote, since matching bytes are not ownership; refuses a path segment that is `.git`
under case folding or trailing-dot stripping, and a symbolic link anywhere on the path; stages new
bytes in an exclusively created file, `fsync`s it and moves it into place with `os.replace`;
re-checks the bytes it replaces; and compares exact bytes, never normalized text. An update keeps
what upstream offers, the base last accepted and the project's bytes apart, and advances the base only
on an accepted change. (O, §3)

**C15. A command that runs a project's checks owns their whole process group.** A timeout that kills
only the direct child leaves its descendants running: start each check in its own session or process
group and end the group at the limit. Variables the runner sets for its own calls stay out of the
checks' environment, and each check's evidence goes to a file no other check can overwrite. (L, O,
§3)

## 1. What the tools do (VOLATILE)

### Status vocabularies

| Tool | Words or marks | Levels |
| --- | --- | --- |
| Homebrew `brew doctor` | a check returns findings or nothing; every finding is a "warning"; findings carry a support `tier` | 2 |
| Flutter `flutter doctor` | `[✓] [!] [✗] [☠]`: success, partial, notAvailable, missing, crash; messages `✗ ! •` (error, hint, information) | 5 |
| npm `npm doctor` | `Ok` / `Not ok` | 2 |
| Expo `expo-doctor` | `✔` / `✖`; `isSuccessful` with `issues[]` and `advice[]` | 2 |
| mise `mise doctor` | information sections, then `warnings[]` and `errors[]` | 2 |
| Nix `nix config check` | `[PASS] [FAIL] [INFO]` (a "Warning: …" message is emitted as `[FAIL]`) | 3 |
| chezmoi `chezmoi doctor` | `omitted failed skipped ok info warning error` (integers −3 to 3; omitted rows not printed) | 7 |
| conda `conda doctor` | `✅` / `❌` | 2 |
| WP-CLI `wp doctor` | `success` / `warning` / `error` (internal `incomplete`) | 3 |
| pnpm `pnpm doctor` | `pass` / `warn` / `fail`; `✓ ‼ ✗` | 3 |
| Composer `composer diagnose` | `OK` / `WARNING` / `FAIL` / `SKIP` (with a reason) | 4 |
| Symfony `check:requirements` | `[OK] [WARN] [ERROR]`, dots `. W E`; mandatory against optional | 3 |
| `gh auth status` | `✓ Logged in` / `X Failed` / timeout; `!` for missing scopes | 3 |
| rustup `rustup check` | `up to date` / `update available` | 2 |
| tauri `tauri info` | `- ✔ ⚠ ✘` (Neutral, Success, Warning, Error) | 4 |
| wails `wails doctor` | `Installed` / `Available` / `Not Found`; `* Optional` | 3 |
| React Native `doctor` | `✓` / `✖` (required) / `●` (optional) | 3 |
| storybook `doctor` | `passed` / `has_issues` / `check_error` | 3 |
| bit `bit doctor` | `passed` / `failed`; `symptoms` and `cure` | 2 |
| IETF health check draft | `pass` / `fail` / `warn` (aliases ok/up, error/down) | 3 |
| rustc diagnostics | `error` / `warning` / `note` / `help`; only `help` proposes a fix | 4 |

Nearly every diagnosing tool prints an explicit all-clear: "Your system is ready to brew.", "•
No issues found!", "No problems found", "All checks passed", "No issues found with the installed
bundle", "Your Storybook project looks good!", "no problems detected", "No broken requirements
found.", "All set!", "Everything looks fine.", "N/N checks passed. No issues detected!", "All N checks
report 'success'." Exceptions: Nix (no summary), npm (silence on success), cdk and tilt (no verdict).

Vocabularies beyond the table: rbenv-doctor `OK`, `not found`, `multiple`, `found at wrong position`,
`warning`; jenv `[OK]` and `[ERROR]`; flyctl `PASSED`, `FAILED` and `Nope`; Jekyll `Warning:` and
`Conflict:`; poetry `Error:`, `Warning:` and `All set!`; Sapling `repaired` and `failed to fix`; and
`dotnet sdk check`, a staleness table reading `Up to date.`, `Patch 7.0.201 is available.` or `.NET
3.1 is out of support.`, with a download URL. (L)

### Exit codes

| Source | Codes |
| --- | --- |
| clig.dev | "Return zero exit code on success, non-zero on failure … Map the non-zero exit codes to the most important failure modes." |
| GNU Coding Standards §4.2 | "Do not use a count of errors as the exit status … exit status values are limited to 8 bits" |
| GNU grep §2.3 | 0 a line selected, 1 none selected, 2 an error; with `-q`, a selected line exits 0 even if an error occurred |
| GNU diff, cmp, sdiff | 0 no differences, 1 some differences, 2 trouble |
| ShellCheck | 0 no issues, 1 some issues, 2 some files could not be processed, 3 bad syntax, 4 bad options |
| pytest (`pytest.ExitCode`) | 0 passed, 1 some failed, 2 interrupted, 3 internal error, 4 usage error, 5 no tests collected, 6 too many warnings |
| git bisect run | 0 good; 1–127 except 125 bad; 125 cannot be tested; 126 and 127 reserved by shells |
| pre-commit | 1 hook failure or precondition failure; 3 unexpected error, with "Check the log at …"; 130 interrupted |
| BSD `sysexits.h` (deprecated for FreeBSD base) | 64 usage, 65 data, 66 no input, 67 no user, 68 no host, 69 unavailable, 70 software, 71 OS error, 72 OS file, 73 can't create, 74 I/O error, 75 temporary failure, 76 protocol, 77 no permission, 78 configuration |
| rustup check | 0 up to date, 100 at least one update available, 1 error |
| Mercurial `hg debuginstall` | the number of problems found |
| Nix `nix config check` | 2 on any FAIL |
| `gh auth status` | 1 on any authentication issue; always 0 with `--json` unless fatal |

Why the codes are what they are. `sysexits.h` starts at 64 (`EX__BASE`) "to reduce the possibility of
clashing with other exit statuses that random programs may already return"; 75 (`EX_TEMPFAIL`) means
the user "is invited to retry" and is "not really an error"; 69 (`EX_UNAVAILABLE`) doubles as a
catchall "when something you wanted to do doesn't work, but you don't know why" (S). GNU grep notes
that "Other grep implementations may exit with status greater than 2 on error." git bisect chose 125
"as the highest sensible value", because POSIX shells use 126 (found but not executable) and 127 (not
found); "Any other exit code will abort the bisect process." A pre-commit hook "must exit nonzero on
failure or modify files"; the run's code is the bitwise OR of its hooks' codes, a hook that changed
files is marked `- files were modified by this hook`, and a known fatal error exits 1 ("An error has
occurred"). rustup's 100 ("At least one update is available.") is the clearest non-zero code that
reports information rather than an error. (L) [as-of 2026-10-01]

Doctor commands on findings (read from source unless documented):

| Behaviour | Tools |
| --- | --- |
| Any finding or warning fails | Homebrew (any finding), rbenv-doctor (any warning), Composer (WARNING 1, FAIL 2), npm (two levels only), Expo (any failed check), Jekyll, Nix, `gh auth status` |
| Only errors fail | mise, chezmoi, WP-CLI doctor, pnpm, Flutter (`missing` and `crash` only), Symfony (mandatory only), poetry (unless `--strict`), wails (required only; code UNVERIFIED) |
| Never fails on findings | conda (returns 0), flyctl (prints FAILED, exits 0), tilt, cdk (only on reserved environment variables) |
| Stops at the first failure | flyctl (after its authentication and WireGuard checks); Capacitor runs every check of a platform and joins the failures they return, but one thrown error ends the run |

Flutter's `ExitStatus.warning` feeds analytics only in the source read; its run-time exit code with
issues is UNVERIFIED.

### Machine-readable shapes

| Tool or format | Shape |
| --- | --- |
| IETF `application/health+json` (draft 06, expired 2022) | root `status`, `version`, `releaseId`, `notes[]`, `output` (omitted on pass), `checks{"component:measurement": [{componentId, componentType, observedValue, observedUnit, status, affectedEndpoints, time, output, links}]}`, `links{}`, `description`; user-defined keys allowed |
| Homebrew `--json` (hidden) | `{tier, findings: [{text, tier, affects, links, remediation: {commands, text}}]}` |
| pnpm `--json` | `{checks: [{title, status: pass/warn/fail, detail?, fix?, durationMs?}]}`; a check skipped by `--offline` reported as `pass` with `detail: "skipped (--offline)"` |
| mise `-J` | every information section as a key, plus `errors[]` and `warnings[]` |
| WP-CLI doctor | rows `{name, status, message}` in `--format=json`, csv, yaml or count |
| flyctl `--json` | flat map `{name: "ok" or error string}` |
| `gh auth status --json` | `{hosts: {host: [{state, error, active, host, login, tokenSource, token, scopes, gitProtocol}]}}` |
| pulumi `about --json` | information sections plus `errors[]` |
| rustc `--error-format json` | one object per diagnostic: `message`, `code {code, explanation}`, `level`, `spans[]` (location, `is_primary`, `label`, `suggested_replacement`, `suggestion_applicability`), `children[]`, `rendered`; emitted as JSON lines |
| Flutter | `fromJson` for `type`, `statusInfo`, `messages[{type, message, piiStrippedMessage, contextUrl}]` (no CLI flag) |
| none | Flutter, npm, Expo, Nix, chezmoi, tilt, cdk, Composer diagnose, React Native doctor, storybook, wails v2, tauri |

The IETF draft (16 October 2021, expired 19 April 2022) gives `pass`, `fail` and `warn`, with the
aliases `ok`/`up` and `error`/`down`, as the values publishers "SHOULD use", case-insensitive; it has
no skipped, not-applicable or declined status. `output` and `affectedEndpoints` "SHOULD be omitted"
on pass; `componentType` is `component`, `datastore`, `system`, a well-known term or a URI; the
pre-defined measurement names are `utilization`, `responseTime`, `connections` and `uptime`; `time` is
ISO 8601; a single-node component still takes a one-element array; and implementations "MAY ignore
any keys that are not part of the list of standard keys". Its §4.5 defines a check's `status` with the
sentence it uses for `output`, read as a drafting slip. (S) [as-of 2026-10-01]

Other machine output: `hg debuginstall -Tjson` through Mercurial's formatter; wails v3's report
carries JSON tags and a `ready` boolean; `bit doctor --save` and `--archive` write the report to a
file for sharing; envinfo offers `--json` and `--markdown`. (L)

clig: keep `--json` and `--plain` stable, because output for humans will change.

### Remedies

- "12 Factor CLI Apps" (Dickey, 2018): an error has a code, a title, an optional description, how to
  fix it, and a URL. Its example: `Error: EPERM - Invalid permissions on myfile.out` / `Cannot write
  to myfile.out, file does not have write permissions.` / `Fix with: chmod +w myfile.out`.
- rustc dev guide: the error states the problem; only the `help` sub-diagnostic proposes a fix, with
  an applicability confidence (MachineApplicable, HasPlaceholders, MaybeIncorrect, Unspecified; "Be
  conservative when choosing the level"); `note` carries context and links. Suggestions are
  statements ("there is a struct with a similar name: `Foo`"), not questions; no "the following" or
  "as shown". Give an error a code only when its explanation says more than the error itself.
- Homebrew renders a finding's remediation as its text or "You can solve this by running:" with the
  literal commands; npm's thrown error text is the remedy ("Use npm v…", "Add … to your $PATH");
  Expo prints issues then `Advice:` lines; bit prints `symptoms` and `cure`; `gh auth status` prints
  "To re-authenticate, run: gh auth login -h host".
- clig: catch expected errors and rewrite them for humans; group repeated errors under one header;
  write debug detail to a file, not the terminal; make bug reports effortless. pre-commit on an
  unexpected error prints "Check the log at …" and writes a log with version information and the
  traceback.
- `composer diagnose` keeps the worst code across its checks and prints `SKIP` with a reason
  ("Because allow_url_fopen is missing."). `gh auth status` attaches a command to each problem ("To
  request missing scopes, run: gh auth refresh -h <host>"; "To forget about this account, run: gh auth
  logout -h <host> -u <login>"). flyctl marks a missing optional dependency without failing (`Nope`,
  and in verbose mode "This is fine, we'll use a remote builder."). jenv prints `To fix :` lines;
  rbenv-doctor prints "Please run `rbenv init' and follow the instructions." and "Please reorder your
  PATH."; storybook ends "You can always recheck the health of your project(s) by running: npx
  storybook doctor". tauri offers "Run the automatic fix?" only for an Error row, in interactive mode,
  when the check has a fix; React Native's interactive mode fixes all issues, errors or warnings by
  key (`f`, `e`, `w`); Sapling, which repairs by default, says when it cannot ("changelog: cannot fix
  automatically (consider reclone)") and exits 1. pyenv-doctor proves readiness by building a probe
  Python and exits with the build's status. (L) [as-of 2026-10-01]

### Deliberately not set up

| Tool | Mechanism | Records why? |
| --- | --- | --- |
| Flutter | `flutter config --no-enable-web` persists a flag; the validator disappears; the Flutter row lists non-default flags; `notAvailable` for "not applicable or available on the current host" counts as an issue, never a failure | no |
| mise | an `ignored_config_files` section, "(none)" when empty | no |
| WP-CLI doctor | `doctor.yml` with `_: {inherit: default, skipped_checks: [...]}` | no |
| Expo | `package.json` `expo.doctor.<check>.enabled` and `exclude` (entries in `/…/` become regexes); for the dependency-version check (disabled by `EXPO_DOCTOR_SKIP_DEPENDENCY_VERSION_CHECK`) and `appConfigFieldsNotSyncedCheck`, every run prints that the check is disabled and how to re-enable it; a disabled React Native Directory check is simply not run; an environment variable that conflicts with the config wins, with a warning | no |
| Composer | `SKIP` printed with the reason ("Network is disabled by COMPOSER_DISABLE_NETWORK.") | the cause, not a decision |
| chezmoi | each check declares its own severity when a tool is absent (required tools error, secret managers info) | no |
| pnpm | a skipped check reported as `pass` with a detail | no |
| Symfony, wails, React Native | mandatory against optional requirements; only mandatory ones fail | no |
| Rust | `#[allow(lint, reason = "…")]` shows the reason when the lint fires; `#[expect(lint)]` reports an unfulfilled expectation | yes |
| Homebrew, npm, Nix, bundler, conda, storybook, cdk, tilt | positive selection by name only, or nothing | — |

### Display against diagnose

Explicit pairs: `nix config show` / `nix config check`; `react-native info` / `doctor`; `brew
config` / `brew doctor`; `claude doctor` (read-only, from the shell) / `/doctor` (reports first, asks
before changing) / `/status`; `dotnet --info` / `dotnet sdk check`; `conda info` / `conda doctor`.
Dumps with a diagnostic name: `cdk doctor`, `tilt doctor`, `dvc doctor` (an alias of `dvc version`),
`skaffold diagnose` (the effective configuration), `nvm debug`. Hybrids that keep the verdict apart:
mise (sections, then warnings, then problems), wails (System, Dependencies, then Diagnosis). "For bug
reports" is the stated purpose of every pure dump (`brew config`, `cdk doctor`, `tilt doctor`, `next
info`, `nx report`, envinfo, `react-native info`, `pulumi about`, `dvc doctor`). Hybrids that mix
inventory and verdict in one stream: chezmoi (environment rows inside the check table), `composer
diagnose` (versions between checks), `tauri info` (sections headed by their worst status), Flutter
(its first row carries version, channel and non-default flags) and `gcloud info --run-diagnostics`
(an opt-in diagnostics pass inside an info command). (L)

Claude Code, read 2026-09-22 and re-read [as-of 2026-10-01]: `claude doctor` prints "read-only
installation and settings diagnostics from the terminal without starting a session, including
install health, settings-file validation errors, and Remote Control eligibility"; it reports an
invalid hooks array, lists a dropped settings key, and its Search row reads `OK (bundled)` or the
path of the system ripgrep. `/doctor` (alias `/checkup`) checks duplicate or leftover installs,
`PATH` problems and unparseable settings; finds unused skills, MCP servers and plugins against their
context cost; flags slow hooks; checks for a newer version on the release channel; deduplicates
local `CLAUDE.md` files against checked-in ones, trims checked-in ones of what Claude can derive
from the codebase and moves the remaining always-loaded guidance into skills and nested `CLAUDE.md`
files; offers to make auto mode the default and to pre-approve frequently denied read-only commands;
and "Reports findings first and asks for confirmation before changing anything". Before v2.1.205 it
was a read-only screen whose `f` key sent the report to Claude; since v2.1.283 it takes a
`prompt-audit` subcommand, and a separate `/skill-doctor` exists since v2.1.252. (L, volatile)

### Other details worth keeping

- Homebrew runs its two slow checks last and drops cask checks when no casks are installed; its
  source comment: "a default install should not trigger any brew doctor messages".
- Homebrew's checks are the public `check_*` methods of one class: `--list-checks` lists them, any can
  be run alone by name, an unknown name fails ("No check available by the name: …"), and
  `--audit-debug` profiles each one. Named subsets of the same checks run inside other commands as
  preconditions and exit 1 when fatal (`fatal_preinstall_checks` and
  `fatal_build_from_source_checks`; a third, for setting up the build environment, is now empty), so
  the doctor's checks double as install and build preflight. Findings go to stderr through `opoo`,
  which emits GitHub Actions `warning` annotations when running in Actions; a configuration outside
  support tier 1 ends "This is a Tier N configuration: … Read the above document before opening any
  issues or PRs." (L) [as-of 2026-10-01]
- Rows about things the user does not use read as noise: Homebrew prints a banner telling users to
  ignore its warnings ("If everything you use Homebrew for is working fine: please don't worry or file
  an issue; just ignore this."); chezmoi lists sixteen secret-manager rows (nineteen with `age`,
  `gpg` and `pinentry`), each reported `info` when absent; and Flutter shows `[!] Android toolchain`
  to anyone who has not turned Android off. mise guards against false positives on purpose: "Paths before the
  shim directory are allowed to take precedence intentionally, so report only concrete command
  collisions instead of warning merely because shims are not first"; "Optional deps and tools whose
  plugin isn't installed are silently skipped"; "One wording for an empty install, so the text and
  JSON paths cannot drift." It counts warnings ("N warnings found:") apart from problems ("N problems
  found:", or "No problems found"). (L)
- A check that throws is one row, not the end of the run: Flutter turns a validator's exception into a
  `crash` row (`[☠]`, "Due to an error, the doctor check did not complete. If the error message below
  is not helpful, please let us know about this issue at https://github.com/flutter/flutter/issues.")
  and runs the rest; only `crash` and `missing` make the overall result false. A grouped validator
  with a mix of outcomes reports `partial` (all `missing` stays `missing`). The default run opens with
  "Doctor summary (to see all details, run flutter doctor -v):", hides information messages and
  per-validator durations unless verbose, leaves out validators that do not apply to the host, and
  ends "No issues found!" or "Doctor found issues in N categories."; a separate summary text words
  each row "is fully installed.", "is partially installed; more components are available.", "is not
  available." or "is not installed.". The Flutter row exists "for diagnosing issues on Github bug
  reports by displaying specific commit information". (L) [as-of 2026-10-01]
- Flutter prints "This is taking an unexpectedly long time..." after 10 s on one validator and has a
  4 min 30 s hard timeout ("This should only ever be reached if a process is stuck."); it can run
  its validators once and render with and without personally identifying information.
- mise: "Deliberately only the empty case. A directory holding files but no runnable binary cannot be
  told apart from a tool that legitimately ships none, and calling a healthy install broken is worse
  than missing one." Its dotfiles section: "Inspects only: never syncs, applies, or prompts."
- chezmoi replaces the home directory with `~` in its table to avoid exposing the user name; cdk
  prints the first four characters of `AWS_ACCESS_KEY_ID` and `<redacted>` for secrets; `gcloud info
  --anonymize` minimizes identifying information for sharing.
- Expo prints check results in completion order so CI log timestamps reflect execution time, and
  switches its spinner to plain logs when not interactive. It runs its checks in parallel and filters
  them by each check's SDK version range; `EXPO_DEBUG` with `--verbose` adds durations; its source
  carries `// TODO: add offline flag`; its React Native Directory check is on by default from SDK 52;
  and `CI=1 npx expo install --check` "will fail if any installed packages are outdated". (L)
- pnpm's `doctor` (added in v11.14.0) says "Each check reports how to fix what it finds" and
  "Warnings do not fail the command". Its registry check has a 15-second timeout and is skipped with
  `--offline`; its install smoke test is "always offline by construction, so --offline does not skip
  it"; its store check is skipped when no store is configured. It ends "All checks passed" or "All
  checks passed with N warning(s)", with each non-pass `fix` dimmed on the next line, and takes
  `--json` and `--benchmark`. (L) [as-of 2026-10-01]
- npm's docs say why each check exists and what to do when it fails ("you should probably run `npm
  cache clean -f`"); its checks run by group (`connection`, `registry`, `versions`, `environment`,
  `permissions`, `cache`); it is "unaware of workspaces"; and a source comment asks of its unbuilt
  checks "What is the fix for these?". WP-CLI keeps per-environment check files (`prod.yml`,
  `dev.yml`) that inherit the defaults, lists checks with `wp doctor list`, has no `--strict`, and
  states its purpose as replacing memory: "Without `wp doctor`, your team has to rely on their memory
  to manually debug problems." conda's `doctor` has the alias `conda check`, `--list` prints each
  check with its fix capability, and a plugin declares `CondaHealthCheck(name, action, fixer, summary,
  fix)`. (L)
- Tools already offer the failures-only view agents need: WP-CLI's `--spotlight` ("Focus on warnings
  and errors; ignore any successful checks."), bundler's `--quiet` ("Only output warnings and
  errors."), and Expo, which hides passing checks unless `--verbose` ("print all test results,
  including passing ones") and, when a check failed, says "Use the --verbose flag to see more details
  about passed checks." A quiet default with `--verbose` for detail (`-v` in most; Expo's `-v` is
  `--version`) is shared by Flutter, Expo, conda, `next info`, flyctl and pyenv-doctor. (L)
- conda `--fix` asks with default no and supports `--dry-run` and `--yes`; its checks are a plugin
  hook (`conda_health_checks`). WP-CLI checks are YAML-declared PHP classes; Flutter has experimental
  extension validators and bit an in-code registrar. Homebrew, npm, Expo and mise have no extension
  point for checks.
- Where chezmoi hides the user name, `nvm debug` prints `whoami` and `$HOME` as they are, with a
  sanitised `$PATH`. `cdk doctor` exits −1 only when one of its three reserved environment variables
  is set; `tilt doctor` skips a
  field whose query errors and exits 0; Nix's `config check` honours the global `--offline`. (L)
- `rbenv doctor` and `pyenv doctor` are separate installer or plugin scripts, not core commands;
  `yarn dlx @yarnpkg/doctor` lints packages for Plug'n'Play rather than diagnosing an environment;
  Ionic's `doctor check` and `doctor treat` are absent from the current CLI source, and their docs
  pages return 404.

## 2. Published guidance

**clig.dev.** Human-first design; "Saying (just) enough" (too little when a command hangs silently,
too much when it dumps pages of debug output); discoverable help with examples and suggested next
commands. Output: human-readable is paramount; machine-readable where it does not hurt usability;
`--plain` for one record per line; `--json` for structure; brief output on success, `-q` to suppress
it; "If you change state, tell the user"; make current state easy to see (as `git status` does);
"Suggest commands the user should run"; actions crossing the program's boundary should be explicit.
Errors: "Put the most important information at the end of the output"; readable signal-to-noise;
unexpected errors get debug information and a bug-report path. Flags: prefer flags to arguments;
full-length versions of all flags; standard names (`-h/--help`, `--version`, `-q/--quiet`,
`-n/--dry-run`, `-f/--force`, `--json`, `--no-input`, `-d/--debug`); "Never require a prompt"; confirm
before anything dangerous, with `-f/--force` for scripts; a special word such as `none` for an
optional value. Robustness: validate input; "Print something to the user in <100ms"; show progress
for long work; time out; be recoverable. Future-proofing: subcommands, flags, configuration files and
environment variables are interfaces; keep changes additive; no catch-all subcommand; no arbitrary
abbreviations. Further rules: check each stream for a terminal separately, since "if you're piping
stdout to another program, it's still useful to get colors on stderr", and offer an app-specific
`MYAPP_NO_COLOR`; use colour with intention ("if everything is a different color, then the color
means nothing"; "The eye will be drawn to red text, so use it intentionally and sparingly"); "Use
symbols and emoji where it makes things clearer"; show output that only helps the tool's authors
"only in verbose mode", and keep log-level labels (`ERR`, `WARN`) off by default; "Use a pager only if
stdin or stdout is an interactive terminal"; `-v` "can often mean either verbose or version", so the
page suggests `-d` for verbose and `-v` for version, or nothing, while its flag list gives `-d,
--debug` for debugging output; with `--no-input`, or when stdin is not a terminal, never prompt: "fail
and tell the user how to pass the information"; when a command expects piped input and stdin is a
terminal, "display help immediately and quit"; "Lead with examples" and "Provide a support path";
danger comes in tiers (mild; moderate, with a dry run; severe); "Make it crash-only"; "Responsive is
more important than fast"; "Warn before you make a non-additive change" and "Don't create a 'time
bomb'"; and read the general variables `NO_COLOR`, `FORCE_COLOR`, `DEBUG`, `TERM`, `TERMINFO`,
`TERMCAP`, `PAGER`, `LINES` and `COLUMNS`. (P) [as-of 2026-10-01]

**"12 Factor CLI Apps"** (Jeff Dickey, Heroku, 9 October 2018, read from a Wayback Machine capture
because Medium refused direct fetches): twelve factors, among them "Encourage contributions" and
"Follow XDG-spec", none about exit codes; "-h,--help should be a reserved flag used for help only",
and help shows the command's description, its arguments, every flag and "most importantly" examples
of common usage; every form of help (`mycli`, `--help`, `help`, `-h`, per subcommand) shows
help; the version command carries debugging information; stdout for output, stderr for messaging;
the error format above; colour and spinners only on a TTY, respecting `TERM=dumb`, `NO_COLOR` and
`--no-color`, with an app-specific variable; never require a prompt; one entry per table row, no
borders, CSV or JSON on request; speed tiers (under 100 ms very fast, 100–500 ms fast enough, 500 ms–2
s usable, over 2 s languid); list subcommands or show help when called with no arguments. An
unexpected error should have "a way to view full traceback information as well as full debug output
with environment variables", and error logs kept for post-mortems need timestamps, occasional
truncation and no ANSI colour codes. (P)

**Error and diagnostic design.** GNU §4.4: errors look like `sourcefile:lineno: message` or `program:
message`; `--help` and `--version` print to stdout and exit successfully. Rust RFC 1644 (2016):
separate errors clearly; a visually distinct header per error; readable without colour; avoid Unicode
art; labels on the source rather than trailing notes; keep `filename:line` easy to spot; primary
labels say what, secondary labels say why. rustc style guide: plain English, lower-case messages
without final punctuation, identifiers in backticks, "The word 'illegal' is illegal", one message per
error, warnings chosen to avoid fatigue and false positives. Elm, "Compiler Errors for Humans" (2015):
show the user's code exactly as written with its line numbers; every message has a useful hint;
short context above the code, specific hints below; one message per visually separated block. Elm
0.15.1 (2015-06-30) emits the same errors as JSON with `--report=json` for editor plugins, keeps an
error-message catalog, "a collection of Elm programs that trigger error messages", so the messages can
keep improving, and gives colour two jobs: red draws attention to the problem, blue separates one
message from the next. rustc's guide: a diagnostic's message "should be general and able to stand on
its own", a primary label must make sense if it "were the only thing being displayed (for example, in
an IDE)", and messages stay succinct because "Users will see these error messages many times", with
the longer explanation behind `--explain`; `help` shows "changes the user can possibly make to fix the
problem", `note` everything else. RFC 1644 (start date 2016-06-07) keeps the error code "as a way to
help improve search results", aims at a format that "works well for new developers, post-onboarding,
and experienced developers without special configuration", and proposes ending with a tally and the
next command ("note: compile failed due to 2 errors. You can compile again with `--explain errors`
for more information"); rustc's own runs end "aborting due to N previous errors". (P)
[as-of 2026-10-01]

**Colour.** `NO_COLOR` (no-color.org, updated 2026-09-29): when present and not empty, whatever its
value, suppress ANSI colour; command-line flags and user configuration override it; it does not
disable bold or underline. `FORCE_COLOR` (force-color.org, 2026-09-10): when present and not empty,
force colour; its sample applies `NO_COLOR`, then options, then `FORCE_COLOR`. `CLICOLOR` and
`CLICOLOR_FORCE` (bixense.com) are deprecated in favour of the two. Node and chalk treat
`FORCE_COLOR=0` as "off" and 1–3 as colour depths, which conflicts with force-color.org's "any
non-empty value forces colour". `FORCE_COLOR` was "proposed in 2023" because piping through `less`,
`grep` or `tee`, and CI runners detected as non-interactive, turn colour off, and a program piping
output internally "can't externally use --color". no-color.org asks software that colours by default
to "consider not doing so", tells software that does not "you do not need to bother with this
standard", and calls the variable "a hint to the software running in the terminal … not to the
terminal". The deprecated CLICOLOR standard treats empty variables "as though they were unset", asks
software that supports it to treat `FORCE_COLOR` as an alias of `CLICOLOR_FORCE` unless `NO_COLOR` is
set, and maps flags: `--color`, `--color=always` or `--color=on` force colour, `--color=never` or
`--color=no` act as `NO_COLOR`, `--color=auto` colours only on a terminal. Node also honours
`NODE_DISABLE_COLORS`. (S) In tools: Homebrew's `HOMEBREW_NO_COLOR` defaults to `$NO_COLOR`,
pre-commit's `--color` takes `auto`, `always` or `never`, and rbenv-doctor colours only when
`[ -t 1 ]`. (L) [as-of 2026-10-01]

**Onboarding conventions.** GitHub's "Scripts To Rule Them All": `script/bootstrap`, `setup`,
`update`, `server`, `test`, `cibuild`, `console`, so contributors "only need to know the pattern";
linting goes first in `script/test` so it fails faster; the pattern has no doctor script. Each
script "is responsible for a unit of work" that other scripts call: `script/setup` puts a fresh clone,
or a reset project, in its initial state and so shows "that your bootstrapping actually works";
`script/update` typically runs bootstrap and then any migrations; `script/update` "should be called
ahead of any application booting" by `script/server`; `script/cibuild` is the CI entry point and
`script/console` opens a console. (P) [as-of 2026-10-01] The Dev
Container specification promises repeatable setup and consistency across developers and CI.
*Software Engineering at Google*, chapter 3, addresses onboarding culture (mentors, six months to
ramp up) and says nothing about diagnostic tooling.

**For agent readers.** The graded evidence is practice S6 and §6 of
[writing-for-models.md](writing-for-models.md); in brief, scripts agents run should be
non-interactive and self-documenting, with actionable errors, structured stdout kept apart from
stderr diagnostics, idempotent behaviour, a dry run, meaningful exit codes and bounded output; "An
opaque 'Error: invalid input' wastes a turn" [other-labs-23] (P). Tool responses should carry
actionable errors rather than opaque codes, truncation that tells the agent how to narrow its
request, sensible pagination and filter defaults, and a concise/detailed switch [deterministic-13]
(L). Custom lint messages "inject remediation instructions into agent context" [deterministic-2]
(L). Wrap noisy tools so the agent never reads walls of passing output: a one-line pass on success,
the focused failure otherwise [deterministic-5, practitioners-10] (A). CLIs rewritten for agents
offer machine-readable output, runtime schema introspection, input validation that treats agent
input as adversarial, and `--dry-run` before mutations [deterministic-20] (A). Input length alone
degraded model performance by 13.9–85% even with perfect retrieval [research-12] (M); structured
interfaces made repeated attempts more consistent [deterministic-29] (M). Hiding output can make
what the agent sees diverge from what happened [latent-space-5] (A).

**Reports that do not inflate.** Readiness tools that count well: skip, not fail, criteria whose
layer is not enabled [repo-readiness-audits-9]; report a dimension that did not run as n/a and average
only over what ran [repo-readiness-audits-11]; record each executed command with its working
directory, result and artifacts, and count a capability only when a check proved it ("A command that
was not executed is a claim") [repo-readiness-audits-16]; record environment blockers apart from the
repository's own failures [repo-readiness-audits-18]; list the platform controls a scan cannot see
(branch protection, required status checks, environment approvals) under "Not verified from
repository contents", so their absence never reads as a pass [repo-readiness-audits-20]. (A)

## 3. Traps in check and install commands

Each of these was observed in a real check or install command. Those marked (O) were reproduced in
one project's own engine, its reviews or probes; the unmarked ones under Reporting are one
observation each (A).

### Reporting

- An installer exits non-zero when the harness it installed for would not load what it wrote; a
  count of files written establishes nothing about loading. Installed, loaded and executed are three
  facts, and writing files establishes only the first.
- A repeated flag (`--harness a --harness b`) is accepted as a list or refused, never silently
  reduced to its last value.
- Every documented command runs from where its reader stands: one that assumes the tool's own
  directory is on the import path fails from the reader's checkout with `No module named …`.
- A report's "not checked" line names only a fact the command could not check itself.
- An exit code is a verdict, never a count of rows in an unexpected state; commands that ship
  together share one status vocabulary and take their input in one form.
- A flag the route does not support is refused, never silently ignored and reported as honoured.
- A recorded observation (which CI system a project uses) is refreshed, or it goes stale while still
  being read; an absent key means "never observed" and an empty list "observed none", and a reader
  keeps them apart.
- A reader refuses a format version it does not know rather than misclassifying newer records. A
  reader older than the records it meets either misreads them or refuses everything: a released
  reader with no dispatch for a new record kind classified those rows by their bytes, reported
  `unchanged` on rows it had never verified and exited 0 (4 only under `--strict`), and one new
  field under its schema's `additionalProperties: false` made it refuse the whole manifest (O).
  Upgrade every gate that reads the records before any writer emits a
  new kind or field.
- A record of the commit that contains it can never match: an install check that compared a committed
  source receipt with the running commit failed on every later commit, and re-recording the source at
  one commit commits a receipt the next commit fails against (O). Record what does not
  change with the commit, such as content digests, or check ancestry.
- A status mark is chosen from the verdicts on its line, in one place. One engine took a line's mark
  from its template and printed the passed mark beside `FAIL` on three surfaces: a release checklist
  whose version check failed, a policy plan that returned `FAIL`, and a line that said only that
  detection had run (O). The passed mark belongs only to a non-empty list holding `PASS`
  alone; a failure, an UNVERIFIED, or a line that names no check takes another.
- A mark is chosen by what the output stream can encode. A script that printed an emoji mark to a
  stream whose encoding was ASCII (`PYTHONIOENCODING=ascii`) raised `UnicodeEncodeError` and exited
  1 (O; reproduced on Python 3.14.7 [as-of 2026-10-01]). Encode the mark with the stream's
  encoding first and fall back to an ASCII mark where that fails; the word beside it carries the
  verdict either way.
- An empty base reference, such as an unset CI variable, is refused or read as UNVERIFIED: passed
  through, it produced a green run that compared nothing.
- `--quiet` does not change the exit code; grep's `-q`, which exits 0 on a match even after an error,
  is the trap to avoid.

### Running a project's commands (C15)

- **Timeouts kill the process group.** "If the timeout expires, the child process will be killed and
  waited for" (L, Python `subprocess`): only the child. On Python 3.14.7 a command that started a
  grandchild and timed out under `subprocess.run(timeout=…)` left the grandchild running, while one
  started with `start_new_session=True` and ended with `os.killpg` left nothing (O) [as-of
  2026-10-01]. In one runner, a check that spawned a 120-second grandchild left it running until the
  runner exited; with the check in its own process group, ended whole at the limit, it timed out at
  2 s with the grandchild gone (O). A check that times out reads UNVERIFIED, with no exit code.
- **The runner's environment stays its own.** A runner that set `GIT_OPTIONAL_LOCKS=0` process-wide
  for its own Git calls passed it to every project command it ran; set such variables in the
  environment of the runner's own calls only ([git.md](git.md) §9).
- **Evidence files cannot collide.** Log file names derived from check names collided after
  sanitizing (`a b` and `a-b`), and one check's log overwrote the other's evidence. Give each run a
  fresh, exclusively created directory and each check an index; a failed log write makes the evidence
  UNVERIFIED and never changes a command's FAIL, and a result never names a log that was not written.
- **Identify a tool by its version, not its bytes.** Hashing a launcher binary as a check's identity
  (a `node` binary is on the order of 100 MB) cost a full read per check and recorded nothing about
  the version; probe the version instead. Other costs met in the same runner: re-hashing every tracked
  file under the selected roots took about 0.4 s for 198 files a pass, and one check run made four
  Git snapshots and three such passes; finding a file's released copies by `git tag --list` and one
  `git show` per file per tag grows as files × tags (O).

### Writing into a project (C14)

- **Paths a writer may touch.** A check that refuses `.git` only in lower case admits
  `.GIT/hooks/pre-commit`, `.Git/config` and `.git./x`, each of which is `.git` on a case-insensitive
  file system (macOS by default, Windows) or one that drops trailing dots and spaces (Windows) (O,
  probes; on a case-insensitive macOS volume `.GIT/config` opened `.git/config`
  [as-of 2026-10-01]). Microsoft's guidance: "Do not assume case sensitivity", and "Do not end
  a file or directory name with a space or a period" (L). Refuse any path segment for which
  `segment.casefold().rstrip(". ") == ".git"`.
- **Symbolic links.** A committed link let an archive command write its summary outside its
  directory; Python's `Path.is_symlink()` inspects only the final component, so a glob match reached
  through a linked parent passed a leaf-only check; and one link gave two answers, a literal target
  admitted because it resolved inside the root while a glob through the same link was dropped (O).
  Resolve each path, check every ancestor, refuse one that leaves the root
  or passes through a link, and treat literal and glob paths alike.
- **Safe writes.** A write that must not damage the project refuses a link anywhere on its path,
  stages the new bytes in a file opened exclusively (`O_EXCL`), `fsync`s it, moves it into place with
  `os.replace`, and re-checks the bytes of the file it replaces, so a hand edit made since it was read
  is refused rather than lost; the tool's own records are written the same way, and last (O). Such a
  journaled apply cost, at p50/p95 over ten trials after three
  warmups with 4 KiB files on Python 3.14.7 and macOS arm64, 2.392/2.782 ms for 2 files,
  17.475/18.468 ms for 25 and 65.615/66.873 ms for 100, and a no-op run 0.259/0.333, 1.782/2.604
  and 6.750/7.779 ms: linear in the files and dominated by `fsync` (O, one local sample).
- **Matching bytes are not ownership.** An installer that recognised a developer's own `CLAUDE.md`,
  holding only `@AGENTS.md`, as the pointer it would have written took the file into its records and
  deleted it on removal. Record only what the installer wrote; observe everything else and leave it.
- **Directives are lines, not substrings.** A substring test for a directive matched prose, comments,
  code samples and longer names: `@AGENTS.md` in a sentence read as "already routes", `@AGENTS.md.bak`
  matched, and a managed-block marker quoted inside a fenced code sample blocked adoption. Match a
  line-anchored directive outside fenced blocks.
- **One file, many spellings.** On a case-insensitive or Unicode-normalizing file system,
  `CLAUDE.md`, `claude.md` and `CLAUDE.MD`, or the NFC and NFD spellings of one name, are one file;
  an installer that compared names exactly appended into a file another record owned. Compare
  destinations under NFC and case folding, and refuse a path that is another's ancestor.
- **Names and paths from input.** Python's `$` "Matches the end of the string or just before the
  newline at the end of the string" (L, Python `re`), so `^[a-z0-9-]+$` accepts a name followed by a
  newline, and such a name can end a skill's YAML frontmatter early; in one engine's input checks,
  four terminal-newline names and six paths holding control characters passed (O). Use
  `re.fullmatch` or `\Z`, and refuse ASCII control characters and DEL in names and paths before
  rendering them or touching the file system. A path holding a NUL byte raises `ValueError`, not
  `OSError` (`lstat: embedded null character in path` on 3.14), so a command that catches only
  `OSError` stops on a traceback; refuse such a value where it is read (O, Python 3.10 and 3.14)
  [as-of 2026-09-25]. Keep a configuration file's stricter path grammar off paths Git reports: a
  staged `src/a:b.txt` aborted a run that applied it (O).
- **What an install adds can ship.** In one adopting repository the project's own build packaged
  every entry under `.agents/skills`, so a skill copy an installer put there would have shipped to
  that project's users. Build the project's packages offline before and after an install and compare
  them; there, they came out identical except for an intended exclusion of the install's own
  directory (A).

### Updating installed files (C14)

Five defects of one merge-based updater, each reproduced in a scratch copy (O):

- A three-way update needs a verified base: with an unverified base cache, an upgrade deleted a local
  instruction and reported zero conflicts.
- Keep three facts per file apart, what upstream offers now, the base last accepted and the bytes the
  project uses, and advance the base only when an upstream change is accepted: a frozen file whose
  base advanced lost the pending change while its version marker moved.
- Extend the inventory rather than rebuild it from the current run: rebuilding dropped one harness's
  installed skill when a second harness was added, and an edit to that skill then passed the drift
  check.
- An untouched older copy of a file was refused as a local edit.
- A path collision found after the first file was written left an instruction file pointing at a
  skill that was never installed: check every destination before the first write, detect an
  interrupted apply before planning again, and treat a file at an expected path as unowned until a
  record says otherwise.

Refusing any file whose bytes differ from its record avoids most of these, at the cost of merging.
Compare files that execute as exact bytes: hashing whitespace-normalized text let an update drop a
space inside a Python multi-line string in an installed helper, and a normalized digest calls a file
that differs only by CRLF or trailing spaces unchanged, so a removal decided on it can delete bytes no
digest authenticated (O).

## How to apply

A check command a person, a script, CI and an agent can all act on:

1. **Verdicts.** PASS, FAIL or UNVERIFIED per check; a check that could not run, or whose evidence is
   missing, is UNVERIFIED, never PASS and never FAIL (C2). A deliberate "not set up" is shown with its
   recorded reason and where it is recorded, and does not change the exit code; if the recorded
   decision does not match what is installed, the row becomes UNVERIFIED (C9). A decision nobody
   recorded is not a decline: with no record, a candidate the evidence names reads "not decided"
   (UNVERIFIED), an installed component needs no record, and nothing is inferred as declined from an
   absence. One engine's setup step defaulted a decision to "none" and kept no record, so a
   deliberate absence could not be told from a question never asked (O). A recorded
   decline carries its reason, who and when, and one whose subject is no longer observed is reported
   stale, as Rust's `#[expect]` reports an unfulfilled expectation (L).
2. **Human output on stdout, in order.** A header with the target and the versions compared (no
   digests); one line per check, `STATUS  name — short detail`, with the word, not only a glyph, so it
   survives no-colour terminals and grep; under each non-PASS line what was observed (a path or
   ref), why it matters in one sentence, and exactly one thing to do as a copyable command; detail
   behind `-v`; a closing tally and the next commands last (C1, C5, C10). The next commands are ones
   that exist, the project's own entry points first where it has them (`script/bootstrap`,
   `script/test`), so contributors "only need to know the pattern" (P). Progress and notes go to
   stderr, only on a TTY.
3. **Exit codes.** 0 when every check passes; 1 when at least one FAILs; 2 when none fails but at
   least one is UNVERIFIED; a distinct code for an internal crash and for a usage error (pytest uses 3
   and 4; `sysexits.h` uses 70 and 64); never a count; documented in `--help` (C3, C4). When FAIL and
   UNVERIFIED both occur, FAIL decides the code and the JSON carries both counts.
4. **JSON on request.** One document on stdout: a schema or format version, the overall status, the
   exit code, counts per status, and one record per check with its id, title, status, what was
   observed, why, the remedy (text, commands, and whether it can be applied mechanically), any
   recorded reason for not setting it up, links, and the rendered human line; omit the remedy on
   PASS. The text report is rendered from these records, so the two cannot drift (C6).
5. **Read-only.** A check writes nothing; a fix is a separate command that shows what it will change
   and asks, or takes `--accept` (C7).
6. **Network.** Offline by default or switchable, with a network failure reading UNVERIFIED and
   saying which check needed the network (C13).
7. **For agents.** Quiet on success, failures only with their fix, bounded length, no prompts, and
   stable machine output (C11).
8. **Run every check, and stay quiet about what nobody chose.** A check whose input cannot be read
   becomes one UNVERIFIED row carrying the error, and every other check still runs: flyctl stops
   after a failed authentication check and hides what else is wrong, and in Capacitor one thrown
   error ends the run. A component nobody selected produces no finding: Homebrew's source says "a
   default install should not trigger any brew doctor messages", and chezmoi's sixteen
   secret-manager rows show the cost of listing every optional tool. Put such components in an
   inventory section or under `-v` (L, read 2026-09-22 and 2026-10-01).
9. **Running and writing.** Run a project's commands in their own process group and end the group
   at the limit; write into a project only through exclusive staging and `os.replace`, after checking
   every destination, and only files the tool's records say it owns (C14, C15).

## Limits and open questions

- The catalog is a reading of documentation and source on 2026-09-22, re-read on 2026-10-01 only for
  the claims added that day; for several tools the run-time exit
  code is UNVERIFIED (Flutter with issues, tauri, wails, React Native non-interactive, storybook,
  jenv, the yarn doctor package), as are `conda doctor --json`'s effect, Claude Code's `claude doctor`
  layout, vocabulary and exit codes (only an `OK` row is documented), and pre-commit's `SKIP`
  variable (from memory, not quoted).
- Documentation pages could not be reached for `bundle doctor`, `sl doctor`, `cap doctor`, `bit
  doctor` and `hg debuginstall`, and `rustup check` is absent from the rustup book pages read; their
  source was read instead. "12 Factor CLI Apps" was read from an archived capture.
- Documentation and source disagree often enough that a tool's exit behaviour has to be read from
  its source or observed. bundler's man page says that when issues are detected it "prints them and
  exits status 1", but its source raises only for broken links to dynamic libraries, and a permission
  warning suppresses the success line yet exits 0; `hg debuginstall`'s docstring says "Returns 0 on
  success." while the command returns the number of problems; Expo's config comment says its React
  Native Directory check defaults to off, while its docs page and its code (on from SDK 52) say on;
  and Flutter's `ExitStatus.warning` reaches only timing labels in the source read. (L, O)
- The re-reading of 2026-10-01 found tools that had moved or changed since 2026-09-22: Capacitor runs
  all checks of a platform rather than stopping at the first, Homebrew's build-environment subset is
  empty, pre-commit's and Composer's wording changed, Flutter's diagnostic types moved to a new
  package, bundler moved to the repository root and gained an `ssl` check, conda gained `--fix`, and
  Mercurial's GitHub mirror path is gone (read from its own host). The §1 tables are a snapshot.
- Pages that render by JavaScript or not at all were read from their sources: the Elm post, the
  rustc dev guide, and the npm and Expo docs; bundler.io rendered empty. The Google SRE Workbook was
  not consulted.
- The traps of §3 come from one project's engine, its reviews and probes; each is a mechanism shown
  once, not a rate.
- No source measures whether any of these conventions changes what a person or an agent does next.

## Sources

Read 2026-09-22 from docs and source on each project's default branch:
[clig.dev](https://clig.dev/);
[12 Factor CLI Apps](https://web.archive.org/web/2019id_/https://medium.com/@jdxcode/12-factor-cli-apps-dd3c227a0e46);
[IETF draft-inadarei-api-health-check-06](https://www.ietf.org/archive/id/draft-inadarei-api-health-check-06.txt);
[GNU Coding Standards](https://www.gnu.org/prep/standards/standards.html);
[BSD sysexits.h](https://raw.githubusercontent.com/freebsd/freebsd-src/main/include/sysexits.h);
[GNU grep](https://www.gnu.org/software/grep/manual/grep.html);
[GNU diffutils](https://www.gnu.org/software/diffutils/manual/diffutils.html);
[ShellCheck man page](https://github.com/koalaman/shellcheck/blob/master/shellcheck.1.md);
[git-bisect](https://github.com/git/git/blob/master/Documentation/git-bisect.adoc);
[pre-commit](https://pre-commit.com/);
[pytest exit codes](https://docs.pytest.org/en/stable/reference/exit-codes.html);
[rustc dev guide, diagnostics](https://rustc-dev-guide.rust-lang.org/diagnostics.html);
[Rust RFC 1644](https://github.com/rust-lang/rfcs/blob/master/text/1644-default-and-expanded-rustc-errors.md);
[Rust Reference, diagnostic attributes](https://doc.rust-lang.org/reference/attributes/diagnostics.html);
[Elm, Compiler Errors for Humans](https://elm-lang.org/news/compiler-errors-for-humans);
[no-color.org](https://no-color.org/); [force-color.org](https://force-color.org/);
[CLICOLOR](https://bixense.com/clicolors/); Node.js `tty` docs and chalk/supports-color;
[Scripts To Rule Them All](https://github.com/github/scripts-to-rule-them-all);
[Software Engineering at Google, ch. 3](https://abseil.io/resources/swe-book/html/ch03.html);
[Dev Container overview](https://containers.dev/overview).
Tools: Homebrew (`cmd/doctor.rb`, `diagnostic.rb`, `diagnostic/finding.rb`, manpage); Flutter
(`doctor.dart`, `doctor_validator.dart`, `diagnostics.dart`, `features.dart`,
[CLI reference](https://docs.flutter.dev/reference/flutter-cli)); [npm doctor](https://docs.npmjs.com/cli/v11/commands/npm-doctor)
and `lib/commands/doctor.js`; [Expo Doctor](https://docs.expo.dev/develop/tools/) and
`packages/expo-doctor`; [mise doctor](https://mise.jdx.dev/cli/doctor.html) and
`src/cli/doctor/mod.rs`; [nix config check](https://nix.dev/manual/nix/latest/command-ref/new-cli/nix3-config-check)
and the 2.20 release notes; Claude Code [CLI reference](https://code.claude.com/docs/en/cli-reference),
[commands](https://code.claude.com/docs/en/commands) and
[troubleshooting](https://code.claude.com/docs/en/troubleshooting);
[conda doctor](https://docs.conda.io/projects/conda/en/latest/commands/doctor.html); WP-CLI
`doctor-command` README and handbook; bundler `bundle-doctor.1.ronn`;
[chezmoi doctor](https://www.chezmoi.io/reference/commands/doctor/) and `doctorcmd.go`;
[cdk doctor](https://docs.aws.amazon.com/cdk/v2/guide/ref-cli-cmd-doctor.html);
[tilt doctor](https://docs.tilt.dev/cli/tilt_doctor.html); [skaffold](https://skaffold.dev/docs/references/cli/);
[pulumi about](https://www.pulumi.com/docs/cli/commands/pulumi_about/);
[tauri](https://v2.tauri.app/reference/cli/); wails `cli.mdx`; Capacitor `doctor.ts`;
[Jekyll](https://jekyllrb.com/docs/usage/); [dvc doctor](https://doc.dvc.org/command-reference/doctor);
React Native `cli-doctor`; Sapling `doctor.py`; [pnpm doctor](https://pnpm.io/cli/doctor);
`@yarnpkg/doctor`; [storybook](https://storybook.js.org/docs/api/cli-options);
[composer diagnose](https://getcomposer.org/doc/03-cli.md#diagnose);
[symfony requirements](https://symfony.com/doc/current/setup.html) and requirements-checker;
[gh auth status](https://cli.github.com/manual/gh_auth_status); rustup `rustup_mode.rs` and `help.rs`;
git-lfs `git-lfs-env.adoc`; [flyctl doctor](https://fly.io/docs/flyctl/doctor/); `nvm.sh`;
rbenv-installer `rbenv-doctor`; pyenv-doctor; jenv `jenv-doctor`;
[dotnet](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet) and `dotnet-sdk-check.md`;
envinfo README; [next info](https://nextjs.org/docs/app/api-reference/cli/next);
[nx report](https://nx.dev/reference/core-api/nx/documents/report); bit `doctor-cmd.ts`;
Mercurial `debugcommands.py`; [pip check](https://pip.pypa.io/en/stable/cli/pip_check/);
[poetry check](https://python-poetry.org/docs/cli/#check);
[gcloud info](https://docs.cloud.google.com/sdk/gcloud/reference/info). Evidence records for agent
readers and readiness tools: `_evidence/2026-09-25.jsonl`, read 2026-09-25.

Re-read 2026-10-01 for the claims added or corrected that day: the IETF draft, clig.dev, the archived
"12 Factor CLI Apps", `sysexits.h`, GNU grep, `git-bisect.adoc`, pre-commit (`run.py`,
`error_handler.py`, `color.py`, `main.py`), rustup `help.rs`, the rustc dev guide, RFC 1644, the Elm
post's source, force-color.org, no-color.org, bixense.com, Node `tty.md`, Homebrew (`Manpage.md`,
`cmd/doctor.rb`, `diagnostic.rb`, `diagnostic/finding.rb`, `utils/output.rb`), Scripts To Rule Them
All, Flutter (`doctor.dart`, `doctor_validator.dart`, `commands/doctor.dart`,
`flutter_tools_core/lib/src/diagnostics.dart`), Claude Code's
[commands](https://code.claude.com/docs/en/commands),
[troubleshooting](https://code.claude.com/docs/en/troubleshooting),
[debug-your-config](https://code.claude.com/docs/en/debug-your-config) and
[CLI reference](https://code.claude.com/docs/en/cli-reference), chezmoi `doctorcmd.go`, mise
`src/cli/doctor/mod.rs`, pnpm, Expo (`src/index.ts`, `src/doctor.ts`, `utils/doctorConfig.ts`,
`utils/checkResolver.ts` and the docs), npm, WP-CLI's README and handbook, conda (`doctor.rst`,
`plugins/types.py`), Composer (`DiagnoseCommand.php`, `ValidateCommand.php`), `gh` `status.go`,
flyctl `doctor.go`, jenv, rbenv-doctor, storybook, tauri `info/mod.rs`, React Native `cli-doctor`,
Sapling `doctor.py`, pyenv-doctor, Jekyll, poetry `check.py`, `dotnet-sdk-check.md`, Mercurial
`debugcommands.py` (from its own host), wails v3 `doctor.go`, bit `doctor-cmd.ts`, envinfo, gcloud
info, `nvm.sh`, cdk `doctor.ts`, tilt `doctor.go`, Nix, bundler (`bundle-doctor.1.ronn`,
`cli/doctor/diagnose.rb`, now under the repository root), Capacitor `common.ts`, and the Rust
Reference's diagnostic attributes. For §3: Python's [`subprocess`](https://docs.python.org/3/library/subprocess.html)
and [`re`](https://docs.python.org/3/library/re.html) documentation and Microsoft's
[Naming Files, Paths, and Namespaces](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file),
read 2026-10-01; one project's engine, its reviews, work records and probes.
