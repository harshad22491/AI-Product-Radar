# Fable adversarial editorial and product-value review

> Historical build-stage review. See [current verification](../VERIFICATION.md) for resolved findings and remaining blockers.

Ticket: [04 Adversarial editorial and product-value review](../wayfinder/tickets/04-adversarial-editorial.md)
Reviewer: Fable 5.1 (Claude subscription). Review date: 2026-09-15.
Scope: the proposed seven-item daily digest as specified in `docs/BUILD-CONTRACT.md`, `CONTEXT.md`, and the untracked draft modules `radar/domain.py`, `radar/render.py`, `radar/learning.py`, `radar/selection.py`. Documentation only; no code was changed and nothing was committed.

Method: every attack below was checked against the draft code by reading it. Command execution was not permitted in this session, so the reproduction script in Appendix A was written but not run. Line references point at the draft modules as they existed on the review date. Ticket 10 should run Appendix A and treat any "expected" line that does not match as a regression in this review, not in the code.

Parallel work read for consistency: `prompts/fable.md`, `prompts/astra.md`, `config/topics.json`, `config/sources.json`, `docs/reviews/astra-sources.md`, and `docs/reviews/fable-reliability.md`. Where the reliability review already defines a control, this review cites it (C-nn) instead of restating it, and the editorial criteria are written to nest inside those controls.

## Verdict

The digest as drafted would validate, render, and deliver, but it would not become a better newsletter over time and it would not resist filler. Five defects block acceptance:

1. **Ratings cannot change what is selected.** The relevance multiplier returns neutral for any item without its own rating, and delivered items are never reselected, so learned topic and repository weights are never applied to a new candidate. The email legend promises "suppress similar items" and "reduce similar items", which the code cannot do.
2. **Deduplication is defeated by ordinary URLs.** Tracking parameters, `www.`, and arXiv version or PDF variants each produce a different item ID, so the same source can be featured repeatedly and the "material release" exception has no test.
3. **The validator accepts filler.** Thirty single-vendor items with summary "TBD", empty topics, evidence label "verified", repository "any", and guidance strings carrying their own label prefixes pass validation.
4. **Repository examples are unverifiable.** The repository field is free text and repository evidence is optional, so every item can claim a connection to the owner's work without any.
5. **Novelty is self-declared.** The publish date is model-supplied and only checked against the freshness window, so an old post stamped with a recent date is "new".
6. **The prompts instruct the generic answer.** The Fable prompt defines the Where line as an "applicable domain" such as "inference servers", allows `repository: main-project`, asks for free-form topics like `ai`, and describes a general AI-industry research focus. None of this mentions the owner's repositories or the nine work topics in `config/topics.json`. The Astra validation path re-checks schema and dates only. A digest produced exactly as instructed would be disconnected from actual work.

The seven-item floor and the product-heavy mix are map decisions and are not relitigated here. The criteria below make them survivable.

## Attack findings

### A. Noise and filler

| # | Attack | Evidence | Consequence |
|---|--------|----------|-------------|
| A1 | Submit 30 items from one host with placeholder text. | `radar/domain.py:254` enforces only a lower bound of 7; `_text` at `:53` enforces only nonempty and a 20,000-character ceiling. No host, repository, or topic caps exist. | Filler is indistinguishable from findings at the accept gate. |
| A2 | Leave `topics` empty. | `radar/domain.py:298-301` accepts an empty list. `pair_weights` at `radar/learning.py:239-243` then records nothing for the item. | An item with no topics is invisible to learning and to diversity scoring. |
| A3 | Write `evidence_label: "verified"` for a vendor blog post. | `radar/domain.py:311` accepts any string. | The reader is told something was verified when nothing was. |
| A4 | Write guidance strings as "Where: ...". | `radar/render.py:80-83` prefixes labels itself. | Email shows "Where: Where: ...". Validator does not reject the prefix. |
| A5 | On a thin day, pad to seven with weak items. | `radar/selection.py:200-201` refuses to select fewer than the limit, but the cloud producer writes the bundle directly; nothing downstream measures item quality. | The floor creates pressure to invent, and the only guard is the producer's honesty. |

