# Astra architecture review

> Historical build-stage review. See [current verification](../VERIFICATION.md) for resolved findings and remaining blockers.

Reviewed: 2026-09-15
Scope: `docs/BUILD-CONTRACT.md` and the repository planning documents
Decision: **conditional go for implementation; no-go for unattended deployment until the P0 rules below are added and proven**

## Executive assessment

The local Python domain, rendering, ranking, and offline-sync work is feasible with the stated standard-library constraint. Google Apps Script can act as the single cloud reducer and mail sender. Subscription-backed Claude and ChatGPT cloud jobs can also run while the PC is off.

The contract does not yet define a system that can reliably join those pieces. Its largest assumption is that four subscription products behave like endpoints behind one failover router. They do not. A subscription login is not a portable inference credential, and the Google gateway has no specified authenticated ingress, candidate-selection protocol, or way to observe provider completion. Current Claude Routines do expose a subscription-only `/fire` control endpoint, but it is a research-preview endpoint for a preconfigured routine, not a general model-routing interface; there is no equivalent stable cross-provider interface in this contract. Anthropic also documents subscription and API billing as separate systems. See [Claude subscription authentication](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan), [Claude Routines](https://code.claude.com/docs/en/routines), and [ChatGPT scheduled tasks](https://help.openai.com/en/articles/10291617-chatgpt-tasks).

The appropriate architecture is therefore provider-native scheduling plus a shared, deterministic Google state machine:

```text
provider-native Fable / Astra / Opus / Sol jobs
                    |
          authenticated create-only ingress
                    v
     immutable candidate + validation journal
                    |
        Apps Script reducer under ScriptLock
                    v
       sealed edition + versioned snapshot
                    |
       durable delivery outbox -> Gmail

email / Form / Obsidian rating commands
                    |
          immutable RatingEvents journal
                    v
              current projections
```

Google decides which already-produced candidate wins. It must not pretend to invoke, route, or retry subscription model inference unless a separately verified provider-native trigger supports that operation.

## Priority summary

| Priority | Finding | Required result |
|---|---|---|
| P0 | Subscription fallback has no coordination protocol | Independent jobs publish candidates; Google deterministically selects and seals one |
| P0 | Provider-to-Google bridge is unspecified | One authenticated, unattended, tested ingress and one read-only status path |
| P0 | “Immutable” processing is not transactional | Hash-addressed journal, idempotent reducer, versioned snapshots, and a real outbox |
| P0 | Rating conflict rules cannot work through the stated email/Form interfaces | Every command carries or is securely bound to the revision the user saw |
| P0 | Private-repository safety is prompt-only | Read-only authorization plus an enforceable repository/content allowlist or sanitized input |
| P0 | 17:00 is described more precisely than Apps Script guarantees | Never-before guard, short polling trigger, explicit late/missed policy, measured timestamps |
| P1 | Bundle v1 leaves cross-runtime validation ambiguous | Normative canonicalization, limits, enums, collision rules, and shared conformance vectors |
| P1 | Review, validation, experiment, and delivery records have no schemas | Add versioned envelopes and state transitions for each |
| P1 | Deployment status can be inferred from documentation | Evidence-backed activation checklist and explicit `PENDING`/`VERIFIED` states |
| P2 | File ownership and operational limits are incomplete | Disjoint review filenames, quotas, retention, observability, and recovery rules |

## P0 findings and concrete fixes

### 1. Subscription cloud fallback is not an API routing layer

The four clock times define desired starts, not a failover algorithm. A delayed Fable run can race an Astra or Opus run; a task cannot infer that a prior task failed merely because its output is not visible at one instant; and a late higher-priority result must not replace an edition already emailed. `producer` and `model_id` do not capture whether Astra validated Fable or independently produced a fallback.

Current product behavior reinforces the distinction:

- Claude Routines run in Anthropic's cloud, can be scheduled, and may start a few minutes late because of stagger. Their `/fire` endpoint is expressly research preview and triggers a saved routine; it is not the Anthropic Messages interface. [Claude Routines](https://code.claude.com/docs/en/routines)
- ChatGPT scheduled work is native to the ChatGPT account and connected-app permissions. The cited interface documents scheduled and supported event triggers, not an arbitrary subscription-inference endpoint that Google can use as a symmetric router. [ChatGPT Work and Codex](https://help.openai.com/en/articles/20001275/)
- Supplying an Anthropic API key changes Claude Code to separately billed API usage. That would violate the no-API-key constraint. [Anthropic authentication precedence](https://code.claude.com/docs/en/team)

**Fix:** make each provider task independent and add these persisted records:

- `Candidate`: `schema_version`, `submission_id`, `edition_date`, `run_id`, `payload_sha256`, `producer`, `requested_model`, `observed_model`, `model_id_source`, `attempt_role` (`primary` or `fallback`), `submitted_at`, and the digest payload.
- `Validation`: `validation_id`, `edition_date`, `validator`, `validated_run_id`, `validated_payload_sha256`, `decision` (`pass` or `fail`), `reasons`, and `created_at`.
- `Edition`: `edition_date`, `state` (`COLLECTING`, `READY`, `SEALED`, `DELIVERY_UNKNOWN`, `DELIVERED`, `MISSED`), `selected_run_id`, `selected_payload_sha256`, `selection_reason`, `sealed_at`, and monotonically increasing `state_revision`.

At its native schedule, each fallback reads the Google edition status and may publish a candidate; it never calls another model. At 17:00 or later, Apps Script seals exactly one candidate using a declared order such as: Astra-attested Fable, Astra fallback, Opus fallback, then Sol fallback. Unattested Fable is not equivalent to Astra validation. A candidate arriving after `SEALED` is retained as `SUPERSEDED_LATE` and cannot cause a second delivery. Same `run_id` plus same hash is idempotent; same `run_id` plus a different hash is an integrity error.

This also requires changing `kind=digest` into an envelope that can distinguish `digest`, `validation`, `repository_review`, and `experiment_proposal`, or defining separate versioned schemas. Otherwise Astra's validation cannot be represented without masquerading as a digest.

### 2. The Google bridge is a missing seam

The contract names Drive folders but never says how an unattended Claude or ChatGPT job creates an inbox file, reads edition status, authenticates, handles a timeout, or learns whether a submission was accepted. Writing a prompt that says “save to Drive” is not an interface.

Connector capabilities also differ. ChatGPT Google Drive actions depend on plan, granted Google scopes, workspace controls, and the particular action; mutating actions can require confirmation. Claude Routines include configured connectors in autonomous runs and warn that included connectors may have write tools. See [ChatGPT Google Drive setup](https://help.openai.com/en/articles/10929079) and [Claude Routines connectors](https://code.claude.com/docs/en/routines).

**Fix:** define a `CloudExchange` interface with exactly two operations:

1. `submit(envelope) -> {submission_id, payload_sha256, disposition}` where disposition is `RECEIVED`, `DUPLICATE`, or `REJECTED` with stable reason codes.
2. `get_edition_status(edition_date) -> {state, state_revision, selected_run_id?, updated_at}` with no state mutation.

Use one adapter in production and one in tests. The preferred production adapter is a dedicated Google Drive connector that has been proven, in an unattended scheduled run, to create a new file in only the inbox and read only a minimal status artifact. If either provider cannot do that, use an HTTPS `doPost` web-app ingress executing as the owner, a 256-bit rotatable capability kept in Script Properties and the provider's secret store, a strict JSON content type, a small body limit, and no secret in the URL. Apps Script web-app request handling is defined around `doGet(e)` and `doPost(e)` parameters; do not assume arbitrary authorization headers are available without an integration test. [Apps Script web apps](https://developers.google.com/apps-script/guides/web)

`doGet` may return status or render a form only. All writes must use authenticated `doPost`, a native Form submit event, or the Drive inbox. Deployment is blocked until both a successful unattended submission and a rejected bad-secret submission are observed. Do not use the private GitHub repository as a message bus; that contradicts the stated data boundary.

### 3. Immutability and transaction semantics are incomplete

Drive files are mutable, Sheet updates are not a multi-table transaction, and `ScriptLock` only prevents concurrent script sections; it does not make Drive, Sheets, snapshots, and Gmail one atomic commit. The listed folders omit the “durable outbox” that the contract requires. `snapshot.json` replacement can also expose a partially updated or mismatched projection to the Windows sync.

**Fix:** define logical immutability and recovery explicitly:

1. On intake, read exact bytes once, enforce size limits, compute SHA-256, and journal `(Drive file_id, submission_id, payload_sha256)` before projection work.
2. Never treat a reused file name as identity. If a previously seen file ID or run ID changes hash, quarantine it as `MUTATED_INPUT`.
3. Store accepted payloads under hash-addressed names and never edit them. Moving an input is allowed; changing its bytes is not.
4. Under `ScriptLock`, append an `ACCEPTED` journal record, apply idempotent projections, then append `APPLIED`. On interruption, the next dispatcher resumes from the journal. `Items`, `CurrentRatings`, repository profiles, and preferences are projections; `Runs`, `RatingEvents`, validations, reviews, and delivery attempts are append-only facts.
5. Write `snapshot-<state_revision>-<sha256>.json`, verify its hash, then replace a small `snapshot-latest.json` manifest containing the versioned file ID and hash. Keep `snapshot.json` only if its non-atomic replacement risk is explicitly accepted. The local sync must validate the manifest/hash before import.
6. Add an `outbox` folder or make `Deliveries` an explicitly durable outbox. Required states are `PREPARED`, `SENDING`, `UNKNOWN`, `SENT`, and `FAILED_RETRYABLE`; every record contains `delivery_id`, edition, selected payload hash, recipient, subject token, attempt count, and timestamps.

`MailApp.sendEmail` returns `void`, so “send succeeded” cannot be established from a provider message ID returned by the call. After an exception or timeout, record `UNKNOWN`; reconcile by searching the authorized account's Sent mail for the unique delivery token before retrying. Never automatically retry `UNKNOWN`. [Apps Script MailApp](https://developers.google.com/apps-script/reference/mail/mail-app)

### 4. Ratings are internally sound but externally incoherent

The event reducer rules are close to correct, but the input interfaces cannot supply the required concurrency token. `RATE RAD-id 5 good match` contains no `base_revision`. A Form link also has no stated revision or integrity binding. If Apps Script fills in the current revision at processing time, a stale user action silently overwrites a newer rating, directly violating the contract.

**Fix:** specify these rules:

- An unrated item has revision `0`. An accepted event must have `base_revision == current_revision`; it becomes revision `current_revision + 1`. Acceptance order under `ScriptLock`, not `created_at`, determines current state.
- Email keeps the simple reply syntax only when the command is a reply in a known delivery thread. The delivery manifest stores the displayed revision for every item, and Apps Script derives `base_revision` from that immutable manifest. A standalone email with no known delivery/thread binding is rejected. Alternatively, change the syntax to `RATE RAD-… 5 REV 3 good-match`.
- A Form submission includes `item_id`, `base_revision`, `delivery_id`, and a signed nonce bound to those values. GET/prefill performs no mutation; only the submit event creates an event.
- Obsidian exports the revision from its last verified snapshot. A conflict is written to a conflict file/report and the local note is not overwritten.
- `event_id` generation is deterministic for polled Gmail messages and Form responses (source record ID plus normalized command), so polling is idempotent. Locally authored events use UUIDv4. Define UUID syntax and canonical payload serialization.
- Duplicate `event_id` compares every normalized immutable field. Exact equality is ignored; any difference is `EVENT_ID_REUSE`.
- Reject an event for an unknown `item_id`. Validate scores as numeric integers in both runtimes; JavaScript booleans and numeric strings are invalid.
- Split `reason` into `reason_tag` and optional `reason_text`. Declare tags such as `good-match`, `too-technical`, `already-knew`, and `too-much-effort`; declare case, whitespace, and unknown-tag behavior.
- Ratings alter only a relevance feature. Credibility/evidence fields are immutable inputs to a separate scoring term. A score of 4 creates one idempotent investigation queue record; 5 creates one proposal record, never a repository write.

For Gmail, matching the visible `From` string alone is not an authentication rule. Process commands authored in the configured account's Sent mailbox and belonging to a known delivery thread, rather than accepting arbitrary inbound mail that claims the address. Store the Gmail message ID as `source_ref` and label it only after the rating transaction commits.

### 5. Private GitHub review is not safely enforceable as written

The review schedule and cursor principle are good, but no read adapter, repository allowlist, file policy, review schema, or force-push behavior is defined. “Do not read credentials/customer data” in a prompt does not enforce that exclusion when a cloud job clones the complete private repository.

This matters because current Claude Routines clone selected repositories on every run and can create/push `claude/` branches by default; autonomous routines have no approval prompt and included connectors can write. That conflicts with “no writes.” [Claude Routines repository permissions](https://code.claude.com/docs/en/routines) ChatGPT's GitHub app is documented as read-only for repository search and analysis, including authorized private repositories, making it a better fit for Astra's read-only review role, though private-repository authorization still must be verified. [Connecting GitHub to ChatGPT](https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt)

**Fix:** use one of two explicit modes:

- `SANITIZED_PROFILE` (required for repositories containing excluded material): a deterministic local or separately trusted extractor emits only allowlisted metadata, documentation, dependency manifests, and selected diff hunks. Cloud models never receive the full repository. Reviews can run when the PC next comes online; the cloud may use the dated prior baseline meanwhile.
- `DIRECT_READ_ONLY` (only for repositories approved as safe for provider access): use the ChatGPT read-only GitHub connection or a GitHub App/fine-grained token scoped to selected repositories with `Contents: read` and metadata only. GitHub recommends selecting the minimum repositories and permissions. [GitHub fine-grained tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)

Do not use a Claude Routine attached directly to a reviewed repository unless write capability is technically removed, not merely forbidden by the prompt. If the product cannot remove its default branch-write capability, it fails this contract's direct-review mode.

Add a `RepositoryReview v1` record with `repository_id` (sanitized), `mode`, `default_branch`, `base_sha`, `head_sha`, `started_at`, `completed_at`, `coverage_manifest`, `evidence[]` containing sanitized `commit` and `path`, `inferences[]`, `status`, and `failure_code`. Define “successful coverage” as every allowlisted path/category at `head_sha` either examined or explicitly recorded as absent. Advance `last_successful_review_at` and the SHA cursor only for that status. A force push or missing base SHA produces `CURSOR_DIVERGED` and requires a new bounded baseline; it must not silently diff unrelated histories.

Ten elapsed days means `now_utc >= last_successful_review_at + 240 hours`. A `BASELINE_ONLY` result shows the baseline's date, does not advance the cursor or last-success time, and cannot claim current repository coverage. Repository content is untrusted data: instructions found in files must never expand tools, paths, network access, or write permissions.

### 6. 17:00 Asia/Kolkata needs an honest precision contract

An Apps Script daily trigger at hour 17 is insufficient: Google documents that recurring clock triggers may be randomized within the hour, while `nearMinute` is plus or minus 15 minutes and could run before 17:00. Apps Script also has quotas and transient failures. [Installable trigger timing](https://developers.google.com/apps-script/guides/triggers/installable), [ClockTriggerBuilder](https://developers.google.com/apps-script/reference/script), and [Apps Script quotas](https://developers.google.com/apps-script/guides/services/quotas)

**Fix:** install one short recurring trigger, preferably every minute, and put the precision in `dispatchRadar()`:

- Compute `edition_date` and local clock from the same captured `now` using the literal IANA zone `Asia/Kolkata`; never rely on script, Sheet, browser, account, or machine defaults.
- Return without mutation before local 17:00:00.
- At or after 17:00, acquire `ScriptLock`, reconcile any `UNKNOWN` delivery, select/seal if needed, and send only an unsent sealed edition.
- Keep pre-17:00 polling extremely cheap so the consumer-account trigger-runtime quota is not consumed by Drive scans. Check a Script Property first and perform heavy work only when due.
- Record `scheduled_for`, `trigger_started_at`, `sealed_at`, `send_attempted_at`, `sent_confirmed_at`, and `lateness_seconds` in UTC.

The promise should read: **never intentionally send before 17:00 IST; attempt at the first successful dispatcher run at or after 17:00; exact send or inbox-arrival time is not guaranteed.** Set an operational objective, not a false guarantee—for example, attempt by 17:02 on healthy days and alert on lateness over 10 minutes.

Define the terminal policy now: accept late candidates until 23:59:59 IST if the edition is still unsealed; after that record `MISSED_NO_VALID_BUNDLE`, do not invent filler, and do not send yesterday's digest as today's. A sealed/sent edition is immutable. The following day's jobs cannot reuse its items.

## P1 interface defects

### Bundle v1 needs one normative cross-runtime definition

Python validates bundles, but Apps Script must independently validate the same bytes. Without a normative algorithm and conformance vectors, the two implementations will drift. Before implementation, add these rules to the contract and give one owner permission to add shared valid/invalid JSON fixtures:

- State whether validators return a deep normalized copy and never mutate input; give stable error codes and JSON paths in `ValueError` messages.
- Define `canonical_url` completely: accepted schemes, IDNA/Unicode handling, lowercase host, default ports, path normalization, fragment removal, query and tracking-parameter policy, trailing slash policy, and percent-encoding. Do not sort or discard query parameters without an explicit source rule because that can change resource identity.
- SHA-256 uses UTF-8 bytes of the canonical URL and the first 12 lowercase hexadecimal characters. If one `item_id` maps to two canonical URLs, reject with `ITEM_ID_COLLISION`; never merge them.
- Define uniqueness within and across editions by canonical URL/item ID. Persist the delivered-item ledger. Material releases require a distinct canonical release URL; a changed title or summary is not material.
- Define inclusive calendar-age arithmetic, including month-end and leap-day behavior. Compare `published_at` to `edition_date`, not server “today.”
- Reject unknown fields or explicitly preserve them; currently neither behavior is stated. Add maximum item count, string lengths, topics count, bundle byte size, Unicode normalization, and control-character rules.
- Replace positional `guidance` strings with an object keyed by `where`, `try`, `benefit`, `effort`, and `check`, or require those five exact prefixes in that exact order.
- Define `evidence_label` as an enum with evidence requirements. Define the shapes of `source_dates` and `repository_evidence`; the latter must not leak private repository names, sensitive paths, excerpts, or URLs into email/Obsidian.
- Separate `producer` (task identity) from provider, requested model, observed model, and how the model identity was observed. If a subscription surface exposes only a configured display label, record `model_id_source=configured`; do not call it an observed actual model.

Also reconcile “items (7+)” with “normally seven” by defining a bounded range, recommended 7–10. An invalid or short candidate is rejected atomically; there is no partial acceptance.

### Missing record schemas

`Repositories`, `Reviews`, `Runs`, `Deliveries`, `Sources`, and `Preferences` are named but not defined. Validation attestations and experiment proposals are behaviorally important but also have no interface. Add versioned schemas, primary/idempotency keys, immutable versus projected fields, state transitions, and retention rules for each before teams implement them independently.

The local snapshot also needs a monotonic `state_revision`, `payload_sha256`, and a precise meaning for `digests`: full accepted candidates, only sealed editions, or delivered editions. Recommended: snapshot only sealed editions, with delivery status adjacent; keep rejected/superseded candidates out of the sync projection.

### Owned file boundaries overlap and omit shared artifacts

“Astra reviews and Fable reviews: own `docs/reviews/*.md`” gives two writers the same boundary. Assign disjoint prefixes (`astra-*` and `fable-*`) or explicit filenames. No owner may currently add conformance fixtures, schema documents, or an integration harness spanning Python and Apps Script. Assign those files before parallel implementation. Interface conformance tests should exercise public seams rather than duplicate each module's internal tests.

## Honest deployment and acceptance status

This review assesses the contract, not the correctness of implementation files that may be created concurrently. The presence of local source, tests, prompts, or setup instructions is not evidence that any cloud resource was provisioned or activated. No deployment identifiers, authorization evidence, verified trigger execution, accepted production bundle, or confirmed mail receipt were examined. Therefore the only status supported by this review is:

> **CONTRACT REVIEWED; IMPLEMENTATION NOT VERIFIED; CLOUD ACTIVATION NOT VERIFIED; TEST EMAIL DELIVERY NOT VERIFIED.**

Documentation or generated setup instructions are not deployment. Maintain an activation checklist with evidence and timestamps:

1. Local unit and cross-runtime conformance tests pass.
2. Apps Script project, Drive folders including outbox, Sheet tabs, and Form exist; their IDs are stored only in Script Properties.
3. Required OAuth scopes are authorized by the account that owns the trigger and sends mail.
4. The recurring trigger exists, its creator is the authorized sender, and a real execution is visible.
5. Every provider-native task exists, is enabled, uses the documented timezone/model, and has a successful run URL/history.
6. Private GitHub access is verified against one approved repository in the selected safety mode; prohibited writes are technically unavailable.
7. Good and bad ingress authentication tests, duplicate/hash-conflict tests, stale-rating tests, partial-projection recovery, and unknown-mail reconciliation all pass.
8. A test bundle traverses the real bridge and a test email is confirmed received at the fixed recipient. It is recorded as `delivery_type=TEST` and never marks a regular edition delivered.
9. One regular 17:00 run records actual timing and delivery evidence.

Each item is `PENDING` until observed, then `VERIFIED` with who/when/evidence. Failures return the item to `PENDING` or `DEGRADED`; setup text must never set it to verified.

## Recommended implementation order

1. Amend the contract with the candidate/validation/edition state machine, CloudExchange interface, rating revision binding, and private-repository modes.
2. Freeze Bundle v1 canonicalization and add cross-runtime fixtures.
3. Implement and test the pure Python reducer/renderer/ranking seams.
4. Implement Apps Script intake, journal/reducer, versioned snapshot, and outbox recovery before Gmail or Forms.
5. Prove one provider's unattended bridge, then add the remaining provider-native schedules and deterministic fallback selection.
6. Add rating channels and offline sync, including deliberate stale/conflict tests.
7. Activate private-repository review only after read-only and content-scope controls are proven.
8. Perform the real test delivery and mark deployment verified only from observed evidence.

With those changes the design is implementable without GitHub Actions or an Anthropic API key. Without them, a demo may work on a healthy day, but the system cannot truthfully claim automatic fallback, immutable processing, coherent concurrent ratings, private-repository containment, precise 17:00 delivery, or completed deployment.
