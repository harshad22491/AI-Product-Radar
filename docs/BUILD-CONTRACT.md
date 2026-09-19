# Implementation contract

**September 19 amendment:** The owner explicitly authorized the working newsletter's GitHub Actions approach for both Radar editions. [ACTIONS-MIGRATION.md](ACTIONS-MIGRATION.md) supersedes the older cloud-routine-only and no-Actions constraints below. Independent source review, subscription authentication, Google delivery/state and duplicate protection remain required.

User approved build and test delivery to harshad422@gmail.com. Do not ask more design questions. No Anthropic API key: Claude subscription CLI/cloud only. Research runs in Claude/ChatGPT cloud; Google Apps Script sends at or after 17:00 Asia/Kolkata. Exact provider execution timing is not guaranteed. No GitHub Actions.

Python 3.11+, standard library runtime, unittest. JavaScript Apps Script V8 for Google orchestration, native HTML email, JSON bundles, Markdown Obsidian notes. All teams use the following shared interfaces. No new dependencies without a concrete need. Do not send email or change external services from subagents.

## Latest routing amendment

The user's later instruction supersedes the original Astra schedule: routine analysis and validation use OpenAI Sol (gpt-5.6-sol). Claude Fable remains primary at 12:30 IST; Sol fallback14:30, Claude Opus15:45, Sol rescue16:30. Independent Sol validator tasks inspect candidates at13:45 and16:50; optional manual Astra is not a daily dependency. This amendment overrides historical role names in the review documents.

All rating submissions bind an explicit base revision: `RATE RAD-id 5 REV=0 good match` for a first rating. Existing ratings use their displayed current revision. Attestations use kind `validation`, candidate_run_id, SHA256 of exact immutable original bundle bytes, validator/model_id, verdict, and checked_at. Digests never approve themselves. Snapshot state_revision increases monotonically; digests remain full bundles and guidance/topics remain arrays.

## Bundle v1

JSON object: schema_version=1; run_id (safe slug); edition_date (YYYY-MM-DD India date); generated_at (UTC aware ISO); producer (fable/astra/opus/sol); model_id (actual string); kind (digest); items (7+ objects). A run is valid only with all selected items valid and unique. Every item: item_id (RAD- plus 12 hex digits from sha256 canonical URL), title, source_url (https only), published_at (YYYY-MM-DD), source_type (academic/product/tool/technique), summary (plain language), why_it_matters, evidence_label, repository (sanitized name), guidance (exactly 5 nonempty strings: Where, Try, Benefit, Effort, Check), topics (list of strings). Optional source_dates and repository_evidence. Dates must be real and not future. Academic age cap 2 calendar years; other sources 6 calendar months relative to edition_date. Source date is original publish/release date, not a crawl date. Candidate selection retains original dates. Reruns cannot repeat delivered items unless a material release has a new canonical release URL.

## Ratings

event_id UUID; item_id; score 1..5 integer (bool invalid); reason optional string; origin (email/form/chat/obsidian); base_revision integer; created_at aware UTC. Current rating includes revision increment per accepted event, score, reason. Duplicate event id ignored; same event id different payload error; stale base_revision conflicts, not overwrite. Missing ratings neutral. Rating affects relevance never credibility. Reason too technical affects presentation, already knew suppresses repeat, too much effort favors small scope. 4 queue investigation; 5 experiment proposal only. All email tops include entire 1-5 legend, consequences, reason tags, reply syntax RATE RAD-id 5 good match. No GET-side state mutation.

## Cloud exchange

Drive directory children inbox (immutable JSON input), accepted (accepted bundles), rejected (validation report), snapshots, feedback (events). Apps Script is sole Sheet writer. Sheet tabs Items, RatingEvents, CurrentRatings, Repositories, Reviews, Runs, Deliveries, Sources, Preferences. Use ScriptLock. Save durable outbox BEFORE mail, keep uncertain outcomes for reconciliation rather than blind repeat. sender uses authorized Gmail account, fixed recipient. Gmail replies accept only authenticated configured user's address and exact RATE syntax, never other senders. Email HTML escapes all fields; no model-authored raw HTML or recipient fields honored.

snapshot.json: schema_version 1, items [], digests [] (accepted bundles), ratings {} keyed item_id, updated_at UTC. feedback files {schema_version:1,kind:ratings,events:[...]}. Sync exports changed Obsidian ratings first, then imports snapshots preserving User notes section. Never overwrite an unsynced edit; path traversal prohibited; atomic writes, persistent last-exported map. Run only at login or when PC online; cloud continues while off.

## Ten-day review

Daily due check based on last_successful_review_at + 10 elapsed days. Per-repo SHA cursors advance only for successful coverage. Profile metadata/docs/dependencies/selected code changes only; no workbooks/PDFs/credentials/customer/portfolio data. Persist evidence with commit/path; inferred opportunities labelled. Baseline profile used when GitHub unavailable, date shown. No writes to reviewed repositories.

## Owned file boundaries

Luna core: radar/__init__.py, radar/domain.py, radar/render.py, tests/test_domain.py, tests/test_render.py. API validate_bundle(dict)->dict (raise ValueError); canonical_url(str)->str; stable_item_id(url)->str; render_html(bundle, rating_url='')->str; render_text(bundle)->str.
Luna ranking: radar/learning.py, radar/selection.py, tests/test_learning.py, tests/test_selection.py. Standalone pure functions; don't edit core modules.
Sonnet Google: google/Code.js, google/appsscript.json, google/README.md, google/test_gateway.cjs. setupRadar() provisions folder/Sheet/Form, installRadarTriggers(), dispatchRadar(), sendTestDigest() only to target; settings stored Script Properties. Test does not mark regular edition delivered.
Haiku prompts: prompts/*.md and docs/CLOUD-SETUP.md only. Exactly agreed schedules 12:30 Fable, 14:30 Astra, 15:45 Opus, 16:30 Sol; Fable routine validation by Astra distinct from fallback. Cloud setup must be marked pending until real activation verified, not pretend docs are deployment.
OpenRouter sync: radar/sync.py, scripts/sync-vault.ps1, tests/test_sync.py only. Standard library implementation of export-before-import. No model/API call in sync. These are sanitized new project files; never read outside this repo.
Astra reviews and Fable reviews: own docs/reviews/*.md only, no code.

## 2026-09-16 newsletter and cloud amendment

User requires fuller, nontechnical explanations and at least one genuinely user-facing AI product in EVERY edition. Optional item keys user_facing_ai:boolean (legacy default false) and application_example:string are added. New validated editions require at least one true marker; that item requires a nonempty example <=4000 characters. Producers should supply examples for every item. Selection preserves this minimum after freshness/deduplication filters. Five guidance entries are retained but written as full, descriptive explanations.

For subscription cloud operation, an independent Opus review routine is configured as the fallback for unavailable Sol scheduling. Fable remains primary. Attestations allow exactly sol/gpt-5.6-sol or opus/claude-opus-5; self-approval is rejected. Native scheduled tasks remain paused until the actual connector test passes. Google delivery/reply triggers are authorized, with final mail transport verification recorded separately.
