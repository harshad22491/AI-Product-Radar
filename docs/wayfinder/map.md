# Map: Build AI Product Radar

Label: `wayfinder:map`

## Destination

A tested local and private-GitHub repository that defines and implements a cloud-first daily AI product newsletter, ten-day read-only GitHub review, unified rating loop, Google cloud exchange, and a separate Obsidian vault, including a successfully delivered test email.

## Notes

- This effort explicitly carries execution through the map; ticket agents may create implementation deliverables.
- Daily delivery target: 17:00 `Asia/Kolkata`, including weekends.
- Fable 5.1, Opus, Sonnet, and Haiku use Claude subscription authentication. No Anthropic API key may be required or configured.
- Astra, Luna, and Sol use OpenAI/Codex routes. The designated external agent may use the existing OpenRouter budget.
- GitHub analysis is read-only. Scheduled execution must not use GitHub Actions.
- Minimum seven findings: product-heavy, simple language, examples wherever possible. Academic age cap is two years; all other sources six months.
- Private Google Drive/Sheets/Forms/Apps Script provide the free cloud exchange. Obsidian is a separate local vault with eventual synchronization.
- Target newsletter address: `harshad422@gmail.com`.

## Decisions so far

- [Define the editorial and evidence contract](tickets/01-editorial-evidence.md): product-heavy daily digest with seven or more plain-language, source-backed findings.
- [Define model routing and failure semantics](tickets/02-model-routing.md): Fable primary; Astra, Opus, Sol fallback; actual model recorded.
- [Define cloud state and delivery](tickets/03-cloud-state.md): immutable Drive bundles reduced into Sheets and delivered by Apps Script.
- [Define ratings and learning](tickets/04-ratings-learning.md): item-level event history synchronized into one current record.
- [Define GitHub review boundaries](tickets/05-github-review.md): incremental, read-only review every ten elapsed days with strict exclusions.
- [Define Obsidian synchronization](tickets/06-obsidian.md): separate local vault that catches up from cloud state without paid Obsidian Sync.

## Frontier

- [Source and editorial specification](tickets/01-editorial-evidence.md)
- [Architecture and model-routing specification](tickets/02-model-routing.md)
- [Adversarial privacy and reliability review](tickets/03-adversarial-reliability.md)
- [Adversarial editorial and product-value review](tickets/04-adversarial-editorial.md)
- [Core domain and configuration implementation](tickets/05-core-domain.md)
- [Collection, ranking, and learning implementation](tickets/06-ranking-learning.md)
- [Cloud task prompts and schedules](tickets/07-cloud-tasks.md)
- [Google Apps Script gateway and email](tickets/08-google-gateway.md)
- [Obsidian vault and synchronization](tickets/09-obsidian-sync.md)
- [Integration verification and release review](tickets/10-integration-review.md)

## Not yet specified

- Account-specific connector authorization and IDs will be captured through setup tooling without entering secrets in Git.
- The final test email depends on successful Gmail authorization.

## Out of scope

- Automatic modification of reviewed repositories.
- GitHub Actions as a scheduler or hosting platform.
- Storing customer documents, financial records, credentials, or raw private-repository content.
- Anthropic API authentication or billing.
