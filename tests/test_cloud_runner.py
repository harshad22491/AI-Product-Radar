import copy
import hashlib
import json
import unittest
from datetime import datetime, timezone

from radar.cloud_runner import run_channel, parse_model_json
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
            return {'items': copy.deepcopy(make_bundle()['items'])}, 'claude-fable-5-1'
        return {'verdict': 'approved', 'reasons': []}, 'claude-opus-5'

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
                return {'verdict': 'rejected', 'reasons': ['Unverified date']}, 'claude-opus-5'
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
            return value, 'claude-fable-5-1'
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
