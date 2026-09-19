# AI Product Radar

A private research newsletter for harshad422@gmail.com, with a separate free Obsidian vault. Delivery target: every day at **17:00 Asia/Kolkata**, including weekends. Google checks every five minutes; exact start time is not guaranteed.

There are two separate mailers: **AI Product Radar** covers products, tools and techniques; **AI Research Radar** contains only formally published, peer-reviewed academic papers from the past two calendar years. Both use the same descriptive writing, seven-item minimum, practical examples, five application steps and reply ratings. The academic edition includes at least one proposed, paper-backed AI product for an end user. See [academic mailer](docs/ACADEMIC-MAILER.md).

## What each edition contains

- At least seven findings, including **one genuine AI product an end user can interact with**, such as a recommendation service or a document question-answer assistant.
- Plain explanations for a nontechnical reader: the practical task, why it could help, a fictional example from the owner's work, and five descriptive application steps.
- Primary-source links and original dates. Academic papers: at most two calendar years old. Other sources: at most six calendar months old.
- The complete 1–5 rating legend at the top, plus an item-specific reply template. A 4 requests investigation; a 5 proposes an experiment. Neither changes a repository automatically.

## Cloud components

The September 19 repair moves Fable subscription research and separate Opus review into GitHub Actions, using direct Google API state exchange. It reuses the working news briefing's external scheduler and adds backup runs. No Anthropic API key or paid Obsidian Sync is used. See [migration and activation evidence](docs/ACTIONS-MIGRATION.md).

Google Apps Script manages delivery, reply ratings, the canonical Google Sheet, and a private Drive exchange. The local PC only synchronizes Markdown notes into Obsidian; it is not the cloud email host.

## Operational status

As of September 19, the GitHub Actions replacement is deployed and the external dispatch job is installed. A full hosted run produced independently approved seven-item bundles for both editions; a second run safely skipped both without new research. Google deployment version 6 exports an Actions-readable state mirror and per-edition delivery status. Today's email delivery remains scheduled for 17:00 India time; research completion is not confirmation of receipt. The old Claude cloud routines remain paused. See [current migration evidence](docs/ACTIONS-MIGRATION.md); the older verification/cloud-setup documents describe the superseded Drive-connector failure.

The academic extension uses the same authorized Google service. Its seven-paper test was delivered to SENT and INBOX and synchronized into Obsidian on 2026-09-16. Both mailers retain independent daily delivery tracking and shared reply ratings. The Actions replacement handles both editions without using Claude's Drive connector.

The original preview was delivered through the Gmail connector. The rewritten preview was sent by the real Google gateway on 2026-09-16; the delivery ledger records sent and Gmail confirms SENT and INBOX. Its seven items are registered for ratings.

## Read and rate

Open `D:\Paper Recommender\AI Product Radar Vault` as an Obsidian vault. Start with Dashboard or Digests. Each Items note shows a blank `rating` field and an optional `rating_reason`. Enter 1–5 to rate; leaving it blank submits nothing. Numeric text from Obsidian's property editor is accepted too. The note includes the current reply command for email ratings.

To rate a newsletter item by email, reply with the template shown under that item, replacing SCORE with 1–5, for example:

```text
RATE RAD-0123456789ab 4 REV=0 Useful for report preparation
```

Use the actual item ID. Replies are read every 15 minutes. The revision prevents an old reply from replacing newer feedback. Only replies from the owner in issued newsletter threads are accepted. Quoted text and duplicates do not create new ratings.

## Verification

```text
python -m unittest discover -s tests -q
node google/test_gateway.cjs
node google/test_gmail_transport.cjs
node google/test_activation.cjs
node google/test_parity.cjs
```

The suites cover content rules, selection, reply replay, offline notes, preview/daily separation, independent review, UTF-8 email transport, owner-only activation and Python/JavaScript compatibility. Google-service tests use mocks; live status is documented separately.

## Layout

`radar/`: Python 3.11 standard-library domain, ranking, rendering and Obsidian sync.
`google/`: Apps Script gateway, Gmail API transport and activation page.
`prompts/` and `config/`: research instructions and source/topic/model configuration.
`docs/wayfinder/map.md`: development map. `docs/PORTFOLIO-OVERVIEW.md`: sanitized work profile.

Read-only incremental GitHub review every ten elapsed days remains implemented locally but its unattended OpenAI schedule is not activated. Client records, private source, credentials and local deployment identifiers are excluded from Git.
