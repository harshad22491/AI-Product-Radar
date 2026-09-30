"""Fresh owned-repository metadata for each research run.

Reads names, descriptions, languages, topics, push times and recent commit
subject lines through GET requests only. No source files are read. The result
goes into the model prompt and must never be printed: Actions logs are public.
"""
import json
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API = 'https://api.github.com/'
ACTIVE_DAYS = 30
COMMITS_PER_REPO = 10


def _get(token, path):
    request = Request(API + path, headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    })
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except (HTTPError, URLError):
        # Never echo the URL or body; private repository names would reach public logs.
        raise RuntimeError('GitHub inventory request failed; verify RADAR_GITHUB_TOKEN') from None


def collect(token, *, now=None, get=_get):
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=ACTIVE_DAYS)
    repos = []
    page = 1
    while True:
        rows = get(token, f'user/repos?affiliation=owner&sort=pushed&per_page=100&page={page}')
        repos.extend(rows)
        if len(rows) < 100:
            break
        page += 1
    inventory = []
    for repo in repos:
        if repo.get('archived'):
            continue
        pushed = repo.get('pushed_at') or ''
        entry = {'name': repo['name'], 'private': bool(repo.get('private')),
                 'description': repo.get('description') or '', 'language': repo.get('language') or '',
                 'topics': repo.get('topics') or [], 'pushed_at': pushed, 'fork': bool(repo.get('fork')),
                 'recent_commits': []}
        if pushed and datetime.fromisoformat(pushed.replace('Z', '+00:00')) >= since:
            path = (f"repos/{quote(repo['full_name'], safe='/')}/commits"
                    f"?since={since.strftime('%Y-%m-%dT%H:%M:%SZ')}&per_page={COMMITS_PER_REPO}")
            try:
                commits = get(token, path)
            except RuntimeError:
                commits = []  # An empty repository returns 409; keep its metadata.
            entry['recent_commits'] = [
                {'date': c['commit']['committer']['date'][:10],
                 'subject': c['commit']['message'].splitlines()[0][:160]}
                for c in commits if c.get('commit', {}).get('message')]
        inventory.append(entry)
    inventory.sort(key=lambda r: r['pushed_at'], reverse=True)
    return inventory
