# Final integration review

> Historical build-stage review. See [current verification](../VERIFICATION.md) for resolved findings and remaining blockers.

## P0 — Valid pre-17:00 bundles are consumed without ever being delivered

`google/Code.js:1017-1032` accepts each inbox bundle, records its items, and trashes the input immediately. Delivery at `google/Code.js:1035-1040` can only select from the current invocation's in-memory `validatedBundles`. With the contracted final producer running at 16:30 and the dispatcher polling every 15 minutes, a pre-17:00 poll can consume the bundle; the first poll at or after 17:00 then sees an empty inbox and sends nothing. The same code records every accepted item as delivered before any successful send, so those never-emailed items also suppress later reruns.

## P0 — The Python and cloud Bundle v1 validators are wire-incompatible

The contract, prompts, and `radar/domain.py:295-298` require `guidance` to be a list of exactly five strings. `google/Code.js:249-264` rejects lists and requires an object keyed by `Where/Try/Benefit/Effort/Check`, so contract-compliant producer bundles are rejected by the cloud gateway. Item identity also diverges: `google/Code.js:174-203` removes tracking parameters while `radar/domain.py:173-180` retains and sorts them, producing different `RAD-` hashes for the same input URL. The two validators additionally disagree on run-id syntax, optional-field shapes, unknown fields, and nonempty topics. There is no shared parity fixture, and the gateway tests encode the incompatible object shape at `google/test_gateway.cjs:151-165`.

## P0 — Obsidian feedback files have no cloud consumer

`radar/sync.py:229-244` writes valid immutable rating bundles into `feedback/`, but the Google implementation only provisions that folder (`google/Code.js:52-58`). `dispatchRadar` reads inbox bundles and exports snapshots (`google/Code.js:999-1043`) without ever enumerating or reducing feedback files. Obsidian ratings therefore never reach `RatingEvents`, `CurrentRatings`, or relevance learning.

## P1 — The snapshot reducer emits and accepts the wrong schema

`google/Code.js:949-980` exports flattened Sheet rows: guidance is split into `guidance_where` etc., topics is a comma-delimited string, and `digests` contains run-id strings rather than the contracted accepted bundles. `radar/sync.py:138-171` validates only a few item fields, ignores `updated_at`, and accepts any list as `digests`; `render_item_note` then looks only for list-valued `guidance` at `radar/sync.py:283-286`. A real cloud snapshot is accepted locally but silently produces incomplete Obsidian notes and cannot reproduce accepted digests; a stale snapshot is also not rejected by timestamp.

## P1 — An acknowledged offline rating never advances its local base revision

After exporting an offline edit, `radar/sync.py:238` stores the event's old base revision in `last_exported`. When the cloud later echoes the accepted score/reason at revision +1, `radar/sync.py:339-343` treats the differing revision as another local edit and preserves the old frontmatter revision; nothing reconciles `last_exported` to the accepted revision. The next local correction is emitted against the old base revision and is guaranteed to conflict instead of becoming the new current rating.

## P1 — Gmail rating replay is not idempotent across trigger retries

`google/Code.js:1199-1211` assigns a fresh random UUID every time it scans a RATE reply and marks the message read only after applying all commands. If execution stops after `applyRatingEvent` but before `markRead`, the next trigger gives the same reply a new event ID, accepts it at the new current revision, and increments the rating again. The duplicate-event rule cannot detect this replay.

## P1 — The durable outbox does not prevent a duplicate daily email

`google/Code.js:917-944` appends separate `pending` and outcome rows but the send gate consults only `LAST_DELIVERED_EDITION_DATE`, not those durable records. A crash after Gmail accepts the message but before the delivered-date property is written leaves either `pending` or `sent` evidence while the day remains eligible. If another valid bundle arrives that day, it is sent automatically. `reconcileUncertainDeliveries` at `google/Code.js:1222-1226` only lists `uncertain` rows, ignores `pending`, and cannot close either state, so the outbox does not provide the promised reconciliation barrier.

## P1 — The production recipient is mutable away from the approved address

`google/Code.js:683-684` reads `OWNER_EMAIL` from Script Properties and `google/Code.js:911-925` sends the private digest to that value without asserting it equals `harshad422@gmail.com`. `google/README.md:72-76` explicitly instructs operators how to choose another address. A stale or mistyped property therefore sends both test and production mail to the wrong recipient, contrary to the fixed-recipient boundary.

## P1 — Future editions and future source dates can be accepted and emailed

`google/Code.js:338-378` checks item dates only against the model-supplied `edition_date`; it never checks that edition date against the current India date. `dispatchRadar` likewise does not require the bundle edition to equal the dispatch India date (`google/Code.js:1035-1040`). A bundle dated in 2099 with 2099 publication dates validates today and can be emailed, while the Python validator correctly rejects future editions at `radar/domain.py:239-245`.

## P1 — Scheduled roles and times contradict the approved four-task schedule

The contract requires exactly 12:30 Fable, 14:30 Astra, 15:45 Opus, and 16:30 Sol, with Astra's routine validation distinct from fallback. `config/models.json:9-13` and `docs/CLOUD-SETUP.md:28-38` instead add 13:45 and 16:50 Sol validators and assign the 14:30 role to Sol; `prompts/astra.md:1-3` explicitly removes Astra from the daily schedule. Activating the documented configuration would run the wrong provider/role sequence.

## P1 — The documented Apps Script test gate is red

`node google/test_gateway.cjs` exits nonzero: 50 tests pass and 3 fail at `google/test_gateway.cjs:185`, `:343`, and `:406`. All three use `assert.deepStrictEqual` on arrays/objects created in a separate `vm` realm, which Node does not consider prototype-equal. This is a harness defect rather than evidence that the corresponding pure functions are wrong, but it makes the repository's documented no-dependency gateway verification command unusable as a release gate.
