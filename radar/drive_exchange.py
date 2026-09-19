"""Narrow Drive file exchange. OAuth secrets are supplied only to this process."""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4


class DriveExchange:
    def __init__(self, credentials, folders):
        self.credentials = credentials
        self.folders = folders
        self.token = None
        self.expires = 0

    @classmethod
    def from_env(cls):
        return cls(json.loads(os.environ['GOOGLE_DRIVE_OAUTH']), json.loads(os.environ['RADAR_FOLDERS']))

    def _authorize(self):
        if self.token and time.time() < self.expires:
            return
        body = {key: self.credentials[key] for key in ('client_id', 'client_secret', 'refresh_token')}
        body['grant_type'] = 'refresh_token'
        request = Request('https://oauth2.googleapis.com/token', data=urlencode(body).encode())
        try:
            with urlopen(request, timeout=30) as response:
                result = json.load(response)
        except (HTTPError, URLError) as error:
            raise RuntimeError('Google OAuth refresh failed; verify GOOGLE_DRIVE_OAUTH') from None
        self.token = result['access_token']
        self.expires = time.time() + int(result.get('expires_in', 3600)) - 60

    def request(self, path, *, data=None, content_type=None, upload=False):
        self._authorize()
        base = 'https://www.googleapis.com/' + ('upload/' if upload else '') + 'drive/v3/'
        headers = {'Authorization': 'Bearer ' + self.token}
        if content_type:
            headers['Content-Type'] = content_type
        # Writes are not blindly retried: a timeout may have committed the file.
        for attempt in range(3 if data is None else 1):
            try:
                with urlopen(Request(base + path, data=data, headers=headers), timeout=60) as response:
                    return response.read()
            except HTTPError as error:
                if data is None and error.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f'Drive request failed (HTTP {error.code})') from None
            except URLError:
                if data is None and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError('Drive request failed (network error)') from None

    def list_files(self, folder=None, *, query=None):
        files, page = [], None
        while True:
            params = {'q': query or f"'{folder}' in parents and trashed = false", 'fields': 'files(id,name),nextPageToken', 'pageSize': 100}
            if page:
                params['pageToken'] = page
            result = json.loads(self.request('files?' + urlencode(params)))
            files.extend(result.get('files', []))
            page = result.get('nextPageToken')
            if not page:
                return files

    def read(self, file_id):
        return self.request('files/' + file_id + '?alt=media')

    def state(self):
        state = json.loads(self.read(self.folders['state']))
        checked = datetime.fromisoformat(state['checked_at'].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        if checked.tzinfo is None or not timedelta(minutes=-5) <= now - checked <= timedelta(minutes=20):
            raise RuntimeError('Google state mirror is stale; check the delivery dispatcher')
        records = {entry['name']: entry['raw'].encode('utf-8') for entry in state['files']}
        day = now.astimezone(timezone(timedelta(hours=5, minutes=30))).date().isoformat()
        # Include our app-owned originals even after the gateway trashes them.
        # This closes the gap before its next mirror export and survives retries.
        for entry in self.list_files(query=f"appProperties has {{ key='radar_edition' and value='{day}' }}"):
            records[entry['name']] = self.read(entry['id'])
        return state['snapshot'], state['preferences'], list(records.items())

    def upload(self, name, raw):
        # Recover a response-lost upload by checking immutable contents.
        escaped = name.replace('\\', '\\\\').replace("'", "\\'")
        query = f"name = '{escaped}' and appProperties has {{ key='radar_exchange' and value='v1' }}"
        for entry in self.list_files(query=query):
            if self.read(entry['id']) != raw:
                raise ValueError('Immutable Drive file conflicts: ' + name)
            return entry['id']
        boundary = 'radar_' + uuid4().hex
        value = json.loads(raw)
        day = value.get('edition_date') or datetime.now(timezone(timedelta(hours=5, minutes=30))).date().isoformat()
        metadata = json.dumps({'name': name, 'parents': [self.folders['inbox']], 'mimeType': 'application/json',
                               'appProperties': {'radar_edition': day, 'radar_exchange': 'v1'}}).encode()
        body = (f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'.encode() + metadata
                + f'\r\n--{boundary}\r\nContent-Type: application/json\r\n\r\n'.encode() + raw
                + f'\r\n--{boundary}--\r\n'.encode())
        result = json.loads(self.request('files?uploadType=multipart&fields=id', data=body,
                                         content_type='multipart/related; boundary=' + boundary, upload=True))
        if self.read(result['id']) != raw:
            raise RuntimeError('Drive upload readback differs from approved bytes')
        return result['id']
