import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from radar.drive_exchange import DriveExchange


class ExchangeTests(unittest.TestCase):
    def setUp(self):
        self.drive = DriveExchange({}, {'inbox': 'inbox', 'accepted': 'accepted', 'snapshots': 'snapshots'})

    def test_listing_reads_all_pages(self):
        responses = [b'{"files":[{"id":"one"}],"nextPageToken":"next"}', b'{"files":[{"id":"two"}]}']
        with patch.object(self.drive, 'request', side_effect=responses):
            self.assertEqual(self.drive.list_files('inbox'), [{'id': 'one'}, {'id': 'two'}])

    def test_response_lost_upload_is_reused_without_overwriting(self):
        with patch.object(self.drive, 'list_files', return_value=[{'name': 'edition.json', 'id': 'existing'}]), \
             patch.object(self.drive, 'read', return_value=b'exact bytes'), \
             patch.object(self.drive, 'request', side_effect=AssertionError('must not upload again')):
            self.assertEqual(self.drive.upload('edition.json', b'exact bytes'), 'existing')

    def test_conflicting_file_cannot_be_overwritten(self):
        with patch.object(self.drive, 'list_files', return_value=[{'name': 'edition.json', 'id': 'existing'}]), \
             patch.object(self.drive, 'read', return_value=b'changed'):
            with self.assertRaisesRegex(ValueError, 'conflicts'):
                self.drive.upload('edition.json', b'{"edition_date":"2026-09-19"}')

    def test_upload_readback_must_match_original_bytes(self):
        with patch.object(self.drive, 'list_files', return_value=[]), \
             patch.object(self.drive, 'request', return_value=b'{"id":"created"}'), \
             patch.object(self.drive, 'read', return_value=b'changed'):
            with self.assertRaisesRegex(RuntimeError, 'readback differs'):
                self.drive.upload('edition.json', b'{"edition_date":"2026-09-19"}')

    def test_state_uses_app_owned_mirror_and_preserves_new_upload_bytes(self):
        self.drive.folders['state'] = 'mirror'
        state = {'checked_at': datetime.now(timezone.utc).isoformat(),
                 'snapshot': {'items': []}, 'preferences': {'ratings': {}},
                 'files': [{'name': 'approved.json', 'raw': '{ "original": true }'}]}
        bodies = {'mirror': json.dumps(state).encode(), 'new': b'{ "new": true }'}
        with patch.object(self.drive, 'read', side_effect=lambda fid: bodies[fid]), \
             patch.object(self.drive, 'list_files', return_value=[{'id': 'new', 'name': 'new.json'}]):
            snapshot, prefs, files = self.drive.state()
        self.assertEqual(snapshot, {'items': []})
        self.assertEqual(prefs, {'ratings': {}})
        self.assertEqual(dict(files), {'approved.json': b'{ "original": true }', 'new.json': b'{ "new": true }'})

    def test_stale_state_stops_research_instead_of_using_old_exclusions(self):
        self.drive.folders['state'] = 'mirror'
        with patch.object(self.drive, 'read', return_value=b'{"checked_at":"2020-01-01T00:00:00Z"}'):
            with self.assertRaisesRegex(RuntimeError, 'mirror is stale'):
                self.drive.state()

    def test_gateway_disposed_original_cannot_resurrect_rejected_candidate(self):
        self.drive.folders['state'] = 'mirror'
        state = {'checked_at': datetime.now(timezone.utc).isoformat(),
                 'snapshot': {'items': []}, 'preferences': {}, 'files': []}
        bodies = {'mirror': json.dumps(state).encode(), 'rejected': b'{"kind":"digest"}'}
        with patch.object(self.drive, 'read', side_effect=lambda fid: bodies[fid]), \
             patch.object(self.drive, 'list_files', return_value=[{'id': 'rejected', 'name': 'rejected.json', 'trashed': True}]):
            _, _, files = self.drive.state()
        self.assertEqual(files, [])
