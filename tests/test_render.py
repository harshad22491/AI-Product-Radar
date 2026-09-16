import unittest

from radar.render import render_html, render_text
from tests.test_domain import make_bundle


class RenderTests(unittest.TestCase):
    def test_html_puts_rating_system_first_and_escapes_fields(self):
        bundle = make_bundle()
        bundle["items"][0]["title"] = '<script>alert("x")</script>'
        bundle["items"][0]["summary"] = "Use <b>only</b> if it fits."
        output = render_html(bundle, "https://forms.example.test/rate?item=1&mode=quick")
        self.assertLess(output.index("Quick rating"), output.index("Signal 1"))
        self.assertIn("1</td>", output)
        self.assertIn("5</td>", output)
        self.assertIn("queue an investigation", output)
        self.assertIn("propose an experiment only", output)
        self.assertIn("too technical", output)
        self.assertIn("RATE RAD-id SCORE REV=0 your reason", output)
        self.assertIn("RATE RAD-", output)
        self.assertIn("Source date:", output)
        self.assertIn("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;", output)
        self.assertNotIn('<script>alert("x")</script>', output)
        self.assertIn("forms.example.test/rate?item=1&amp;mode=quick", output)

    def test_html_rejects_unsafe_rating_link(self):
        with self.assertRaisesRegex(ValueError, "scheme must be https"):
            render_html(make_bundle(), "javascript:alert(1)")

    def test_text_contains_rating_legend_dates_and_guidance(self):
        bundle = make_bundle()
        bundle["items"][0]["source_dates"] = {"released": "2026-07-31", "updated": "2026-08-01"}
        bundle["items"][0]["repository_evidence"] = ["commit abc123", "path radar/domain.py"]
        output = render_text(bundle)
        self.assertLess(output.index("HOW TO RATE"), output.index("1. Signal 0"))
        self.assertIn("1 - Skip: suppress similar items", output)
        self.assertIn("4 - Strong match: queue an investigation", output)
        self.assertIn("5 - Excellent: propose an experiment only", output)
        self.assertIn("Reason tags: too technical, already knew, too much effort", output)
        self.assertIn("Source date: 2026-08-01", output)
        self.assertIn("Source dates: released: 2026-07-31; updated: 2026-08-01", output)
        self.assertIn("Where it fits in your work: Read the module", output)
        self.assertIn("Repository evidence: commit abc123; path radar/domain.py", output)
        self.assertIn("Product marker: User-facing AI product", output)
        self.assertIn("Example application:", output)
        self.assertIn("Where it fits in your work: Read the module", output)
        self.assertIn("Rate this item: RATE RAD-", output)

    def test_renderers_validate_before_rendering(self):
        bundle = make_bundle()
        bundle["items"] = bundle["items"][:6]
        with self.assertRaises(ValueError):
            render_html(bundle)
        with self.assertRaises(ValueError):
            render_text(bundle)


if __name__ == "__main__":
    unittest.main()
