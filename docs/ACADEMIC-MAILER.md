# AI Research Radar

A second email to harshad422@gmail.com, with the same 17:00 Asia/Kolkata delivery target and descriptive style as AI Product Radar.

## What changes

Every finding must be a formally published, peer-reviewed journal or conference paper, published within two calendar years of the edition date. Preprint-only papers, submitted manuscripts, blogs, product releases and vendor white papers do not qualify. Each item records its venue and primary publisher/proceedings link. Independent review must verify those claims on the source page; a JSON declaration is not proof of publication.

There is no five-product/tool quota in this edition. At least one paper must support a proposed AI product that an end user could interact with. For example, a recommendation paper could inspire a coffee-selection feature in forty-degrees. The newsletter explains the proposed input and output without suggesting that a research result is already a shipped product or has been tested in the user's repository.

## What stays the same

- At least seven findings; no padding when fewer qualify.
- Simple, descriptive summaries and hypothetical examples from the sanitized portfolio.
- Five practical application entries: where to use it, a small first trial, benefit, estimated effort and a success check.
- Rating legend at the top; the same RATE reply syntax and fifteen-minute reply reader.
- One canonical Sheet, rating history and preference system, with both editions in the existing separate Obsidian vault.
- Shared read-only portfolio review inputs. The ten-day cloud review remains unactivated.
- Fable subscription research and independent Opus review while Sol scheduling is unavailable. No Anthropic API key or GitHub Actions.

## Implementation

An optional bundle field `newsletter` identifies `academic` or `product`; older bundles without it remain product editions. The academic validator requires `source_type: academic` for every item and a publication object containing `status: published`, `venue`, and `publication_url` matching the canonical source URL. Preprint hosts are rejected. The independent model review determines whether the venue/page really establishes publication and supports the summary.

The shared gateway dispatches the two channels independently. Each has its own once-per-day state and durable delivery records, including uncertain-send protection. Existing delivery rows with no channel remain product records. Both use the original authorized Gmail account, Sheet and Drive folders. New Sheet fields are appended, preserving existing columns and ratings. Delivered-item filtering is shared, preventing the same paper being repeated between the mailers.

The new configuration is `config/academic.json`; producer instructions are `prompts/academic.md`. The reviewer instructions in `prompts/opus-validator.md` cover both channels. A planned Fable research time of 12:45 IST leaves time for the 13:45 and 16:45 reviews. It is a configured plan, not evidence of a live provider schedule.

## Verification and activation

The seven-paper example is `examples/academic-digest.json`, with source evidence in `examples/academic-digest-sources.md`. Python and Google tests cover the source restrictions, two simultaneous daily deliveries, uncertain-send isolation, preview safety, publication preservation and rating replies from the academic subject.

Automatic research remains blocked by the existing Claude Drive scope error. Saving the new provider routine also encountered a local Claude runtime failure: Windows reported insufficient paging-file capacity before the client could configure a task. No new academic routine ID or successful unattended research run is claimed. No machine paging settings were changed. Google deployment and actual test-delivery evidence are recorded in `docs/VERIFICATION.md` after verification.
