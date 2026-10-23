import copy
import hashlib
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from radar.cloud_runner import call_model, run_channel, parse_model_json
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


    def test_both_channels_receive_sources_and_current_coverage(self):
        for channel in ('product', 'academic'):
            with self.subTest(channel=channel):
                def inspect(role, prompt):
                    for url in ('https://huggingface.co/papers', 'https://huggingface.co/',
                                'https://www.kdnuggets.com/', 'https://www.freecodecamp.org/news/'):
                        self.assertIn(url, prompt)
                    self.assertIn('bank-statement-consolidation', prompt)
                    self.assertIn('tally-voucher-agent', prompt)
                    value, model = self.model(role, prompt)
                    if role == 'research' and channel == 'academic':
                        for item in value['items']:
                            item['source_type'] = 'academic'
                            item['publication'] = {'status': 'published', 'venue': 'Example conference',
                                                   'publication_url': item['source_url']}
                    return value, model
                self.assertEqual(run_channel(channel, MemoryDrive(), inspect, now=self.now)['status'], 'approved')

    def test_excluded_portal_cannot_reach_either_delivery_inbox(self):
        for channel in ('product', 'academic'):
            for repository in ('GHADC', 'ghadc-trade-licensing-portal',
                               'harshad22491/ghadc-trade-licensing-portal'):
                with self.subTest(channel=channel, repository=repository):
                    drive = MemoryDrive()
                    def excluded(role, prompt):
                        self.assertEqual(role, 'research', 'Excluded work must fail before review')
                        value, model = self.model(role, prompt)
                        value['items'][0]['repository'] = repository
                        return value, model
                    with self.assertRaisesRegex(ValueError, 'excluded repository'):
                        run_channel(channel, drive, excluded, now=self.now)
                    self.assertEqual(drive.files, [])

    def test_cached_excluded_candidate_is_not_reused(self):
        drive = MemoryDrive()
        run_channel('product', drive, self.model, now=self.now)
        candidate = json.loads(drive.files[0][1])
        candidate['items'][0]['repository'] = 'GHADC'
        raw = json.dumps(candidate).encode()
        approval = json.loads(drive.files[1][1])
        approval['candidate_sha256'] = hashlib.sha256(raw).hexdigest()
        drive.files = [(drive.files[0][0], raw), (drive.files[1][0], json.dumps(approval).encode())]
        self.assertEqual(run_channel('product', drive, self.model, now=self.now)['status'], 'approved')

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

    def test_long_evidence_label_is_trimmed_instead_of_failing_the_attempt(self):
        drive = MemoryDrive()
        def verbose(role, prompt):
            value, model = self.model(role, prompt)
            if role == 'research':
                value['items'][3]['evidence_label'] = 'Release notes and changelog entry ' * 20
            return value, model
        self.assertEqual(run_channel('product', drive, verbose, now=self.now)['status'], 'approved')
        label = json.loads(drive.files[0][1])['items'][3]['evidence_label']
        self.assertLessEqual(len(label), 300)
        self.assertTrue(label.startswith('Release notes and changelog entry'))

    def test_failed_cli_reports_provider_message(self):
        envelope = json.dumps({'type': 'result', 'is_error': True, 'result': 'Usage limit reached'})
        failed = SimpleNamespace(returncode=1, stdout=envelope, stderr='')
        with mock.patch('radar.cloud_runner.subprocess.run', return_value=failed):
            with self.assertRaisesRegex(RuntimeError, r'research CLI failed \(exit 1\): Usage limit reached'):
                call_model('research', 'prompt')

    def test_research_falls_back_to_opus_when_fable_is_out_of_credits(self):
        out = SimpleNamespace(returncode=1, stderr='', stdout=json.dumps(
            {'is_error': True, 'result': "You're out of usage credits. Switch to another model to continue."}))
        ok = SimpleNamespace(returncode=0, stderr='', stdout=json.dumps(
            {'modelUsage': {'claude-opus-5-5': {}}, 'structured_output': {'items': []}}))
        with mock.patch('radar.cloud_runner.subprocess.run', side_effect=[out, ok]) as run:
            self.assertEqual(call_model('research', 'prompt'), ({'items': []}, 'claude-opus-5-5'))
        self.assertIn('claude-opus-5-5', run.call_args_list[1].args[0])
        drive = MemoryDrive()
        def fallback(role, prompt):
            value, model = self.model(role, prompt)
            return value, 'claude-opus-5-5' if role == 'research' else model
        self.assertEqual(run_channel('product', drive, fallback, now=self.now)['status'], 'approved')
        self.assertEqual(json.loads(drive.files[0][1])['model_id'], 'claude-opus-5-5')

    def test_reviewer_out_of_credits_does_not_fall_back(self):
        out = SimpleNamespace(returncode=1, stderr='', stdout=json.dumps(
            {'is_error': True, 'result': "You're out of usage credits."}))
        with mock.patch('radar.cloud_runner.subprocess.run', return_value=out) as run:
            with self.assertRaisesRegex(RuntimeError, 'out of usage credits'):
                call_model('review', 'prompt')
        self.assertEqual(run.call_count, 1)