### B. Promotional bias

| # | Attack | Evidence | Consequence |
|---|--------|----------|-------------|
| B1 | Label everything `product`. | `radar/selection.py:116-119` adds 0.75 for product and 0.20 for tool. The rating multiplier is bounded to 0.75 to 1.25 of base score (`radar/learning.py:18-19`), and base scores are candidate-supplied (`radar/selection.py:56-63`). | A static type bonus outweighs the strongest possible rating signal. A reader who dislikes launch posts cannot demote them. |
| B2 | Supply `relevance: 9.0` on the model's own candidate. | `_base_score` at `radar/selection.py:56-63` trusts any numeric field on the candidate. | Self-scoring decides the digest. |
| B3 | Link the press release, the launch blog, the docs page, and the changelog for one launch. | Canonical URL dedupe is exact-path only (`radar/domain.py:134-178`). | One launch takes four of seven slots. |
| B4 | Use vendor superlatives in title and summary. | No lexical checks anywhere. | The digest reads as marketing. |

### C. Repetition

| # | Attack | Evidence | Consequence |
|---|--------|----------|-------------|
| C1 | Re-feature a delivered item via `?utm_source=x`. | `canonical_url` sorts query pairs but keeps them (`radar/domain.py:174-177`). | New item ID, passes the delivered check. |
| C2 | Re-feature an arXiv paper via `v2` or `/pdf/`. | No host-specific normalization. | Same paper, new ID, up to three times. |
| C3 | Re-feature through `www.` versus bare host. | Host is lowercased but `www.` is retained (`:164-169`). | New ID. |
| C4 | Feature "prompt caching" every day from a different URL. | Topic diversity is per edition only (`radar/selection.py:206-237`); nothing reads prior editions. | Daily sameness with distinct IDs. |
| C5 | Use the "material release" exception weekly. | Contract text only; no field records what changed or which earlier item is superseded. | Any changelog URL qualifies. |
| C6 | Rate "already knew". | Suppression at `radar/selection.py:191-193` removes only that item ID, which is already blocked as delivered. | The tag has no forward effect. |

### D. Technical language

| # | Attack | Evidence | Consequence |
|---|--------|----------|-------------|
| D1 | Paste the paper abstract as the summary. | "plain language" appears only in the contract prose. No sentence, acronym, or identifier checks. | Unreadable summaries validate. |
| D2 | Rate "too technical". | `rating_effects` at `radar/learning.py:288-290` emits `presentation: simplify`; nothing consumes it. | The tag does nothing. |
| D3 | Rate "not too technical at all". | Substring match at `:290` and `:132` of the two modules. | Triggers simplify and small-scope effects in reverse. |
| D4 | Write "Effort: quick" on a multi-day change. | `_effort_is_small` at `radar/selection.py:73-82` sniffs keywords in free text. | Effort preference is gamed by wording. The heading "Five-minute guidance" at `radar/render.py:104` contradicts multi-day effort lines. |

### E. Fake novelty

| # | Attack | Evidence | Consequence |
|---|--------|----------|-------------|
| E1 | Stamp a 2024 post with `published_at: 2026-09-10`. | `radar/domain.py:283-292` checks only not-future and within-window. `source_dates` is optional (`:38`). | Old content passes as fresh. |
| E2 | Call a 20-month-old paper "new". | Age is never rendered; only the raw date at `radar/render.py:96`. The glossary's "Useful discovery" label has no field or rendering. | The reader cannot tell discovery from news. |
| E3 | Feature a minor patch as a material release. | See C5. | Repeat coverage disguised as novelty. |

### F. Weak repository examples

