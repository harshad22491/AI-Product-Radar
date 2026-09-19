"""Subscription research/review on Actions; existing Google gateway owns sending."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from radar.domain import stable_item_id, validate_bundle

ROOT = Path(__file__).resolve().parents[1]
IST = timezone(timedelta(hours=5, minutes=30))


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def validate_gateway(value):
    result = subprocess.run(['node', str(ROOT / 'scripts/validate-cloud-bundle.cjs')],
                            input=encode(value), capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError('Google gateway validation: ' + result.stdout.decode('utf-8')[:2000])


def approved(bundle, raw, records):
    digest = hashlib.sha256(raw).hexdigest()
    return any(
        value.get('kind') == 'validation'
        and value.get('candidate_run_id') == bundle['run_id']
        and value.get('candidate_sha256') == digest
        and value.get('verdict') == 'approved'
        and value.get('validator') == 'opus'
        and value.get('model_id') == 'claude-opus-5'
        and bundle.get('producer') != 'opus'
        for value in records
    )


def run_channel(channel, drive, model, *, now=None, correction=''):
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(IST).date().isoformat()
    snapshot, preferences, files = drive.state()
    delivered = {i['item_id'] for i in snapshot['items'] if i.get('first_delivered_edition_date')}
    sent_today = {i['item_id']: i.get('run_id') for i in snapshot['items']
                  if i.get('first_delivered_edition_date') == day}
    records = []
    candidates = []
    for _, raw in files:
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError):
            continue
        if not isinstance(value, dict):
            continue
        records.append(value)
        if value.get('kind') == 'digest':
            candidates.append((value, raw))
    for bundle in snapshot.get('digests', []):
        if (bundle.get('newsletter', 'product') == channel and bundle.get('edition_date') == day
                and bundle.get('items')
                and all(sent_today.get(i['item_id']) == bundle['run_id'] for i in bundle['items'])):
            return {'newsletter': channel, 'status': 'sent'}
    for bundle, raw in candidates:
        if bundle.get('newsletter', 'product') != channel or bundle.get('edition_date') != day:
            continue
        try:
            validate_bundle(bundle)
            validate_gateway(bundle)
        except ValueError:
            continue
        if not any(i['item_id'] in delivered for i in bundle['items']) and approved(bundle, raw, records):
            return {'newsletter': channel, 'status': 'ready', 'run_id': bundle['run_id']}

    brief = (ROOT / 'docs/PORTFOLIO-OVERVIEW.md').read_text(encoding='utf-8')
    contract = (ROOT / 'prompts/actions-research.md').read_text(encoding='utf-8')
    context = {'edition_date': day, 'newsletter': channel, 'preferences': preferences,
               'previous_items': snapshot['items']}
    if correction:
        context['previous_attempt_failure'] = correction
    # Also avoid papers queued by the other channel in this same run.
    queued = [i for b, raw in candidates if b.get('edition_date') == day
              and b.get('newsletter', 'product') != channel and approved(b, raw, records)
              for i in b.get('items', [])]
    context['queued_items'] = queued
    research, actual_model = model('research', contract + '\n' + brief + '\nINPUT:\n' + json.dumps(context))
    if actual_model != 'claude-fable-5-1':
        raise ValueError('Unexpected research model: ' + actual_model)
    bundle = {'schema_version': 1, 'kind': 'digest', 'newsletter': channel,
              'run_id': f'{channel}-fable-{day}-{uuid4().hex[:12]}', 'edition_date': day,
              'generated_at': now.isoformat(), 'producer': 'fable', 'model_id': actual_model,
              'items': research['items']}
    for item in bundle['items']:
        item['item_id'] = stable_item_id(item['source_url'])
    bundle = validate_bundle(bundle)
    validate_gateway(bundle)
    excluded = delivered | {i['item_id'] for i in queued}
    if any(i['item_id'] in excluded for i in bundle['items']):
        raise ValueError('Candidate contains an already delivered or queued item')
    raw = encode(bundle)
    review_prompt = (ROOT / 'prompts/actions-review.md').read_text(encoding='utf-8')
    review, reviewer_model = model('review', review_prompt + '\n' + contract + '\n' + brief
                                   + '\nCANDIDATE:\n' + raw.decode('utf-8'))
    if reviewer_model != 'claude-opus-5':
        raise ValueError('Unexpected reviewer model: ' + reviewer_model)
    if review.get('verdict') != 'approved':
        raise RuntimeError('Independent review rejected candidate: ' + str(review.get('reasons', [])))
    attestation = {'schema_version': 1, 'kind': 'validation',
                   'run_id': 'validation-opus-' + bundle['run_id'],
                   'candidate_run_id': bundle['run_id'],
                   'candidate_sha256': hashlib.sha256(raw).hexdigest(),
                   'validator': 'opus', 'model_id': reviewer_model, 'verdict': 'approved',
                   'checked_at': datetime.now(timezone.utc).isoformat()}
    validate_gateway(attestation)
    candidate_id = drive.upload(bundle['run_id'] + '.json', raw)
    approval_id = drive.upload(attestation['run_id'] + '.json', encode(attestation))
    return {'newsletter': channel, 'status': 'approved', 'run_id': bundle['run_id'],
            'candidate_file_id': candidate_id, 'approval_file_id': approval_id}


def parse_model_json(text):
    """Accept prose/code fences around one object; reject ambiguous answers."""
    decoder = json.JSONDecoder()
    objects = []
    cursor = 0
    while cursor < len(text):
        start = text.find('{', cursor)
        if start < 0:
            break
        try:
            value, end = decoder.raw_decode(text[start:])
        except ValueError:
            cursor = start + 1
            continue
        if isinstance(value, dict):
            objects.append(value)
        cursor = start + end
    if len(objects) != 1:
        raise ValueError('Model response must contain exactly one JSON object')
    return objects[0]


def call_model(role, prompt):
    model = 'claude-fable-5-1' if role == 'research' else 'claude-opus-5'
    print(f'Starting {role} with {model}', flush=True)
    env = dict(os.environ)
    # The research process gets subscription auth, never Drive or GitHub credentials.
    for key in list(env):
        if key.startswith(('GOOGLE_', 'RADAR_', 'GH_', 'GITHUB_', 'ANTHROPIC_')):
            env.pop(key)
    with tempfile.TemporaryDirectory(prefix='radar-model-') as temp:
        Path(temp, 'mcp.json').write_text('{"mcpServers":{}}', encoding='utf-8')
        result = subprocess.run(
            ['claude', '-p', '--model', model, '--output-format', 'json', '--max-turns', '45',
             '--tools', 'WebSearch,WebFetch', '--allowedTools', 'WebSearch,WebFetch',
             '--strict-mcp-config', '--mcp-config', str(Path(temp, 'mcp.json')),
             '--setting-sources', '', '--no-session-persistence'],
            input=prompt, capture_output=True, text=True, encoding='utf-8',
            timeout=600, cwd=temp, env=env, check=False)
    if result.returncode:
        raise RuntimeError(f'{role} CLI failed (exit {result.returncode})')
    envelope = json.loads(result.stdout)
    if envelope.get('is_error'):
        raise RuntimeError(f'{role} returned a provider error')
    if envelope.get('permission_denials'):
        raise RuntimeError(f'{role} could not access required research tools')
    usage = envelope.get('modelUsage', {})
    if model not in usage:
        raise ValueError(f'{role} did not report expected model {model}')
    value = envelope.get('structured_output')
    if not isinstance(value, dict):
        value = parse_model_json(envelope.get('result', ''))
    print(f'Completed {role} with {model}', flush=True)
    return value, model


def main():
    from radar.drive_exchange import DriveExchange
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Read state and validate credentials only')
    args = parser.parse_args()
    drive = DriveExchange.from_env()
    if args.check:
        snapshot, _, files = drive.state()
        print(json.dumps({'status': 'connected', 'items': len(snapshot['items']), 'files': len(files)}))
        return 0
    outcomes = []
    for channel in ('product', 'academic'):
        correction = ''
        for attempt in range(3):
            try:
                print(f'{channel} attempt {attempt + 1}: starting', flush=True)
                result = run_channel(channel, drive, call_model, correction=correction)
                outcomes.append(result)
                print(json.dumps(result), flush=True)
                break
            except Exception as error:
                correction = str(error)[:12000]
                print(f'{channel} attempt {attempt + 1}: {type(error).__name__}: {error}', flush=True)
                if attempt == 2:
                    outcomes.append({'newsletter': channel, 'status': 'failed'})
    target = ROOT / 'out/cloud-run-status.json'
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(encode({'checked_at': datetime.now(timezone.utc).isoformat(), 'newsletters': outcomes}))
    return int(any(r['status'] == 'failed' for r in outcomes))


if __name__ == '__main__':
    raise SystemExit(main())
