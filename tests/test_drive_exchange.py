import json
import unittest
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
                self.drive.upload('edition.json', b'original')

    def test_upload_readback_must_match_original_bytes(self):
        with patch.object(self.drive, 'list_files', return_value=[]), \
             patch.object(self.drive, 'request', return_value=b'{"id":"created"}'), \
             patch.object(self.drive, 'read', return_value=b'changed'):
            with self.assertRaisesRegex(RuntimeError, 'readback differs'):
                self.drive.upload('edition.json', b'original')
