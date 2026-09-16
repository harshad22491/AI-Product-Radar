import copy
import unittest
from datetime import datetime, timezone

from radar.github_review import apply_review, plan_reviews


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


def inventory(*, head_sha="b" * 40):
    return {
        "schema_version": 1,
        "repositories": [
            {
                "full_name": "owner/project",
                "default_branch": "main",
                "pushed_at": "2026-09-14T10:00:00Z",
                "head_sha": head_sha,
            }
        ],
    }


class GithubReviewTests(unittest.TestCase):
    def test_new_repository_is_due(self):
        plan = plan_reviews(inventory(), {"schema_version": 1, "repositories": {}}, now=NOW)
        self.assertEqual([entry["repository"] for entry in plan["reviews"]], ["owner/project"])
        self.assertEqual(plan["reviews"][0]["reason"], "new")

    def test_exact_ten_elapsed_days_is_due(self):
        state = {
            "schema_version": 1,
            "repositories": {
                "owner/project": {
                    "last_successful_review_at": "2026-09-05T12:00:00Z",
                    "cursor_sha": "a" * 40,
                    "last_status": "success",
                }
            },
        }
        plan = plan_reviews(inventory(), state, now=NOW)
        self.assertEqual(len(plan["reviews"]), 1)
        self.assertEqual(plan["reviews"][0]["reason"], "interval")

        state["repositories"]["owner/project"]["last_successful_review_at"] = "2026-09-05T12:00:01Z"
        self.assertEqual(plan_reviews(inventory(), state, now=NOW)["reviews"], [])

    def test_failure_does_not_advance_success_cursor_and_remains_due(self):
        state = {
            "schema_version": 1,
            "repositories": {
                "owner/project": {
                    "last_successful_review_at": "2026-09-01T12:00:00Z",
                    "cursor_sha": "a" * 40,
                    "last_status": "success",
                }
            },
        }
        original = copy.deepcopy(state)
        updated = apply_review(
            state,
            {
                "repository": "owner/project",
                "status": "failure",
                "reviewed_at": "2026-09-15T12:00:00Z",
                "cursor_sha": "b" * 40,
                "summary": "GitHub was unavailable.",
            },
        )
        repo = updated["repositories"]["owner/project"]
        self.assertEqual(repo["cursor_sha"], original["repositories"]["owner/project"]["cursor_sha"])
        self.assertEqual(repo["last_successful_review_at"], original["repositories"]["owner/project"]["last_successful_review_at"])
        self.assertEqual(plan_reviews(inventory(), updated, now=NOW)["reviews"][0]["reason"], "failed")

    def test_success_records_cursor_for_only_target_repository(self):
        state = {
            "schema_version": 1,
            "repositories": {
                "owner/project": {
                    "last_successful_review_at": "2026-09-01T12:00:00Z",
                    "cursor_sha": "a" * 40,
                    "last_status": "success",
                },
                "owner/other": {
                    "last_successful_review_at": "2026-09-10T12:00:00Z",
                    "cursor_sha": "c" * 40,
                    "last_status": "success",
                },
            },
        }
        updated = apply_review(
            state,
            {
                "repository": "owner/project",
                "status": "success",
                "reviewed_at": "2026-09-15T12:00:00Z",
                "cursor_sha": "b" * 40,
                "summary": "No changes since the previous cursor.",
            },
        )
        self.assertEqual(updated["repositories"]["owner/project"]["cursor_sha"], "b" * 40)
        self.assertEqual(updated["repositories"]["owner/other"], state["repositories"]["owner/other"])


if __name__ == "__main__":
    unittest.main()
