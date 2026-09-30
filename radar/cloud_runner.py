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

PRODUCER, RESEARCH_MODEL = 'opus', 'claude-opus-5-5'
VALIDATOR, REVIEW_MODEL = 'astra', 'gpt-6-astra'
# Mirrors VALIDATOR_MODELS in google/Code.js; the gateway rejects anything else.
VALIDATOR_MODELS = {'astra': 'gpt-6-astra', 'opus': 'claude-opus-5', 'sol': 'gpt-5.6-sol'}
# The owner asked for these two to be researched less: at most one item per edition.
LOW_PRIORITY_REPOSITORIES = {'ghadc', 'ghadc-trade-licensing-portal', 'forty-degrees'}
AUTH_FAILURE_MARKERS = ('401', 'unauthorized', 'refresh token', 'refresh_token', 'log in again',
                        'login again', 'not logged in', 'token_expired', 'invalid_grant')
# Model subprocesses never see Drive, GitHub or the other provider's credentials.
SCRUBBED_PREFIXES = ('GOOGLE_', 'RADAR_', 'GH_', 'GITHUB_', 'ANTHROPIC_', 'OPENAI_', 'CODEX_',
                     'CLAUDE_CODE_OAUTH')
VERDICT_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['verdict', 'reasons'],
    'properties': {'verdict': {'type': 'string', 'enum': ['approved', 'rejected']},
                   'reasons': {'type': 'array', 'items': {'type': 'string'}}},
}


class AstraAuthError(RuntimeError):
    """Astra's saved ChatGPT login was rejected; the PC repair task reseeds it."""


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
        and VALIDATOR_MODELS.get(value.get('validator')) == value.get('model_id')
        and bundle.get('producer') != value.get('validator')
        for value in records
    )


def check_repository_priority(items):
    low = [i['repository'] for i in items
           if i['repository'].rsplit('/', 1)[-1].lower() in LOW_PRIORITY_REPOSITORIES]
    if len(low) > 1:
        raise ValueError('At most one item may target GHADC or forty-degrees (low priority); '
                         f'this candidate has {len(low)}. Replace the extras with other repositories.')


def run_channel(channel, drive, model, *, now=None, correction='', repositories=None):
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
               'previous_items': snapshot['items'], 'github_repositories': repositories}
    if correction:
        context['previous_attempt_failure'] = correction
    # Also avoid papers queued by the other channel in this same run.
    queued = [i for b, raw in candidates if b.get('edition_date') == day
              and b.get('newsletter', 'product') != channel and approved(b, raw, records)
              for i in b.get('items', [])]
    context['queued_items'] = queued
    research, actual_model = model('research', contract + '\n' + brief + '\nINPUT:\n' + json.dumps(context))
    if actual_model != RESEARCH_MODEL:
        raise ValueError('Unexpected research model: ' + actual_model)
    bundle = {'schema_version': 1, 'kind': 'digest', 'newsletter': channel,
              'run_id': f'{channel}-{PRODUCER}-{day}-{uuid4().hex[:12]}', 'edition_date': day,
              'generated_at': now.isoformat(), 'producer': PRODUCER, 'model_id': actual_model,
              'items': research['items']}
    for item in bundle['items']:
        item['item_id'] = stable_item_id(item['source_url'])
    bundle = validate_bundle(bundle)
    validate_gateway(bundle)
    check_repository_priority(bundle['items'])
    excluded = delivered | {i['item_id'] for i in queued}
    if any(i['item_id'] in excluded for i in bundle['items']):
        raise ValueError('Candidate contains an already delivered or queued item')
    raw = encode(bundle)
    review_prompt = (ROOT / 'prompts/actions-review.md').read_text(encoding='utf-8')
    review, reviewer_model = model('review', review_prompt + '\n' + contract + '\n' + brief
                                   + '\nGITHUB_REPOSITORIES:\n' + json.dumps(repositories)
                                   + '\nCANDIDATE:\n' + raw.decode('utf-8'))
    if reviewer_model != REVIEW_MODEL:
        raise ValueError('Unexpected reviewer model: ' + reviewer_model)
    if review.get('verdict') != 'approved':
        raise RuntimeError('Independent review rejected candidate: ' + str(review.get('reasons', [])))
    attestation = {'schema_version': 1, 'kind': 'validation',
                   'run_id': f'validation-{VALIDATOR}-' + bundle['run_id'],
                   'candidate_run_id': bundle['run_id'],
                   'candidate_sha256': hashlib.sha256(raw).hexdigest(),
                   'validator': VALIDATOR, 'model_id': reviewer_model, 'verdict': 'approved',
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


def scrubbed_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUBBED_PREFIXES)}
    env.update(extra)
    return env


def call_model(role, prompt):
    return call_claude(prompt) if role == 'research' else call_codex(prompt)


def call_claude(prompt):
    model = RESEARCH_MODEL
    print(f'Starting research with {model}', flush=True)
    # The research process gets subscription auth, never Drive or GitHub credentials.
    env = scrubbed_env(CLAUDE_CODE_OAUTH_TOKEN=os.environ.get('CLAUDE_CODE_OAUTH_TOKEN', ''))
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
        raise RuntimeError(f'research CLI failed (exit {result.returncode})')
    envelope = json.loads(result.stdout)
    if envelope.get('is_error'):
        raise RuntimeError('research returned a provider error')
    if envelope.get('permission_denials'):
        raise RuntimeError('research could not access required research tools')
    usage = envelope.get('modelUsage', {})
    if model not in usage:
        raise ValueError(f'research did not report expected model {model}')
    value = envelope.get('structured_output')
    if not isinstance(value, dict):
        value = parse_model_json(envelope.get('result', ''))
    print(f'Completed research with {model}', flush=True)
    return value, model


