import copy
import unittest

from radar.domain import canonical_url, stable_item_id, validate_bundle


def make_item(number=0, *, source_type="product", published_at="2026-08-01"):
    source = f"https://Example.com/library/../signal-{number}/?b=2&a=1#section"
    return {
        "item_id": stable_item_id(source),
        "title": f"Signal {number}",
        "source_url": source,
        "published_at": published_at,
        "source_type": source_type,
        "summary": "This product turns a messy input into a structured result that an operator can inspect, correct, and reuse. It explains the main workflow in plain language and leaves approval with the person doing the work.",
        "why_it_matters": "It makes a useful workflow easier to try.",
        "evidence_label": "Documented release",
        "repository": "owner/project",
        "guidance": ["Read the module", "Try the small example", "Save a baseline", "One hour", "Check output"],
        "topics": ["automation", "evaluation"],
        "user_facing_ai": number == 0,
        "application_example": "Use it on a synthetic document before connecting it to an approved workflow.",
    }


def make_bundle():
    return {
        "schema_version": 1,
        "run_id": "edition-2026-09-01",
        "edition_date": "2026-09-01",
        "generated_at": "2026-09-01T12:00:00Z",
        "producer": "fable",
        "model_id": "fable-5.1",
        "kind": "digest",
        "items": [make_item(number) for number in range(7)],
    }


class DomainTests(unittest.TestCase):
    def test_canonical_url_normalizes_host_path_query_and_fragment(self):
        self.assertEqual(
            canonical_url(" HTTPS://EXAMPLE.com:443/a/../b/?z=2&a=1#read "),
            "https://example.com/b?a=1&z=2",
        )

    def test_stable_id_uses_canonical_url(self):
        first = stable_item_id("https://example.com/a#one")
        second = stable_item_id("HTTPS://EXAMPLE.COM:443/a/")
        self.assertEqual(first, second)
        self.assertRegex(first, r"^RAD-[0-9a-f]{12}$")

    def test_valid_bundle_returns_normalized_copy(self):
        bundle = make_bundle()
        normalized = validate_bundle(bundle)
        self.assertIsNot(normalized, bundle)
        self.assertEqual(normalized["items"][0]["source_url"], "https://example.com/signal-0?a=1&b=2")
        self.assertEqual(normalized["items"][0]["published_at"], "2026-08-01")
        self.assertNotIn("source_dates", normalized["items"][0])
        self.assertTrue(normalized["items"][0]["user_facing_ai"])

    def test_requires_user_facing_product_and_normalizes_legacy_marker(self):
        bundle = make_bundle()
        for item in bundle["items"]:
            item.pop("user_facing_ai", None)
        with self.assertRaisesRegex(ValueError, "user-facing AI product"):
            validate_bundle(bundle)
        bundle = make_bundle()
        bundle["items"][0]["user_facing_ai"] = "yes"
        with self.assertRaisesRegex(ValueError, "must be a boolean"):
            validate_bundle(bundle)

    def test_user_facing_product_requires_bounded_application_example(self):
        bundle = make_bundle()
        bundle["items"][0].pop("application_example")
        with self.assertRaisesRegex(ValueError, "application_example.*required"):
            validate_bundle(bundle)
        bundle = make_bundle()
        bundle["items"][0]["application_example"] = "x" * 4001
        with self.assertRaisesRegex(ValueError, "at most 4000"):
            validate_bundle(bundle)

    def test_rejects_too_few_items(self):
        bundle = make_bundle()
        bundle["items"] = bundle["items"][:6]
        with self.assertRaisesRegex(ValueError, "at least 7"):
            validate_bundle(bundle)

    def test_rejects_unknown_bundle_field(self):
        bundle = make_bundle()
        bundle["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "unknown field"):
            validate_bundle(bundle)

    def test_rejects_bad_calendar_date(self):
        bundle = make_bundle()
        bundle["items"][0]["published_at"] = "2026-02-29"
        with self.assertRaisesRegex(ValueError, "real calendar date"):
            validate_bundle(bundle)

    def test_rejects_calendar_freshness_boundary(self):
        bundle = make_bundle()
        bundle["items"][0] = make_item(source_type="tool", published_at="2026-02-28")
        with self.assertRaisesRegex(ValueError, "freshness window"):
            validate_bundle(bundle)

    def test_rejects_future_and_wrong_id(self):
        bundle = make_bundle()
        bundle["items"][0]["published_at"] = "2026-09-02"
        with self.assertRaisesRegex(ValueError, "after edition_date"):
            validate_bundle(bundle)
        bundle = make_bundle()
        bundle["items"][0]["item_id"] = "RAD-000000000000"
        with self.assertRaisesRegex(ValueError, "must equal RAD-"):
            validate_bundle(bundle)

    def test_rejects_invalid_guidance_and_duplicate_source(self):
        bundle = make_bundle()
        bundle["items"][0]["guidance"] = ["only", "four", "lines", "are", "not", "allowed"]
        with self.assertRaisesRegex(ValueError, "exactly 5"):
            validate_bundle(bundle)
        bundle = make_bundle()
        bundle["items"][1] = copy.deepcopy(bundle["items"][0])
        with self.assertRaisesRegex(ValueError, "duplicates"):
            validate_bundle(bundle)

    def test_rejects_invalid_optional_fields(self):
        bundle = make_bundle()
        bundle["items"][0]["source_dates"] = {"released": "2025-02-29"}
        with self.assertRaisesRegex(ValueError, "real calendar date"):
            validate_bundle(bundle)
        bundle = make_bundle()
        bundle["items"][0]["repository_evidence"] = {"commit": 42}
        with self.assertRaisesRegex(ValueError, "must be a string"):
            validate_bundle(bundle)

    def test_rejects_path_like_repository_name(self):
        bundle = make_bundle()
        bundle["items"][0]["repository"] = "../secrets"
        with self.assertRaisesRegex(ValueError, "sanitized repository"):
            validate_bundle(bundle)


if __name__ == "__main__":
    unittest.main()
