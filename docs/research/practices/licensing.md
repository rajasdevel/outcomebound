---
last_checked: 2026-10-02
volatility: STABLE (licence texts, §§1–7) / VOLATILE (§8 AI training, court rulings and platform terms)
sources:
  - https://www.apache.org/licenses/LICENSE-2.0
  - https://www.apache.org/foundation/license-faq.html
  - https://spdx.org/licenses/LLVM-exception.html
  - https://opensource.org/license/mit
  - https://opensource.org/osd
  - https://www.mozilla.org/en-US/MPL/2.0/
  - https://www.gnu.org/licenses/agpl-3.0.html
  - https://fsl.software/
  - https://mariadb.com/bsl11/
  - https://www.elastic.co/licensing/elastic-license
  - https://creativecommons.org/licenses/by/4.0/legalcode.en
  - https://creativecommons.org/faq/
  - https://wiki.creativecommons.org/wiki/Marking/Creators/Marking_third_party_content
  - https://developercertificate.org/
  - https://www.law.cornell.edu/uscode/text/17/107
  - https://www.law.cornell.edu/treaties/berne/10.html
  - https://www.copyright.gov/ai/
  - https://docs.github.com/en/site-policy/github-terms/github-terms-of-service
  - https://eur-lex.europa.eu/eli/dir/2019/790/oj
  - https://supreme.justia.com/cases/federal/us/499/340/
  - https://www.legislation.gov.uk/ukpga/1988/48/section/30
  - https://www.gesetze-im-internet.de/englisch_urhg/englisch_urhg.html
---

# Licensing a contract, its engine and a research library

Re-check when a licence steward publishes a new version (Apache, Creative Commons, Mozilla, OSI's
definition), a court rules on model training or on copying by agents, GitHub changes its terms of
service, or a project's commercial strategy changes.

How to license three kinds of work that coding-agent projects produce: text written to be copied into
other repositories (instruction files, skills, templates), the software that installs it, and a
research library of original prose, evidence records quoting third-party sources, and automation
code. It also covers contributions (DCO or CLA), trademarks, and what licences can and cannot say
about AI. It is for a maintainer choosing or revisiting a licence, and for an agent asked what a
licence lets a user do.

**Evidence classes.** (S) a licence or statute text; (L) a licence steward's or platform's own
guidance (Apache FAQ, Creative Commons FAQ and wiki, OSI, GitHub); (M) a court ruling or an
agency report; (O) a count made in this library's own evidence ledgers on 2026-10-02. Not legal
advice: the sections name where a lawyer is needed.

## Key findings

**LI1. Apache-2.0 fits a permissive tool whose text other companies copy.** It grants copyright and
patent licences, ends the patent licence of anyone who sues over the work (§3), withholds trademarks
(§6), makes a contribution arrive under the same licence unless stated otherwise (§5), and defines
Source form to include documentation (§1), so one licence can cover a contract, its skills and its
engine. (S)

**LI2. Every common permissive licence makes a redistributor carry notices.** Apache-2.0 §4 asks
whoever redistributes the work or a derivative to (a) give recipients a copy of the licence, (b) mark
changed files, (c) keep copyright and attribution notices, and (d) pass on the NOTICE file's
attributions. MIT requires its notice "in all copies or substantial portions"; CC BY requires
attribution. Apache's conditions sit in its Redistribution section (§4), so they bite when copies are
distributed; where internal sharing ends is a lawyer's question. Only a public-domain-style
grant (CC0, MIT-0, 0BSD) or an added exception removes the duty. (S)

**LI3. An additive exception can lift those duties for text meant to be embedded.** The LLVM
exception to Apache-2.0 lets portions embedded in compiled output be redistributed without §4(a),
(b) and (d) when compiling embeds them in object code. By analogy, an exception can cover the text an
installer writes into adopters' repositories, keeping one licence, the patent grant and the
disclaimer. An exception only adds permission; SPDX writes the result as
`Apache-2.0 WITH <exception>`, and a custom exception is not on SPDX's list and wants a lawyer's
reading. (S)

**LI4. Copyleft reaches the adopter's own files.** Under MPL-2.0 a Modification includes "any new
file in Source Code Form that contains any Covered Software" and must stay under MPL (§1.10, §3.1),
so an `AGENTS.md` carrying MPL text would become MPL; GPL and AGPL reach further, and AGPL's
network clause adds nothing for text. Choose copyleft only for deliberate reciprocity. (S)

**LI5. Source-available licences are not open source.** BUSL restricts production use until a
change date, FSL restricts competing uses and converts to Apache-2.0 or MIT after two years, and the
Elastic License 2.0 forbids offering the software as a managed service. They protect a product
against a competitor or a cloud host, and every adopter carries their terms. (S, L)

