"""Readable plain-text and HTML digest renderers."""

from __future__ import annotations

from html import escape

from .domain import canonical_url, validate_bundle


_RATING_LEGEND = (
    ("1", "Skip", "suppress similar items"),
    ("2", "Weak match", "reduce similar items"),
    ("3", "Useful", "keep the mix balanced"),
    ("4", "Strong match", "queue an investigation"),
    ("5", "Excellent", "propose an experiment only"),
)
_REASON_TAGS = ("too technical", "already knew", "too much effort")
_GUIDANCE_LABELS = ("Where", "Try", "Benefit", "Effort", "Check")
_GUIDANCE_HEADINGS = {
    "Where": "Where it fits in your work",
    "Try": "Try it step by step",
    "Benefit": "Benefit you can look for",
    "Effort": "Effort and prerequisites",
    "Check": "Check the result safely",
}


def _guidance_text(label: str, value: str) -> str:
    prefix = label + ":"
    return value[len(prefix):].strip() if value.startswith(prefix) else value


def _rating_url(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("rating_url: must be a string")
    if not value:
        return ""
    return canonical_url(value)


def _source_dates_text(item: dict) -> str:
    source_dates = item.get("source_dates")
    if source_dates is None:
        return ""
    if isinstance(source_dates, dict):
        return "; ".join(f"{key}: {value}" for key, value in source_dates.items())
    return "; ".join(source_dates)


def _evidence_text(item: dict) -> str:
    evidence = item.get("repository_evidence")
    if evidence is None:
        return ""
    if isinstance(evidence, dict):
        return "; ".join(f"{key}: {value}" for key, value in evidence.items())
    if isinstance(evidence, list):
        return "; ".join(evidence)
    return evidence


def _rating_html(rating_url: str) -> str:
    rows = "".join(
        f'<tr><td class="rating-number">{score}</td><td><strong>{escape(label)}</strong> - '
        f"{escape(consequence)}</td></tr>"
        for score, label, consequence in _RATING_LEGEND
    )
    link = (
        f'<p><a class="rating-button" href="{escape(rating_url, quote=True)}">Rate this digest securely</a></p>'
        if rating_url
        else ""
    )
    tags = " ".join(f'<span class="tag">{escape(tag)}</span>' for tag in _REASON_TAGS)
    return (
        '<section class="rating-panel" aria-label="Rating instructions">'
        "<h2>Quick rating</h2>"
        "<p>Reply with <code>RATE RAD-id SCORE REV=0 your reason</code>. "
        "Use the item's current revision when correcting a rating. "
        "Ratings tune relevance; they never change source credibility.</p>"
        '<table class="legend"><thead><tr><th>Score</th><th>What happens</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
        f"<p class=\"reason-line\"><strong>Optional reason tags:</strong> {tags}</p>"
        f"{link}</section>"
    )


def render_html(bundle: dict, rating_url: str = "") -> str:
    """Render a validated digest as escaped, self-contained email HTML."""
    data = validate_bundle(bundle)
    safe_rating_url = _rating_url(rating_url)
    cards = []
    for item in data["items"]:
        topics = " ".join(f'<span class="topic">{escape(topic)}</span>' for topic in item["topics"])
        guidance = "".join(
            f'<li><strong>{escape(_GUIDANCE_HEADINGS[label])}:</strong> {escape(_guidance_text(label, value))}</li>'
            for label, value in zip(_GUIDANCE_LABELS, item["guidance"])
        )
        source_dates = _source_dates_text(item)
        extra_dates = (
            f'<p class="meta"><strong>Source dates:</strong> {escape(source_dates)}</p>' if source_dates else ""
        )
        evidence = _evidence_text(item)
        repository_evidence = (
            f'<p><strong>Repository evidence:</strong> {escape(evidence)}</p>' if evidence else ""
        )
        publication = item.get("publication")
        publication_html = (
            f'<p class="meta"><strong>Publication:</strong> {escape(publication["venue"])} | '
            f'<a href="{escape(publication["publication_url"], quote=True)}">Open publication</a></p>'
            if publication else ""
        )
        product_marker = (
            "Proposed paper-backed product" if data.get("newsletter", "product") == "academic"
            else "User-facing AI product"
        )
        cards.append(
            '<article class="item-card">'
            f'<div class="item-kicker">{escape(item["item_id"])} | {escape(item["source_type"].title())}'
            f'{" | " + product_marker if item["user_facing_ai"] else ""}</div>'
            f'<h2>{escape(item["title"])}</h2>'
            f'<p class="meta"><strong>Source date:</strong> {escape(item["published_at"])} | '
            f'<a href="{escape(item["source_url"], quote=True)}">Open source</a></p>'
            f"{publication_html}"
            f"{extra_dates}"
            f'<p>{escape(item["summary"])}</p>'
            f'<p><strong>Why it matters:</strong> {escape(item["why_it_matters"])}</p>'
            f'{("<p><strong>Example application:</strong> " + escape(item["application_example"]) + "</p>") if item.get("application_example") else ""}'
            f'<p><strong>Evidence:</strong> {escape(item["evidence_label"])} | '
            f'<strong>Repository:</strong> {escape(item["repository"])}</p>'
            f"{repository_evidence}"
            f'<h3>How you could use it</h3><ol class="guidance">{guidance}</ol>'
            f'<p class="rating-command"><strong>Rate this item:</strong> '
            f'<code>RATE {escape(item["item_id"])} SCORE REV=0 your reason</code></p>'
            f'<div class="topics">{topics}</div>'
            "</article>"
        )
    return (
        '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width, initial-scale=1"><style>'
        "body{margin:0;background:#f4f1eb;color:#25231f;font:16px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}"
        ".wrap{max-width:760px;margin:0 auto;padding:28px 18px 48px}.masthead{background:#263b35;color:#fff;padding:28px;border-radius:18px 18px 4px 4px;}"
        ".eyebrow,.item-kicker{font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:#b8d9c5}.masthead h1{margin:5px 0 4px;font:700 32px/1.1 Georgia,serif}.masthead p{margin:0;color:#e0e8df}"
        ".rating-panel{background:#fffdf8;border:1px solid #d8cdbb;border-radius:10px;padding:20px;margin:16px 0}.rating-panel h2{margin-top:0;color:#263b35}.legend{border-collapse:collapse;width:100%;margin:14px 0}.legend td,.legend th{text-align:left;padding:7px 8px;border-bottom:1px solid #e7dfd2}.legend th{font-size:12px;text-transform:uppercase;color:#6c665d}.rating-number{font-weight:700;color:#b55c35;width:34px}.tag,.topic{display:inline-block;border-radius:999px;padding:2px 9px;margin:3px 3px 0 0;background:#eee6d8;color:#5d5144;font-size:13px}.rating-button{display:inline-block;background:#c76238;color:#fff;padding:9px 14px;border-radius:7px;text-decoration:none;font-weight:700}.item-card{background:#fff;border:1px solid #e1d9cd;border-radius:10px;padding:22px;margin:16px 0;box-shadow:0 3px 12px #392b1710}.item-card h2{font:700 25px/1.2 Georgia,serif;margin:7px 0}.item-card h3{font-size:16px;color:#263b35;margin-bottom:5px}.item-kicker{color:#b55c35}.meta{font-size:14px;color:#6c665d}.meta a{color:#9c4929}.guidance{padding-left:24px;margin-top:4px}.guidance li{padding:3px 0}.topics{margin-top:14px}.footer{color:#6c665d;font-size:13px;text-align:center;margin-top:24px}"
        '</style></head><body><main class="wrap">'
        f'<header class="masthead"><div class="eyebrow">{("AI Research Radar" if data.get("newsletter", "product") == "academic" else "AI Product Radar")} | {escape(data["edition_date"])}</div>'
        f'<h1>{("AI Research Radar" if data.get("newsletter", "product") == "academic" else "Seven useful signals")}</h1><p>Prepared by {escape(data["producer"])} | {escape(data["model_id"])}</p></header>'
        f"{_rating_html(safe_rating_url)}"
        f"{''.join(cards)}"
        f'<p class="footer">Run {escape(data["run_id"])} | Generated {escape(data["generated_at"])}</p>'
        "</main></body></html>"
    )


def render_text(bundle: dict) -> str:
    """Render a validated digest as readable plain text."""
    data = validate_bundle(bundle)
    lines = [
        "AI Research Radar" if data.get("newsletter", "product") == "academic" else "AI PRODUCT RADAR",
        f"Edition: {data['edition_date']} | Prepared by {data['producer']} ({data['model_id']})",
        "",
        "HOW TO RATE (always applies)",
        "Reply: RATE RAD-id SCORE REV=0 your reason",
        "For a correction, replace REV=0 with the current rating revision.",
        "Ratings tune relevance; they never change source credibility.",
    ]
    for score, label, consequence in _RATING_LEGEND:
        lines.append(f"{score} - {label}: {consequence}")
    lines.extend(["Reason tags: " + ", ".join(_REASON_TAGS), ""])
    for number, item in enumerate(data["items"], 1):
        lines.extend(
            [
                f"{number}. {item['title']} [{item['item_id']}]",
                f"Source: {item['source_url']}",
                f"Source date: {item['published_at']} ({item['source_type']})",
                ("Product marker: Proposed paper-backed product" if data.get("newsletter", "product") == "academic" else "Product marker: User-facing AI product") if item["user_facing_ai"] else "Product marker: Supporting research or tool",
                f"Rate this item: RATE {item['item_id']} SCORE REV=0 your reason",
            ]
        )
        source_dates = _source_dates_text(item)
        if source_dates:
            lines.append(f"Source dates: {source_dates}")
        publication = item.get("publication")
        if publication:
            lines.append(f"Publication: {publication['venue']} ({publication['publication_url']})")
        lines.extend(
            [
                f"Summary: {item['summary']}",
                f"Why it matters: {item['why_it_matters']}",
                *([f"Example application: {item['application_example']}"] if item.get("application_example") else []),
                f"Evidence: {item['evidence_label']} | Repository: {item['repository']}",
                "Guidance:",
            ]
        )
        lines.extend(
            f"  {_GUIDANCE_HEADINGS[label]}: {_guidance_text(label, value)}"
            for label, value in zip(_GUIDANCE_LABELS, item["guidance"])
        )
        if item["topics"]:
            lines.append("Topics: " + ", ".join(item["topics"]))
        evidence = _evidence_text(item)
        if evidence:
            lines.append(f"Repository evidence: {evidence}")
        lines.append("")
    lines.append(f"Run: {data['run_id']} | Generated: {data['generated_at']}")
    return "\n".join(lines)
