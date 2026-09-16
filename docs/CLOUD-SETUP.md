# AI Product Radar cloud setup

**Status: Google delivery and replies ACTIVE; automatic research BLOCKED.**

## Live status (2026-09-16)

| Component | Status | Evidence |
|---|---|---|
| Local build | Verified | 58 Python tests, 83 gateway scenarios, transport, activation and parity suites pass |
| Private GitHub repository | Published privately | Build commit 37d8273 pushed to main; GitHub is source storage only |
| Private Drive folder and native Google Sheet | Created | Nine database tabs verified through Drive MCP |
| Apps Script project and triggers | Active | Private version 4; activation, runtime and reply status files verified |
| Google Form | Optional, not created | Email and Obsidian are the current rating channels |
| Fable research and Opus independent review | Paused | Two Fable cloud runs failed Drive scope, including after reauthorization |
| OpenAI schedules and ten-day GitHub review | Not activated | No native schedule creation available in this session |
| Revised test email | Delivered and ratable | Gateway ledger sent; Gmail SENT and INBOX; seven registered items |

## What counts as activated

A schedule is live only when all three are recorded here: the provider task ID, one unattended run that started without the PC or a browser session, and the Drive file ID the run wrote. Native provider cloud tasks or routines are required. Claude CLI workers on the local PC are not cloud schedules and cannot stand in for one. If a provider cannot write to Drive unattended, that producer stays pending and reports `BLOCKED`.

No Anthropic API key is used and none may be configured. Claude runs use the Claude subscription cloud task feature. OpenAI runs use the OpenAI subscription scheduled task feature. A subscription does not provide API access and the docs must not claim it does.

## Roles and daily schedule (Asia/Kolkata)

The table below is the original proposed schedule, not a list of active jobs. `config/models.json` records the current amendment: paused Fable research at 12:30 and paused Opus independent review at 13:45 and 16:45 IST. OpenAI schedules are not provisioned.

| Time | Provider and model label | Role | Prompt |
|---|---|---|---|
| 10:00 | OpenAI, `gpt-5.6-sol` | Ten-day GitHub incremental review poll | `prompts/github-review.md` |
| 12:30 | Claude subscription, `Fable 5.1` | Primary research | `prompts/fable.md` |
| 13:45 | OpenAI, `gpt-5.6-sol` | Independent validation of inbox candidates | `prompts/validator.md` |
| 14:30 | OpenAI, `gpt-5.6-sol` | Research fallback | `prompts/sol.md` |
| 15:45 | Claude subscription, `Opus` | Research fallback | `prompts/opus.md` |
| 16:30 | OpenAI, `gpt-5.6-sol` | Research rescue | `prompts/sol.md` |
| 16:50 | OpenAI, `gpt-5.6-sol` | Second validation of inbox candidates | `prompts/validator.md` |
| 17:00 or later | Google Apps Script | Deliver the accepted edition by Gmail | `google/Code.js` |
| Manual only | OpenAI, `gpt-6-astra` | Optional complex review, advisory | `prompts/astra.md` |

Provider execution timing is not guaranteed; the gateway polls every five minutes and sends at the first opportunity at or after 17:00.

Rules that every task follows:

- `model_id` is the model label actually displayed in the session. Do not write API model ids. Do not self-upgrade to a newer model.
- Every fallback and rescue run first checks the Drive `accepted/` folder for a validated bundle with today's `edition_date`. An earlier task response or a candidate in `inbox/` does not count. If an accepted bundle exists, the run reports `NO-OP`.
- Delivered item IDs come from `snapshots/snapshot.json`, never from memory.
- A run that lacks a needed capability (Drive read, Drive write, browsing, hashing) reports `BLOCKED` with the missing capability.
- No run loosens criteria to reach seven items. A short day is recorded as undelivered.

## Drive exchange

```
<private Radar folder>
├── inbox/       immutable candidate bundles and validation attestations
├── accepted/    validated bundles (one winner per edition)
├── rejected/    validation reports
├── snapshots/   snapshot.json (items, digests, ratings)
├── feedback/    rating event files
└── reviews/     advisory Astra output, never read for delivery
```

Apps Script is the only Sheet writer. Sheet tabs: Items, RatingEvents, CurrentRatings, Repositories, Reviews, Runs, Deliveries, Sources, Preferences.

## Bundle rules (summary)

Full text in `docs/BUILD-CONTRACT.md`; reference example in `examples/test-digest.json`.

- At least seven items, all valid and unique. Academic within 2 calendar years of `edition_date`; other sources within 6 calendar months. Original publish or release date, never a crawl date. No future dates.
- `item_id` is `RAD-` plus the first 12 hex digits of SHA-256 of the canonical URL. `source_url` is https only.
- `guidance` is exactly five nonempty plain sentences in the order Where, Try, Benefit, Effort, Check.
- At least five product or tool items per edition; at most one security item, and only when work-relevant.
- Preprints and small maintainers are allowed with primary evidence and a stated status in `evidence_label`.
- Reruns cannot repeat delivered items unless a material release has a new canonical release URL.

