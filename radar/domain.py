"""Validation and canonicalization for Radar v1 digest bundles."""

from __future__ import annotations

import calendar
import copy
import hashlib
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit


_BUNDLE_KEYS = {
    "schema_version",
    "run_id",
    "edition_date",
    "generated_at",
    "producer",
    "model_id",
    "kind",
    "newsletter",
    "items",
}
_ITEM_KEYS = {
    "item_id",
    "title",
    "source_url",
    "published_at",
    "source_type",
    "summary",
    "why_it_matters",
    "evidence_label",
    "repository",
    "guidance",
    "topics",
    "source_dates",
    "repository_evidence",
    "user_facing_ai",
    "application_example",
    "publication",
}
_REQUIRED_ITEM_KEYS = _ITEM_KEYS - {"source_dates", "repository_evidence", "user_facing_ai", "application_example", "publication"}
_PRODUCERS = {"fable", "astra", "opus", "sol"}
_SOURCE_TYPES = {"academic", "product", "tool", "technique"}
_NEWSLETTERS = {"product", "academic"}
_PREPRINT_HOSTS = {"arxiv.org", "biorxiv.org", "medrxiv.org"}
_GUIDANCE_LABELS = ("Where", "Try", "Benefit", "Effort", "Check")
_RUN_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ITEM_ID_RE = re.compile(r"^RAD-[0-9a-f]{12}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PERCENT_ESCAPE_RE = re.compile(r"%([0-9a-fA-F]{2})")
_UNRESERVED = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~")


def _fail(path: str, message: str) -> None:
    raise ValueError(f"{path}: {message}")


def _text(value: object, path: str, *, allow_empty: bool = False, max_length: int = 20_000) -> str:
    if not isinstance(value, str):
        _fail(path, "must be a string")
    result = value.strip()
    if not result and not allow_empty:
        _fail(path, "must not be empty")
    if len(result) > max_length:
        _fail(path, f"must be at most {max_length} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in result):
        _fail(path, "must not contain control characters")
    return result


def _parse_date(value: object, path: str) -> date:
    text = _text(value, path)
    if not _DATE_RE.fullmatch(text):
        _fail(path, "must use YYYY-MM-DD")
    try:
        return date.fromisoformat(text)
    except ValueError:
        _fail(path, "is not a real calendar date")
    raise AssertionError("unreachable")


def _parse_utc_datetime(value: object, path: str) -> tuple[datetime, str]:
    text = _text(value, path)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        _fail(path, "must be an ISO datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(path, "must include a timezone")
    if parsed.utcoffset() != timedelta(0):
        _fail(path, "must be in UTC")
    parsed = parsed.astimezone(timezone.utc)
    return parsed, text


def _subtract_years(value: date, years: int) -> date:
    year = value.year - years
    return value.replace(year=year, day=min(value.day, calendar.monthrange(year, value.month)[1]))


def _subtract_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _normalize_percent_escapes(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        byte = chr(int(match.group(1), 16))
        return byte if byte in _UNRESERVED else f"%{match.group(1).upper()}"

    return _PERCENT_ESCAPE_RE.sub(replace, value)


def _remove_dot_segments(path: str) -> str:
    """Apply the URL dot-segment rule without decoding meaningful escapes."""
    output: list[str] = []
    absolute = path.startswith("/")
    trailing = path.endswith("/") or path.endswith("/.") or path.endswith("/..")
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if output and output[-1] != "..":
                output.pop()
            elif not absolute:
                output.append(segment)
        else:
            output.append(segment)
    normalized = "/".join(output)
    if absolute:
        normalized = "/" + normalized
    if trailing and normalized != "/":
        normalized += "/"
    return normalized or "/"


def canonical_url(url: str) -> str:
    """Return the stable, fragment-free HTTPS representation of *url*.

    Query parameters are sorted, default HTTPS ports and trailing path slashes
    are removed, and only unreserved percent escapes are decoded.
    """
    if not isinstance(url, str):
        raise ValueError("url: must be a string")
    value = url.strip()
    if not value:
        raise ValueError("url: must not be empty")
    if any(ord(character) <= 32 or ord(character) == 127 for character in value):
        raise ValueError("url: must not contain whitespace or control characters")
    if re.search(r"%(?![0-9a-fA-F]{2})", value):
        raise ValueError("url: malformed percent escape")
    try:
        parts = urlsplit(value)
        scheme = parts.scheme.lower()
        hostname = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise ValueError(f"url: invalid URL ({exc})") from exc
    if scheme != "https":
        raise ValueError("url: scheme must be https")
    if not hostname:
        raise ValueError("url: host is required")
    if parts.username is not None or parts.password is not None:
        raise ValueError("url: credentials are not allowed")
    if "\\" in parts.netloc:
        raise ValueError("url: backslashes are not allowed")

    try:
        ascii_host = hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("url: invalid host") from exc
    if ":" in ascii_host:
        ascii_host = f"[{ascii_host}]"
    host_port = ascii_host if port in (None, 443) else f"{ascii_host}:{port}"

    path = _remove_dot_segments(_normalize_percent_escapes(parts.path or "/"))
    path = path.rstrip("/") or "/"
    try:
        query_pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise ValueError(f"url: invalid query ({exc})") from exc
    query = urlencode(sorted(query_pairs), doseq=True)
    return urlunsplit(("https", host_port, quote(path, safe="/%:@!$&'()*+,;=%"), query, ""))


def stable_item_id(url: str) -> str:
    """Return the v1 item ID derived solely from the canonical source URL."""
    digest = hashlib.sha256(canonical_url(url).encode("utf-8")).hexdigest()[:12]
    return f"RAD-{digest}"


def _validate_source_dates(value: object, path: str, edition_date: date) -> object:
    if isinstance(value, dict):
        result: dict[str, str] = {}
        for key, raw_date in value.items():
            label = _text(key, f"{path} key", max_length=100)
            parsed = _parse_date(raw_date, f"{path}.{label}")
            if parsed > edition_date:
                _fail(f"{path}.{label}", "must not be after edition_date")
            result[label] = parsed.isoformat()
        return result
    if isinstance(value, list):
        result = []
        for index, raw_date in enumerate(value):
            parsed = _parse_date(raw_date, f"{path}[{index}]")
            if parsed > edition_date:
                _fail(f"{path}[{index}]", "must not be after edition_date")
            result.append(parsed.isoformat())
        return result
    _fail(path, "must be a date map or list of YYYY-MM-DD strings")


def _validate_repository_evidence(value: object, path: str) -> object:
    if isinstance(value, str):
        return _text(value, path)
    if isinstance(value, list):
        return [_text(entry, f"{path}[{index}]") for index, entry in enumerate(value)]
    if isinstance(value, dict):
        result: dict[str, str] = {}
        for key, entry in value.items():
            label = _text(key, f"{path} key", max_length=100)
            result[label] = _text(entry, f"{path}.{label}")
        return result
    _fail(path, "must be a string, list of strings, or string map")


def validate_bundle(bundle: dict) -> dict:
    """Validate and return a normalized defensive copy of a v1 digest bundle."""
    if not isinstance(bundle, dict):
        raise ValueError("bundle: must be an object")
    unknown = set(bundle) - _BUNDLE_KEYS
    if unknown:
        _fail("bundle", f"unknown field(s): {', '.join(sorted(map(str, unknown)))}")
    missing = (_BUNDLE_KEYS - {"newsletter"}) - set(bundle)
    if missing:
        _fail("bundle", f"missing field(s): {', '.join(sorted(missing))}")
    if not isinstance(bundle["schema_version"], int) or isinstance(bundle["schema_version"], bool) or bundle["schema_version"] != 1:
        _fail("schema_version", "must be integer 1")
    run_id = _text(bundle["run_id"], "run_id", max_length=100)
    if not _RUN_ID_RE.fullmatch(run_id):
        _fail("run_id", "must be a lowercase safe slug using hyphens")
    edition = _parse_date(bundle["edition_date"], "edition_date")
    india_today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    if edition > india_today:
        _fail("edition_date", "must not be in the future")
    generated, generated_text = _parse_utc_datetime(bundle["generated_at"], "generated_at")
    if generated > datetime.now(timezone.utc):
        _fail("generated_at", "must not be in the future")
    producer = _text(bundle["producer"], "producer")
    if producer not in _PRODUCERS:
        _fail("producer", f"must be one of {', '.join(sorted(_PRODUCERS))}")
    model_id = _text(bundle["model_id"], "model_id", max_length=300)
    kind = _text(bundle["kind"], "kind")
    if kind != "digest":
        _fail("kind", "must be digest")
    newsletter_present = "newsletter" in bundle
    newsletter = _text(bundle.get("newsletter", "product"), "newsletter")
    if newsletter not in _NEWSLETTERS:
        _fail("newsletter", "must be one of academic, product")
    items = bundle["items"]
    if not isinstance(items, list):
        _fail("items", "must be a list")
    if len(items) < 7:
        _fail("items", "must contain at least 7 items")

    normalized_items: list[dict] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for index, raw_item in enumerate(items):
        path = f"items[{index}]"
        if not isinstance(raw_item, dict):
            _fail(path, "must be an object")
        unknown = set(raw_item) - _ITEM_KEYS
        if unknown:
            _fail(path, f"unknown field(s): {', '.join(sorted(map(str, unknown)))}")
        missing = _REQUIRED_ITEM_KEYS - set(raw_item)
        if missing:
            _fail(path, f"missing field(s): {', '.join(sorted(missing))}")

        source = canonical_url(raw_item["source_url"])
        if source in seen_urls:
            _fail(f"{path}.source_url", "duplicates another item")
        seen_urls.add(source)
        expected_id = stable_item_id(source)
        item_id = _text(raw_item["item_id"], f"{path}.item_id")
        if not _ITEM_ID_RE.fullmatch(item_id) or item_id != expected_id:
            _fail(f"{path}.item_id", f"must equal {expected_id}")
        if item_id in seen_ids:
            _fail(f"{path}.item_id", "duplicates another item")
        seen_ids.add(item_id)

        published = _parse_date(raw_item["published_at"], f"{path}.published_at")
        if published > edition:
            _fail(f"{path}.published_at", "must not be after edition_date")
        source_type = _text(raw_item["source_type"], f"{path}.source_type")
        if source_type not in _SOURCE_TYPES:
            _fail(f"{path}.source_type", f"must be one of {', '.join(sorted(_SOURCE_TYPES))}")
        cutoff = _subtract_years(edition, 2) if source_type == "academic" else _subtract_months(edition, 6)
        if published < cutoff:
            _fail(f"{path}.published_at", f"is older than the {source_type} freshness window")

        guidance = raw_item["guidance"]
        if not isinstance(guidance, list) or len(guidance) != 5:
            _fail(f"{path}.guidance", "must contain exactly 5 strings")
        normalized_guidance = [_text(entry, f"{path}.guidance[{n}]") for n, entry in enumerate(guidance)]
        topics = raw_item["topics"]
        if not isinstance(topics, list):
            _fail(f"{path}.topics", "must be a list of strings")
        normalized_topics = [_text(entry, f"{path}.topics[{n}]", max_length=100) for n, entry in enumerate(topics)]

        repository = _text(raw_item["repository"], f"{path}.repository", max_length=300)
        repository_parts = repository.split("/")
        if (
            "\\" in repository
            or ":" in repository
            or any(part in ("", ".", "..") for part in repository_parts)
        ):
            _fail(f"{path}.repository", "must be a sanitized repository name")

        normalized_item = {
            "item_id": item_id,
            "title": _text(raw_item["title"], f"{path}.title", max_length=500),
            "source_url": source,
            "published_at": published.isoformat(),
            "source_type": source_type,
            "summary": _text(raw_item["summary"], f"{path}.summary"),
            "why_it_matters": _text(raw_item["why_it_matters"], f"{path}.why_it_matters"),
            "evidence_label": _text(raw_item["evidence_label"], f"{path}.evidence_label", max_length=300),
            "repository": repository,
            "guidance": normalized_guidance,
            "topics": normalized_topics,
            "user_facing_ai": raw_item.get("user_facing_ai", False),
        }
        if "publication" in raw_item:
            publication = raw_item["publication"]
            if not isinstance(publication, dict):
                _fail(f"{path}.publication", "must be an object")
            unknown_publication = set(publication) - {"status", "venue", "publication_url"}
            if unknown_publication:
                _fail(f"{path}.publication", f"unknown field(s): {', '.join(sorted(map(str, unknown_publication)))}")
            for field in ("status", "venue", "publication_url"):
                if field not in publication:
                    _fail(f"{path}.publication.{field}", "is required")
            status = _text(publication["status"], f"{path}.publication.status")
            if status != "published":
                _fail(f"{path}.publication.status", "must be published")
            venue = _text(publication["venue"], f"{path}.publication.venue", max_length=300)
            publication_url = canonical_url(publication["publication_url"])
            publication_host = urlsplit(publication_url).hostname.lower().rstrip(".")
            if any(publication_host == host or publication_host.endswith(f".{host}") for host in _PREPRINT_HOSTS):
                _fail(f"{path}.publication.publication_url", "must not be a preprint host")
            if publication_url != source:
                _fail(f"{path}.publication.publication_url", "must canonically equal source_url")
            normalized_item["publication"] = {
                "status": status,
                "venue": venue,
                "publication_url": publication_url,
            }
        if newsletter == "academic":
            if source_type != "academic":
                _fail(f"{path}.source_type", "academic newsletter requires academic sources")
            if "publication" not in normalized_item:
                _fail(f"{path}.publication", "is required for academic newsletter")
        if not isinstance(normalized_item["user_facing_ai"], bool):
            _fail(f"{path}.user_facing_ai", "must be a boolean")
        if "application_example" in raw_item:
            normalized_item["application_example"] = _text(
                raw_item["application_example"], f"{path}.application_example", max_length=4000
            )
        if normalized_item["user_facing_ai"] and "application_example" not in normalized_item:
            _fail(f"{path}.application_example", "is required for user-facing AI products")
        if "source_dates" in raw_item:
            normalized_item["source_dates"] = _validate_source_dates(
                raw_item["source_dates"], f"{path}.source_dates", edition
            )
        if "repository_evidence" in raw_item:
            normalized_item["repository_evidence"] = _validate_repository_evidence(
                raw_item["repository_evidence"], f"{path}.repository_evidence"
            )
        normalized_items.append(normalized_item)

    if not any(item["user_facing_ai"] for item in normalized_items):
        _fail("items", "must contain at least one user-facing AI product")

    normalized_bundle = {
        "schema_version": 1,
        "run_id": run_id,
        "edition_date": edition.isoformat(),
        "generated_at": generated_text,
        "producer": producer,
        "model_id": model_id,
        "kind": "digest",
        "items": copy.deepcopy(normalized_items),
    }
    if newsletter_present:
        normalized_bundle["newsletter"] = newsletter
    return normalized_bundle