| # | Attack | Evidence | Consequence |
|---|--------|----------|-------------|
| F1 | Write `repository: "your dashboard app"`. | `radar/domain.py:312` accepts any string up to 300 characters. | Nonexistent or vague repositories pass. |
| F2 | Omit `repository_evidence`. | Optional at `:38`. | No item has to point at a real path or commit. |
| F3 | Write "Where: anywhere in the codebase". | No lint. | Guidance stops being guidance. |
| F4 | Put all seven items on the same repository. | Only a 0.16 first-occurrence bonus (`radar/selection.py:125`). | Concentration is cheap. |
| F5 | Ignore the ten-day review output. | Nothing in the bundle links an item to a profile date or cursor. | The two halves of the product never meet. |

### G. Rating feedback loops

| # | Attack | Evidence | Consequence |
|---|--------|----------|-------------|
| G1 | Rate anything; watch the next digest. | `relevance_multiplier` returns neutral when the item itself is unrated (`radar/learning.py:262-264`). Selection calls it for unrated candidates (`radar/selection.py:112`). Delivered items are excluded (`:189-190`). | No rating ever changes a future selection. The loop is open, not runaway. |
| G2 | Rate a 5 daily. | `queue: experiment` at `radar/learning.py:291` has no cap and no expiry anywhere in the contract. | Unbounded proposal backlog. |
| G3 | Read the legend. | `radar/render.py:10-16` promises "suppress similar items" and "reduce similar items". | The product lies about what ratings do until G1 is fixed. |
| G4 | Try to rate item 5 from a phone. | The only rating affordance is the top panel (`radar/render.py:49-70`); cards carry the ID but no link. | Rating friction starves the loop. |
| G5 | Rely on exploration. | Every unrated candidate is "exploration" (`radar/selection.py:85-88`), so the bonus is uniform; the final-slot override at `:241-243` picks the first eligible unrated candidate in input order, not the best. | Exploration is arbitrary and can replace the most diverse pick. |
| G6 | Use topics "LLM", "llm", "large language models". | Pair keys casefold only (`radar/learning.py:201-202`). | Signal fragments across synonyms. |

### H. Overload

| # | Attack | Evidence | Consequence |
|---|--------|----------|-------------|
| H1 | Open on mobile. | The full legend, tag list, and button precede the first finding in HTML and text (`radar/render.py:118`, `:132-138`). | The first screen is instructions, every day. |
| H2 | Ship nine items. | Validator floor only; render loops over all items (`radar/render.py:78`) while the heading says "Seven useful signals". | Reading load is unbounded; the heading is wrong. |
| H3 | Write 300-word summaries. | 20,000-character ceiling. | An edition can run several thousand words. |
| H4 | Rate 4 and 5 generously. | See G2. | Investigation and experiment queues grow without bound. |

### I. Prompts that produce the failures above

| # | Attack | Evidence | Consequence |
|---|--------|----------|-------------|
| I1 | Follow the Fable prompt's guidance template literally. | `prompts/fable.md:80-86` defines Where as "applicable domain (e.g., inference servers, training pipelines, prompt engineering)" and Effort as "small/medium/large". | Every Where line is a domain, never a place in the owner's code. F3 becomes the norm. |
| I2 | Use the allowed `main-project` repository. | `prompts/fable.md:79` and `:98`. | Every item can dodge the repository link. |
| I3 | Follow the research focus. | `prompts/fable.md:10-15` and `prompts/astra.md:84-91` prioritize model releases, inference optimization, fine-tuning, and alignment. `config/topics.json` names Python automation, Excel, Tally, agents, document intelligence, local data, developer products, applied research, and work-relevant security. | The prompt optimizes for industry news, not the owner's work. |
| I4 | Write topics as `["ai", "key-topic-1"]`. | `prompts/fable.md:87`, `prompts/astra.md:161`. `config/topics.json` already defines stable ids. | Free tags fragment learning (G6) and defeat any topic cap. |
| I5 | Write `evidence_label` as "primary category (e.g., model-release)". | `prompts/fable.md:78`. | The label describes the subject, not the evidence. E1 is impossible until the prompt changes. |
| I6 | Write 150-word summaries. | `prompts/fable.md:95` allows 50 to 150 words. | Seven of them exceed the reading budget in H3. |
| I7 | Pass Astra validation with an old post and a fake date. | `prompts/astra.md:24-27` checks window and future only. | N2 has no home until the validation path checks the page. |
| I8 | Run the fallback digest on "adjacent areas not fully covered". | `prompts/astra.md:72-78`. | The fallback is designed to broaden, which is the opposite of what a seven-slot, work-focused digest needs. |

