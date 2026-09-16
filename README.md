# AI Product Radar

A private research newsletter for harshad422@gmail.com, with a separate free Obsidian vault. Delivery target: every day at **17:00 Asia/Kolkata**, including weekends. Google checks every five minutes; exact start time is not guaranteed.

## What each edition contains

- At least seven findings, including **one genuine AI product an end user can interact with**, such as a recommendation service or a document question-answer assistant.
- Plain explanations for a nontechnical reader: the practical task, why it could help, a fictional example from the owner's work, and five descriptive application steps.
- Primary-source links and original dates. Academic papers: at most two calendar years old. Other sources: at most six calendar months old.
- The complete 1–5 rating legend at the top, plus an item-specific reply template. A 4 requests investigation; a 5 proposes an experiment. Neither changes a repository automatically.

## Cloud components

Fable 5.1 researches through the Claude subscription. A separate Opus routine is configured for independent review because Sol cloud scheduling is unavailable in the current session. Sol remains the preferred OpenAI reviewer when its schedule can be provisioned. No Anthropic API key, GitHub Actions, or paid Obsidian Sync is used.

Google Apps Script manages delivery, reply ratings, the canonical Google Sheet, and a private Drive exchange. The local PC only synchronizes Markdown notes into Obsidian; it is not the cloud email host.

## Operational status

Google's owner authorization and delivery/reply triggers were verified on 2026-09-16. Research routines remain paused until Claude's Drive connector passes a real read/write test: the first run and the retry after reconnection both returned insufficient scope. An installed delivery timer does not by itself prove that new editions will be produced. See [verification](docs/VERIFICATION.md) and [cloud setup](docs/CLOUD-SETUP.md) for evidence and remaining work.

The original preview was delivered through the Gmail connector. The rewritten preview was sent by the real Google gateway on 2026-09-16; the delivery ledger records sent and Gmail confirms SENT and INBOX. Its seven items are registered for ratings.

## Read and rate

Open `D:\Paper Recommender\AI Product Radar Vault` as an Obsidian vault. Start with Dashboard or Digests. Each Items note accepts numeric `rating` (1–5) and optional `rating_reason` properties.

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
