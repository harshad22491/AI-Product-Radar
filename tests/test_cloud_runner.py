import copy
import hashlib
import json
import unittest
from datetime import datetime, timezone

import os
import tempfile
from pathlib import Path
from unittest import mock

from radar import cloud_runner, github_inventory
from radar.cloud_runner import approved, run_channel, parse_model_json
from test_domain import make_bundle


class MemoryDrive:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot or {'items': [], 'digests': []}
        self.files = []

    def state(self):
        return self.snapshot, {}, list(self.files)

    def upload(self, name, raw):
        self.files.append((name, raw))
        return name


class CloudRunnerTests(unittest.TestCase):
    now = datetime(2026, 9, 1, 6, tzinfo=timezone.utc)

    def model(self, role, prompt):
        if role == 'research':
            return {'items': copy.deepcopy(make_bundle()['items'])}, 'claude-opus-5-5'
        return {'verdict': 'approved', 'reasons': []}, 'gpt-6-astra'

    def test_model_json_tolerates_preamble_and_markdown_without_changing_payload(self):
        self.assertEqual(parse_model_json('Here is the verified result:\n```json\n{"items": []}\n```'), {'items': []})
        self.assertEqual(parse_model_json('{"verdict":"approved","reasons":[]}\nReview complete.'),
                         {'verdict': 'approved', 'reasons': []})

    def test_ambiguous_multiple_model_objects_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_model_json('{"verdict":"rejected"}\n{"verdict":"approved"}')

    def test_research_receives_previous_review_failure_for_correction(self):
        def corrected(role, prompt):
            if role == 'research':
                self.assertIn('Unsupported cell-editing claim', prompt)
            return self.model(role, prompt)
        result = run_channel('product', MemoryDrive(), corrected, now=self.now,
                             correction='Unsupported cell-editing claim')
        self.assertEqual(result['status'], 'approved')

    def test_approved_bytes_are_uploaded_once_and_backup_skips_them(self):
        drive = MemoryDrive()
        result = run_channel('product', drive, self.model, now=self.now)
        self.assertEqual(result['status'], 'approved')
        candidate = drive.files[0][1]
        attestation = json.loads(drive.files[1][1])
        self.assertEqual(attestation['candidate_sha256'], hashlib.sha256(candidate).hexdigest())
        self.assertEqual(run_channel('product', drive, lambda *_: self.fail('duplicate research'), now=self.now)['status'], 'ready')
        self.assertEqual(len(drive.files), 2)

    def test_rejected_research_never_reaches_delivery_inbox(self):
        drive = MemoryDrive()
        def rejected(role, prompt):
            if role == 'review':
                return {'verdict': 'rejected', 'reasons': ['Unverified date']}, 'gpt-6-astra'
            return self.model(role, prompt)
        with self.assertRaisesRegex(RuntimeError, 'Unverified date'):
            run_channel('product', drive, rejected, now=self.now)
        self.assertEqual(drive.files, [])

    def test_delivered_channel_does_not_spend_model_calls(self):
        bundle = make_bundle()
        drive = MemoryDrive({'items': [dict(i, first_delivered_edition_date='2026-09-01', run_id=bundle['run_id']) for i in bundle['items']], 'digests': [bundle]})
        self.assertEqual(run_channel('product', drive, lambda *_: self.fail('already sent'), now=self.now)['status'], 'sent')

    def test_changed_or_unapproved_candidate_does_not_skip_research(self):
        drive = MemoryDrive()
        run_channel('product', drive, self.model, now=self.now)
        drive.files[0] = (drive.files[0][0], drive.files[0][1] + b' ')
        result = run_channel('product', drive, self.model, now=self.now)
        self.assertEqual(result['status'], 'approved')

    def test_existing_delivered_item_is_rejected(self):
        item = make_bundle()['items'][0]
        drive = MemoryDrive({'items': [dict(item, first_delivered_edition_date='2026-08-31')], 'digests': []})
        with self.assertRaisesRegex(ValueError, 'already delivered'):
            run_channel('product', drive, self.model, now=self.now)
        self.assertEqual(drive.files, [])

    def test_accepted_repeat_from_prior_day_is_not_reported_as_sent_today(self):
        bundle = make_bundle()
        drive = MemoryDrive({'items': [dict(i, first_delivered_edition_date='2026-08-31') for i in bundle['items']],
                             'digests': [bundle]})
        with self.assertRaisesRegex(ValueError, 'already delivered'):
            run_channel('product', drive, self.model, now=self.now)

    def test_wrong_reviewer_model_cannot_create_approval(self):
        def wrong_model(role, prompt):
            value, model = self.model(role, prompt)
            return value, 'claude-opus-5-5'
        with self.assertRaisesRegex(ValueError, 'reviewer model'):
            run_channel('product', MemoryDrive(), wrong_model, now=self.now)

    def test_gateway_rejected_shape_is_caught_before_upload(self):
        drive = MemoryDrive()
        def too_long(role, prompt):
            value, model = self.model(role, prompt)
            if role == 'research':
                value['items'][0]['title'] = 'x' * 301
            return value, model
        with self.assertRaisesRegex(ValueError, 'gateway'):
            run_channel('product', drive, too_long, now=self.now)
        self.assertEqual(drive.files, [])

    def test_product_approval_does_not_skip_academic_research(self):
        drive = MemoryDrive()
        run_channel('product', drive, self.model, now=self.now)
        def academic(role, prompt):
            result, model = self.model(role, prompt)
            if role == 'research':
                for index, item in enumerate(result['items']):
                    item['source_url'] = f'https://proceedings.example/paper-{index}'
                    item['source_type'] = 'academic'
                    item['publication'] = {'status': 'published', 'venue': 'Example conference',
                                           'publication_url': item['source_url']}
            return result, model
        self.assertEqual(run_channel('academic', drive, academic, now=self.now)['status'], 'approved')
        self.assertEqual(json.loads(drive.files[2][1])['newsletter'], 'academic')
        self.assertEqual(len(drive.files), 4)

    def test_attestation_names_astra_and_bundle_names_opus(self):
        drive = MemoryDrive()
        run_channel('product', drive, self.model, now=self.now)
        bundle, attestation = json.loads(drive.files[0][1]), json.loads(drive.files[1][1])
        self.assertEqual((bundle['producer'], bundle['model_id']), ('opus', 'claude-opus-5-5'))
        self.assertTrue(bundle['run_id'].startswith('product-opus-'))
        self.assertEqual((attestation['validator'], attestation['model_id']), ('astra', 'gpt-6-astra'))

    def test_self_approval_by_same_validator_family_is_ignored(self):
        bundle = dict(make_bundle(), producer='opus')
        raw = json.dumps(bundle).encode()
        attestation = {'kind': 'validation', 'candidate_run_id': bundle['run_id'],
                       'candidate_sha256': hashlib.sha256(raw).hexdigest(), 'verdict': 'approved',
                       'validator': 'opus', 'model_id': 'claude-opus-5'}
        self.assertFalse(approved(bundle, raw, [attestation]))
        self.assertTrue(approved(bundle, raw, [dict(attestation, validator='astra', model_id='gpt-6-astra')]))
        self.assertFalse(approved(bundle, raw, [dict(attestation, validator='astra', model_id='gpt-5.5')]))

    def test_more_than_one_low_priority_repository_is_rejected_before_review(self):
        drive = MemoryDrive()
        def heavy(role, prompt):
            value, model = self.model(role, prompt)
            if role == 'review':
                self.fail('review should not run')
            value['items'][0]['repository'] = 'GHADC'
            value['items'][1]['repository'] = 'harshad22491/forty-degrees'
            return value, model
        with self.assertRaisesRegex(ValueError, 'GHADC or forty-degrees'):
            run_channel('product', drive, heavy, now=self.now)
        self.assertEqual(drive.files, [])

    def test_one_low_priority_item_is_allowed(self):
        def one(role, prompt):
            value, model = self.model(role, prompt)
            if role == 'research':
                value['items'][0]['repository'] = 'forty-degrees'
            return value, model
        self.assertEqual(run_channel('product', MemoryDrive(), one, now=self.now)['status'], 'approved')

    def test_fresh_repository_inventory_reaches_research_and_review(self):
        repos = [{'name': 'bank-statement-consolidation', 'recent_commits': [{'subject': 'add parser'}]}]
        seen = {}
        def capture(role, prompt):
            seen[role] = prompt
            return self.model(role, prompt)
        run_channel('product', MemoryDrive(), capture, now=self.now, repositories=repos)
        self.assertIn('bank-statement-consolidation', seen['research'])
        self.assertIn('bank-statement-consolidation', seen['review'])