def is_auth_failure(text):
    lowered = text.lower()
    return any(marker in lowered for marker in AUTH_FAILURE_MARKERS)


def session_models(codex_home, thread_id):
    """Models recorded in Codex's own session log for this run (evidence, not a label)."""
    models = set()
    for path in Path(codex_home, 'sessions').rglob(f'*{thread_id}*.jsonl'):
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                models |= _find_models(json.loads(line))
            except ValueError:
                continue
    return models


def _find_models(value):
    found = set()
    if isinstance(value, dict):
        if isinstance(value.get('model'), str):
            found.add(value['model'])
        for child in value.values():
            found |= _find_models(child)
    elif isinstance(value, list):
        for child in value:
            found |= _find_models(child)
    return found


def call_codex(prompt):
    model = REVIEW_MODEL
    codex_home = os.environ.get('CODEX_HOME', '')
    if not codex_home or not Path(codex_home, 'auth.json').is_file():
        raise AstraAuthError('Astra login missing: CODEX_HOME/auth.json not restored')
    print(f'Starting review with {model}', flush=True)
    # CODEX_HOME holds only auth.json (restored from the secret) plus this run's session log.
    env = scrubbed_env(CODEX_HOME=codex_home)
    with tempfile.TemporaryDirectory(prefix='radar-review-') as temp:
        schema = Path(temp, 'verdict.schema.json')
        schema.write_text(json.dumps(VERDICT_SCHEMA), encoding='utf-8')
        last = Path(temp, 'last-message.txt')
        # No shell tool: a prompt-injected page cannot make the reviewer read auth.json.
        result = subprocess.run(
            ['codex', 'exec', '-m', model, '-c', 'web_search="live"', '--disable', 'shell_tool',
             '--ignore-user-config', '--ignore-rules', '--skip-git-repo-check', '-s', 'read-only',
             '--json', '--output-schema', str(schema), '-o', str(last), '-'],
            input=prompt, capture_output=True, text=True, encoding='utf-8',
            timeout=1500, cwd=temp, env=env, check=False)
        answer = last.read_text(encoding='utf-8') if last.is_file() else ''
    events = []
    for line in result.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    # Transient error events (reconnects) are normal; only a failed run without an answer counts.
    errors = ' '.join(json.dumps(e) for e in events if e.get('type') in ('error', 'turn.failed'))
    if result.returncode or not answer.strip():
        if is_auth_failure(result.stderr + ' ' + errors):
            raise AstraAuthError('Astra login rejected by OpenAI; reseed required')
        raise RuntimeError(f'review CLI failed (exit {result.returncode})')
    thread = next((e.get('thread_id') for e in events if e.get('type') == 'thread.started'), '')
    models = session_models(codex_home, thread) if thread else set()
    if models != {model}:
        raise ValueError(f'review did not report expected model {model}')
    # Any completed call proves the login works, even if the verdict is a rejection.
    write_status('astra-auth-status', 'ok')
    value = parse_model_json(answer)
    print(f'Completed review with {model}', flush=True)
    return value, model


def write_status(name, text):
    target = ROOT / 'out' / name
    target.parent.mkdir(exist_ok=True)
    target.write_text(text, encoding='utf-8')


def main():
    from radar.drive_exchange import DriveExchange
    from radar import github_inventory
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Read state and validate credentials only')
    args = parser.parse_args()
    drive = DriveExchange.from_env()
    token = os.environ.get('RADAR_GITHUB_TOKEN', '')
    if args.check:
        snapshot, _, files = drive.state()
        repositories = github_inventory.collect(token) if token else []
        print(json.dumps({'status': 'connected', 'items': len(snapshot['items']), 'files': len(files),
                          'repositories': len(repositories)}))
        return 0
    repositories, inventory_status = None, 'missing_token'
    if token:
        try:
            repositories = github_inventory.collect(token)
            inventory_status = 'ok'
            # Count only: repository names and commit subjects must stay out of public logs.
            print(f'GitHub inventory: {len(repositories)} repositories', flush=True)
        except RuntimeError as error:
            inventory_status = 'failed'
            print(f'::warning::{error}; researching from the static portfolio brief only', flush=True)
    else:
        print('::warning::RADAR_GITHUB_TOKEN missing; researching from the static brief only', flush=True)
    outcomes = []
    for channel in ('product', 'academic'):
        correction = ''
        for attempt in range(3):
            try:
                print(f'{channel} attempt {attempt + 1}: starting', flush=True)
                result = run_channel(channel, drive, call_model, correction=correction,
                                     repositories=repositories)
                outcomes.append(result)
                print(json.dumps(result), flush=True)
                break
            except AstraAuthError as error:
                # Retrying cannot fix a revoked login; stop before spending more research.
                # The workflow flags it and the PC repair task reseeds the secret.
                write_status('astra-auth-status', 'broken')
                print(f'::error::{error}', flush=True)
                outcomes.append({'newsletter': channel, 'status': 'blocked_astra_auth'})
                break
            except Exception as error:
                correction = str(error)[:12000]
                print(f'{channel} attempt {attempt + 1}: {type(error).__name__}: {error}', flush=True)
                if attempt == 2:
                    outcomes.append({'newsletter': channel, 'status': 'failed'})
        if outcomes and outcomes[-1]['status'] == 'blocked_astra_auth':
            break
    target = ROOT / 'out/cloud-run-status.json'
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(encode({'checked_at': datetime.now(timezone.utc).isoformat(),
                               'github_inventory': inventory_status, 'newsletters': outcomes}))
    return int(any(r['status'] in ('failed', 'blocked_astra_auth') for r in outcomes))


if __name__ == '__main__':
    raise SystemExit(main())
