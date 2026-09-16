import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar.sync import (
    SyncError, atomic_write_json, ensure_vault, export_ratings, import_snapshot,
    parse_frontmatter, render_frontmatter, render_item_note, render_digest_note, run_sync, safe_path, safe_slug,
    validate_snapshot, VAULT_DIRS,
)


def make_item(iid="RAD-aaaaaaaaaaaa", title="Test Item"):
    return {
        "item_id": iid,
        "title": title,
        "source_url": "https://example.com/a",
        "published_at": "2025-01-01",
        "source_type": "academic",
        "summary": "s",
        "why_it_matters": "w",
        "evidence_label": "e",
        "repository": "repo-one",
        "guidance": ["a", "b", "c", "d", "e"],
        "topics": ["t"],
    }


def make_snapshot(items=None, ratings=None, digests=None, state_revision=0,
                  updated_at="2025-01-01T00:00:00Z"):
    return {"schema_version": 1, "items": items or [make_item()],
            "digests": digests or [], "ratings": ratings or {},
            "state_revision": state_revision, "updated_at": updated_at}


class TestHelpers(unittest.TestCase):
    def test_safe_slug(self):
        self.assertEqual(safe_slug("My Repo/Name"), "My-Repo-Name")

    def test_safe_slug_rejects_dotdot(self):
        with self.assertRaises(SyncError):
            safe_slug("..")

    def test_safe_path_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            with self.assertRaises(SyncError):
                safe_path(vault, "Items", "../evil.md")
            with self.assertRaises(SyncError):
                safe_path(vault, "Items", "a/b.md")
            self.assertTrue(str(safe_path(vault, "Items", "ok.md")).startswith(str(vault)))

    def test_frontmatter_scalars(self):
        fm, _ = parse_frontmatter('---\ntitle: "hello"\nn: 3\nflag: true\nlist: ["a",1]\n---\nBody')
        self.assertEqual(fm["title"], "hello")
        self.assertEqual(fm["n"], 3)
        self.assertIs(fm["flag"], True)
        self.assertEqual(fm["list"], ["a", 1])

    def test_item_note_preserves_publication_metadata(self):
        item = make_item()
        item["publication"] = {
            "status": "published",
            "venue": "Systems Journal",
            "publication_url": "https://example.com/a",
        }
        note = render_item_note(item, None, None)
        fm, body = parse_frontmatter(note)
        self.assertEqual(fm["publication"]["venue"], "Systems Journal")
        self.assertIn("Publication: [Systems Journal](https://example.com/a)", body)

    def test_academic_digest_note_title_keeps_edition_date(self):
        note = render_digest_note({"run_id": "academic-1", "edition_date": "2026-09-16", "newsletter": "academic", "items": []}, None)
        self.assertIn("# AI Research Radar 2026-09-16", note)


class TestValidation(unittest.TestCase):
    def test_valid_snapshot(self):
        snap = make_snapshot()
        self.assertEqual(validate_snapshot(snap), snap)

    def test_malformed_snapshot(self):
        with self.assertRaises(SyncError):
            validate_snapshot({"schema_version": 2, "items": [], "digests": [], "ratings": {}})
        with self.assertRaises(SyncError):
            validate_snapshot(make_snapshot(items=[make_item(), make_item()]))
        bad = make_item(iid="bad-id")
        with self.assertRaises(SyncError):
            validate_snapshot(make_snapshot(items=[bad]))
        with self.assertRaises(SyncError):
            validate_snapshot(make_snapshot(ratings={"RAD-aaaaaaaaaaaa": {"score": True, "revision": 0}}))
        with self.assertRaises(SyncError):
            validate_snapshot(make_snapshot(ratings={"RAD-aaaaaaaaaaaa": {"score": 9, "revision": 0}}))

    def test_malformed_snapshot_file_leaves_vault_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            ex = Path(d) / "ex"
            vault = Path(d) / "vault"
            ensure_vault(vault)
            (ex / "snapshots").mkdir(parents=True)
            (ex / "snapshots" / "snapshot.json").write_text("{not json", encoding="utf-8")
            before = sorted(str(p) for p in vault.rglob("*.md"))
            with self.assertRaises(SyncError):
                run_sync(ex, vault)
            after = sorted(str(p) for p in vault.rglob("*.md"))
            self.assertEqual(before, after)