class AstraCallTests(unittest.TestCase):
    def test_missing_login_is_an_auth_failure(self):
        with mock.patch.dict(os.environ, {'CODEX_HOME': ''}):
            with self.assertRaises(cloud_runner.AstraAuthError):
                cloud_runner.call_codex('prompt')

    def test_auth_markers_are_recognised(self):
        self.assertTrue(cloud_runner.is_auth_failure('Your refresh token was already used. Please log in again.'))
        self.assertTrue(cloud_runner.is_auth_failure('unexpected status 401 Unauthorized'))
        self.assertFalse(cloud_runner.is_auth_failure('stream disconnected before completion'))

    def test_model_evidence_comes_from_session_log(self):
        with tempfile.TemporaryDirectory() as home:
            day = Path(home, 'sessions', '2026', '10', '01')
            day.mkdir(parents=True)
            day.joinpath('rollout-x-thread123.jsonl').write_text(
                json.dumps({'type': 'turn_context', 'payload': {'model': 'gpt-6-astra'}}) + '\n', encoding='utf-8')
            self.assertEqual(cloud_runner.session_models(home, 'thread123'), {'gpt-6-astra'})
            self.assertEqual(cloud_runner.session_models(home, 'other'), set())

    def test_model_subprocess_env_drops_every_credential(self):
        secrets = {'RADAR_GITHUB_TOKEN': 'x', 'GOOGLE_DRIVE_OAUTH': 'x', 'CLAUDE_CODE_OAUTH_TOKEN': 'x',
                   'CODEX_HOME': '/h', 'GH_TOKEN': 'x', 'OPENAI_API_KEY': 'x'}
        with mock.patch.dict(os.environ, secrets):
            env = cloud_runner.scrubbed_env(CODEX_HOME='/h')
        self.assertEqual(env['CODEX_HOME'], '/h')
        for key in secrets.keys() - {'CODEX_HOME'}:
            self.assertNotIn(key, env)