**LI6. Under Apache-2.0 a CLA adds little; under copyleft it decides dual licensing.** The DCO
certifies that a contributor may submit the change under the project's licence; it assigns nothing.
Apache-2.0's grant includes the right to sublicense (§2), and §4 lets a distributor license
"any such Derivative Works as a whole" under different terms while keeping the notices, so a
maintainer can ship contributed Apache code inside later versions under other terms without a CLA.
Nobody can withdraw the Apache grant on versions already published, so anyone may fork the last
Apache version whatever the paperwork. A CLA matters where the inbound licence is copyleft or
non-sublicensable (a GPL project selling commercial licences needs ownership or a broad grant), and
as provenance. A lawyer should confirm before relying on relicensing. (S, L)

**LI7. CC BY 4.0 suits prose and data; it is not for software.** It licenses sui generis database
rights (§4), lets attribution be given "in any reasonable manner based on the medium, means, and
context" (§3(a)(2)), excludes patent and trademark rights (§2(b)(2)), and is non-sublicensable:
every recipient takes the licence directly from the licensor (§2(a)(1), §2(a)(5)). Creative Commons
"recommend[s] against using Creative Commons licenses for software" while allowing them for software
documentation, so a repository holding prose, data and code can license its code under Apache-2.0
and the rest under CC BY 4.0. (S, L)

**LI8. Nobody can license someone else's quotation.** A licence covers only the licensor's own
material; Creative Commons advises marking third-party content and gives "Except where otherwise
noted, this work is available under [license]" as a sample notice. Reuse of a quotation rests on the source's own terms or a legal exception: US
fair use weighs purpose, the nature of the work, amount and market effect (17 U.S.C. §107), and the
Berne Convention lets member states permit quotation from a work lawfully made available to the
public, compatible with fair practice, no longer than the purpose justifies, naming the source and
the author if it appears on the work (Art. 10(1), 10(3)). Facts themselves are not protected (Feist
v. Rural, 499 U.S. 340 (1991)). A per-record verdict that a
claim is supported says nothing about the right to quote it. (S, L)

**LI9. No open licence can forbid model training.** A field-of-use restriction breaks the Open
Source Definition (§6, no discrimination against fields of endeavour). (S, L; the rest of this
finding is VOLATILE, §8)

**LI10. Text an agent wrote may carry thin copyright.** The US Copyright Office's January 2025
report concludes that copyright protects human authorship and that, "given current generally
available technology", prompts alone do not make the user the author of the output; AI used to
assist rather than stand in for human creativity does not affect protection, and human selection,
arrangement and modification remain protectable, case by case. A licence on largely agent-written
prose may be weaker than it looks; a project's durable assets are its name, the currency of its data
and its software. (M)

## 1. Choosing by what the work is for

| Goal | Licence shape |
| --- | --- |
| Most adoption by companies, text copied into their repositories | Apache-2.0 (patent grant, trademark carve-out), plus an exception for the embedded text (LI3), or MIT-0/CC0 if attribution and patents do not matter |
| Changes to the work must stay open | MPL-2.0 (file-level) or GPL/AGPL; accept that adopters' files may fall under it (LI4) |
| Open core: a public foundation, a private product built on it | Permissive foundation; keep the differentiating parts private. Competitors get the same public permissions |
| Protect a product from a competitor or a host | Source-available (LI5), with a CLA from the first contribution; adoption suffers |
| Prose and research data, with attribution | CC BY 4.0 for prose and data, Apache-2.0 for code (LI7) |
| No attribution wanted at all | CC0 for content, MIT-0 or 0BSD for code; no patent grant |

## 2. Text that gets copied into other repositories

Instruction files, skills and templates are meant to be copied; the licence decides what every copy
carries. Apache's duties bite on distribution (LI2): a public repository or a client delivery
distributes. With plain Apache-2.0 the adopter owes the licence copy and the NOTICE attributions
(LI2). Two ways to spare it: an exception in the licence (LI3), which costs no file and no token in the
copied text, or an installer that writes the licence and NOTICE beside what it installs, which keeps
standard terms but adds files to every adopter and misses hand-copied text. A copied block that
carries no notice leaves §4(c) nothing to retain.

## 3. Comparing the permissive and copyleft choices

