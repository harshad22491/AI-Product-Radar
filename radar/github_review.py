"""Offline planning and state reduction for read-only GitHub reviews.

The module deliberately has no GitHub client, credential access, or network
code.  An authorized external process supplies repository metadata as an
inventory JSON file; this module only decides what is due and records an
explicitly supplied review result.
"""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = 1
REVIEW_INTERVAL = timedelta(days=10)
_REPOSITORY_RE = re.compile(r"^[^/\\\s]+/[^/\\\s]+$")
_UTC_Z_RE = re.compile(r"Z$", re.IGNORECASE)


class ReviewError(ValueError):
    """Raised for malformed inventory, state, or review results."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ReviewError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ReviewError(f"{field} must be an aware UTC ISO timestamp")
    candidate = _UTC_Z_RE.sub("+00:00", value.strip())
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ReviewError(f"{field} must be an aware UTC ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.utcoffset() != timedelta(0):
        raise ReviewError(f"{field} must be an aware UTC ISO timestamp")
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _text(value: Any, field: str, *, max_length: int = 300) -> str:
    if not isinstance(value, str):
        raise ReviewError(f"{field} must be a string")
    result = value.strip()
    if not result:
        raise ReviewError(f"{field} must not be empty")
    if len(result) > max_length:
        raise ReviewError(f"{field} must be at most {max_length} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in result):
        raise ReviewError(f"{field} must not contain control characters")
    return result


def _summary(value: Any) -> str:
    # Store a plain, compact summary so review output cannot become markup or
    # a multi-line transport payload.  Content policy remains the reviewer's
    # responsibility; this seam only enforces safe serialization.
    result = _text(value, "summary", max_length=20_000)
    return " ".join(result.split())


def _repository(value: Any, field: str = "repository") -> str:
    result = _text(value, field, max_length=300)
    if not _REPOSITORY_RE.fullmatch(result):
        raise ReviewError(f"{field} must be an owner/name repository")
    owner, name = result.split("/", 1)
    if owner in {".", ".."} or name in {".", ".."}:
        raise ReviewError(f"{field} must be an owner/name repository")
    return result


def _sha(value: Any, field: str) -> str:
    return _text(value, field, max_length=200)


def _metadata(raw: Any, index: int) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        raise ReviewError(f"repositories[{index}] must be an object")
    prefix = f"repositories[{index}]"
    return {
        "full_name": _repository(raw.get("full_name"), f"{prefix}.full_name"),
        "default_branch": _text(raw.get("default_branch"), f"{prefix}.default_branch", max_length=300),
        "pushed_at": _iso_utc(_utc_datetime(raw.get("pushed_at"), f"{prefix}.pushed_at")),
        "head_sha": _sha(raw.get("head_sha"), f"{prefix}.head_sha"),
    }


def normalize_inventory(inventory: Any) -> list[dict[str, str]]:
    """Validate gh-produced metadata and return deterministic repository rows."""

    if isinstance(inventory, list):
        raw_repositories = inventory
    elif isinstance(inventory, Mapping):
        raw_repositories = inventory.get("repositories")
        if raw_repositories is None:
            raw_repositories = inventory.get("items")
        if raw_repositories is None and "full_name" in inventory:
            raw_repositories = [inventory]
    else:
        raw_repositories = None
    if not isinstance(raw_repositories, list):
        raise ReviewError("inventory must contain a repositories list")

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_repositories):
        row = _metadata(raw, index)
        if row["full_name"] in seen:
            raise ReviewError(f"repositories[{index}].full_name duplicates another repository")
        seen.add(row["full_name"])
        result.append(row)
    return sorted(result, key=lambda row: row["full_name"])


def normalize_state(state: Any) -> dict[str, Any]:
    """Return a defensive state copy with a v1 repository mapping."""

    if state is None:
        state = {}
    if not isinstance(state, Mapping):
        raise ReviewError("state must be an object")
    result = copy.deepcopy(dict(state))
    if "schema_version" in result and result["schema_version"] != SCHEMA_VERSION:
        raise ReviewError("state schema_version must be 1")
    result["schema_version"] = SCHEMA_VERSION
    repositories = result.get("repositories", {})
    if not isinstance(repositories, Mapping):
        raise ReviewError("state.repositories must be an object")
    result["repositories"] = copy.deepcopy(dict(repositories))
    return result


def _repository_state(state: Mapping[str, Any], repository: str) -> Mapping[str, Any] | None:
    value = state.get("repositories", {}).get(repository)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ReviewError(f"state.repositories.{repository} must be an object")
    return value


def is_review_due(record: Mapping[str, Any] | None, now: datetime | None = None) -> tuple[bool, str]:
    """Return due status and a stable reason for one repository record."""

    if record is None:
        return True, "new"
    status = record.get("last_status", record.get("status"))
    if status in {"failure", "failed"}:
        return True, "failed"
    last_success = record.get("last_successful_review_at")
    if not last_success:
        return True, "no_successful_review"
    current = _as_utc(now or _utc_now(), "now")
    if current - _utc_datetime(last_success, "last_successful_review_at") >= REVIEW_INTERVAL:
        return True, "interval"
    return False, "not_due"


def plan_reviews(inventory: Any, state: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Build a read-only incremental review plan from local JSON values."""

    rows = normalize_inventory(inventory)
    normalized_state = normalize_state(state)
    current = _as_utc(now or _utc_now(), "now")
    reviews: list[dict[str, Any]] = []
    for row in rows:
        prior = _repository_state(normalized_state, row["full_name"])
        due, reason = is_review_due(prior, current)
        if not due:
            continue
        cursor = prior.get("cursor_sha") if prior else None
        entry = dict(row)
        entry.update(
            {
                "repository": row["full_name"],
                "cursor_sha": cursor,
                "reason": reason,
                "unchanged": cursor is not None and cursor == row["head_sha"],
            }
        )
        if prior and prior.get("last_successful_review_at"):
            entry["last_successful_review_at"] = prior["last_successful_review_at"]
        reviews.append(entry)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(current),
        "reviews": reviews,
    }