## Acceptance criteria

Each criterion names the enforcement point, the owning ticket, and the proof that must exist before ticket 10 signs off. Priority P0 blocks delivery of the first real edition; P1 blocks the release review; P2 is required within the first ten-day cycle. Enforcement points: **validator** is `validate_bundle` (it may gain an optional keyword-only `policy` argument without breaking the contract signature), **selection** is `select_candidates`, **renderer** is `render_html` and `render_text`, **gate** is the Apps Script accept step which has Sheet history, **Astra** is the routine validation prompt which must write a per-item verdict into the rejection report, **prompt** is the Fable research prompt.

### Learning and ratings

| ID | Pri | Rule | Enforcement | Owner | Proof |
|----|-----|------|-------------|-------|-------|
| L1 | P0 | A current rating of 1 or 2 on an item with topic-repository pair (T, R) lowers the rank of an unrated candidate carrying (T, R); a 4 or 5 raises it. The effect on an unrated candidate stays within 0.75 to 1.25 of its base score. | selection, learning | 06 | `tests/test_selection.py`: two otherwise identical candidates, one sharing a 1-rated pair, one neutral; the neutral one is selected first. Mirror test for a 5-rated pair. |
| L2 | P0 | No static bonus (source type, exploration, diversity) may exceed the largest rating effect available on the same candidate. Product preference is a multiplier no greater than 1.25, not an additive constant. | selection | 06 | Test: an unrated product candidate whose pair carries a 1-star history ranks below an equal-base tool candidate with neutral history. |
| L3 | P0 | Legend consequences are generated from the implemented effects, not hand-written. Every consequence string in the legend corresponds to a documented, tested behaviour. | renderer, learning | 05, 06 | `tests/test_render.py` imports the effect table from learning and asserts the legend text is derived from it. Until L1 passes, the legend must not say "similar". |
| L4 | P0 | Reason tags are a closed vocabulary parsed as whole tokens: `too technical`, `already knew`, `too much effort`. Free text after the tags is stored but not interpreted. "not too technical" produces no tag. | learning, gate | 06, 08 | `tests/test_learning.py` negative test; `google/test_gateway.cjs` parses `RATE RAD-x 2 not too technical` and stores no tag. |
| L5 | P1 | `already knew` applies a 90-day negative weight to the item's pairs and blocks near-duplicate titles (see R4) for 90 days. | selection, gate | 06, 08 | Selection test with a dated event; gateway test with a near-duplicate title. |
| L6 | P1 | `too technical` on any item in the last 14 days sets Preferences `presentation=simplify`, which tightens T1 limits (sentence cap 20 words, summary cap 50 words) and is passed to the prompt as an instruction. | gate, validator, prompt | 08, 05, 07 | Validator test with `policy={"presentation": "simplify"}` rejects a 24-word sentence. Prompt text contains the conditional block. |
| L7 | P1 | Open investigation queue is capped at 10 and open experiment proposals at 3. Ratings beyond the cap are accepted and marked `waitlisted`; the next edition footer states the queue lengths. | gate, renderer | 08, 05 | Gateway test: eleventh 4-rating is stored with `waitlisted`; render footer shows queue counts when supplied. |
| L8 | P0 | Every item card carries a per-item rating affordance: in HTML a link to the rating form with the item ID prefilled when `rating_url` is supplied; in text a ready-to-copy line `RATE RAD-... <score> <reason>` directly under the item. | renderer | 05 | `tests/test_render.py` asserts one prefilled link per item and one `RATE` line per item. |
| L9 | P1 | Exploration means a candidate none of whose pairs has rating history. The exploration bonus applies only to those candidates. The reserved exploration slot goes to the highest-ranked exploration candidate that does not violate any concentration cap. | selection | 06 | Test: with a partially rated pool, the reserved slot picks the top-ranked history-free candidate, not the first in input order. |
| L10 | P0 | Topics are the `id` values in `config/topics.json` (for example `document-intelligence`), one to three per item. Any other topic string is rejected. The list changes only by editing that file, never by the producer. Pair weights therefore key on stable ids. | validator (policy), gate, prompt | 05, 08, 07 | Validator test rejects `ai` and `LLM`; accepts `python-automation`. Prompt shows the id list verbatim. |

