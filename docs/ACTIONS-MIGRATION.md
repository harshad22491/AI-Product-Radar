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

Local: 78 Python tests, 91 gateway scenarios, Gmail transport, owner activation
and cross-runtime parity suites pass. Regression tests cover false-success
status, exact approval hashes, repeated backup runs, rejection, previous delivery
and reviewer model identity. Live activation evidence is recorded below after
the hosted workflow runs.

References: [GitHub workflow triggers](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
and [Google Drive multipart uploads](https://developers.google.com/workspace/drive/api/guides/manage-uploads).
