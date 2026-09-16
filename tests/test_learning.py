import unittest
from copy import deepcopy

from radar.learning import (
    MAX_PAIR_CHANGE,
    NEUTRAL_WEIGHT,
    pair_weights,
    rating_effects,
    replay_rating_events,
)


def event(event_id, item_id="RAD-000000000001", score=5, base_revision=0, reason=None):
    return {
        "event_id": event_id,
        "item_id": item_id,
        "score": score,
        "reason": reason,
        "origin": "form",
        "base_revision": base_revision,
        "created_at": "2026-09-15T12:00:00Z",
    }


class LearningTests(unittest.TestCase):
    def test_duplicate_same_payload_is_ignored_and_conflict_is_explicit(self):
        first = event("11111111-1111-4111-8111-111111111111")
        stale = event("22222222-2222-4222-8222-222222222222", score=1, base_revision=0)
        result = replay_rating_events([first, deepcopy(first), stale])

        self.assertEqual(result.ratings["RAD-000000000001"]["revision"], 1)
        self.assertEqual(result.duplicate_event_ids, ("11111111-1111-4111-8111-111111111111",))
        self.assertEqual(len(result.conflicts), 1)
        self.assertEqual(result.conflicts[0].current_revision, 1)
        self.assertEqual(result.ratings["RAD-000000000001"]["score"], 5)

    def test_same_event_id_with_different_payload_errors(self):
        first = event("11111111-1111-4111-8111-111111111111")
        different = event("11111111-1111-4111-8111-111111111111", score=4)
        with self.assertRaises(ValueError):
            replay_rating_events([first, different])

    def test_correction_replaces_prior_contribution_on_replay(self):
        events = [
            event("11111111-1111-4111-8111-111111111111", score=5),
            event("22222222-2222-4222-8222-222222222222", score=1, base_revision=1),
        ]
        items = [{"item_id": "RAD-000000000001", "repository": "app", "topics": ["agents"]}]
        result = replay_rating_events(events)
        weights = pair_weights(items, result)

        self.assertEqual(result.ratings[items[0]["item_id"]]["score"], 1)
        self.assertLess(weights[("agents", "app")], NEUTRAL_WEIGHT)
        self.assertEqual(result.ratings[items[0]["item_id"]]["revision"], 2)

    def test_unrated_is_neutral_and_weight_change_is_bounded(self):
        items = [
            {"item_id": "RAD-000000000001", "repository": "app", "topics": ["agents"]},
            {"item_id": "RAD-000000000002", "repository": "app", "topics": ["agents"]},
        ]
        result = replay_rating_events([event("11111111-1111-4111-8111-111111111111")])
        weights = pair_weights(items, result)
        self.assertLessEqual(abs(weights[("agents", "app")] - NEUTRAL_WEIGHT), MAX_PAIR_CHANGE)
        self.assertEqual(pair_weights(items[1:], result), {})

    def test_rating_effects_do_not_touch_credibility(self):
        effects = rating_effects(
            replay_rating_events(
                [event("11111111-1111-4111-8111-111111111111", score=5, reason="too technical")]
            )
        )
        effect = effects["RAD-000000000001"]
        self.assertEqual(effect["queue"], "experiment")
        self.assertEqual(effect["presentation"], "simplify")
        self.assertNotIn("credibility", effect)


if __name__ == "__main__":
    unittest.main()