### Deduplication and repetition

| ID | Pri | Rule | Enforcement | Owner | Proof |
|----|-----|------|-------------|-------|-------|
| R1 | P0 | Same as reliability control C-18: `canonical_url` removes tracking parameters (`utm_*`, `fbclid`, `gclid`, `mc_cid`, `mc_eid`, `ref`, `ref_src`, `igshid`, `si`, `source`) and a leading `www.` label. | validator | 05 | `tests/test_domain.py`: the six pairs in Appendix A that should be equal are equal. |
| R2 | P0 | Same as C-18: arXiv URLs normalize to `https://arxiv.org/abs/<id>` with no version suffix, from `abs`, `pdf`, `html`, and versioned forms. | validator | 05 | Same test file. |
| R3 | P0 | At most 2 items per source host per edition and at most 5 per host across the last 7 accepted editions. | validator (per edition), gate (rolling) | 05, 08 | Validator test with three items on one host fails; gateway test with rolling history rejects the sixth. |
| R4 | P0 | Near-duplicate titles are rejected: after casefolding, stripping punctuation, digits, and version tokens, a title whose word set overlaps a delivered title from the last 60 days by 0.8 or more is rejected unless the re-feature rule (N4) is satisfied. | gate | 08 | Gateway test with "Foo 1.2 released" after "Foo 1.1 released". |
| R5 | P1 | Selection accepts a rolling topic histogram from the last 7 editions and penalizes a topic that appeared in 4 or more of them, so that an equal candidate with a fresh topic ranks above it. | selection | 06 | Test with a saturated topic. |
| R6 | P1 | Each accepted item records the edition it was featured in; the Items tab is the single source for delivered IDs, and the selection input `delivered_item_ids` is populated from it, never from the producer's own memory. The gate-side repeat rejection is C-36. | gate, prompt | 08, 07 | Gateway test; prompt states that the delivered list is read from the snapshot, not recalled. |

### Novelty and dates

| ID | Pri | Rule | Enforcement | Owner | Proof |
|----|-----|------|-------------|-------|-------|
| N1 | P0 | `source_dates` stays optional in the schema but is required at the gate for digest items. It must contain at least one of `published`, `released`, `submitted`, and `published_at` must equal the earliest of those. | gate, validator (policy) | 08, 05 | Validator policy test; gateway test. |
| N2 | P0 | Astra confirms `published_at` against the page (arXiv v1 date, `article:published_time`, GitHub release date, changelog heading) and records the observed date. A difference greater than 7 days rejects the item. | Astra | 07 | Prompt contains the check and the report field; a sample rejection report in `docs/CLOUD-SETUP.md` shows it. |
| N3 | P1 | The renderer shows age in days next to the date. Items older than 30 days carry the kicker `Discovery` instead of the source type alone. At most 3 discovery items per edition. Discovery items may not use `new`, `just`, `launches`, `announces`, or `today` in title or summary. | renderer, validator | 05 | Render test on a 45-day-old item; validator test on the word list. |
| N4 | P1 | A re-feature of a previously delivered product requires `source_dates.previous_feature` set to the earlier edition date, a summary that begins with `Update:` and states what changed, and at most one re-feature per host per 60 days. | gate | 08 | Gateway tests for each of the three conditions. |

