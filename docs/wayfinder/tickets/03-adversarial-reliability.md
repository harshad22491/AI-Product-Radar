# Adversarial privacy and reliability review

Label: `wayfinder:research`

## Question

Which privacy, prompt-injection, scheduling, state-corruption, delivery, and private-repository failures could invalidate the proposed design, and what narrow controls are required?

## Resolution

Reviewed 2026-09-15 by Fable 5.1. Full findings with failure scenarios: [docs/reviews/fable-reliability.md](../../reviews/fable-reliability.md). No code changed.

Three findings invalidate the design as planned unless closed before activation:

1. No producer has a proven write path into the Drive inbox. Claude's Drive connector is read-oriented and ChatGPT scheduled tasks do not write files. Every producer stays pending until a canary file appears in the Runs tab. If no connector can write, an Apps Script `doPost` gateway with a bearer token is the ingestion path.
2. Model-authored text written to Sheets with `setValue` becomes a formula when it starts with `=`, and free-text repository evidence can carry verbatim private code or secrets into the Sheet, email, vault, and provider transcripts.
3. Replay halts on the first malformed rating event, and Sheets date coercion of `created_at` makes one row poison every snapshot.

Required controls (C-01 to C-43 in the review), grouped by the ticket that must implement them:

- **Cloud tasks (07):** canary-proven write path per producer (C-01); fallback checks inbox, accepted, and rejected, and Astra is advisory only in a separate `reviews/` child (C-03); pre-authorized connector actions with expected-by times (C-07); folder-ID and repository allowlists in every prompt (C-08); web research and repository review never share a session, no URLs outside `source_url` (C-15); private repositories never through OpenRouter, `providers_allowed` per repository (C-11); read-only repository-scoped GitHub grants (C-14); cursor reachability check and one review attempt per day with `last_attempted_at` (C-12, C-13); `run_id` embeds edition date and producer (C-33).
- **Google gateway (08):** single-winner editions with superseded status (C-02); deliver only when `edition_date` equals the dispatch India date (C-04); explicit "no valid edition" notice, never partial (C-05); script timezone `Asia/Kolkata` and a 15-minute dispatch poll with due check (C-06); text-format cells and quote prefix for formula-leading values (C-19); `ScriptLock` on every entry point, Form not linked to a sheet, `rebuildRadarState()` (C-24); hard-coded recipient assertion and `instance_id` match (C-25); acceptance decided once and persisted with `status` and `revision_assigned` (C-26); gateway stamps `base_revision` for email and form origins (C-27); deterministic event IDs from message and response IDs (C-29); feedback files may carry only `obsidian` origin, `chat` disabled in v1 (C-30); test sends flagged and ignored for repeat suppression (C-31); Deliveries `sending`, `sent`, `uncertain` with Sent-folder reconciliation by subject token and no automatic resend (C-32); seen inbox file IDs skipped, content hash recorded (C-23, C-34); Items and email rendered from the accepted record (C-35); snapshot regenerated after every accepted edition and event batch, repeat rule enforced by the gateway (C-36); replies accepted only in a script-sent thread, from the configured address, with DKIM or SPF pass, and only the unquoted top segment parsed (C-16, C-37); always send a text body alongside HTML through one escape helper (C-40); versioned snapshot files with pointer and SHA-256 (C-22).
- **Core domain (05):** reject `RATE RAD-` in any text field (C-16); reject Unicode format characters and show hostnames beside links (C-17); strip tracking parameters and apply arXiv and GitHub release canonicalization rules (C-18); reject text fields starting with `=`, `+`, `-`, `@` (C-19); email-visible field limits with HTML under 90 KB (C-38); evidence entries limited to `repo@sha:path — sentence` with path exclusion list and secret pattern denylist (C-10).
- **Ranking and learning (06):** quarantining replay wrapper that never halts on one bad event, payload equality excluding `created_at` formatting (C-21); replay only `accepted` rows in assigned revision order (C-26).
- **Obsidian sync (09):** export marked only after verified write, conflicts surfaced in the note, no automatic corrective events (C-28); persisted UUIDv4 per note before export (C-29); verify snapshot hash and never import an older snapshot (C-22); note filenames from `item_id` only (C-42); rename retry with backoff and vault outside mirrored folders (C-41, C-43); local delivery watchdog (C-39).
- **Integration review (10):** shared cross-language fixtures for bundles, URLs, escaping, and secret patterns that both `tests/test_domain.py` and `google/test_gateway.cjs` load (C-20); every S1 control has a test or documented manual check; `docs/CLOUD-SETUP.md` shows each producer as pending until its canary is observed.

Also noted: the map's "Decisions so far" links point to ticket files that do not exist and should be repaired.
