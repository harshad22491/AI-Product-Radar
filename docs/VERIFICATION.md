# Verification and deployment status

Verified on 2026-09-16 UTC. **Google delivery and reply processing are running. Automatic research is blocked; the complete daily service is not yet active.**

## Live evidence

- Private Apps Script deployment version 4 is owner-authorized. `activation-status.json` confirms delivery and reply triggers. Dispatch checks every five minutes and sends approved daily editions at or after 17:00 Asia/Kolkata. Replies are checked every fifteen minutes.
- The rewritten seven-item test was sent through the deployed gateway's Advanced Gmail API at 03:52:57 UTC. The delivery ledger records `sent`; Gmail confirms SENT and INBOX. Subject: `[TEST] AI Product Radar — 2026-09-16 [2026-09-16-1010c619]`.
- All seven preview items are registered in the canonical Sheet and can be rated. Preview delivery does not consume a daily edition or mark items delivered in a regular edition.
- `runtime-status.json` reports `ok` at 03:58:54 UTC, after owner activation, proving a subsequent dispatcher execution.
- `reply-status.json` reports `ok` at 03:56:17 UTC: two threads scanned, zero rating commands. A real user rating reply has not yet been received and verified; no synthetic preferences were submitted.
- The separate Obsidian vault synchronized successfully from the project's Drive exchange. Free synchronization runs every fifteen minutes after Windows login while the PC is online. Windows Task Scheduler registration was denied; the per-user startup loop is the installed alternative.

Account-specific deployment IDs remain in ignored local configuration. The canonical Sheet has nine tabs: Items, RatingEvents, CurrentRatings, Repositories, Reviews, Runs, Deliveries, Sources and Preferences.

## Research blockers

Two actual Fable cloud runs, including a retry after the owner reconnected Google Drive, both failed with `Insufficient scope`. Neither read the project inputs nor wrote a research candidate. The routine uses a self-contained sanitized project specification and no longer requires a GitHub checkout.

Fable primary research and independent Opus review are configured but paused until the connector passes a project-folder read/write test. Opus review is scheduled in the draft for 13:45 and 16:45 IST. No Anthropic API key is used.

OpenAI Sol schedules, including the ten-day incremental GitHub review, are not activated. This session exposes no native schedule-creation tool; ChatGPT returned a verification/403 page in Playwright. The local incremental-review implementation does not prove unattended cloud execution.

## Automated verification

- 58 Python tests pass.
- 83 Google gateway scenarios pass.
- Separate Gmail transport, owner activation and Python/JavaScript parity suites pass.
- Coverage includes mandatory user-facing AI products after filtering, source-age limits, dashboard links after item-title changes, examples and HTML escaping, delivery timing, matching independent review hashes, durable send claims, typed Sheet values, preview/daily separation, owner-only reply parsing, quoted text, duplicate events, revision conflicts, offline notes and ten-day repository cursors.

Google-service unit tests use mocks. Live delivery and scans above are separate evidence; a real rating round trip and an unattended approved research edition remain unverified.

## Editorial and implementation review

The revised preview contains longer plain-language explanations, fictional examples tied to the owner's work and five practical application steps per finding. Its first item proposes a report question-answer assistant. A separate Sol review checked all seven release claims against primary sources and found no blocking editorial issue.

Ten original worker roles ran in separate Herdr tabs; those tabs were closed after completion. Claude workers used the Max subscription, Luna used Codex, and only the designated build-time sync worker used the approved OpenRouter route. Review documents describe earlier build stages; their original line numbers and findings are historical.

Resolved defects included mismatched producer schemas, drafts consumed before delivery time, items marked delivered too early, ignored Obsidian feedback, flattened snapshots, rating replay errors and stringified Sheet booleans. The current implementation preserves pending drafts, requires matching review hashes, reconstructs snapshots and ratings, and normalizes typed values.

## Practical limits

Provider jobs and Google triggers can run later than requested. Unknown email outcomes require reconciliation before retry. Large-mailbox history pagination and broader Unicode URL canonicalization are not certified by the current fixtures. Model review and schema validation do not guarantee factual accuracy. See [cloud setup](CLOUD-SETUP.md) for the remaining activation steps.

## Second mailer: academic papers (2026-09-16)

AI Research Radar is implemented with the same seven-item minimum, descriptive examples, five application steps, reply ratings, shared preferences and Obsidian archive. It requires formally published academic papers within two calendar years, plus a paper-backed end-user product concept. Separate channel delivery records allow both emails on the same day without duplicate sends.

63 Python tests and 87 gateway scenarios pass, along with Gmail transport, activation and cross-runtime checks for both real previews. New scenarios cover mixed-source rejection, missing publication evidence, preprint-host rejection, independent same-day sends, uncertain-send isolation, academic rating replies and preserving publication metadata.

The initial academic edition contains seven published ICML 2025 papers, verified against PMLR records. Its source notes distinguish publisher evidence from proposed portfolio applications. The local HTML is rendered in `out/academic-preview/academic-digest.html`.

Apps Script version 5 is deployed. At 05:44 UTC, activation-status.json lists both newsletters with active delivery and reply triggers, runtime-status.json reports success, and Gmail confirms SENT and INBOX for `[TEST] AI Research Radar — 2026-09-16 [2026-09-16-296ad395]`. The reply scan also reports success. All seven academic items imported into Obsidian, preserving their publication records. No user rating was fabricated.

Windows virtual-memory exhaustion briefly prevented deployment; the user freed memory and the deployment then completed. The existing Claude Drive scope blocker still prevents automatic research. The new Fable routine and updated dual-mailer reviewer prompt are prepared locally, but saving them through the Claude client did not complete: it exited after tool discovery without a create/update result. No new task ID or cloud prompt update is claimed. Google activation alone does not prove research execution.
