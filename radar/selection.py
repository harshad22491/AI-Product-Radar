"""Pure candidate filtering, ranking, and diversification."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from typing import Any, Iterable, Mapping

from .learning import RatingReplay, _current_rating_map, _text, pair_weights, relevance_multiplier


MINIMUM_DIGEST_ITEMS = 7


class InsufficientCandidatesError(ValueError):
    """Selection cannot meet the requested digest size without filler."""

    def __init__(self, required: int, available: int, *, excluded: int = 0) -> None:
        self.required = required
        self.available = available
        self.excluded = excluded
        super().__init__(
            f"insufficient eligible unsent candidates: need {required}, have {available}"
        )


class MissingUserFacingProductError(ValueError):
    """Selection cannot include the required user-facing AI product."""

    def __init__(self) -> None:
        super().__init__("no eligible user-facing AI product is available for this digest")


def _as_date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field} must be YYYY-MM-DD") from exc
    raise ValueError(f"{field} must be YYYY-MM-DD")


def _subtract_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _age_floor(edition_date: date, source_type: str) -> date:
    if source_type == "academic":
        try:
            return edition_date.replace(year=edition_date.year - 2)
        except ValueError:  # February 29 on a non-leap year.
            return edition_date.replace(year=edition_date.year - 2, day=28)
    return _subtract_months(edition_date, 6)


def _base_score(candidate: Mapping[str, Any]) -> float:
    for key in ("relevance", "quality", "score"):
        value = candidate.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def _topics(candidate: Mapping[str, Any]) -> tuple[str, ...]:
    topics = candidate.get("topics", ())
    if isinstance(topics, str):
        topics = (topics,)
    return tuple(topic for topic in (_text(value) for value in topics or ()) if topic)


def _effort_is_small(candidate: Mapping[str, Any]) -> bool:
    guidance = candidate.get("guidance", ())
    if isinstance(guidance, Mapping):
        effort = guidance.get("Effort", guidance.get("effort", ""))
    elif isinstance(guidance, (list, tuple)) and len(guidance) >= 4:
        effort = guidance[3]
    else:
        effort = candidate.get("effort", "")
    value = _text(effort)
    return any(word in value for word in ("small", "low", "easy", "quick", "minimal", "minutes"))


def _is_exploration(candidate: Mapping[str, Any], current: Mapping[str, Mapping[str, Any]]) -> bool:
    if candidate.get("exploration") is True:
        return True
    return candidate.get("item_id") not in current


def _candidate_sort_key(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(candidate.get("item_id", "")),
        str(candidate.get("source_url", "")),
        str(candidate.get("title", "")),
    )


def _rank_score(
    candidate: Mapping[str, Any],
    *,
    current: Mapping[str, Mapping[str, Any]],
    weights: Mapping[tuple[str, str], float],
    topic_counts: Mapping[str, int],
    repository_counts: Mapping[str, int],
    source_counts: Mapping[str, int],
    selected_count: int,
    target: int,
) -> float:
    source_type = _text(candidate.get("source_type"))
    score = _base_score(candidate)
    score *= relevance_multiplier(candidate, current, weights=weights)

    # Product/tool discoveries are the main practical use of the digest.
    if source_type == "product":
        score += 0.75
    elif source_type == "tool":
        score += 0.20

    if _is_exploration(candidate, current):
        score += 0.12

    topics = _topics(candidate)
    repository = _text(candidate.get("repository"))
    score += 0.16 if repository and repository not in repository_counts else 0.0
    score += 0.08 if any(topic not in topic_counts for topic in topics) else 0.0
    score += 0.04 if source_type and source_type not in source_counts else 0.0

    # A rating of "too much effort" is a preference for smaller experiments,
    # not a credibility judgment.
    rating = current.get(candidate.get("item_id"))
    if rating and "too much effort" in _text(rating.get("reason")):
        score += 0.16 if _effort_is_small(candidate) else -0.16

    # Keep a small, deterministic exploration pressure throughout the greedy
    # pass without allowing it to overwhelm a strong known match.
    if selected_count >= max(1, target // 2) and _is_exploration(candidate, current):
        score += 0.05
    return score


def select_candidates(
    candidates: Iterable[Mapping[str, Any]],
    *,
    edition_date: date | datetime | str,
    delivered_item_ids: Iterable[str] = (),
    sent_item_ids: Iterable[str] = (),
    ratings: Any = (),
    limit: int = MINIMUM_DIGEST_ITEMS,
    minimum: int = MINIMUM_DIGEST_ITEMS,
) -> list[dict[str, Any]]:
    """Return a deterministic, diverse selection of eligible candidates.

    The returned dictionaries are shallow copies; inputs, rating state, and
    delivery sets are never modified.  ``minimum`` defaults to the contract's
    seven-item digest floor.  If the pool cannot satisfy ``limit`` the
    function raises ``InsufficientCandidatesError`` instead of manufacturing
    filler.
    """

    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1:
        raise ValueError("minimum must be a positive integer")
    minimum = max(MINIMUM_DIGEST_ITEMS, minimum)
    if limit < minimum:
        raise ValueError(f"limit must be at least the minimum of {minimum}")
    edition = _as_date(edition_date, "edition_date")
    delivered = {str(item_id) for item_id in delivered_item_ids}
    sent = {str(item_id) for item_id in sent_item_ids}
    blocked = delivered | sent
    current = _current_rating_map(ratings)

    unique: dict[str, Mapping[str, Any]] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("each candidate must be an object")
        item_id = candidate.get("item_id")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError("each candidate needs a non-empty item_id")
        if item_id in unique:
            # ID is the identity boundary.  Keep the first normalized finding
            # so a repeated source cannot consume two digest slots.
            continue
        unique[item_id] = candidate

    eligible: list[Mapping[str, Any]] = []
    for candidate in unique.values():
        item_id = candidate["item_id"]
        if item_id in blocked:
            continue
        rating = current.get(item_id)
        if rating and "already knew" in _text(rating.get("reason")):
            continue
        source_type = _text(candidate.get("source_type"))
        published = _as_date(candidate.get("published_at"), "published_at")
        if published > edition or published < _age_floor(edition, source_type):
            continue
        eligible.append(candidate)

    if len(eligible) < limit:
        raise InsufficientCandidatesError(limit, len(eligible), excluded=len(unique) - len(eligible))

    qualifying = [candidate for candidate in eligible if candidate.get("user_facing_ai") is True]
    if not qualifying:
        raise MissingUserFacingProductError()

    weights = pair_weights(eligible, current)
    remaining = list(eligible)
    selected: list[Mapping[str, Any]] = []
    topic_counts: dict[str, int] = {}
    repository_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}

    while remaining and len(selected) < limit:
        ranked = sorted(
            remaining,
            key=lambda candidate: (
                -_rank_score(
                    candidate,
                    current=current,
                    weights=weights,
                    topic_counts=topic_counts,
                    repository_counts=repository_counts,
                    source_counts=source_counts,
                    selected_count=len(selected),
                    target=limit,
                ),
                _candidate_sort_key(candidate),
            ),
        )
        chosen = ranked[0]
        selected.append(chosen)
        remaining.remove(chosen)
        for topic in _topics(chosen):
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        repository = _text(chosen.get("repository"))
        if repository:
            repository_counts[repository] = repository_counts.get(repository, 0) + 1
        source_type = _text(chosen.get("source_type"))
        if source_type:
            source_counts[source_type] = source_counts.get(source_type, 0) + 1

    # Greedy diversity can still fill every slot with known high scores.  An
    # available unrated finding is explicitly reserved as exploration.
    # Reserve both a useful new discovery and at least one genuinely
    # user-facing AI product, even when either ranks below the greedy cutoff.
    exploration = next((candidate for candidate in eligible if _is_exploration(candidate, current)), None)
    reserved = [exploration, qualifying[0]]
    for required_candidate in reserved:
        if required_candidate is not None and not any(
            item["item_id"] == required_candidate["item_id"] for item in selected
        ):
            selected[-1] = required_candidate

    # The product reservation may have replaced the exploration reservation;
    # keep the product contract authoritative and deterministic.
    if not any(item.get("user_facing_ai") is True for item in selected):
        selected[-1] = qualifying[0]

    return [dict(candidate) for candidate in selected]


select = select_candidates
rank_candidates = select_candidates


__all__ = [
    "InsufficientCandidatesError",
    "MissingUserFacingProductError",
    "MINIMUM_DIGEST_ITEMS",
    "rank_candidates",
    "select",
    "select_candidates",
]
