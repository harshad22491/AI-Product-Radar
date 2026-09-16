# Academic digest source and applicability notes

Edition date: 2026-09-16 (Asia/Kolkata)

All seven items are formally published, peer-reviewed ICML 2025 conference papers in Proceedings of Machine Learning Research volume 267. The [primary PMLR volume page](https://proceedings.mlr.press/v267/) identifies the conference as held 13–19 July 2025 and the proceedings volume as published on **6 October 2025**. Accordingly, `published_at` records `2025-10-06`, the publisher's exact formal publication date, rather than an arXiv submission date or search-engine timestamp. Each paper page supplies its title, authors, venue, pages, abstract and canonical proceedings URL.

The applications below are hypotheses based only on `docs/PORTFOLIO-OVERVIEW.md`. None of the methods has been installed, integrated or tested in the user's repositories. Performance claims from the papers concern their reported experimental settings and must not be treated as expected portfolio results.

## Evidence map

1. **Compositional Condition Question Answering in Tabular Understanding** — [primary proceedings page](https://proceedings.mlr.press/v267/jiang25o.html)
   - Formal record: Jiang, Zhou, Zhan and Ye; ICML 2025; PMLR 267:27831–27850.
   - Paper evidence used: the abstract identifies missed question conditions and poor row recognition as limitations, then describes row/column patches and staged learning in CoCoTab. It mentions financial report analysis only as an example task area, not as validation on the user's documents.
   - Proposed use: adversarial multi-condition questions over synthetic reporting tables for Branding-Report-Automation.

2. **Agent Workflow Memory** — [primary proceedings page](https://proceedings.mlr.press/v267/wang25bx.html)
   - Formal record: Wang, Mao, Fried and Neubig; ICML 2025; PMLR 267:63897–63911.
   - Paper evidence used: the abstract describes inducing reusable workflows offline or online and evaluating them on Mind2Web and WebArena. Reported benchmark improvements are deliberately not restated as expected GHADC gains.
   - Proposed use: retrieve reviewed browser-test routines, with visible-state assertions and safe stopping in a fictional GHADC environment.

3. **PatchPilot: A Cost-Efficient Software Engineering Agent with Early Attempts on Formal Verification** — [primary proceedings page](https://proceedings.mlr.press/v267/li25cf.html)
   - Formal record: Li, Tang, Wang and Guo; ICML 2025; PMLR 267:35922–35941.
   - Paper evidence used: the abstract defines the reproduction, localization, generation, validation and refinement workflow and evaluates it on SWE-bench. This does not prove correctness for financial or reporting code.
   - Proposed use: a reviewable repair trace for one synthetic parser defect in Daily-Position-Automation.

4. **Otter: Generating Tests from Issues to Validate SWE Patches** — [primary proceedings page](https://proceedings.mlr.press/v267/ahmed25b.html)
   - Formal record: Ahmed, Devanbu and Hellendoorn; ICML 2025; PMLR 267:752–771.
   - Paper evidence used: the paper studies generating tests from issue descriptions and using those tests to validate software patches. Generated tests remain candidates requiring inspection; the digest does not claim they are automatically correct.
   - Proposed use: turn a synthetic spreadsheet-import issue into a reviewed failing fixture and regression test for TCPL-Data-Entry.

5. **Improving LLMs for Recommendation with Out-Of-Vocabulary Tokens** — [primary proceedings page](https://proceedings.mlr.press/v267/huang25ar.html)
   - Formal record: Huang, Yang, Shen, Liu, Zhan and Ye; ICML 2025; PMLR 267:26041–26057.
   - Paper evidence used: the abstract describes clustering learned interaction representations, assigning shared out-of-vocabulary tokens, adding them to an LLM vocabulary and evaluating downstream recommendation tasks.
   - Proposed use: the digest's sole `user_facing_ai` concept, a synthetic coffee recommender that compares the paper-inspired method with simpler baselines and gives evidence-bound reasons. This product concept has not been built or tested.

6. **On the Vulnerability of Applying Retrieval-Augmented Generation within Knowledge-Intensive Application Domains** — [primary proceedings page](https://proceedings.mlr.press/v267/xian25a.html)
   - Formal record: Xian et al.; ICML 2025; PMLR 267:68292–68315.
   - Paper evidence used: the paper examines vulnerabilities that arise through retrieved content in knowledge-intensive RAG settings. The digest applies the general failure boundary to controlled conflicting report passages without claiming a portfolio vulnerability exists.
   - Proposed use: test source authority, citations and abstention for a synthetic Branding-Report-Automation question-answer system.

7. **Windows Agent Arena: Evaluating Multi-Modal OS Agents at Scale** — [primary proceedings page](https://proceedings.mlr.press/v267/bonatti25a.html)
   - Formal record: Bonatti et al.; ICML 2025; PMLR 267:4874–4910.
   - Paper evidence used: the abstract describes 150-plus desktop tasks, parallel evaluation and a substantial observed gap between agent and human task success. That limitation motivates evaluation; it is not a forecast for the user's environment.
   - Proposed use: a resettable, read-only Windows task suite with machine-checkable end states for TCPL-Data-Entry-style workflows.

## Limitations and uncertainties

- PMLR publishes the whole ICML volume under one exact date, so all seven `published_at` values are the same. Individual paper records give the conference range rather than separate paper-release days.
- The source review used publisher abstracts and bibliographic records. It did not reproduce experiments, audit datasets, or independently verify the papers' empirical results.
- Repository relevance comes from a sanitized portfolio overview. No private repository, production document, customer history, accounting system or browser environment was inspected.
- Suggested effort is a planning estimate for a small synthetic trial, not a paper result or delivery commitment.