| Licence | Patent grant | Notice on copies | Reaches adopter files | Notes |
| --- | --- | --- | --- | --- |
| Apache-2.0 | yes, with termination | licence + NOTICE (§4) | no | §5 inbound = outbound; §6 trademarks withheld |
| MIT, BSD | no express grant | yes | no | shortest |
| MIT-0, 0BSD, CC0 | no | no | no | public-domain style |
| MPL-2.0 | yes | yes | files containing covered text | file-level copyleft |
| GPL-3.0, AGPL-3.0 | yes | yes | the whole conveyed work | AGPL adds network use |
| BUSL, FSL, ELv2 | varies | yes | n/a | not open source |
| CC BY 4.0 | excluded | attribution | no | database rights licensed; not for software |
| CC BY-SA 4.0 | excluded | attribution | adaptations | ShareAlike |

## 4. A research library with quotations

A library of original prose plus evidence records quoting sources holds three kinds of material:
the maintainer's prose and paraphrased claims (licensable), the compilation and its database rights
(licensable; CC BY 4.0 §4 covers them, Apache-2.0 does not say), and the quotations (not
licensable). Mark the third explicitly, in the licence section and beside the ledgers: the quote
field and quoted passages are the words of the named source, reproduced for verification, and not
licensed by the repository.

Exposure grows with the share of one work that is quoted, not with the number of records. In this
library's ledgers on 2026-10-02, 978 of 1,010 records carry a quote, median 167 characters
and longest 462; one prompting guide page is quoted in 28 records totalling about 4,800 characters,
and one newsletter site in 57 records (O). Review the most-quoted sources and trim each quote to
what its claim needs; a quotation inside prose deserves the same check.

## 5. Contributions: DCO or CLA

| | DCO | CLA |
| --- | --- | --- |
| What the contributor signs | a sign-off line certifying the right to submit | an agreement granting rights (sometimes assignment) |
| Friction | none beyond `git commit -s` | an agreement per person or employer, administered |
| Relicensing later, Apache project | possible for future versions as a derivative work (LI6); published versions stay Apache | the same, with clearer provenance |
| Relicensing later, copyleft project | needs every contributor's consent | possible if the CLA grants it |
| Dual licensing (copyleft + commercial), copyleft project | not possible for others' code | the usual basis |
| Forks of the last open version | always possible | always possible |

A CC BY 4.0 project has no Apache-style §5, so its contribution guide must state the inbound terms
(for example: text under CC BY 4.0, code under Apache-2.0, signed off under the DCO).

## 6. Trademarks

Apache-2.0 §6 grants no trademark rights beyond describing the work's origin and reproducing the
NOTICE file; CC BY licenses none (§2(b)(2)). Say in the README that
naming the project descriptively ("uses X") is fine and a fork ships under its own name. Clearance
and registration of a name are a lawyer's work.

## 7. What needs a lawyer

The wording of any custom exception; quotation law where the maintainer or the readers are outside
the US (quotation and fair-dealing law, for example UK CDPA s.30, German UrhG §51, Indian Copyright Act
s.52); trademark clearance;
any client contract touching the work (keep grants non-exclusive so public licences stay valid); any
relicensing after outside contributions.

## 8. AI training and agent copying (VOLATILE)

- A person reading a work needs no licence; automated reading makes copies, which is why the EU
  created text-and-data-mining exceptions (Directive 2019/790, Art. 3 and 4). Copying protected
  expression into a new file is copying whether a person or an agent does it, and the licence then
  governs the copy. (S)
- GitHub's terms of service (§D.4, "License Grant to Us") give GitHub the right to "store, host,
  archive, parse, display, and make copies of Your Content as necessary to provide, develop, and
  improve the Service, including by training AI Features, and for the purpose of training,
  developing, and improving artificial intelligence and machine learning models and technologies of
  our Affiliates"; it covers all Your Content, not only repositories, and §J.3 separately licenses
  inputs and outputs for training, with an opt-out. A licence term cannot take that back from a
  repository hosted there. (L, read 2026-10-02)
- Bartz v. Anthropic (N.D. Cal., 23 June 2025) held training "exceedingly transformative and … a fair
  use" but held the pirated central-library copies not fair use; the case settled in September 2025
  (reported at $1.5 billion). Kadrey v. Meta (N.D. Cal., 25 June 2025) granted Meta summary judgment
  on fair use while saying the ruling "stands only for the proposition that these plaintiffs made the
  wrong arguments", found the shadow-library sourcing did not change the result on that record, and
  left a distribution claim open. Both are trial-court rulings, not binding precedent. (M)
- The EU exception for text and data mining (Art. 4) applies unless rights holders have reserved
  their rights "in an appropriate manner, such as machine-readable means" for content online
  (Art. 4(3)); it is not limited to commercial mining. A project written for machines to read gains
  little by reserving that right. (S)

## Sources

Licence texts and steward guidance in the frontmatter, read 2026-10-02. Ledger counts in §4 come
from `_evidence/*.jsonl` (O).
