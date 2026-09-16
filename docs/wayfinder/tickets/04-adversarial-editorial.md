# Adversarial editorial and product-value review

Label: `wayfinder:research`

## Question

How could the digest become noisy, promotional, repetitive, overly technical, or disconnected from actual work, and which acceptance rules prevent that?

## Resolution

Reviewed 2026-09-15 by Fable 5.1 (Claude subscription, no API). Full findings and acceptance criteria: [docs/reviews/fable-editorial.md](../../reviews/fable-editorial.md). Documentation only; no code changed, nothing committed.

The drafted digest validates and renders but fails as a product in five blocking ways:

1. Ratings never influence a future selection. The relevance multiplier is neutral for any unrated item and delivered items are never reselected, so learned topic-repository weights are dead. The email legend promises effects the code cannot produce.
2. Deduplication is defeated by tracking parameters, `www.`, and arXiv version or PDF variants, which also leaves the "material release" exception untestable.
3. The validator accepts filler: no item ceiling, no length floors, free-text evidence labels and repositories, empty topics, and guidance strings that duplicate their own labels.
4. Repository examples are unverifiable because the repository name is free text and evidence is optional.
5. Novelty is self-declared because the publish date is model-supplied and only window-checked.
6. The Fable and Astra prompts instruct the generic answer: Where is defined as an industry domain, `main-project` is an allowed repository, topics are free tags, and the research focus ignores the nine work topics in `config/topics.json`.

Acceptance rules are stated as enforceable criteria in groups L (learning), R (repetition), N (novelty), E (evidence), F (repositories), T (plain language), O (load), and P (prompts), each with an enforcement point, owning ticket, and required test. P0 criteria block the first real delivery: L1-L4, L8, L10, R1-R4, N1-N2, E1, F1-F3, T1-T2, O1-O2, P1-P3. Owners: ticket 05 (validator and renderer), 06 (selection and learning), 07 (prompts and Astra validation), 08 (Apps Script gate), 10 (runs the reproduction script in the review's Appendix A). Where the reliability review under ticket 03 already defines a control (C-10, C-17, C-18, C-36, C-38), the editorial criteria cite and nest inside it rather than restating it.

The seven-item floor and product-heavy mix are map decisions and were kept; criterion O5 makes a short day an undelivered, recorded edition rather than a padded one.