class GitHubInventoryTests(unittest.TestCase):
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)

    def test_collects_metadata_and_recent_commit_subjects_only(self):
        repos = [
            {'name': 'old', 'full_name': 'me/old', 'pushed_at': '2026-05-01T00:00:00Z', 'private': True},
            {'name': 'gone', 'full_name': 'me/gone', 'pushed_at': '2026-09-30T00:00:00Z', 'archived': True},
            {'name': 'new', 'full_name': 'me/new', 'pushed_at': '2026-09-29T00:00:00Z', 'description': 'd',
             'language': 'Python', 'topics': ['ai']},
        ]
        calls = []
        def get(token, path):
            calls.append(path)
            if path.startswith('user/repos'):
                return repos
            return [{'commit': {'message': 'feat: add parser\n\nCo-Authored-By: x',
                                'committer': {'date': '2026-09-29T10:00:00Z'}}}]
        result = github_inventory.collect('t', now=self.now, get=get)
        self.assertEqual([r['name'] for r in result], ['new', 'old'])
        self.assertEqual(result[0]['recent_commits'], [{'date': '2026-09-29', 'subject': 'feat: add parser'}])
        self.assertEqual(result[1]['recent_commits'], [])
        self.assertEqual(sum('commits' in c for c in calls), 1)