Validate locally:

```
python -m radar validate examples/test-digest.json
python -m unittest discover -s tests -t .
node google/test_gateway.cjs
```

## Email, rating legend, and replies

The full legend sits at the top of every email, above the first item, in both HTML and text. It is never moved below the fold.

| Score | Meaning | What happens |
|---|---|---|
| 1 | Skip | Suppress similar items |
| 2 | Weak match | Reduce similar items |
| 3 | Useful | Keep the mix balanced |
| 4 | Strong match | Queue an investigation |
| 5 | Excellent | Propose an experiment only |

Ratings change relevance, never source credibility. Reason tags: `too technical` simplifies presentation, `already knew` suppresses repeats, `too much effort` favors smaller scope. Missing ratings are neutral.

Reply syntax, one line per rating, with the item's current revision as shown in the email:

```
RATE RAD-3751a967d486 5 REV=0 good match
```

`REV=n` is required. A reply whose revision is missing, unknown, or stale is recorded as a conflict and does not overwrite the current rating. Duplicate event IDs are ignored; the same event ID with a different payload is an error. Replies are accepted only from the configured owner address in a thread the script sent. All fields are HTML-escaped; model-authored HTML and recipient fields are never honored.

Delivery: the sender is the authorized Gmail account, the recipient is fixed to harshad422@gmail.com, and a Deliveries row is written before any send. Uncertain outcomes wait for manual reconciliation and are never blindly resent.

## Google gateway

Deployment steps, function list, and locking behavior are in `google/README.md`. Deploy the staged gateway, transport, activation, manifest and local configuration files; publish the owner-only web application and open its activation page. A test send never marks a regular edition delivered.

## Obsidian sync

`scripts/sync-vault.ps1` runs `python -m radar.sync`, which exports changed Obsidian ratings first, then imports snapshots while preserving the User notes section. It never overwrites an unsynced edit and makes no model or API calls. Run it at login or whenever the PC is online; the cloud continues while the PC is off.

## Activation checklist

- [x] Private Drive folder and native Sheet created
- [x] Private GitHub repository created
- [x] Repository pushed privately
- [x] Local test suites recorded as passing
- [x] Apps Script deployed, owner-authorized, and activated; Form optional
- [x] Revised test digest sent by the deployed gateway and received
- [x] Google delivery and reply triggers installed
- [ ] Each cloud task: task ID, unattended run, and Drive file ID recorded above
- [ ] First accepted edition delivered at or after 17:00
- [ ] Rating reply and Obsidian round trip verified

Mark ACTIVE only after every row above has evidence.

## Current activation amendment (2026-09-16)

This section supersedes historical setup tables above. Google owner authorization succeeded. Both delivery and email-reply triggers are installed and verified through activation-status.json. Dispatch polls every five minutes after 17:00 IST; reply import polls every fifteen minutes. Forms are optional and have not been provisioned.

Fable's self-contained cloud routine no longer needs a GitHub checkout. Two real cloud runs both stopped on the connected Google Drive service's insufficient-scope error, including the retry after user reconnection. They wrote no candidate. The routine remains paused until that connector works. The existing Opus draft was repurposed as an independent reviewer at 13:45 and 16:45 IST, also paused. Sol schedules and ten-day GitHub review are not yet provisioned. The original proposed schedule above is not a list of active jobs.

The gateway uses the Advanced Gmail API with gmail.modify, not GmailApp. The revised test is verified in Deliveries and Gmail; the subsequent dispatcher and reply scan both report success. The gateway writes runtime-status.json for operational diagnosis.

Completed local checks: 58 Python tests, 83 gateway scenarios, Gmail transport, owner-only activation and cross-runtime parity. The original preview reached SENT and INBOX through the Gmail connector. The revised, ratable preview was delivered by the Google gateway at 03:52:57 UTC. A real user rating round trip remains unverified.

The free Obsidian sync is installed as a per-user Windows startup loop, every fifteen minutes while online. Windows Task Scheduler was denied; no Windows scheduled task is claimed.

## Troubleshooting

- No edition delivered: check `Runs` and `Deliveries` tabs, then `rejected/` for the validation report. Confirm an accepted bundle for today's date exists.
- Email not received: check the Deliveries row status, Gmail authorization, and the owner address in Script Properties. Never resend an uncertain delivery without checking the Sent folder.
- Rating not applied: confirm the exact `RATE` line, the `REV=n` value, and that the reply came from the owner address.
- Sync problems: rerun `scripts/sync-vault.ps1` with the exchange and vault paths; unsynced edits are reported, not overwritten.
