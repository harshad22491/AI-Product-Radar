# Fable adversarial integration review of generated code

> Historical build-stage review. See [current verification](../VERIFICATION.md) for resolved findings and remaining blockers.

Reviewer: Fable 5.1 (Claude subscription, no Anthropic API). Date: 2026-09-15.
Ticket: [10 Integration verification and release review](../wayfinder/tickets/10-integration-review.md).
Scope: the generated code as it exists today in `google/Code.js`, `google/test_gateway.cjs`, `radar/domain.py`, `radar/render.py`, `radar/learning.py`, `radar/selection.py`, `radar/sync.py`, `radar/__main__.py`, `radar/github_review.py`, `prompts/*.md`, `config/models.json`, `examples/test-digest.json`, `tests/*.py`. Documentation only. No application file was edited, no service was contacted, nothing outside this repository was read.

Method: every finding was traced by reading the current files (Luna's `radar/sync.py` repair had already landed when it was read). Command execution was denied in this session, so `python -m unittest discover -s tests -t .` and `node google/test_gateway.cjs` were not run here. Ticket 10 should run both before acting on this report. Line numbers are as read on 2026-09-15 and will drift while Sonnet, Luna, and Haiku repair their slices; function names are the stable anchor.

Prior reviews (`fable-reliability.md`, `fable-editorial.md`, Astra's reviews) are design history. Nothing below repeats a control from them unless the generated code makes it newly concrete. Severity: **S1** no delivery, silent loss, or corrupted canonical state. **S2** wrong or duplicate user-visible output. **S3** quality or operability.

Constraint honored throughout: the rating legend stays at the very top of every email. `buildDigestHtml` places it directly under the `h1` and `render_html` places it directly under the masthead. Both are correct and no fix below moves it.

---

## Verdict

As generated, the system cannot deliver a single edition and cannot record a single rating from any of the three rating channels. The four S1 findings (F1, F2, F3, F4) each independently break the main loop. They are small, local fixes, but each must land before the first live test, or the test will report failure for reasons unrelated to Google authorization.

| # | Sev | Where | One line |
|---|-----|-------|----------|
| F1 | S1 | `google/Code.js` `validateGuidance`, `validateItem` | Gateway rejects the guidance and source_dates shapes that the contract, prompts, Python validator, and example bundle all produce. |
| F2 | S1 | `google/Code.js` `dispatchRadar` | Bundles arriving before 17:00 are consumed, marked delivered, and never sent. |
| F3 | S1 | `google/Code.js` `processGmailReplies` | Owner replies are self-addressed mail and are read before the poll, so `is:unread` never finds them. |
| F4 | S1 | `google/Code.js` (missing reader), `radar/sync.py` `export_ratings` | Nothing reads `feedback/`; every Obsidian rating is written to a folder no code opens. |
| F5 | S1 | `google/Code.js` `dispatchRadar`, `recordRun` | An inbox file containing `null` throws every run before the send step, forever. |
| F6 | S2 | `radar/sync.py` `export_ratings`, `import_snapshot` | The second Obsidian edit of any item (including a reason-only edit) is sent with a stale base_revision and silently lost. |
| F7 | S2 | `google/Code.js` `applyRatingEvent`, `processGmailReplies` | Partial write leaves the log saying applied while state is stale; retry creates a second event with a fresh ID. |
| F8 | S2 | `google/Code.js` `exportSnapshot`, `recordItems`; `radar/sync.py` `validate_snapshot` | Sheets coercion flattens the snapshot; one numeric reason or title aborts every future sync. |
| F9 | S2 | `google/Code.js` `dispatchRadar`, `writeJsonFile`; `prompts/validator.md` | Validator attestations are trashed as rejected bundles; nothing is hashed, nothing is immutable. |
| F10 | S2 | `google/Code.js` `canonicalUrl`; `radar/domain.py` `canonical_url` | Two canonicalizers produce different item IDs for ordinary URLs, so the gateway rejects Python-valid bundles. |
| F11 | S2 | `google/Code.js` `derivePreferences`; `radar/learning.py`; `prompts/*.md` | Ratings reach the Sheet and stop; no producer, selector, or gateway path reads them. |
| F12 | S3 | `google/Code.js` `buildRatingLegendHtml`; `radar/render.py` `_RATING_LEGEND`; `docs/CLOUD-SETUP.md` | Three different legends promise three different consequences. |

---

## F1. Gateway rejects every contract-shaped bundle (S1)

Where. `google/Code.js:249-265` `validateGuidance` requires `guidance` to be an object keyed `Where/Try/Benefit/Effort/Check` and returns an error for arrays. `google/Code.js:323-327` `validateItem` requires `source_dates` to be an array. `google/test_gateway.cjs:139` asserts that a five-string array is rejected, so the test suite enshrines the wrong shape.

Contract and everything else. `docs/BUILD-CONTRACT.md` says guidance is "exactly 5 nonempty strings". `radar/domain.py:295-298` requires a list of five strings and rejects objects. `radar/render.py:80-83` zips labels onto a list. `prompts/fable.md:80-86`, `prompts/opus.md:91-97`, `prompts/sol.md:98-104` all instruct an array. `examples/test-digest.json` uses an array and a `source_dates` object (`{"released": "2026-09-04"}`), which `radar/domain.py:189-198` accepts and the gateway rejects on both counts.

Reproduce. Drop `examples/test-digest.json` into `inbox/` on 2026-09-16 (its `edition_date`; note `python -m radar validate examples/test-digest.json` also fails until then because `radar/domain.py:240-242` treats tomorrow as future). Expected in `rejected/`: seven lines `items[n]: guidance must be an object keyed by Where/Try/Benefit/Effort/Check` and seven lines `source_dates, when present, must be real non-future YYYY-MM-DD dates`.

Downstream. `buildDigestHtml` (`:612-614`), `buildDigestText` (`:636-638`), and `recordItems` (`:871-875`) all read `item.guidance.Where`, so a fix only in the validator would print `undefined` five times per item.

Fix. In `validateGuidance` accept exactly a five-element array of nonempty strings (optionally also accept the object form and normalize to the array). Add one normalizer `guidanceList(item)` and use it in `buildDigestHtml`, `buildDigestText`, and `recordItems`. In `validateItem` accept `source_dates` as an array of dates or an object whose values are dates, matching `_validate_source_dates`. Flip `test_gateway.cjs:139` and add a test that loads `examples/test-digest.json` and expects `ok === true` with `nowMs` fixed. Better: the shared fixture directory from reliability control C-20, so this class cannot recur.

## F2. Pre-17:00 ingestion consumes the edition; nothing is left to send (S1)

Where. `google/Code.js:992-1045` `dispatchRadar`. The trigger runs every 15 minutes all day (`installRadarTriggers:811`). Each run validates every inbox file, copies it to `accepted/`, appends its items to `Items` with `first_delivered_edition_date` (`recordItems:858-889`), trashes the inbox file (`:1031`), and pushes the bundle onto the in-memory array `validatedBundles`. The send (`:1037-1041`) requires `dueCheck.due && validatedBundles.length > 0`, and `validatedBundles` exists only inside that one execution.

Reproduce. Fable writes a valid bundle at 12:30 IST as scheduled. The 12:45 run ingests it: `accepted/` has the file, `Items` has seven rows, `Runs` says `accepted`, inbox is empty. The 17:00 run finds no inbox files, `validatedBundles` is empty, no email is sent, `LAST_DELIVERED_EDITION_DATE` stays unset. Tomorrow's bundle from the same producer repeats zero items (dedupe by `getDeliveredItemIds:843-850`) and the cycle repeats: every edition is "delivered" in the Sheet and never delivered to the recipient. Under the designed schedule (12:30, 14:30, 15:45, 16:30, all before 17:00) this is the only possible outcome. Same root cause, second symptom: when two bundles land in the same run, only `validatedBundles[0]` is sent (`:1038`) but both are recorded as delivered, so the second producer's items are lost permanently.

Fix. Separate accept from deliver. At accept time record in `Runs` the accepted file's Drive ID and status `accepted`, and do **not** write `Items`. At dispatch time (due check true) select from `Runs` the oldest `accepted` row for today's `editionDate` with no `Deliveries` row of status `sent` for its `run_id`, re-read the bundle from `accepted/` by the stored file ID, send it, and only after outcome `sent` write `Items`, `Sources`, and `LAST_DELIVERED_EDITION_DATE`. Reject-by-repeat should then check `Items` plus the items of today's already-accepted rows, so two same-day bundles cannot both be accepted with overlapping items. Add a Node test for a pure `selectDeliverableRun(runsRows, deliveriesRows, editionDate)` so the rule is testable without Google.

## F3. Owner replies are never processed (S1)

Where. `google/Code.js:1188-1215` `processGmailReplies` searches `is:unread subject:"AI Product Radar"` and only processes messages that are still unread.

Why it fails. Sender and recipient are the same Gmail account (`getOwnerEmail`, contract "sender uses authorized Gmail account, fixed recipient"). When the owner replies from that account, the reply is a message the account itself sent, shown inside the open thread in their own mailbox. Gmail treats it as read at send time, and even where a client shows it unread, the owner is looking at the thread and it is read within seconds. The 15-minute poll therefore finds nothing. Result: zero `RatingEvents` rows from email, ever. Secondary effect of the same design: any unread message in a matching thread is force-marked read (`:1196`, `:1211`), so the script silently reads the owner's mail.

Cannot be verified here. This session cannot touch Gmail. It is the first thing the live test must check: reply `RATE RAD-xxxxxxxxxxxx 4 test` from the owner account and confirm a `RatingEvents` row within 30 minutes. The fix below is correct whether or not Gmail marks the self-reply read, so apply it regardless.

Fix. Do not key on read state. Record the digest thread ID in `Deliveries` (`GmailApp.sendEmail` cannot return it; search `in:sent subject:"<subject>"` once after sending, or switch to `GmailApp.createDraft(...).send()` which returns the `GmailMessage` and its thread). In `processGmailReplies`, iterate `Deliveries` threads for the last 30 days, process every message in the thread whose Gmail message ID is not yet in `RatingEvents` (store `gmail_message_id` as a column, or use a `radar/processed` label and query `-label:radar/processed`), never call `markRead`. Combine with the deterministic event IDs from F7 so a reprocessed message is a `duplicate`, not a second rating.

## F4. The feedback folder is write-only (S1)

Where. `radar/sync.py:239-244` `export_ratings` writes `feedback/obsidian-<ts>-<8hex>.json` with `{"schema_version":1,"kind":"ratings","events":[...]}` exactly as the contract specifies. `google/Code.js` mentions `feedback` only to create the folder (`:57`, `getOrCreateDriveTree`). No function lists, reads, validates, or applies feedback files. `RATING_ORIGINS` (`:37`) accepts `obsidian`, but the only callers of `applyRatingEvent` are the Form trigger and the Gmail poll.

Reproduce. Rate any note in the vault, run `scripts/sync-vault.ps1`, confirm the feedback file appears in the Drive mirror. Wait any number of days. `RatingEvents` never gains a row, `snapshot.json` never shows the rating, and `export_ratings` (`:221`) considers it exported so it is never re-sent.

Fix. In `dispatchRadar`, under the same lock, before `exportSnapshot`: list `folders.feedback` files not yet recorded (keep a `Preferences` row `processed_feedback_file_ids`, or move processed files into `feedback/processed/`), parse each, require `schema_version === 1`, `kind === "ratings"`, an `events` array of at most 500, and `origin === "obsidian"` for every event (reject the file whole otherwise, per reliability C-30), then call `applyRatingEvent(event)` for each in file order. `applyRatingEvent` already handles duplicate IDs, stale `base_revision`, and payload mismatch, so sync retries are safe once the file is actually read. Write a pure `validateFeedbackFile(obj)` and test it in `test_gateway.cjs`.

## F5. A `null` inbox file blocks dispatch permanently (S1)

Where. `google/Code.js:1001-1033`. `readJsonFile` parses `null` successfully. `validateBundle(null)` returns `{ok:false}` correctly (`:341-343`). `dispatchRadar` then calls `recordRun(ss, bundle, 'rejected', ...)` at `:1013`, and `recordRun` (`:891-904`) dereferences `bundle.run_id`, which throws `TypeError: Cannot read properties of null`. The throw happens before `file.setTrashed(true)` at `:1014`, so the file stays in `inbox/`, and before the send block and `exportSnapshot`, so the run does nothing else. Every 15-minute run repeats identically.

Reproduce. Upload a file `x.json` containing the four bytes `null` to `inbox/`. Observe an `Executions` failure every 15 minutes, a growing stack of `x.json.rejected.json` overwrites in `rejected/`, no email at 17:00, and a stale `snapshot.json`. Any single file that throws for any reason inside the `forEach` (Drive quota on `setContent`, a Google Doc named `*.json` whose blob is not text) has the same effect because there is no per-file isolation.

Fix. Wrap the per-file body in `try/catch`; on throw, write `{errors:['unhandled: ' + e.message]}` to `rejected/`, trash or rename the file, and continue. Guard `recordRun` with `var b = (bundle && typeof bundle === 'object' && !Array.isArray(bundle)) ? bundle : {}`. Cap accepted file size (reject above 1 MB without parsing, reliability C-08) and cap files per run. Make the send and snapshot steps run even when ingestion had failures.

## F6. Obsidian revisions never advance, so the second edit of any item is lost (S2)

Where. `radar/sync.py:217-238` `export_ratings` and `:339-343` `import_snapshot`. `export_ratings` takes the base from `last_exported[iid]` first and falls back to `last_imported[iid]`. `last_exported[iid].revision` is written once (`:238`) with the base used at export time and is never updated from a later snapshot. `import_snapshot` keeps the local rating whenever it differs from `last_imported[iid]` including on `revision` (`_same_rating:309-314`), so a note that the user rated by hand (no `rating_revision` key, so revision 0) always wins and never receives the cloud revision.

Reproduce (assumes F4 fixed, otherwise nothing reaches the cloud at all).
1. `snapshot.json` has item X, no rating. Sync. Note X exists; state `last_imported.X = null`.
2. Add `rating: 4` to X's frontmatter. Sync. Feedback event E1 `{score:4, base_revision:0}`; state `last_exported.X = {score:4, reason:"", revision:0}`.
3. Cloud applies E1; X is now revision 1. Next `snapshot.json` has `ratings.X = {score:4, revision:1, reason:""}`. Sync. Local `{4, rev 0}` differs from `last_imported.X = null` so local wins; the note keeps `rating_revision: 0`; state `last_imported.X = {4, 1, ""}`.
4. Change only the reason: `rating_reason: "good match"`. Sync. Base is `last_exported.X` with revision 0, so E2 is `{score:4, reason:"good match", base_revision:0}`. Cloud: current revision 1, `reduceRatingEvent` returns `conflict`. `last_exported.X` is overwritten with the new reason (`:238`), so E2 is never resent. The reason edit vanishes, and every later edit of X conflicts the same way.

Fix. Base revision must come from the cloud's last known value: `base_revision = max(last_imported[iid].revision, frontmatter.rating_revision)`. `last_exported[iid]` should hold only `score` and `reason` for change detection. On import, when the snapshot rating equals `last_exported[iid]` on score and reason, treat it as acknowledgement: write the snapshot revision into the note's `rating_revision` and into `last_imported`. `_same_rating` for the local-wins decision should compare score and reason only, so revision numbers always flow cloud to note. Conflicts must become visible: once F4 lands, `exportSnapshot` should include a `conflicts` map (item_id to `{revision, score, reason}` of the rejected event) and `import_snapshot` should append a `Conflict` line under `## User notes` rather than dropping the edit (reliability C-28). Add a test that runs the four steps above and asserts E2 carries `base_revision: 1`.

## F7. Partial write plus fresh UUIDs: the idempotency key protects nothing (S2)

Where. `google/Code.js:1142-1181` `applyRatingEvent` appends the `RatingEvents` row with `status: applied` (`:1165-1169`) and only then writes `CurrentRatings` (`:1171-1180`). `processGmailReplies` calls `Utilities.getUuid()` per line per poll (`:1202`) and `markRead()` after applying (`:1211`). `onFormSubmit` likewise mints a fresh UUID (`:1106`).

Reproduce. Reply `RATE RAD-x 4`. Poll 1: `RatingEvents` row `applied`, then the execution dies (six-minute limit, Sheets 500, lock loss) before `CurrentRatings` is written. State: log says applied at base 0, `CurrentRatings` has no row for X, message still unread. Poll 2: new UUID, `getCurrentRevision` returns 0, `reduceRatingEvent` finds no existing row for the new ID, applies again. Now `RatingEvents` has two `applied` rows for X both at `base_revision 0`, `CurrentRatings` says revision 1 with `last_event_id` of the second. A rebuild from the event log (the contract's audit path, and `radar/learning.py:replay_rating_events`) would mark the second event a conflict and name the first, so log and state disagree permanently. Inverse case: the Form trigger is not retried by Google, so the same partial write there loses the rating while the log claims it applied. And if event IDs are made deterministic without reordering the writes, poll 2 returns `duplicate` and the lost `CurrentRatings` write is never repaired.

Fix. Write `CurrentRatings` first, then the `RatingEvents` row, so a crash yields a missing log row (recoverable: `last_event_id` names the event) rather than a phantom applied row. Make IDs deterministic: email `sha256(messageId + ':' + lineIndex)` and form `sha256(responseId)`, formatted as `8-4-4-4-12` hex (both `UUID_RE` and Python `uuid.UUID` accept it). In `reduceRatingEvent`, when the existing row is `applied` but `currentRating.last_event_id !== event.event_id` and `event.base_revision === currentRevision`, return `applied` again (repair) instead of `duplicate`. Mark the message with the processed label (F3) before applying, not after.

## F8. Snapshot flattening and Sheets coercion poison the vault import (S2)

Where. `google/Code.js:949-985` `exportSnapshot` copies `Items` rows verbatim by header name, and `recordItems` (`:858-889`) stores guidance as five columns and topics as `join(',')`. `appendRow` lets Sheets parse cell input, so `published_at` `2026-09-04` becomes a date cell and `getValues` returns a JS `Date`; `JSON.stringify` then emits `2026-09-03T18:30:00.000Z` for a sheet in Asia/Kolkata. `radar/sync.py:138-171` `validate_snapshot` requires `title` to be a nonempty `str` and `ratings[*].reason` to be a `str`, and `run_sync:394-397` validates every snapshot before touching the vault.

Reproduce.
- Any accepted item: the vault note gets `published_at: "2026-09-03T18:30:00.000Z"` (wrong day), `topics: "document extraction,pdf"` as a string, and no guidance lines because `render_item_note:283-286` looks for `guidance`, which the snapshot never contains.
- Reply `RATE RAD-x 4 2024`. Sheets stores reason as the number 2024. `exportSnapshot` emits `reason: 2024`. `validate_snapshot` raises `bad rating for RAD-x`, `run_sync` exits 1 before importing anything, and does so on every future run until the cell is edited by hand. A title such as `2025` or `TRUE`, or a reason `TRUE`, does the same via `bad title` and the boolean check.
- Same coercion breaks `ratingPayloadEquals` (`:408-414`) once IDs are deterministic (F7): a replayed event with reason `"2024"` compares against the row's number 2024 and is classified `event_id_payload_mismatch` instead of `duplicate`.

Fix. In `exportSnapshot`, rebuild contract-shaped items instead of copying rows: `guidance: [where, try, benefit, effort, check]`, `topics: String(row.topics).split(',')`, `published_at` and `first_delivered_edition_date` via `Utilities.formatDate(value, 'Asia/Kolkata', 'yyyy-MM-dd')` when the cell is a `Date`, every text field through `String(...)`, and `reason: String(row[2])`. Write model-authored and user-authored cells as text: replace `sheet.appendRow(row)` in `appendRow` with `getRange(last+1, 1, 1, n).setNumberFormat('@').setValues([row])`, and prefix `'` when a value starts with `=`, `+`, `-`, or `@` (reliability C-19; formula injection is otherwise live today). On the sync side, `validate_snapshot` should coerce `reason` with `str()` rather than abort the whole import for one bad rating, and `render_item_note` should accept `topics` given as a comma string.

## F9. Validator attestations are destroyed, and nothing is hashed or immutable (S2)

Where. `prompts/validator.md` and `config/models.json` (role `independent-validation`, 13:45, Sol) instruct Sol to upload `{"kind":"validation", "candidate_sha256": ...}` files into `inbox/`. `dispatchRadar` treats every `*.json` in `inbox/` as a digest: `validateBundle` fails on `kind` and `items`, the file is reported in `rejected/`, logged in `Runs` as `rejected`, and trashed (`:1010-1015`). No column anywhere stores a content hash (`SHEET_SCHEMAS.Runs:70-71`). `writeJsonFile` (`:833-841`) re-serializes with `JSON.stringify(obj, null, 2)` after `bundle.items` was replaced by the filtered list (`:1026`), so bytes in `accepted/` never match bytes the validator hashed, and it overwrites any same-named file with `setContent`, so `accepted/` and `rejected/` are not immutable either. Inbox originals go to trash and auto-purge in 30 days.

Reproduce. Sol uploads `validation-20260916.json`. Within 15 minutes it is in `rejected/` with `kind must equal "digest"`, `Runs` has a row with empty `run_id`, and the attestation is gone. Separately, have Fable name its file `fable.json` two days in a row: day two's `writeJsonFile(folders.accepted, 'fable.json', ...)` silently replaces day one's accepted record.

Fix. Route on `kind` before validation: `digest` to the bundle path, `validation` to a new path that validates `{schema_version, kind, run_id, candidate_run_id, candidate_sha256, validator, model_id, verdict, checked_at}`, appends to a `Validations` tab (add it to `SHEET_SCHEMAS`), and moves the file to `accepted/validations/`; anything else to `rejected/`. Hash the inbox bytes before parsing: `sha256Hex(file.getBlob().getDataAsString('UTF-8'))`, store it in a new `Runs.content_sha256` column, and copy the original string (not a re-serialization) into `accepted/<edition>-<producer>-<sha12>.json`, refusing to overwrite if the name exists. Keep the filtered item list in the Sheet only. If delivery is meant to be gated on an approved attestation, `dispatchRadar` must check `Validations` for `verdict === 'approved'` with a matching `content_sha256`; today no gating exists and the doc should say so until it does.

## F10. Two canonicalizers, two item IDs (S2)

Where. `google/Code.js:174-204` `canonicalUrl` strips `utm_*`, `gclid`, `fbclid`, `mc_cid`, `mc_eid`, and any parameter whose name starts with `ref` (so also `reference`, `refresh`, `refid`), keeps percent escapes and the `:443` port, and does not decode `+`. `radar/domain.py:134-180` `canonical_url` keeps all parameters, removes `:443`, decodes then re-encodes the query with `urlencode` (`%20` becomes `+`), removes dot segments, and uses `strict_parsing=True`, which raises on a bare `?flag`. `validateItem` (`:293-297`) rejects any item whose `item_id` differs from the gateway's own hash.

Reproduce (item IDs computed by Python via `stable_item_id`, bundle otherwise valid).
- `https://example.com/post?ref=newsletter` Python keeps `ref`, gateway drops it: rejected `item_id does not match sha256(canonical source_url)`.
- `https://example.com/search?q=a%20b` Python emits `q=a+b`, gateway keeps `%20`: rejected.
- `https://example.com:443/x` Python drops the port, gateway keeps it: rejected.
- `https://example.com/x?flag` Python raises `invalid query`, gateway accepts: a bundle valid in the cloud cannot be re-rendered locally.

Fix. Pick one algorithm and port it exactly. The Python one is closer to RFC 3986; add the tracking-parameter strip list there (reliability C-18, which the gateway already half-implements) using exact names plus the `utm_` prefix only, never a bare `ref` prefix. Port to JS: sort by decoded key and value, re-encode with the same reserved set, drop default port, remove dot segments, and stop using `strict_parsing`. Share a `fixtures/urls.json` of input to canonical pairs loaded by both `tests/test_domain.py` and `test_gateway.cjs`.

## F11. Ratings are collected and then ignored (S2)

Where. `google/Code.js:454-484` `derivePreferences` is defined and tested but never called; the `Preferences` and `Repositories` tabs are provisioned (`SHEET_SCHEMAS`) and never written; `snapshot.json` carries `ratings` but nothing consumes them. `radar/learning.py` and `radar/selection.py` are pure and correct but no CLI subcommand (`radar/__main__.py`) and no gateway path invokes them. `prompts/fable.md`, `opus.md`, `sol.md` never mention `snapshot.json`, ratings, suppressed repositories, or reason tags; `opus.md:115-118` and `sol.md:124-127` tell the producer to compare against "prior bundles in Google Drive", but inbox files are trashed within 15 minutes and `accepted/` is not named.

Reproduce. Rate an item 1 with reason `already knew` by any channel. Next edition from the same repository is neither suppressed nor demoted; the only repeat protection is exact `item_id` match in `Items`. Rate 5: no experiment proposal is queued anywhere a human or producer can see it.

Fix. Minimal end-to-end wiring: in `dispatchRadar`, after ratings are applied, call `derivePreferences(currentRatingsRows, itemsById)`, write the result to the `Preferences` tab and to `snapshots/preferences.json`, and include `delivered_item_ids` (from `Items`) and `preferences` in `snapshot.json`. Gateway enforcement: reject items whose `repository` is in `suppressed_repositories`. Prompts (Haiku) must instruct every producer to read `snapshots/snapshot.json` for delivered IDs and `preferences.json` for suppressions and small-scope preference, since a producer that cannot read Drive cannot honor the rule at all. The Python ranking modules stay reference implementations until something calls them; say so in `README.md`.

## F12. Three legends, three sets of promises (S3)

Where. `google/Code.js:564-589` (the legend that is actually emailed) says 1 "not relevant right now", 5 "experiment proposal only", and names the three reason tags with their effects. `radar/render.py:10-16` says 1 "Skip: suppress similar items", 2 "reduce similar items", which no code does (F11). `docs/CLOUD-SETUP.md:151-159` says 1 "Misleading or off-topic: unlikely to rerate", a credibility framing the contract forbids.

Reproduce. Render the same bundle with `python -m radar render bundle.json plain --out x` and with `sendTestDigest()`; compare the top block.

Fix. One legend fixture (JSON with score, label, consequence, the three tags, and the reply syntax line) rendered by `buildRatingLegendHtml`, `buildRatingLegendText`, `_rating_html`, `render_text`, and pasted into `docs/CLOUD-SETUP.md`. Wording must describe only what F11's wiring does. The legend remains the first block after the title in every renderer.

---

## Observed, not counted

- `prompts/astra.md` contains a Sol prompt (13:45 validation and 14:30 fallback), while `config/models.json` assigns 13:45 validation to `prompts/validator.md` and lists Astra only as `gpt-6-astra` optional review. Two validator prompts for the same slot; Haiku's slice.
- `examples/test-digest.json` has `edition_date` 2026-09-16, so it fails `radar/domain.py` future check until that India date.
- `radar/sync.py:189` names files with `safe_slug(title)[:60]` but `write_dashboard:359` links with `safe_slug(title[:60])`; for titles over 60 characters with a space at the cut the wiki link is dangling.
- `radar/sync.py:243` writes the feedback file before `run_sync:388-391` persists `last_exported`; a crash between the two re-exports with a new UUID on the next run. Narrow window; deterministic per-note event IDs stored in frontmatter would close it.
- `google/Code.js:1052-1066` `sendTestDigest` does not acquire the lock and reads `SHEET_ID` without `setupRadar` guard; harmless in the documented order, wrong if run first.

## Acceptance for ticket 10

Do not attempt the live test until F1, F2, F3, F4, and F5 are fixed and both test suites pass. The live test then is: one contract-shaped bundle in `inbox/` before 17:00 IST, one email at or after 17:00, one owner reply `RATE ... 4 test` producing one `RatingEvents` row, one Obsidian rating producing one feedback file that produces one more `RatingEvents` row, and a `snapshot.json` whose items carry array guidance and `YYYY-MM-DD` dates.
