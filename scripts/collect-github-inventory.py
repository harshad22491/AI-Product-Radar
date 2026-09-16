"""Collect owned GitHub repository metadata through an existing gh login.

No source contents, credentials, or client files are read. All API calls GET.
The result belongs in ignored state/, never in a public repository.
"""
import argparse
import json
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner', default='harshad22491')
    parser.add_argument('--out', type=Path, default=Path('state/github-inventory.json'))
    args = parser.parse_args()
    raw = subprocess.run(['gh', 'api', '--method', 'GET', '--paginate', '--slurp',
                          'user/repos?affiliation=owner&per_page=100'],
                         check=True, capture_output=True, text=True, encoding='utf-8')
    rows = [repo for page in json.loads(raw.stdout) for repo in page
            if repo['owner']['login'].lower() == args.owner.lower()]
    inventory = [{key: repo.get(key) for key in
                  ('full_name', 'private', 'description', 'language', 'topics',
                   'default_branch', 'pushed_at', 'archived', 'fork')}
                 for repo in rows]
    def add_head(repo):
        endpoint = 'repos/' + repo['full_name'] + '/commits/' + quote(repo['default_branch'], safe='')
        result = subprocess.run(['gh', 'api', '--method', 'GET', endpoint, '--jq', '.sha'],
                                capture_output=True, text=True, encoding='utf-8')
        repo['head_sha'] = result.stdout.strip() if result.returncode == 0 else ''
        if result.returncode != 0:
            repo['inventory_error'] = 'Default branch head unavailable; review must not advance cursor.'
        return repo
    with ThreadPoolExecutor(max_workers=4) as pool:
        inventory = list(pool.map(add_head, inventory))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Saved metadata for {len(inventory)} owned repositories to {args.out}')


if __name__ == '__main__':
    main()