def apply_review(state: Any, result: Any) -> dict[str, Any]:
    """Apply one explicit review result without mutating unrelated repositories.

    A failed result records the attempt but intentionally preserves the last
    successful timestamp and cursor, so the repository remains due.
    """

    normalized_state = normalize_state(state)
    if not isinstance(result, Mapping):
        raise ReviewError("review result must be an object")
    repository = _repository(result.get("repository"))
    status = result.get("status")
    if status not in {"success", "failure"}:
        raise ReviewError("status must be success or failure")
    reviewed_at = _iso_utc(_utc_datetime(result.get("reviewed_at"), "reviewed_at"))
    cursor_sha = _sha(result.get("cursor_sha"), "cursor_sha")
    summary = _summary(result.get("summary"))

    prior = normalized_state["repositories"].get(repository, {})
    if not isinstance(prior, Mapping):
        raise ReviewError(f"state.repositories.{repository} must be an object")
    updated = dict(prior)
    updated["last_status"] = status
    updated["last_attempted_review_at"] = reviewed_at
    updated["last_review_summary"] = summary
    if status == "success":
        updated["last_successful_review_at"] = reviewed_at
        updated["cursor_sha"] = cursor_sha
    normalized_state["repositories"][repository] = updated
    return normalized_state


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewError(f"could not read JSON {path}: {exc}") from exc


def write_json_atomic(path: Path, data: Any) -> None:
    """Atomically replace a JSON file in its destination directory."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


__all__ = [
    "REVIEW_INTERVAL",
    "ReviewError",
    "apply_review",
    "is_review_due",
    "load_json",
    "normalize_inventory",
    "normalize_state",
    "plan_reviews",
    "write_json_atomic",
]