class TestExportImport(unittest.TestCase):
    def _setup(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        ex = Path(d) / "ex"
        vault = Path(d) / "vault"
        return ex, vault

    def test_retry_idempotent(self):
        ex, vault = self._setup()
        atomic_write_json(ex / "snapshots" / "snapshot.json", make_snapshot())
        r1 = run_sync(ex, vault)
        r2 = run_sync(ex, vault)
        self.assertGreater(r1["imported"], 0)
        self.assertEqual(r2["imported"], 0)  # nothing new on retry

    def test_visible_blank_rating_is_neutral_and_text_property_exports_once(self):
        ex, vault = self._setup()
        atomic_write_json(ex / "snapshots" / "snapshot.json", make_snapshot())
        run_sync(ex, vault)
        note = next((vault / "Items").glob("*.md"))
        fm, body = parse_frontmatter(note.read_text(encoding="utf-8"))
        self.assertIn("rating", fm)
        self.assertIsNone(fm["rating"])
        self.assertEqual(fm["rating_reason"], "")
        self.assertIn("## Rate this idea", body)
        run_sync(ex, vault)
        self.assertFalse(list((ex / "feedback").glob("*.json")))
        # Obsidian can save the newly exposed blank field as a text property.
        fm["rating"] = "4"
        fm["rating_reason"] = "Useful for my reports"
        note.write_text(render_frontmatter(fm) + "\n" + body, encoding="utf-8")
        run_sync(ex, vault)
        run_sync(ex, vault)
        events = [event for path in (ex / "feedback").glob("*.json")
                  for event in json.loads(path.read_text(encoding="utf-8"))["events"]]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["score"], 4)
        self.assertEqual(events[0]["base_revision"], 0)
        self.assertEqual(events[0]["reason"], "Useful for my reports")

    def test_snapshot_ordering_is_natural(self):
        ex, vault = self._setup()
        older = make_item(title="Older")
        newer = make_item(title="Newer")
        atomic_write_json(ex / "snapshots" / "snapshot-2.json",
                          make_snapshot([older], state_revision=2))
        atomic_write_json(ex / "snapshots" / "snapshot-10.json",
                          make_snapshot([newer], state_revision=10))
        run_sync(ex, vault)
        note = next((vault / "Items").glob("RAD-*"))
        self.assertIn("# Newer", note.read_text(encoding="utf-8"))

    def test_dashboard_links_follow_existing_notes_after_title_change(self):
        ex, vault = self._setup()
        original = make_item(title="A / " * 25 + "report")
        atomic_write_json(ex / "snapshots" / "snapshot.json", make_snapshot([original]))
        run_sync(ex, vault)
        note = next((vault / "Items").glob("RAD-*"))
        dashboard = vault / "Dashboard" / "Radar Dashboard.md"
        self.assertIn(f"[[Items/{note.stem}|", dashboard.read_text(encoding="utf-8"))
        note.write_text(note.read_text(encoding="utf-8") + "\nMy retained note\n", encoding="utf-8")
        renamed = make_item(title="A clearer report assistant explanation")
        atomic_write_json(ex / "snapshots" / "snapshot.json",
                          make_snapshot([renamed], state_revision=1))
        run_sync(ex, vault)
        self.assertEqual(list((vault / "Items").glob("*.md")), [note])
        self.assertIn("My retained note", note.read_text(encoding="utf-8"))
        self.assertIn(f"[[Items/{note.stem}|{renamed['title']}]]",
                      dashboard.read_text(encoding="utf-8"))

    def test_cloud_rating_update_does_not_export_as_local_edit(self):
        ex, vault = self._setup()
        atomic_write_json(
            ex / "snapshots" / "snapshot.json",
            make_snapshot(ratings={"RAD-aaaaaaaaaaaa": {"score": 2, "revision": 1}}),
        )
        run_sync(ex, vault)
        self.assertFalse(list((ex / "feedback").glob("*.json")))

        atomic_write_json(
            ex / "snapshots" / "snapshot-2.json",
            make_snapshot(ratings={"RAD-aaaaaaaaaaaa": {"score": 4, "revision": 2}},
                          state_revision=2),
        )
        run_sync(ex, vault)
        note = next((vault / "Items").glob("RAD-*"))
        fm, _ = parse_frontmatter(note.read_text(encoding="utf-8"))
        self.assertEqual(fm["rating"], 4)
        self.assertFalse(list((ex / "feedback").glob("*.json")))

    def test_item_title_cannot_escape_vault(self):
        ex, vault = self._setup()
        atomic_write_json(
            ex / "snapshots" / "snapshot.json",
            make_snapshot(items=[make_item(title="../../outside")]),
        )
        run_sync(ex, vault)
        items_dir = (vault / "Items").resolve()
        for note in (vault / "Items").glob("*.md"):
            self.assertTrue(note.resolve().parent == items_dir)
        self.assertFalse((vault.parent / "outside.md").exists())

    def test_offline_edit_preserved(self):
        ex, vault = self._setup()
        atomic_write_json(ex / "snapshots" / "snapshot.json", make_snapshot())
        run_sync(ex, vault)
        note = next((vault / "Items").glob("RAD-*"))
        text = note.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
        fm2 = dict(fm)
        fm2["rating"] = 5
        fm2["rating_reason"] = "great"
        lines = ["---"] + [f'{k}: {json.dumps(v)}' for k, v in fm2.items()] + ["---"]
        body = text.split("---\n", 2)[2]
        note.write_text("\n".join(lines) + "\n" + body, encoding="utf-8")
        # new snapshot with different rating must not overwrite local edit
        atomic_write_json(ex / "snapshots" / "snapshot2.json",
                          make_snapshot(ratings={"RAD-aaaaaaaaaaaa": {"score": 2, "revision": 1}},
                                        state_revision=1))
        run_sync(ex, vault)
        nfm, _ = parse_frontmatter(note.read_text(encoding="utf-8"))
        self.assertEqual(nfm["rating"], 5)
        # exported event exists
        feedback = list((ex / "feedback").glob("*.json"))
        self.assertTrue(feedback)
        data = json.loads(feedback[-1].read_text(encoding="utf-8"))
        self.assertEqual(data["events"][0]["score"], 5)
        self.assertEqual(data["events"][0]["origin"], "obsidian")

    def test_rating_export_before_import(self):
        ex, vault = self._setup()
        ensure_vault(vault)
        # pre-existing vault note with unsynced rating and user notes
        item = make_item()
        note = render_item_note(item, None, None)
        note = note.replace("rating\"", "rating\"")  # noop keep
        note = note.replace("---\n\n#", "---\n\n#")
        # add rating to note directly
        note = note.replace('---\n', '---\n', 1)
        text = note.replace('"topics": [\n      "t"\n    ]\n  }', '')
        # simpler: build note with rating
        fm = {"item_id": item["item_id"], "title": item["title"], "rating": 4}
        lines = ["---"] + [f'{k}: {json.dumps(v)}' for k, v in fm.items()] + ["---", "", "# T", "",
                 "## User notes", "", "my local note"]
        target = vault / "Items" / f"{item['item_id']} Test-Item.md"
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        atomic_write_json(ex / "snapshots" / "snapshot.json",
                          make_snapshot(ratings={item["item_id"]: {"score": 1, "revision": 1}}))
        run_sync(ex, vault)
        nfm, body = parse_frontmatter(target.read_text(encoding="utf-8"))
        self.assertEqual(nfm["rating"], 4)
        self.assertIn("my local note", body)
        fb = list((ex / "feedback").glob("*.json"))
        self.assertTrue(fb, "rating event must be exported before import")

    def test_user_notes_preserved_on_import(self):
        ex, vault = self._setup()
        ensure_vault(vault)
        item = make_item()
        fm = {"item_id": item["item_id"], "title": item["title"], "rating": 3}
        lines = ["---"] + [f'{k}: {json.dumps(v)}' for k, v in fm.items()] + ["---", "", "# T", "",
                 "## User notes", "", "keep me"]
        target = vault / "Items" / f"{item['item_id']} Test-Item.md"
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        atomic_write_json(ex / "snapshots" / "snapshot.json", make_snapshot())
        run_sync(ex, vault)
        _, body = parse_frontmatter(target.read_text(encoding="utf-8"))
        self.assertIn("keep me", body)

    def _set_rating(self, note, score, reason=""):
        text = note.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        fm["rating"] = score
        fm["rating_reason"] = reason
        note.write_text(render_frontmatter(fm) + "\n" + body, encoding="utf-8")

    def test_local_rating_ack_then_next_edit_uses_cloud_revision(self):
        ex, vault = self._setup()
        atomic_write_json(ex / "snapshots" / "snapshot-0.json", make_snapshot())
        run_sync(ex, vault)
        note = next((vault / "Items").glob("RAD-*.md"))
        self._set_rating(note, 4, "good match")
        run_sync(ex, vault)

        atomic_write_json(
            ex / "snapshots" / "snapshot-1.json",
            make_snapshot(ratings={"RAD-aaaaaaaaaaaa": {
                "score": 4, "reason": "good match", "revision": 1}}, state_revision=1),
        )
        run_sync(ex, vault)
        state = json.loads((vault / ".radar-sync-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_exported"]["RAD-aaaaaaaaaaaa"]["revision"], 1)
        self.assertFalse(state["last_exported"]["RAD-aaaaaaaaaaaa"]["pending"])

        self._set_rating(note, 5, "try it")
        run_sync(ex, vault)
        feedback = sorted((ex / "feedback").glob("*.json"))
        events = [event for path in feedback for event in
                  json.loads(path.read_text(encoding="utf-8"))["events"]]
        next_event = next(event for event in events if event["score"] == 5)
        self.assertEqual(next_event["base_revision"], 1)

    def test_reason_only_correction_acknowledges_revision(self):
        ex, vault = self._setup()
        atomic_write_json(ex / "snapshots" / "snapshot-0.json", make_snapshot())
        run_sync(ex, vault)
        note = next((vault / "Items").glob("RAD-*.md"))
        self._set_rating(note, 4, "first reason")
        run_sync(ex, vault)
        atomic_write_json(
            ex / "snapshots" / "snapshot-1.json",
            make_snapshot(ratings={"RAD-aaaaaaaaaaaa": {
                "score": 4, "reason": "first reason", "revision": 1}}, state_revision=1),
        )
        run_sync(ex, vault)
        state = json.loads((vault / ".radar-sync-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_exported"]["RAD-aaaaaaaaaaaa"]["revision"], 1)
        self._set_rating(note, 4, "corrected reason")
        run_sync(ex, vault)
        feedback = sorted((ex / "feedback").glob("*.json"))
        events = [event for path in feedback for event in
                  json.loads(path.read_text(encoding="utf-8"))["events"]]
        correction = next(event for event in events if event["reason"] == "corrected reason")
        self.assertEqual(correction["base_revision"], 1)

        atomic_write_json(
            ex / "snapshots" / "snapshot-2.json",
            make_snapshot(ratings={"RAD-aaaaaaaaaaaa": {
                "score": 4, "reason": "corrected reason", "revision": 2}}, state_revision=2),
        )
        run_sync(ex, vault)
        state = json.loads((vault / ".radar-sync-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_exported"]["RAD-aaaaaaaaaaaa"]["revision"], 2)

    def test_concurrent_cloud_change_keeps_stale_local_base(self):
        ex, vault = self._setup()
        atomic_write_json(ex / "snapshots" / "snapshot-0.json", make_snapshot())
        run_sync(ex, vault)
        note = next((vault / "Items").glob("RAD-*.md"))
        self._set_rating(note, 4, "local")
        run_sync(ex, vault)
        atomic_write_json(
            ex / "snapshots" / "snapshot-1.json",
            make_snapshot(ratings={"RAD-aaaaaaaaaaaa": {"score": 2, "revision": 1}},
                          state_revision=1),
        )
        run_sync(ex, vault)
        fm, _ = parse_frontmatter(note.read_text(encoding="utf-8"))
        self.assertEqual(fm["rating"], 4)
        atomic_write_json(
            ex / "snapshots" / "snapshot-2.json",
            make_snapshot(ratings={"RAD-aaaaaaaaaaaa": {"score": 4, "revision": 2}},
                          state_revision=2),
        )
        run_sync(ex, vault)
        fm, _ = parse_frontmatter(note.read_text(encoding="utf-8"))
        self.assertEqual(fm["rating"], 4)
        self.assertEqual(fm["rating_revision"], 0)
        self._set_rating(note, 5, "new local edit")
        run_sync(ex, vault)
        feedback = sorted((ex / "feedback").glob("*.json"))
        events = [event for path in feedback for event in
                  json.loads(path.read_text(encoding="utf-8"))["events"]]
        next_event = next(event for event in events if event["score"] == 5)
        self.assertEqual(next_event["base_revision"], 0)

    def test_older_snapshot_is_idempotently_ignored(self):
        ex, vault = self._setup()
        atomic_write_json(ex / "snapshots" / "snapshot-new.json",
                          make_snapshot(state_revision=2, updated_at="2025-01-03T00:00:00Z"))
        run_sync(ex, vault)
        atomic_write_json(ex / "snapshots" / "snapshot-old.json",
                          make_snapshot([make_item(title="Old")], state_revision=1,
                                        updated_at="2025-01-04T00:00:00Z"))
        run_sync(ex, vault)
        note = next((vault / "Items").glob("RAD-*.md"))
        self.assertIn("# Test Item", note.read_text(encoding="utf-8"))

    def test_digest_bundle_and_dashboard_preserve_notes(self):
        ex, vault = self._setup()
        digest = {"run_id": "run-1", "edition_date": "2025-01-01",
                  "producer": "fable", "model_id": "model-x", "kind": "digest",
                  "items": [make_item()]}
        atomic_write_json(ex / "snapshots" / "snapshot.json",
                          make_snapshot(digests=[digest], state_revision=1))
        run_sync(ex, vault)
        digest_path = vault / "Digests" / "run-1.md"
        self.assertIn('run_id: "run-1"', digest_path.read_text(encoding="utf-8"))
        digest_path.write_text(digest_path.read_text(encoding="utf-8") +
                               "\n## User notes\n\nkeep digest note\n", encoding="utf-8")
        digest["summary"] = "full bundle field"
        atomic_write_json(ex / "snapshots" / "snapshot-2.json",
                          make_snapshot(digests=[digest], state_revision=2))
        run_sync(ex, vault)
        self.assertIn("keep digest note", digest_path.read_text(encoding="utf-8"))
        dashboard = (vault / "Dashboard" / "Radar Dashboard.md").read_text(encoding="utf-8")
        self.assertIn("[[Items/RAD-aaaaaaaaaaaa", dashboard)
        self.assertIn("[[Digests/run-1|run-1]]", dashboard)

    def test_event_id_survives_feedback_write_failure(self):
        ex, vault = self._setup()
        atomic_write_json(ex / "snapshots" / "snapshot.json", make_snapshot())
        run_sync(ex, vault)
        note = next((vault / "Items").glob("RAD-*.md"))
        self._set_rating(note, 4, "retry")
        original = atomic_write_json
        failed = [False]

        def fail_feedback_once(path, data):
            if path.parent.name == "feedback" and not failed[0]:
                failed[0] = True
                raise OSError("simulated feedback failure")
            return original(path, data)

        with patch("radar.sync.atomic_write_json", side_effect=fail_feedback_once):
            with self.assertRaises(OSError):
                run_sync(ex, vault)
        persisted = json.loads((vault / ".radar-sync-state.json").read_text(encoding="utf-8"))
        event_ids = set(persisted["pending_event_ids"].values())
        run_sync(ex, vault)
        events = [event for path in (ex / "feedback").glob("*.json") for event in
                  json.loads(path.read_text(encoding="utf-8"))["events"]]
        self.assertEqual(len(events), 1)
        self.assertIn(events[0]["event_id"], event_ids)


class TestCli(unittest.TestCase):
    def test_cli_run(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        ex = Path(d) / "ex"
        vault = Path(d) / "vault"
        atomic_write_json(ex / "snapshots" / "snapshot.json", make_snapshot())
        repo = Path(__file__).resolve().parent.parent
        proc = subprocess.run([sys.executable, "-m", "radar.sync", "--exchange", str(ex),
                               "--vault", str(vault)], cwd=str(repo), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((vault / "Dashboard" / "Radar Dashboard.md").exists())
        for sub in VAULT_DIRS:
            self.assertTrue((vault / sub).exists())


if __name__ == "__main__":
    unittest.main()
