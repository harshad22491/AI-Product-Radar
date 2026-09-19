# Daily research migration — 19 September 2026

The owner authorized the working newsletter's GitHub Actions approach for both
Radar editions. This supersedes the old prohibition on Actions in BUILD-CONTRACT.

## Comparison and cause

The working Daily-News-Brief uses cron-job.org primary/backup dispatches, one
hosted build job, generation retries and a durable send log. Root econ PaperRec
runs a complete pipeline from Windows Task Scheduler, with successful logged
sends through September 18. Radar's Google timer was alive, but its separate
Claude cloud producers were paused after Drive scope failures. No new bundles
arrived after September 17. A timer status of `ok` hid the missing editions.

## Replacement

An independent job in the working newsletter's externally dispatched workflow
starts Radar's private `daily.yml`. It runs at the existing primary and backup
times, 07:15 and 07:55 India time. It does not depend on briefing generation.
Radar also schedules backups at 12:37, 14:37 and 16:37 India time. GitHub cron
can be delayed; the external dispatch remains the primary path.

The runner reads canonical Google state using direct OAuth, launches separate
Fable research and Opus source-review processes with public web tools only,
validates the bundle, calculates its immutable SHA-256 and uploads the approved
pair with byte-for-byte readback. Models do not receive Drive/GitHub secrets.
The existing deployment credential has `drive.file`, not unrestricted content
access: it can list gateway files but cannot download their contents. Google
therefore refreshes an Actions-created `actions-state.json` in the private
snapshot folder. The owner explicitly approved this exchange of recommendation
history, ratings/preferences, sanitized portfolio information and research
bundles. No source files from other projects enter the exchange. The runner
requires a fresh mirror and also reads its own pending current-day uploads.
Trashed originals are excluded because Google may have rejected them; accepted
bytes come from the authoritative mirror. Before upload, the host runs the exact
JavaScript gateway validator as well as Python validation to prevent rule drift.
Three attempts per edition handle failed generation/review. One failed edition
does not prevent processing the other. Workflow concurrency serializes backups;
current-day approved pairs or delivered editions are skipped.

Google retains responsibility for sending at or after 17:00 Asia/Kolkata,
ratings, shared deduplication, the delivery ledger and uncertain-send protection.
Unlike the news briefing, Radar cannot fall back to unreviewed snippets: its
source verification and seven-item requirements remain mandatory. A failed
edition reports failure and gets another scheduled attempt, never fabricated
content or a false delivery success.

## Credentials and operation

Radar secrets: `CLAUDE_CODE_OAUTH_TOKEN` (same subscription as the working news
briefing), `GOOGLE_DRIVE_OAUTH` (client ID/secret and refresh token from existing
authorized deployment). `RADAR_FOLDERS` contains only inbox, accepted and snapshot
folder IDs plus the app-owned `state` file ID. The newsletter's
`RADAR_DISPATCH_TOKEN` authorizes workflow dispatch.
No secrets belong in source, logs, artifacts or prompts. Subscription auth remains
in use; no paid model API fallback is configured.
When rotating the Claude subscription token, update both repositories' secrets.
If the GitHub dispatch credential is revoked, replace `RADAR_DISPATCH_TOKEN`.

Run `gh workflow run daily.yml --repo harshad22491/AI-Product-Radar -f check=true`
for a read-only hosted credential/state check. Omit `check` for a normal run.
Actions reports research/upload completion, not email receipt. Confirm
`runtime-status.json` and the Deliveries ledger after 17:00 for actual delivery.
Runtime status distinguishes waiting, blocked and delivered, with each edition's
state; a polling tick by itself is not success.

## Rollback and preservation

Canonical state, historical bundles, ratings, Sheet and vault remain intact.
Existing Claude cloud routines stay paused. To roll back, disable Radar's Actions
workflow and remove only the newsletter's independent Radar dispatch job. Do not
enable the old cloud routines until their actual Drive capability is repaired.
The Google mailer remains safe with either producer because approval and durable
duplicate protection are enforced at the delivery boundary.

## Verification

Local: 83 Python tests, 91 gateway scenarios, Gmail transport, owner activation
and cross-runtime parity suites pass. Regression tests cover false-success
status, exact approval hashes, repeated backup runs, rejection, previous delivery
and reviewer model identity. Live activation evidence follows.

The private hosted credential/state check passed on September 19:
[run 35426925469](https://github.com/harshad22491/AI-Product-Radar/actions/runs/35426925469).
Google deployment version 6 was verified by source readback and the unattended
06:32:40 UTC dispatcher tick exported the new waiting/missing-candidate status.
All three old Claude cloud routines were read back as `enabled: false`.
The working newsletter's independent dispatch job is saved in
[commit 96f8921](https://github.com/harshad22491/Daily-News-Brief/commit/96f89212ad838129e846d598acbf989432f51d58).
The one-time subscription-token copy succeeded and its temporary workflow was
removed. The first full diagnostic run
[35427022803](https://github.com/harshad22491/AI-Product-Radar/actions/runs/35427022803)
exposed JSON-response formatting and an independently rejected product claim.
It was stopped to inspect the logs. The parser now tolerates prose around one
JSON object, and retries receive the prior rejection reasons for correction.
The corrected run is
[35428086029](https://github.com/harshad22491/AI-Product-Radar/actions/runs/35428086029).
Its seven-item product edition was independently approved by Opus and accepted
by Google at 07:07 UTC. Readback confirmed Fable producer identity and the exact
candidate/approval SHA-256 match; the scheduled dispatcher reports product ready.
The same run completed successfully at 07:35 UTC. Its academic edition
(`academic-fable-2026-09-19-82270887019a`) also contains seven items, produced by
Fable and approved independently by Opus with a matching immutable SHA-256.
Academic review rejected unsupported claims in two attempts; the third passed,
demonstrating that rejection feedback and bounded retries work in production.
The queued backup
[35428751866](https://github.com/harshad22491/AI-Product-Radar/actions/runs/35428751866)
then succeeded in 17 seconds, reporting both editions `ready` with the same run
IDs and no new research or review calls. Authenticated exchange readback verified
both seven-item bundles and exact approval hashes. This verifies hosted research,
review, exchange and safe repeat execution. Today's actual email send is still
scheduled for 17:00 India time and was not forced early for this test. The
newsletter's next external scheduled dispatch will occur after this migration;
the manual hosted runs do not establish that a future scheduler has fired.

References: [GitHub workflow triggers](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
and [Google Drive multipart uploads](https://developers.google.com/workspace/drive/api/guides/manage-uploads).
