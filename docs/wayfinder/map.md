# Map: Build AI Product Radar

Label: `wayfinder:map`

## Destination

A tested local and private-GitHub repository that defines and implements a cloud-first daily AI product newsletter, ten-day read-only GitHub review, unified rating loop, Google cloud exchange, and a separate Obsidian vault, including a successfully delivered test email.

## Notes

- This effort explicitly carries execution through the map; ticket agents may create implementation deliverables.
- Daily delivery target: 17:00 `Asia/Kolkata`, including weekends.
- Claude models (Fable 5.1, Opus, and the Sonnet and Haiku build workers) use Claude subscription authentication only. No Anthropic API key may be required or configured. A subscription is not API access.
- OpenAI Sol and Astra use the OpenAI subscription. Luna uses Codex; only the GLM sync worker uses the approved OpenRouter route for build work only, never for private repository data.
- Cloud schedules must be native provider tasks or routines with a verified unattended Drive write. Local Claude CLI workers are not schedules.
- GitHub analysis is read-only. Scheduled execution must not use GitHub Actions.
- Minimum seven findings: product-heavy, simple language, examples wherever possible. Academic age cap is two calendar years; all other sources six calendar months. Security limited to work relevance.
- Private Google Drive/Sheets/Forms/Apps Script provide the free cloud exchange. Obsidian is a separate local vault with eventual synchronization.
- Target newsletter address: `harshad422@gmail.com`.

## Decisions so far

- [Source and editorial specification](tickets/01-editorial-evidence.md): product-heavy daily digest with seven or more plain-language, source-backed findings; source roster reviewed in `docs/reviews/astra-sources.md`.
- [Architecture and model-routing specification](tickets/02-model-routing.md): Fable 5.1 primary at 12:30; Sol validates at 13:45 and 16:50; Sol fallback 14:30, Opus fallback 15:45, Sol rescue 16:30; Astra optional manual review only. Every fallback checks the accepted bundle for today's edition. Actual displayed model label recorded, never self-upgraded. Architecture reviewed in `docs/reviews/astra-architecture.md`.
- [Adversarial privacy and reliability review](tickets/03-adversarial-reliability.md): controls C-01 to C-43 recorded; producers stay pending until a canary write is observed.
- [Adversarial editorial and product-value review](tickets/04-adversarial-editorial.md): acceptance criteria recorded; the full rating legend stays at the top of every email; a short day is undelivered, not padded.

## Frontier

| Ticket | Stage |
|---|---|
| [01 Source and editorial specification](tickets/01-editorial-evidence.md) | Specified; source review recorded |
| [02 Architecture and model-routing specification](tickets/02-model-routing.md) | Specified; routing updated 2026-09-15 to Sol validation |
| [03 Adversarial privacy and reliability review](tickets/03-adversarial-reliability.md) | Resolved 2026-09-15 |
| [04 Adversarial editorial and product-value review](tickets/04-adversarial-editorial.md) | Resolved 2026-09-15 |
| [05 Core domain and configuration implementation](tickets/05-core-domain.md) | Code written (`radar/domain.py`, `radar/render.py`); local verification passed |
| [06 Collection, ranking, and learning implementation](tickets/06-ranking-learning.md) | Code written (`radar/learning.py`, `radar/selection.py`); local verification passed |
| [07 Cloud task prompts and schedules](tickets/07-cloud-tasks.md) | Prompts written; no cloud task activated |
| [08 Google Apps Script gateway and email](tickets/08-google-gateway.md) | Deployed and Google-authorized; reply/delivery triggers installed; revised gateway test delivered; runtime and reply scan verified |
| [09 Obsidian vault and synchronization](tickets/09-obsidian-sync.md) | Code written (`radar/sync.py`, `scripts/sync-vault.ps1`); local verification passed |
| [10 Integration verification and release review](tickets/10-integration-review.md) | Local and gateway checks passed; open for cloud research activation and real rating round trip |
| [11 Academic-only second mailer](../ACADEMIC-MAILER.md) | Shared gateway and ratings implemented; seven published-paper preview prepared; provider activation blocked |

## Live status (2026-09-16)

- Local build and gateway verification passed.
- Private GitHub build published to main (37d8273); GitHub does not host execution.
- Private Drive folder and native Sheet created; free Obsidian sync verified.
- Apps Script deployed and owner-authorized; delivery and reply triggers active.
- Revised seven-item test email delivered by the deployed gateway and registered for ratings.
- Fable and Opus routines paused: real cloud reads still fail Drive scope after reconnection.
- OpenAI schedules and ten-day GitHub review not activated.
- Real user rating round trip and first unattended approved edition remain unverified.

Evidence is maintained in `docs/VERIFICATION.md` and `docs/CLOUD-SETUP.md`.

## Out of scope

- Automatic modification of reviewed repositories.
- GitHub Actions as a scheduler or hosting platform.
- Storing customer documents, financial records, credentials, or raw private-repository content.
- Anthropic API authentication or billing.

## Execution update — 2026-09-16

Newsletter now requires a genuine user-facing AI product and descriptive, nontechnical examples. 58 Python tests and 83 Google gateway scenarios pass, with separate transport, activation and compatibility checks. Google activation is verified; Fable cloud tests twice failed Drive scopes. Independent Opus review is configured as the approved-model cloud fallback, paused until connector verification. The historical routing/status entries above describe earlier stages; README and VERIFICATION carry the operational status.
