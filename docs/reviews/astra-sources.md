# Astra source review

> Historical build-stage review. See [current verification](../VERIFICATION.md) for resolved findings and remaining blockers.

Reviewed: 2026-09-15

## Outcome

The catalog is suitable for a seven-item practical digest. It uses first-party product pages, official project release pages, and primary research indexes. The selection policy requires at least five product or tool items in a seven-item edition, while lower research weights keep useful papers available without allowing them to dominate.

The freshness rules are explicit: use the original publication or release date, reject academic work whose publication year is earlier than `edition year - 2`, and reject nonacademic material older than `edition_date - 6 calendar months`. A crawl date, page update timestamp, repost, or search-index date is not a substitute for the source date.

## Source decisions

| Source | Why it is primary and useful | Editorial handling |
| --- | --- | --- |
| [OpenAI News](https://openai.com/news/) | OpenAI's own dated product, developer, engineering, and research announcements. | Prefer shipped product/API capabilities and concrete applied workflows; downweight company news and broad policy. |
| [Anthropic Engineering](https://www.anthropic.com/engineering) | Anthropic engineers describe agent harnesses, tool use, evaluations, and implementation lessons. | Treat posts as first-party engineering evidence, not independent proof of general superiority. |
| [Google Research Blog](https://research.google/blog/) | Google's dated research summaries link to the underlying work, projects, and publications. | Require a practical match to the configured topics and retain the underlying paper's original date. |
| [GitHub Changelog](https://github.blog/changelog/) | GitHub's official dated record of releases, improvements, and retirements. | Prioritize Copilot, repository workflows, APIs, and developer tooling. Security entries qualify only when directly relevant to the owner's work. |
| [Hugging Face Blog](https://huggingface.co/blog) | First-party and named-project posts cover models, libraries, datasets, and deployment tools. | Confirm the author/project affiliation and follow links to the owning repository or paper before selection. |
| [Docling Releases](https://github.com/docling-project/docling/releases) | The official project release stream provides canonical tags, dates, and change notes. | Favor document, table, PDF, and XLSX improvements that can simplify existing automation. Use the tag URL as the candidate's canonical URL. |
| [MarkItDown Releases](https://github.com/microsoft/markitdown/releases) | Microsoft's official repository records versioned document-conversion changes. | Select material support, quality, integration, or compatibility changes; ignore routine maintenance. |
| [Pydantic AI Releases](https://github.com/pydantic/pydantic-ai/releases) | The official repository provides versioned agent-framework features and fixes. | Prefer stable, actionable changes and call out beta or breaking behavior plainly. |
| [Astral Blog](https://astral.sh/blog) | Astral's own announcements cover uv, Ruff, and other Python tooling. | Keep only workflow-relevant releases; avoid general company announcements. |
| [DuckDB Engineering Blog](https://duckdb.org/news/) | DuckDB's project blog publishes dated releases and technical explanations. | Favor local analytics, Excel/CSV/Parquet ingestion, and small data-pipeline improvements. |
| [Playwright Python Release Notes](https://playwright.dev/python/docs/release-notes) | The official Python documentation records version-specific browser automation changes. | Anchor candidates to the applicable version section and, when available, its canonical release URL. |
| [TallyPrime Developer Release Notes](https://help.tallysolutions.com/tallyprime-developer-release-notes/) | Tally's official help site documents TDL, integration, and customization changes. | Give high weight to XML/TDL integration, accounting workflows, compatibility, and migration impact. |
| [Microsoft Excel Blog](https://techcommunity.microsoft.com/category/microsoft365/blog/excelblog/all-posts) | Microsoft's official Excel channel publishes dated product updates. | Prefer automation, data import, formulas, Python, Office Scripts, Power Query, and Copilot workflow changes; downweight events and templates. |
| [arXiv API search](https://export.arxiv.org/api/query?search_query=all%3Aagent%20OR%20all%3A%22workflow%20automation%22&sortBy=submittedDate&sortOrder=descending&max_results=50) | arXiv exposes author-submitted papers and their original submission metadata through its official Atom API. | A paper is a candidate, not validation by itself. Check authorship, method, evidence, repository, and the two-calendar-year cap; use the canonical abstract URL in a bundle. |

## Mix and relevance controls

- Target seven findings and require at least five whose final `source_type` is `product` or `tool`. The catalog's `kind` is a discovery hint; classification must follow the selected item itself.
- Allow no more than one security-focused item per edition, and only when it maps to an actual work surface such as credentials, dependencies, agent permissions, local data, OAuth, or repository automation.
- Apply topic keyword matches as relevance evidence, not as proof of quality. A downweight reduces rank but does not override source credibility or freshness validation.
- Prefer canonical release, changelog-entry, post, or arXiv abstract URLs over landing pages when creating bundle items. Landing pages in `sources.json` are discovery entry points.
- Preserve original dates throughout candidate selection. Reject undated items unless the primary page or canonical release metadata establishes a real publication date.
- Do not repeat a delivered item. A material later release may qualify only through its own new canonical release URL.

## Residual risks

- Landing pages can change markup, and GitHub release pages can contain noisy maintenance releases. Discovery should fail closed when a date or canonical URL cannot be established.
- Vendor engineering posts are authoritative about what the vendor built, but claims about performance or general applicability still need supporting evidence.
- arXiv submissions are not necessarily peer reviewed. Their credibility label must reflect the paper's evidence and independent reproducibility, never the source weight alone.
- The product/tool quota is a minimum target, not permission to use filler. If seven valid unique items cannot be found, the run should remain invalid under Bundle v1.