### Evidence and repositories

| ID | Pri | Rule | Enforcement | Owner | Proof |
|----|-----|------|-------------|-------|-------|
| E1 | P0 | `evidence_label` is a closed vocabulary: `peer-reviewed`, `preprint`, `independent-benchmark`, `vendor-benchmark`, `vendor-claim`, `hands-on`, `docs-only`, `community-report`. Academic items must be `peer-reviewed` or `preprint`; non-academic items may not be either. This replaces the "primary category" definition in `prompts/fable.md` and `prompts/astra.md`, and satisfies the primary-or-secondary statement required by C-17. | validator, prompt | 05, 07 | Validator tests for an unknown label and for a mismatched pair; prompts list the vocabulary. |
| E2 | P1 | At least 2 of the delivered 7 carry `peer-reviewed`, `preprint`, `independent-benchmark`, or `hands-on`. | validator | 05 | Validator test with seven `vendor-claim` items fails. |
| E3 | P1 | For `vendor-claim` and `vendor-benchmark` items the Check line must describe how to test the claim locally, and `why_it_matters` may not restate the claim as fact. | Astra | 07 | Prompt contains the rule and the verdict field. |
| E4 | P1 | Source hosts that are launch aggregators or press-release wires (`producthunt.com`, `prnewswire.com`, `businesswire.com`, `globenewswire.com`, `prweb.com`) are rejected; link the primary docs or changelog instead. | validator | 05 | Validator test. |
| F1 | P0 | `repository` must be a name present in the Repositories tab (sanitized names from the ten-day review) or the literal `portfolio`. At most 2 `portfolio` items per edition. The prompt value `main-project` is removed. | validator (policy), gate, prompt | 05, 08, 07 | Validator allowlist test; gateway test against the Sheet; prompt no longer offers `main-project`. |
| F2 | P0 | Every non-`portfolio` item carries at least one `repository_evidence` entry in the C-10 format `owner/repo@shortsha:path[:line] — one sentence`, at most 300 characters, or the same format prefixed `inferred:` when the ten-day review has no matching evidence. The path must exist in that repository's current profile file list unless prefixed `inferred:`. | validator (shape), gate (existence) | 05, 08 | Validator test on shape; gateway test on a path absent from the profile. |
| F3 | P0 | Guidance strings may not begin with their own label. The Where line must name a module, file, feature, or workflow and may not use `anywhere`, `any project`, `your codebase`, `all repos`. The Check line must be at least 6 words and may not match `it works`, `see if`, `make sure`, `verify results`, `whether it helps`. | validator | 05 | Validator tests for each phrase. |
| F4 | P1 | `Effort` is a closed vocabulary: `15 minutes`, `1 hour`, `half day`, `1-2 days`, `week or more`. The small-scope preference uses this field, not keyword sniffing. The guidance heading is `What to do`, not `Five-minute guidance`. The prompts' `small/medium/large` wording is replaced. | validator, selection, renderer, prompt | 05, 06, 07 | Validator test; selection test that `quick` in free text no longer counts as small effort; render test on the heading. |
| F5 | P1 | At most 3 items per repository per edition. Over any 7 consecutive editions, each repository with a profile appears at least once or the Runs tab records a reason. | validator, gate (warn) | 05, 08 | Validator test; gateway test writes the warning. |
| F6 | P1 | The prompt receives the current sanitized repository profiles with their dates. If the newest profile is older than 20 days the edition footer says so with the date. | prompt, renderer | 07, 05 | Prompt contains the block; render test on a supplied profile date. |

### Plain language and noise

