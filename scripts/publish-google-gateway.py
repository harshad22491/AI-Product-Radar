"""Publish Code.js only, preserving all other live Apps Script files and access."""
import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen


def request(url, *, data=None, method=None, token=None):
    headers = {}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if data is not None:
        headers['Content-Type'] = 'application/json' if token else 'application/x-www-form-urlencoded'
    try:
        with urlopen(Request(url, data=data, method=method, headers=headers), timeout=60) as response:
            return json.load(response)
    except HTTPError as error:
        raise SystemExit(f'Google deployment request failed: HTTP {error.code}') from None


def digest(source):
    return hashlib.sha256(source.replace('\r\n', '\n').strip().encode('utf-8')).hexdigest()


def main():
    credentials = json.loads(os.environ['GOOGLE_DRIVE_OAUTH'])
    auth = {key: credentials[key] for key in ('client_id', 'client_secret', 'refresh_token')}
    auth['grant_type'] = 'refresh_token'
    token = request('https://oauth2.googleapis.com/token', data=urlencode(auth).encode())['access_token']
    base = 'https://script.googleapis.com/v1/projects/' + quote(os.environ['RADAR_SCRIPT_ID'], safe='')
    deployment_url = base + '/deployments/' + quote(os.environ['RADAR_DEPLOYMENT_ID'], safe='')
    deployment = request(deployment_url, token=token)
    live = request(base + '/content', token=token)
    files = [{key: entry[key] for key in ('name', 'type', 'source')} for entry in live['files']]
    code = next(entry for entry in files if entry['name'] == 'Code' and entry['type'] == 'SERVER_JS')
    source = Path('google/Code.js').read_text(encoding='utf-8')
    if digest(code['source']) not in (os.environ['RADAR_EXPECTED_CODE_SHA256'], digest(source)):
        raise SystemExit('Live Code differs from the reviewed baseline; no changes made.')
    # The manifest, activation, deployment configuration and preview stay untouched.
    code['source'] = source
    request(base + '/content', data=json.dumps({'files': files}).encode(), method='PUT', token=token)
    readback = request(base + '/content', token=token)
    expected = {(f['name'], f['type']): f['source'] for f in files}
    actual = {(f['name'], f['type']): f['source'] for f in readback['files']}
    if actual != expected:
        raise SystemExit('Live source readback differs; stop and inspect the gateway.')
    version = request(base + '/versions', data=json.dumps({
        'description': 'Radar repository coverage and GHADC delivery exclusion'
    }).encode(), method='POST', token=token)
    config = dict(deployment['deploymentConfig'])
    config['versionNumber'] = version['versionNumber']
    config['description'] = 'Radar coverage update'
    request(deployment_url, data=json.dumps({'deploymentConfig': config}).encode(), method='PUT', token=token)
    verified = request(deployment_url, token=token)
    if verified['deploymentConfig']['versionNumber'] != version['versionNumber']:
        raise SystemExit('Deployment version verification failed.')
    print(json.dumps({'status': 'verified', 'version': version['versionNumber'],
                      'code_sha256': digest(source), 'other_live_files_preserved': True}))


if __name__ == '__main__':
    main()
