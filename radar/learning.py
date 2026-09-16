"""Pure rating replay and preference learning for the radar.

The module deliberately knows nothing about storage, email, sheets, or the
domain validator.  It reduces an immutable event stream into current ratings
and derives bounded relevance weights from that reduced state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Iterable, Mapping
from uuid import UUID


ORIGINS = frozenset({"email", "form", "chat", "obsidian"})
MIN_WEIGHT = 0.75
MAX_WEIGHT = 1.25
NEUTRAL_WEIGHT = 1.0
MAX_PAIR_CHANGE = MAX_WEIGHT - NEUTRAL_WEIGHT
_ISO_DATE_TIME = re.compile(r"Z$", re.IGNORECASE)


@dataclass(frozen=True)
class RatingConflict:
    """A stale event that was not allowed to overwrite current state."""

    event_id: str
    item_id: str
    base_revision: int
    current_revision: int
    reason: str


@dataclass(frozen=True)
class RatingReplay:
    """The complete, auditable result of replaying rating events."""

    ratings: dict[str, dict[str, Any]]
    conflicts: tuple[RatingConflict, ...]
    duplicate_event_ids: tuple[str, ...]
    accepted_events: tuple[dict[str, Any], ...]

    def __getitem__(self, item: str) -> Any:
        """Allow the result to be used conveniently like a result mapping."""

        return getattr(self, item)


def _parse_created_at(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("created_at must be an aware UTC ISO timestamp")
    candidate = _ISO_DATE_TIME.sub("+00:00", value.strip())
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError("created_at must be an aware UTC ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("created_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def _canonical_event(event: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(event, Mapping):
        raise ValueError("rating event must be an object")

    event_id_value = event.get("event_id")
    if not isinstance(event_id_value, str):
        raise ValueError("event_id must be a UUID string")
    try:
        event_id = str(UUID(event_id_value))
    except (ValueError, AttributeError) as exc:
        raise ValueError("event_id must be a UUID string") from exc

    item_id = event.get("item_id")
    if not isinstance(item_id, str) or not item_id.strip():
        raise ValueError("item_id must be a non-empty string")

    score = event.get("score")
    if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5:
        raise ValueError("score must be an integer from 1 through 5")

    reason = event.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise ValueError("reason must be a string or null")

    origin = event.get("origin")
    if origin not in ORIGINS:
        raise ValueError(f"origin must be one of {sorted(ORIGINS)}")

    base_revision = event.get("base_revision")
    if (
        isinstance(base_revision, bool)
        or not isinstance(base_revision, int)
        or base_revision < 0
    ):
        raise ValueError("base_revision must be a non-negative integer")

    created_at = _parse_created_at(event.get("created_at"))
    return {
        "event_id": event_id,
        "item_id": item_id,
        "score": score,
        "reason": reason,
        "origin": origin,
        "base_revision": base_revision,
        "created_at": created_at.isoformat().replace("+00:00", "Z"),
    }


def replay_rating_events(events: Iterable[Mapping[str, Any]]) -> RatingReplay:
    """Replay events in supplied order, returning state and explicit conflicts.

    An event ID is an idempotency key.  Repeating the exact same normalized
    payload is ignored; reusing the ID for another payload raises ``ValueError``.
    A stale base revision is reported as a conflict and never changes state.
    Replaying the accepted stream therefore makes a correction replace the
    prior item's contribution rather than accumulating both scores.
    """

    if isinstance(events, (str, bytes)):
        raise ValueError("events must be an iterable of event objects")

    ratings: dict[str, dict[str, Any]] = {}
    seen_events: dict[str, dict[str, Any]] = {}
    conflicts: list[RatingConflict] = []
    duplicates: list[str] = []
    accepted: list[dict[str, Any]] = []

    for raw_event in events:
        event = _canonical_event(raw_event)
        event_id = event["event_id"]
        prior_event = seen_events.get(event_id)
        if prior_event is not None:
            if prior_event != event:
                raise ValueError(f"event_id {event_id} was reused with a different payload")
            duplicates.append(event_id)
            continue

        seen_events[event_id] = event
        item_id = event["item_id"]
        current = ratings.get(item_id)
        current_revision = current["revision"] if current else 0
        if event["base_revision"] != current_revision:
            conflicts.append(
                RatingConflict(
                    event_id=event_id,
                    item_id=item_id,
                    base_revision=event["base_revision"],
                    current_revision=current_revision,
                    reason="stale base_revision",
                )
            )
            continue

        revision = current_revision + 1
        ratings[item_id] = {
            "revision": revision,
            "score": event["score"],
            "reason": event["reason"],
            "event_id": event_id,
            "origin": event["origin"],
            "created_at": event["created_at"],
        }
        accepted.append(event)

    return RatingReplay(
        ratings=ratings,
        conflicts=tuple(conflicts),
        duplicate_event_ids=tuple(duplicates),
        accepted_events=tuple(accepted),
    )


# These names make the small pure seam easy to discover without adding a
# second implementation.
apply_rating_events = replay_rating_events
reduce_rating_events = replay_rating_events
replay_ratings = replay_rating_events


def _rating_signal(score: int) -> float:
    return (score - 3) / 2.0


def _text(value: Any) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def _current_rating_map(ratings_or_events: Any) -> dict[str, dict[str, Any]]:
    if isinstance(ratings_or_events, RatingReplay):
        return ratings_or_events.ratings
    if isinstance(ratings_or_events, Mapping):
        # Current-ratings snapshots are already reduced.  Copy them so the
        # learning functions cannot mutate caller-owned state.
        return {str(key): dict(value) for key, value in ratings_or_events.items()}
    return replay_rating_events(ratings_or_events).ratings


def _pair_key(topic: Any, repository: Any) -> tuple[str, str]:
    return (_text(topic), _text(repository))


def pair_weights(
    items: Iterable[Mapping[str, Any]],
    ratings_or_events: Any,
    *,
    max_change: float = MAX_PAIR_CHANGE,
) -> dict[tuple[str, str], float]:
    """Return bounded topic/repository relevance weights.

    Every item with a current rating contributes once to each of its
    topic-repository pairs.  Pair signals are averaged, so repeated events do
    not accumulate.  Empty or unrated pairs remain exactly neutral.
    """

    if isinstance(max_change, bool) or not isinstance(max_change, (int, float)):
        raise ValueError("max_change must be a number")
    if max_change < 0 or max_change > 1:
        raise ValueError("max_change must be between 0 and 1")

    current = _current_rating_map(ratings_or_events)
    signals: dict[tuple[str, str], list[float]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("each item must be an object")
        item_id = item.get("item_id")
        rating = current.get(item_id)
        if rating is None:
            continue
        score = rating.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5:
            raise ValueError(f"invalid current score for {item_id}")
        repository = item.get("repository", "")
        topics = item.get("topics", ())
        if isinstance(topics, str) or topics is None:
            topics = (topics,) if topics else ()
        for topic in topics:
            key = _pair_key(topic, repository)
            if not key[0] or not key[1]:
                continue
            signals.setdefault(key, []).append(_rating_signal(score))

    result: dict[tuple[str, str], float] = {}
    for key, values in signals.items():
        average = sum(values) / len(values)
        result[key] = max(NEUTRAL_WEIGHT - max_change, min(NEUTRAL_WEIGHT + max_change, NEUTRAL_WEIGHT + max_change * average))
    return result


def relevance_multiplier(
    item: Mapping[str, Any],
    ratings_or_events: Any,
    *,
    weights: Mapping[tuple[str, str], float] | None = None,
) -> float:
    """Return a neutral-to-bounded relevance multiplier for one item."""

    item_id = item.get("item_id")
    current = _current_rating_map(ratings_or_events)
    rating = current.get(item_id)
    if rating is None:
        return NEUTRAL_WEIGHT
    if weights is None:
        weights = pair_weights((item,), current)
    repository = item.get("repository", "")
    topics = item.get("topics", ())
    if isinstance(topics, str) or topics is None:
        topics = (topics,) if topics else ()
    values = [weights.get(_pair_key(topic, repository), NEUTRAL_WEIGHT) for topic in topics]
    return sum(values) / len(values) if values else NEUTRAL_WEIGHT


def rating_effects(ratings_or_events: Any) -> dict[str, dict[str, Any]]:
    """Expose non-credibility consequences of current ratings.

    ``credibility`` is intentionally absent: rating preference can alter
    relevance, presentation, and workflow queues, never source truth.
    """

    current = _current_rating_map(ratings_or_events)
    effects: dict[str, dict[str, Any]] = {}
    for item_id, rating in current.items():
        reason = _text(rating.get("reason"))
        effects[item_id] = {
            "relevance_signal": _rating_signal(rating["score"]),
            "suppress_repeat": "already knew" in reason,
            "presentation": "simplify" if "too technical" in reason else "normal",
            "prefer_small_scope": "too much effort" in reason,
            "queue": "experiment" if rating["score"] == 5 else "investigation" if rating["score"] == 4 else None,
        }
    return effects


__all__ = [
    "MAX_PAIR_CHANGE",
    "MAX_WEIGHT",
    "MIN_WEIGHT",
    "NEUTRAL_WEIGHT",
    "RatingConflict",
    "RatingReplay",
    "apply_rating_events",
    "pair_weights",
    "rating_effects",
    "reduce_rating_events",
    "relevance_multiplier",
    "replay_rating_events",
    "replay_ratings",
]