| ID | Pri | Rule | Enforcement | Owner | Proof |
|----|-----|------|-------------|-------|-------|
| T1 | P0 | Length and readability limits: title 12 to 90 characters; summary 20 to 70 words; `why_it_matters` 10 to 45 words; each guidance line 4 to 35 words; no sentence over 30 words in summary or why. Every all-caps token of 2 to 6 letters outside a Preferences allowlist must be expanded in parentheses on first use within the item. No backtick, `snake_case`, or `CamelCase` tokens in summary or why (allowed in Try and Check). These word limits sit inside the character limits of C-38 and replace the prompts' 50 to 150 word range. | validator, prompt | 05, 07 | Validator tests for each limit and for `RLHF` without expansion; prompts state the new range. |
| T2 | P0 | Placeholder and promotional lint: reject `TBD`, `n/a`, `TODO`, `lorem`, `placeholder`; reject exclamation marks; reject `game-changing`, `revolutionary`, `excited to announce`, `best-in-class`, `next-generation`, `world's first`, `unleash`, `supercharge`, and `10x` without a digit-bearing measurement in the same sentence. | validator | 05 | Validator tests. |
| T3 | P1 | Summary must contain at least one concrete fact: a number, a named capability, or a quoted result. Titles may not be the source page title verbatim. | Astra | 07 | Prompt contains the rule; sample verdicts documented. |
| T4 | P1 | `why_it_matters` must name the repository or say `portfolio` and state an outcome (time, error rate, cost, capability). | Astra | 07 | Prompt contains the rule. |

### Load and shape

| ID | Pri | Rule | Enforcement | Owner | Proof |
|----|-----|------|-------------|-------|-------|
| O1 | P0 | A bundle contains 7 to 10 items. Exactly the first 7 are rendered and delivered; items 8 to 10 are stored as `benched` and become eligible again next edition. The masthead count is computed, not hard-coded. | validator, gate, renderer | 05, 08 | Validator test with 11 fails; render test with 8 renders 7; gateway test records benched items. |
| O2 | P0 | Order of both renderings: masthead, a 7-line index of titles with IDs, the complete legend, then the first item. The legend stays at the top as the contract and C-38 require, but is capped at 12 text lines and 120 words while still carrying all five scores, their consequences, the reason tags, and the reply syntax. The first item starts within the first 30 lines of the text rendering. | renderer | 05 | Render text test on line positions and legend length; HTML test that the index precedes the panel and the panel precedes the first card. |
| O3 | P1 | Text edition is at most 1,400 words; each card at most 190 words including guidance. | renderer, validator | 05 | Render test on a maximal bundle. |
| O4 | P1 | Email subject is `AI Product Radar <edition_date>: <first item title>` truncated to 78 characters. | gate | 08 | Gateway test. |
| O5 | P1 | An edition that cannot reach seven compliant items is not delivered. The Deliveries tab records `insufficient` with the count, and the next delivered edition's footer states the gap. No relaxation of any criterion is permitted to fill the gap. | gate | 08 | Gateway test with a six-item accepted set. |

### Prompts

| ID | Pri | Rule | Enforcement | Owner | Proof |
|----|-----|------|-------------|-------|-------|
| P1 | P0 | The Fable, Astra, Opus, and Sol research prompts state the research focus as the nine topic ids and names from `config/topics.json`, with the downweight lists, and require every item to be tied to one of them. Generic AI-industry focus lists are removed. | prompt | 07 | Each prompt quotes the topic ids; a reviewer can diff the prompt against the config file. |
| P2 | P0 | The prompts receive the sanitized repository list with profile dates and require the Where line to name a module, file, feature, or workflow in the named repository. The guidance template examples are rewritten to that standard. | prompt | 07 | Prompt template shows a Where example that names a repository path; the domain examples are gone. |
| P3 | P0 | The Astra validation path checks every criterion marked Astra in this review (N2, E3, T3, T4) and writes a per-item verdict with the observed page date into the rejection report. | prompt | 07 | `prompts/astra.md` lists the checks; `docs/CLOUD-SETUP.md` shows a sample report with per-item verdicts. |
| P4 | P1 | The fallback digest follows the same focus, caps, and evidence rules as the primary and is not asked to broaden coverage. | prompt | 07 | The "adjacent areas" instruction is removed from `prompts/astra.md`. |

## Not relitigated

