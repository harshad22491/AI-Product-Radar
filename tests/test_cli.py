import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_domain import make_bundle


ROOT = Path(__file__).resolve().parent.parent


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "radar", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_validate_and_render_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle_path = root / "bundle.json"
            bundle_path.write_text(json.dumps(make_bundle()), encoding="utf-8")

            validated = self.run_cli("validate", str(bundle_path))
            self.assertEqual(validated.returncode, 0, validated.stderr)
            self.assertEqual(json.loads(validated.stdout)["schema_version"], 1)

            output = root / "rendered"
            rendered = self.run_cli("render", str(bundle_path), "plain", "--out", str(output))
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertIn("HOW TO RATE", (output / "bundle.txt").read_text(encoding="utf-8"))

    def test_init_vault_and_rating_bundle_are_local(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            initialized = self.run_cli("init-vault", "--vault", str(vault))
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            self.assertTrue((vault / "Reviews").is_dir())

            event = root / "event.json"
            event.write_text(
                json.dumps(
                    {
                        "item_id": "RAD-aaaaaaaaaaaa",
                        "score": 4,
                        "reason": "good match",
                        "origin": "chat",
                        "base_revision": 0,
                    }
                ),
                encoding="utf-8",
            )
            output = root / "ratings.json"
            rated = self.run_cli("rating", str(event), "--out", str(output))
            self.assertEqual(rated.returncode, 0, rated.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            created = data["events"][0]
            self.assertEqual(data["schema_version"], 1)
            self.assertRegex(created["event_id"], r"^[0-9a-f-]{36}$")
            self.assertTrue(created["created_at"].endswith("Z"))
            self.assertEqual(created["base_revision"], 0)

    def test_review_plan_and_apply_review_use_local_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = root / "inventory.json"
            inventory.write_text(
                json.dumps(
                    {
                        "repositories": [
                            {
                                "full_name": "owner/project",
                                "default_branch": "main",
                                "pushed_at": "2026-09-14T10:00:00Z",
                                "head_sha": "b" * 40,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            state = root / "state.json"
            state.write_text(json.dumps({"schema_version": 1, "repositories": {}}), encoding="utf-8")
            plan = root / "plan.json"
            planned = self.run_cli("review-plan", str(inventory), "--state", str(state), "--out", str(plan))
            self.assertEqual(planned.returncode, 0, planned.stderr)
            self.assertEqual(len(json.loads(plan.read_text(encoding="utf-8"))["reviews"]), 1)

            result = root / "result.json"
            result.write_text(
                json.dumps(
                    {
                        "repository": "owner/project",
                        "status": "success",
                        "reviewed_at": "2026-09-15T12:00:00Z",
                        "cursor_sha": "b" * 40,
                        "summary": "No changes.",
                    }
                ),
                encoding="utf-8",
            )
            applied = self.run_cli("apply-review", str(result), "--state", str(state))
            self.assertEqual(applied.returncode, 0, applied.stderr)
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(saved["repositories"]["owner/project"]["cursor_sha"], "b" * 40)


if __name__ == "__main__":
    unittest.main()
