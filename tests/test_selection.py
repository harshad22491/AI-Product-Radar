import unittest

from radar.selection import InsufficientCandidatesError, MissingUserFacingProductError, select_candidates


EDITION = "2026-09-15"


def candidate(number, *, source_type="product", published_at="2026-09-01", topic=None, repository=None, quality=1.0, user_facing_ai=None):
    item_id = f"RAD-{number:012x}"
    return {
        "item_id": item_id,
        "title": f"Candidate {number}",
        "source_url": f"https://example.com/{number}",
        "published_at": published_at,
        "source_type": source_type,
        "repository": repository or f"repo-{number % 3}",
        "topics": [topic or f"topic-{number % 4}"],
        "quality": quality,
        "user_facing_ai": source_type == "product" if user_facing_ai is None else user_facing_ai,
    }


class SelectionTests(unittest.TestCase):
    def test_calendar_age_caps_and_future_dates(self):
        pool = [
            *[candidate(i, published_at="2026-09-01") for i in range(9)],
            candidate(20, source_type="academic", published_at="2024-09-15"),
            candidate(21, source_type="academic", published_at="2024-09-14"),
            candidate(22, source_type="tool", published_at="2026-03-14"),
            candidate(23, source_type="tool", published_at="2026-03-15"),
            candidate(24, source_type="tool", published_at="2026-09-16"),
        ]
        selected = select_candidates(pool, edition_date=EDITION, limit=11)
        ids = {item["item_id"] for item in selected}

        self.assertIn(candidate(20)["item_id"], ids)
        self.assertNotIn(candidate(21)["item_id"], ids)
        self.assertIn(candidate(23)["item_id"], ids)
        self.assertNotIn(candidate(22)["item_id"], ids)
        self.assertNotIn(candidate(24)["item_id"], ids)

    def test_duplicate_ids_and_delivered_or_sent_items_do_not_consume_slots(self):
        pool = [candidate(i) for i in range(9)]
        pool.insert(1, dict(pool[0], title="duplicate"))
        selected = select_candidates(
            pool,
            edition_date=EDITION,
            delivered_item_ids=[candidate(0)["item_id"]],
            sent_item_ids=[candidate(1)["item_id"]],
        )

        self.assertEqual(len(selected), 7)
        ids = [item["item_id"] for item in selected]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn(candidate(0)["item_id"], ids)
        self.assertNotIn(candidate(1)["item_id"], ids)

    def test_product_bias_and_exploration_are_present(self):
        pool = [candidate(i, source_type="academic", quality=1.0, topic="same") for i in range(7)]
        pool.extend(candidate(i + 10, source_type="product", quality=0.5, topic=f"new-{i}") for i in range(3))
        selected = select_candidates(pool, edition_date=EDITION)

        self.assertEqual(len(selected), 7)
        self.assertGreaterEqual(sum(item["source_type"] == "product" for item in selected), 1)
        self.assertTrue(any(item["item_id"] == candidate(0)["item_id"] for item in selected))

    def test_already_knew_suppresses_repeat_and_insufficient_is_error(self):
        pool = [candidate(i) for i in range(8)]
        ratings = {
            candidate(0)["item_id"]: {"revision": 1, "score": 3, "reason": "already knew"}
        }
        selected = select_candidates(pool, edition_date=EDITION, ratings=ratings)
        self.assertNotIn(candidate(0)["item_id"], {item["item_id"] for item in selected})

        with self.assertRaises(InsufficientCandidatesError) as raised:
            select_candidates(pool[:6], edition_date=EDITION)
        self.assertEqual(raised.exception.required, 7)
        self.assertEqual(raised.exception.available, 6)

    def test_original_published_date_is_retained(self):
        pool = [candidate(i, published_at="2026-08-20") for i in range(7)]
        selected = select_candidates(pool, edition_date=EDITION)
        self.assertEqual(selected[0]["published_at"], "2026-08-20")

    def test_reserves_low_rank_user_facing_product(self):
        pool = [candidate(i, source_type="academic", quality=10.0, user_facing_ai=False) for i in range(7)]
        pool.append(candidate(99, source_type="product", quality=-100.0, user_facing_ai=True))
        selected = select_candidates(pool, edition_date=EDITION)
        self.assertIn(candidate(99)["item_id"], {item["item_id"] for item in selected})

    def test_fails_without_eligible_user_facing_product(self):
        pool = [candidate(i, source_type="tool", user_facing_ai=False) for i in range(7)]
        with self.assertRaises(MissingUserFacingProductError):
            select_candidates(pool, edition_date=EDITION)


if __name__ == "__main__":
    unittest.main()