- The seven-item floor and product-heavy mix are map decisions. O5 and A5 make the floor honest rather than removing it.
- The Bundle v1 field set is unchanged. Every rule above uses existing fields, the optional `source_dates` map, an optional validator policy argument, or gate-side Sheet history.

## Appendix A: reproduction script for ticket 10

Run from the repository root with Python 3.11 or later. Expected results are stated inline; each expectation reflects the draft code at review time and should flip once the P0 criteria are implemented.

```python
import sys
sys.path.insert(0, ".")
from radar.domain import stable_item_id, validate_bundle
from radar.learning import pair_weights, relevance_multiplier, rating_effects
from radar.selection import select_candidates

# G1: ratings never reach a new candidate. Expected before fix: True.
ev = [{"event_id": "8b6a0d6e-4b3c-4c1a-9d1e-0a1b2c3d4e5f", "item_id": "RAD-000000000001",
       "score": 1, "reason": "already knew", "origin": "email", "base_revision": 0,
       "created_at": "2026-09-14T10:00:00Z"}]
cands = []
for i in range(9):
    url = f"https://example.com/c{i}"
    cands.append({"item_id": stable_item_id(url), "source_url": url, "title": f"c{i}",
                  "topics": ["prompt caching"] if i < 5 else ["billing"],
                  "repository": "invoice-matcher" if i < 5 else "ledger",
                  "source_type": "product", "published_at": "2026-09-10", "relevance": 1.0})
a = [c["item_id"] for c in select_candidates(cands, edition_date="2026-09-15")]
b = [c["item_id"] for c in select_candidates(cands, edition_date="2026-09-15", ratings=ev)]
print("G1 selection unchanged by a 1-star history:", a == b)
w = pair_weights([{"item_id": "RAD-000000000001", "topics": ["prompt caching"],
                   "repository": "invoice-matcher"}], ev)
print("G1 multiplier for unrated item sharing the pair (expected 1.0):",
      relevance_multiplier(cands[0], ev, weights=w))

# C1-C3, R1, R2: dedupe evasion. Expected before fix: False for the first four pairs.
pairs = [("https://example.com/post", "https://example.com/post?utm_source=newsletter"),
         ("https://arxiv.org/abs/2401.00001", "https://arxiv.org/abs/2401.00001v2"),
         ("https://arxiv.org/abs/2401.00001", "https://arxiv.org/pdf/2401.00001"),
         ("https://example.com/post", "https://www.example.com/post"),
         ("https://example.com/post", "https://example.com/post/"),
         ("https://example.com/post?b=2&a=1", "https://example.com/post?a=1&b=2")]
for x, y in pairs:
    print("same id:", stable_item_id(x) == stable_item_id(y), "|", x, "vs", y)

# A1-A4, O1: filler acceptance. Expected before fix: 30 items accepted.
def item(i):
    url = f"https://vendor.example/{i}"
    return {"item_id": stable_item_id(url), "title": "Revolutionary game-changing AI launch",
            "source_url": url, "published_at": "2026-09-10", "source_type": "product",
            "summary": "TBD", "why_it_matters": "n/a", "evidence_label": "verified",
            "repository": "any", "topics": [],
            "guidance": ["Where: anywhere", "Try: it", "Benefit: yes", "Effort: quick", "Check: it works"]}
bundle = {"schema_version": 1, "run_id": "probe", "edition_date": "2026-09-15",
          "generated_at": "2026-09-15T06:00:00Z", "producer": "fable",
          "model_id": "claude-fable-5-1", "kind": "digest", "items": [item(i) for i in range(30)]}
print("A1 filler items accepted:", len(validate_bundle(bundle)["items"]))

# D3, L4: substring reason tags. Expected before fix: simplify.
neg = dict(ev[0], event_id="1b6a0d6e-4b3c-4c1a-9d1e-0a1b2c3d4e5f", reason="not too technical at all")
print("D3 presentation for 'not too technical at all':",
      rating_effects([neg])["RAD-000000000001"]["presentation"])
```
